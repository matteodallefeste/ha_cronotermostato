"""Config and options flow for the Weekly Thermostat integration.

The initial config flow creates a single entry. All the real configuration
(global hysteresis, daily profiles, floors, areas) is managed through a
menu-driven **options flow**, so users never have to touch YAML.

Floors map to Home Assistant floors (a weekly-schedule group); areas map to
Home Assistant areas (the room a thermostat lives in). When an area is picked,
its temperature sensor and switch actuators are auto-suggested.
"""

from __future__ import annotations

import copy
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    selector,
)
from homeassistant.util import slugify

from .const import (
    CONF_AREA,
    CONF_AREAS,
    CONF_AWAY_TEMP,
    CONF_COOLERS,
    CONF_END,
    CONF_FLOOR,
    CONF_FLOORS,
    CONF_HEATERS,
    CONF_HYSTERESIS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_OVERRIDES,
    CONF_PROFILE,
    CONF_PROFILES,
    CONF_SCHEDULE,
    CONF_SENSOR,
    CONF_START,
    CONF_TEMPERATURE,
    CONF_TIME,
    DEFAULT_AWAY_TEMP,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    WEEKDAYS,
)

ADD_NEW = "__add_new__"
CONF_SLOTS = "slots"
CONF_DELETE = "delete"

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_HAS_FLOOR_SELECTOR = hasattr(selector, "FloorSelector")
_ACTUATOR_DOMAINS = ["switch", "input_boolean"]


# --- Parsing helpers ---------------------------------------------------


def _parse_slots(text: str) -> list[dict[str, Any]]:
    """Parse a multi-line "HH:MM temperature" block into profile slots."""
    slots: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = re.split(r"[=\s]+", line)
        if len(parts) != 2 or not TIME_RE.match(parts[0]):
            raise ValueError(f"Invalid slot: '{line}'")
        try:
            temperature = float(parts[1])
        except ValueError as err:
            raise ValueError(f"Invalid temperature: '{line}'") from err
        slots.append({CONF_TIME: parts[0], CONF_TEMPERATURE: temperature})
    slots.sort(key=lambda item: item[CONF_TIME])
    if not slots or slots[0][CONF_TIME] != "00:00":
        raise ValueError("The first slot must start at 00:00")
    return slots


def _slots_to_text(slots: list[dict[str, Any]]) -> str:
    """Render profile slots back to an editable multi-line string."""
    return "\n".join(f"{s[CONF_TIME]} {s[CONF_TEMPERATURE]}" for s in slots)


