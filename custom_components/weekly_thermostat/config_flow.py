"""Config and options flow for the Weekly Thermostat integration.

The initial config flow creates a single entry. All the real configuration
(global hysteresis, daily profiles, zones, rooms) is managed through a
menu-driven **options flow**, so users never have to touch YAML.
"""

from __future__ import annotations

import copy
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_AWAY_TEMP,
    CONF_COOLERS,
    CONF_END,
    CONF_HEATERS,
    CONF_HYSTERESIS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_OVERRIDES,
    CONF_PROFILE,
    CONF_PROFILES,
    CONF_ROOMS,
    CONF_SCHEDULE,
    CONF_SENSOR,
    CONF_START,
    CONF_TEMPERATURE,
    CONF_TIME,
    CONF_ZONES,
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
    return {CONF_HYSTERESIS: DEFAULT_HYSTERESIS, CONF_PROFILES: {}, CONF_ZONES: {}}


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
    """Menu-driven editor for profiles, zones and rooms."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize with a working copy of the current options."""
        self._entry = config_entry
        self.options: dict[str, Any] = copy.deepcopy(dict(config_entry.options))
        self.options.setdefault(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        self.options.setdefault(CONF_PROFILES, {})
        self.options.setdefault(CONF_ZONES, {})
        self._profile_key: str | None = None
        self._zone_key: str | None = None
        self._room_zone_key: str | None = None
        self._room_key: str | None = None

    # --- Main menu ------------------------------------------------------

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show the main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "profiles", "zones", "rooms", "finish"],
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
                    new_key = _unique_key(user_input[CONF_NAME], profiles)
                    profiles[new_key] = slots
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
        suggested = {}
        if key:
            suggested[CONF_SLOTS] = _slots_to_text(profiles[key])
        schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(
            step_id="profile_edit",
            data_schema=schema,
            errors=errors,
            description_placeholders={"name": key or ""},
        )

    # --- Zones ----------------------------------------------------------

    async def async_step_zones(self, user_input: dict[str, Any] | None = None):
        """Pick a zone to edit or add a new one."""
        if user_input is not None:
            self._zone_key = (
                None if user_input["zone"] == ADD_NEW else user_input["zone"]
            )
            return await self.async_step_zone_edit()

        options = [selector.SelectOptionDict(value=ADD_NEW, label="➕ Add new zone")]
        options += [
            selector.SelectOptionDict(
                value=key, label=zone.get(CONF_NAME, key)
            )
            for key, zone in self.options[CONF_ZONES].items()
        ]
        schema = vol.Schema(
            {
                vol.Required("zone", default=ADD_NEW): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="zones", data_schema=schema)

    async def async_step_zone_edit(self, user_input: dict[str, Any] | None = None):
        """Add or edit a zone (name, weekly schedule, overrides)."""
        zones = self.options[CONF_ZONES]
        profiles = self.options[CONF_PROFILES]
        key = self._zone_key
        errors: dict[str, str] = {}

        if not profiles:
            return self.async_show_form(
                step_id="zone_edit",
                data_schema=vol.Schema({}),
                errors={"base": "no_profiles"},
            )

        zone = zones.get(key, {}) if key else {}

        if user_input is not None:
            if key and user_input.get(CONF_DELETE):
                zones.pop(key, None)
                return await self.async_step_init()
            schedule = {day: user_input[day] for day in WEEKDAYS}
            try:
                overrides = _parse_overrides(user_input.get(CONF_OVERRIDES, ""), profiles)
            except ValueError:
                errors[CONF_OVERRIDES] = "invalid_overrides"
            if not errors:
                name = user_input[CONF_NAME].strip()
                target_key = key or _unique_key(name, zones)
                zones[target_key] = {
                    CONF_NAME: name,
                    CONF_SCHEDULE: schedule,
                    CONF_OVERRIDES: overrides,
                    CONF_ROOMS: zone.get(CONF_ROOMS, {}),
                }
                return await self.async_step_init()

        profile_options = list(profiles)
        default_profile = profile_options[0]
        current_schedule = zone.get(CONF_SCHEDULE, {})

        fields: dict[Any, Any] = {vol.Required(CONF_NAME): selector.TextSelector()}
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
            CONF_NAME: zone.get(CONF_NAME, ""),
            CONF_OVERRIDES: _overrides_to_text(zone.get(CONF_OVERRIDES, [])),
        }
        schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(
            step_id="zone_edit", data_schema=schema, errors=errors
        )

    # --- Rooms ----------------------------------------------------------

    async def async_step_rooms(self, user_input: dict[str, Any] | None = None):
        """Pick the zone whose rooms you want to manage."""
        zones = self.options[CONF_ZONES]
        if not zones:
            return self.async_show_form(
                step_id="rooms",
                data_schema=vol.Schema({}),
                errors={"base": "no_zones"},
            )
        if user_input is not None:
            self._room_zone_key = user_input["zone"]
            return await self.async_step_room_select()

        options = [
            selector.SelectOptionDict(value=key, label=zone.get(CONF_NAME, key))
            for key, zone in zones.items()
        ]
        schema = vol.Schema(
            {
                vol.Required("zone"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="rooms", data_schema=schema)

    async def async_step_room_select(self, user_input: dict[str, Any] | None = None):
        """Pick a room to edit or add a new one within the chosen zone."""
        zone = self.options[CONF_ZONES][self._room_zone_key]
        rooms = zone.setdefault(CONF_ROOMS, {})
        if user_input is not None:
            self._room_key = (
                None if user_input["room"] == ADD_NEW else user_input["room"]
            )
            return await self.async_step_room_edit()

        options = [selector.SelectOptionDict(value=ADD_NEW, label="➕ Add new room")]
        options += [
            selector.SelectOptionDict(value=key, label=room.get(CONF_NAME, key))
            for key, room in rooms.items()
        ]
        schema = vol.Schema(
            {
                vol.Required("room", default=ADD_NEW): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="room_select", data_schema=schema)

    async def async_step_room_edit(self, user_input: dict[str, Any] | None = None):
        """Add or edit a room (sensor, actuators, per-room settings)."""
        zone = self.options[CONF_ZONES][self._room_zone_key]
        rooms = zone.setdefault(CONF_ROOMS, {})
        key = self._room_key
        room = rooms.get(key, {}) if key else {}

        if user_input is not None:
            if key and user_input.get(CONF_DELETE):
                rooms.pop(key, None)
                return await self.async_step_init()
            name = user_input[CONF_NAME].strip()
            data: dict[str, Any] = {
                CONF_NAME: name,
                CONF_SENSOR: user_input[CONF_SENSOR],
                CONF_HEATERS: user_input.get(CONF_HEATERS, []),
                CONF_COOLERS: user_input.get(CONF_COOLERS, []),
                CONF_HYSTERESIS: user_input.get(CONF_HYSTERESIS, self.options[CONF_HYSTERESIS]),
                CONF_AWAY_TEMP: user_input.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP),
                CONF_MIN_TEMP: user_input.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
                CONF_MAX_TEMP: user_input.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
            }
            target_key = key or _unique_key(name, rooms)
            rooms[target_key] = data
            return await self.async_step_init()

        actuator_config = selector.EntitySelectorConfig(
            domain=["switch", "input_boolean"], multiple=True
        )
        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
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
        if key:
            fields[vol.Optional(CONF_DELETE, default=False)] = selector.BooleanSelector()

        schema = vol.Schema(fields)
        suggested = {
            CONF_NAME: room.get(CONF_NAME, ""),
            CONF_SENSOR: room.get(CONF_SENSOR),
            CONF_HEATERS: room.get(CONF_HEATERS, []),
            CONF_COOLERS: room.get(CONF_COOLERS, []),
            CONF_HYSTERESIS: room.get(CONF_HYSTERESIS, self.options[CONF_HYSTERESIS]),
            CONF_AWAY_TEMP: room.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP),
            CONF_MIN_TEMP: room.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
            CONF_MAX_TEMP: room.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
        }
        schema = self.add_suggested_values_to_schema(
            schema, {k: v for k, v in suggested.items() if v is not None}
        )
        return self.async_show_form(step_id="room_edit", data_schema=schema)