def _parse_overrides(text: str, profiles: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse "YYYY-MM-DD YYYY-MM-DD profile" lines into overrides."""
    overrides: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3 or not DATE_RE.match(parts[0]) or not DATE_RE.match(parts[1]):
            raise ValueError(f"Invalid override: '{line}'")
        if parts[2] not in profiles:
            raise ValueError(f"Unknown profile in override: '{parts[2]}'")
        overrides.append({CONF_START: parts[0], CONF_END: parts[1], CONF_PROFILE: parts[2]})
    return overrides


def _overrides_to_text(overrides: list[dict[str, Any]]) -> str:
    """Render overrides back to an editable multi-line string."""
    return "\n".join(
        f"{o[CONF_START]} {o[CONF_END]} {o[CONF_PROFILE]}" for o in overrides
    )


def _unique_key(base: str, existing: dict[str, Any]) -> str:
    """Return a slug-based key that does not collide with existing keys."""
    base = slugify(base) or "item"
    key = base
    index = 2
    while key in existing:
        key = f"{base}_{index}"
        index += 1
    return key


def _default_options() -> dict[str, Any]:
    """Return the empty option structure for a fresh entry."""
    return {CONF_HYSTERESIS: DEFAULT_HYSTERESIS, CONF_PROFILES: {}, CONF_FLOORS: {}}


class WeeklyThermostatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup (single instance)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create the single config entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title="Weekly Thermostat", data={}, options=_default_options()
            )
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_import(self, import_data: dict[str, Any]):
        """Import configuration from YAML into a config entry."""
        await self.async_set_unique_id(DOMAIN)
        for entry in self._async_current_entries():
            self.hass.config_entries.async_update_entry(entry, options=import_data)
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title="Weekly Thermostat", data={}, options=import_data
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WeeklyThermostatOptionsFlow:
        """Return the options flow."""
        return WeeklyThermostatOptionsFlow(config_entry)


class WeeklyThermostatOptionsFlow(OptionsFlow):
    """Menu-driven editor for profiles, floors and areas."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize with a working copy of the current options."""
        self._entry = config_entry
        self.options: dict[str, Any] = copy.deepcopy(dict(config_entry.options))
        self.options.setdefault(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        self.options.setdefault(CONF_PROFILES, {})
        self.options.setdefault(CONF_FLOORS, {})
        self._profile_key: str | None = None
        self._floor_key: str | None = None
        self._area_floor_key: str | None = None
        self._area_key: str | None = None
        self._ha_area: str | None = None

    # --- Home Assistant area helpers -----------------------------------

    def _area_name(self, area_id: str | None) -> str:
        """Return the friendly name of a Home Assistant area."""
        if not area_id:
            return ""
        area = ar.async_get(self.hass).async_get_area(area_id)
        return area.name if area else area_id

    def _area_candidates(self, area_id: str | None) -> tuple[list[str], list[str]]:
        """Return (temperature sensors, switch actuators) found in an HA area."""
        if not area_id:
            return [], []
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        entity_ids: set[str] = {
            entry.entity_id for entry in er.async_entries_for_area(ent_reg, area_id)
        }
        for device in dr.async_entries_for_area(dev_reg, area_id):
            for entry in er.async_entries_for_device(ent_reg, device.id):
                if entry.area_id is None:
                    entity_ids.add(entry.entity_id)

        temp_sensors: list[str] = []
        switches: list[str] = []
        for entity_id in entity_ids:
            domain = entity_id.split(".")[0]
            if domain == "sensor":
                state = self.hass.states.get(entity_id)
                device_class = state.attributes.get("device_class") if state else None
                unit = state.attributes.get("unit_of_measurement") if state else None
                if device_class == "temperature" or unit in ("°C", "°F"):
                    temp_sensors.append(entity_id)
            elif domain in _ACTUATOR_DOMAINS:
                switches.append(entity_id)
        return sorted(temp_sensors), sorted(switches)

    # --- Main menu ------------------------------------------------------

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show the main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "profiles", "floors", "areas", "finish"],
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        """Persist all changes."""
        return self.async_create_entry(title="", data=self.options)

    # --- Global settings ------------------------------------------------

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        """Edit global settings."""
        if user_input is not None:
            self.options[CONF_HYSTERESIS] = user_input[CONF_HYSTERESIS]
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_HYSTERESIS): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=3, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                )
            }
        )
        schema = self.add_suggested_values_to_schema(
            schema, {CONF_HYSTERESIS: self.options[CONF_HYSTERESIS]}
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    # --- Profiles -------------------------------------------------------

    async def async_step_profiles(self, user_input: dict[str, Any] | None = None):
        """Pick a profile to edit or add a new one."""
        if user_input is not None:
            self._profile_key = (
                None if user_input["profile"] == ADD_NEW else user_input["profile"]
            )
            return await self.async_step_profile_edit()

        options = [selector.SelectOptionDict(value=ADD_NEW, label="➕ Add new profile")]
        options += [
            selector.SelectOptionDict(value=key, label=key)
            for key in self.options[CONF_PROFILES]
        ]
        schema = vol.Schema(
            {
                vol.Required("profile", default=ADD_NEW): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="profiles", data_schema=schema)

    async def async_step_profile_edit(self, user_input: dict[str, Any] | None = None):
        """Add or edit a single profile."""
        profiles = self.options[CONF_PROFILES]
        key = self._profile_key
        errors: dict[str, str] = {}

        if user_input is not None:
            if key and user_input.get(CONF_DELETE):
                profiles.pop(key, None)
                return await self.async_step_init()
            try:
                slots = _parse_slots(user_input[CONF_SLOTS])
            except ValueError:
                errors[CONF_SLOTS] = "invalid_slots"
            if not errors:
                if key:  # editing: keep the key stable
                    profiles[key] = slots
                else:
                    profiles[_unique_key(user_input[CONF_NAME], profiles)] = slots
                return await self.async_step_init()

        fields: dict[Any, Any] = {}
        if not key:
            fields[vol.Required(CONF_NAME)] = selector.TextSelector()
        fields[vol.Required(CONF_SLOTS)] = selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        )
        if key:
            fields[vol.Optional(CONF_DELETE, default=False)] = selector.BooleanSelector()

        schema = vol.Schema(fields)
        suggested = {CONF_SLOTS: _slots_to_text(profiles[key])} if key else {}
        schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(
            step_id="profile_edit", data_schema=schema, errors=errors
        )

    # --- Floors ---------------------------------------------------------

    async def async_step_floors(self, user_input: dict[str, Any] | None = None):
        """Pick a floor to edit or add a new one."""
        if user_input is not None:
            self._floor_key = (
                None if user_input["floor"] == ADD_NEW else user_input["floor"]
            )
            return await self.async_step_floor_edit()

        options = [selector.SelectOptionDict(value=ADD_NEW, label="➕ Add new floor")]
        options += [
            selector.SelectOptionDict(value=key, label=floor.get(CONF_NAME, key))
            for key, floor in self.options[CONF_FLOORS].items()
        ]
        schema = vol.Schema(
            {
                vol.Required("floor", default=ADD_NEW): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="floors", data_schema=schema)

    async def async_step_floor_edit(self, user_input: dict[str, Any] | None = None):
        """Add or edit a floor (name, HA floor link, weekly schedule, overrides)."""
        floors = self.options[CONF_FLOORS]
        profiles = self.options[CONF_PROFILES]
        key = self._floor_key
        errors: dict[str, str] = {}

        if not profiles:
            return self.async_show_form(
                step_id="floor_edit",
                data_schema=vol.Schema({}),
                errors={"base": "no_profiles"},
            )

        floor = floors.get(key, {}) if key else {}

        if user_input is not None:
            if key and user_input.get(CONF_DELETE):
                floors.pop(key, None)
                return await self.async_step_init()
            schedule = {day: user_input[day] for day in WEEKDAYS}
            try:
                overrides = _parse_overrides(user_input.get(CONF_OVERRIDES, ""), profiles)
            except ValueError:
                errors[CONF_OVERRIDES] = "invalid_overrides"
            if not errors:
                name = user_input[CONF_NAME].strip()
                target_key = key or _unique_key(name, floors)
                floors[target_key] = {
                    CONF_NAME: name,
                    CONF_FLOOR: user_input.get(CONF_FLOOR) or None,
                    CONF_SCHEDULE: schedule,
                    CONF_OVERRIDES: overrides,
                    CONF_AREAS: floor.get(CONF_AREAS, {}),
                }
                return await self.async_step_init()

        profile_options = list(profiles)
        default_profile = profile_options[0]
        current_schedule = floor.get(CONF_SCHEDULE, {})

        fields: dict[Any, Any] = {vol.Required(CONF_NAME): selector.TextSelector()}
        if _HAS_FLOOR_SELECTOR:
            fields[vol.Optional(CONF_FLOOR)] = selector.FloorSelector()
        for day in WEEKDAYS:
            fields[
                vol.Required(day, default=current_schedule.get(day, default_profile))
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=profile_options, mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        fields[vol.Optional(CONF_OVERRIDES)] = selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        )
        if key:
            fields[vol.Optional(CONF_DELETE, default=False)] = selector.BooleanSelector()

        schema = vol.Schema(fields)
        suggested = {
            CONF_NAME: floor.get(CONF_NAME, ""),
            CONF_OVERRIDES: _overrides_to_text(floor.get(CONF_OVERRIDES, [])),
        }
        if floor.get(CONF_FLOOR):
            suggested[CONF_FLOOR] = floor[CONF_FLOOR]
        schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(
            step_id="floor_edit", data_schema=schema, errors=errors
        )

    # --- Areas ----------------------------------------------------------

    async def async_step_areas(self, user_input: dict[str, Any] | None = None):
        """Pick the floor whose areas you want to manage."""
        floors = self.options[CONF_FLOORS]
        if not floors:
            return self.async_show_form(
                step_id="areas",
                data_schema=vol.Schema({}),
                errors={"base": "no_floors"},
            )
        if user_input is not None:
            self._area_floor_key = user_input["floor"]
            return await self.async_step_area_select()

        options = [
            selector.SelectOptionDict(value=key, label=floor.get(CONF_NAME, key))
            for key, floor in floors.items()
        ]
        schema = vol.Schema(
            {
                vol.Required("floor"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="areas", data_schema=schema)

    async def async_step_area_select(self, user_input: dict[str, Any] | None = None):
        """Pick an area to edit or add a new one within the chosen floor."""
        floor = self.options[CONF_FLOORS][self._area_floor_key]
        areas = floor.setdefault(CONF_AREAS, {})
        if user_input is not None:
            if user_input["area"] == ADD_NEW:
                self._area_key = None
                self._ha_area = None
                return await self.async_step_area_pick()
            self._area_key = user_input["area"]
            self._ha_area = areas[self._area_key].get(CONF_AREA)
            return await self.async_step_area_edit()

        options = [selector.SelectOptionDict(value=ADD_NEW, label="➕ Add new area")]
        options += [
            selector.SelectOptionDict(value=key, label=area.get(CONF_NAME, key))
            for key, area in areas.items()
        ]
        schema = vol.Schema(
            {
                vol.Required("area", default=ADD_NEW): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="area_select", data_schema=schema)

    async def async_step_area_pick(self, user_input: dict[str, Any] | None = None):
        """Pick the Home Assistant area to control."""
        floor = self.options[CONF_FLOORS][self._area_floor_key]
        areas = floor.setdefault(CONF_AREAS, {})
        errors: dict[str, str] = {}

        if user_input is not None:
            area_id = user_input[CONF_AREA]
            if area_id in areas:
                errors[CONF_AREA] = "area_exists"
            else:
                self._ha_area = area_id
                self._area_key = area_id
                return await self.async_step_area_edit()

        schema = vol.Schema({vol.Required(CONF_AREA): selector.AreaSelector()})
        return self.async_show_form(
            step_id="area_pick", data_schema=schema, errors=errors
        )

    async def async_step_area_edit(self, user_input: dict[str, Any] | None = None):
        """Add or edit an area (sensor, actuators, per-area settings)."""
        floor = self.options[CONF_FLOORS][self._area_floor_key]
        areas = floor.setdefault(CONF_AREAS, {})
        key = self._area_key
        area = areas.get(key, {}) if key else {}

        if user_input is not None:
            if key in areas and user_input.get(CONF_DELETE):
                areas.pop(key, None)
                return await self.async_step_init()
            areas[key] = {
                CONF_NAME: user_input[CONF_NAME].strip(),
                CONF_AREA: self._ha_area,
                CONF_SENSOR: user_input[CONF_SENSOR],
                CONF_HEATERS: user_input.get(CONF_HEATERS, []),
                CONF_COOLERS: user_input.get(CONF_COOLERS, []),
                CONF_HYSTERESIS: user_input.get(CONF_HYSTERESIS, self.options[CONF_HYSTERESIS]),
                CONF_AWAY_TEMP: user_input.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP),
                CONF_MIN_TEMP: user_input.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
                CONF_MAX_TEMP: user_input.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
            }
            return await self.async_step_init()

        # Auto-suggest entities from the linked Home Assistant area.
        temp_sensors, switches = self._area_candidates(self._ha_area)

        sensor_config = (
            selector.EntitySelectorConfig(include_entities=temp_sensors)
            if temp_sensors
            else selector.EntitySelectorConfig(domain="sensor")
        )
        actuator_config = (
            selector.EntitySelectorConfig(include_entities=switches, multiple=True)
            if switches
            else selector.EntitySelectorConfig(domain=_ACTUATOR_DOMAINS, multiple=True)
        )

        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_SENSOR): selector.EntitySelector(sensor_config),
            vol.Optional(CONF_HEATERS): selector.EntitySelector(actuator_config),
            vol.Optional(CONF_COOLERS): selector.EntitySelector(actuator_config),
            vol.Optional(CONF_HYSTERESIS): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1, max=3, step=0.1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(CONF_AWAY_TEMP): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, max=30, step=0.5, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(CONF_MIN_TEMP): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, max=30, step=0.5, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(CONF_MAX_TEMP): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, max=35, step=0.5, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
        if key in areas:
            fields[vol.Optional(CONF_DELETE, default=False)] = selector.BooleanSelector()

        default_sensor = area.get(CONF_SENSOR) or (
            temp_sensors[0] if len(temp_sensors) == 1 else None
        )
        suggested = {
            CONF_NAME: area.get(CONF_NAME) or self._area_name(self._ha_area),
            CONF_SENSOR: default_sensor,
            CONF_HEATERS: area.get(CONF_HEATERS, []),
            CONF_COOLERS: area.get(CONF_COOLERS, []),
            CONF_HYSTERESIS: area.get(CONF_HYSTERESIS, self.options[CONF_HYSTERESIS]),
            CONF_AWAY_TEMP: area.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP),
            CONF_MIN_TEMP: area.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
            CONF_MAX_TEMP: area.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
        }
        schema = vol.Schema(fields)
        schema = self.add_suggested_values_to_schema(
            schema, {k: v for k, v in suggested.items() if v is not None}
        )
        return self.async_show_form(
            step_id="area_edit",
            data_schema=schema,
            description_placeholders={"area": self._area_name(self._ha_area)},
        )
