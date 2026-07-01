"""Climate platform for the Weekly Thermostat integration.

Each area is exposed as a ``climate`` entity. The target temperature follows
the area's floor schedule (reusable daily profiles assigned per weekday, with
optional date-range overrides). The entity regulates its own actuators with
hysteresis and never runs heating and cooling at the same time.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import PRESET_AWAY
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AWAY_TEMP,
    CONF_AREA,
    CONF_AREAS,
    CONF_COOLERS,
    CONF_END,
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
    DEFAULT_TARGET_STEP,
    DOMAIN,
    PRESET_MANUAL,
    PRESET_SCHEDULE,
    TRANSLATION_KEY,
    UPDATE_INTERVAL,
    WEEKDAYS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate entities from a config entry."""
    data = entry.options
    profiles = data.get(CONF_PROFILES, {})
    global_hysteresis = data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)

    entities: list[WeeklyThermostat] = []
    for floor_id, floor in data.get(CONF_FLOORS, {}).items():
        floor_name = floor.get(CONF_NAME) or floor_id.replace("_", " ").title()
        for area_id, area in floor.get(CONF_AREAS, {}).items():
            entities.append(
                WeeklyThermostat(
                    floor_id=floor_id,
                    floor_name=floor_name,
                    floor=floor,
                    area_id=area_id,
                    area=area,
                    profiles=profiles,
                    global_hysteresis=global_hysteresis,
                )
            )

    async_add_entities(entities)


class WeeklyThermostat(ClimateEntity, RestoreEntity):
    """An area thermostat driven by its floor's weekly schedule."""

    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_translation_key = TRANSLATION_KEY
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = DEFAULT_TARGET_STEP
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        *,
        floor_id: str,
        floor_name: str,
        floor: dict[str, Any],
        area_id: str,
        area: dict[str, Any],
        profiles: dict[str, list[dict[str, Any]]],
        global_hysteresis: float,
    ) -> None:
        """Initialize the thermostat."""
        area_name = area.get(CONF_NAME) or area_id.replace("_", " ").title()
        self._attr_name = f"{floor_name} {area_name}"
        self._attr_unique_id = f"{DOMAIN}_{floor_id}_{area_id}"
        # Link the entity's device to the Home Assistant area, if known.
        ha_area_id = area.get(CONF_AREA)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="Weekly Thermostat",
            model=f"Floor: {floor_name}",
            suggested_area=ha_area_id,
        )

        self._sensor = area[CONF_SENSOR]
        self._heaters: list[str] = list(area.get(CONF_HEATERS, []))
        self._coolers: list[str] = list(area.get(CONF_COOLERS, []))
        self._hysteresis = float(area.get(CONF_HYSTERESIS, global_hysteresis))
        self._away_temp = float(area.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP))
        self._attr_min_temp = float(area.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
        self._attr_max_temp = float(area.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))

        # Floor schedule data.
        self._schedule: dict[str, str] = floor[CONF_SCHEDULE]
        self._overrides: list[dict[str, Any]] = floor[CONF_OVERRIDES]
        # Pre-sort every profile's slots ascending by time for fast lookup.
        self._profiles: dict[str, list[tuple[int, float]]] = {}
        for name, slots in profiles.items():
            parsed = sorted(
                (
                    (self._time_to_minutes(slot[CONF_TIME]), float(slot[CONF_TEMPERATURE]))
                    for slot in slots
                ),
                key=lambda item: item[0],
            )
            self._profiles[name] = parsed

        # Available HVAC modes depend on the configured actuators.
        modes: list[HVACMode] = [HVACMode.OFF]
        if self._heaters:
            modes.append(HVACMode.HEAT)
        if self._coolers:
            modes.append(HVACMode.COOL)
        self._attr_hvac_modes = modes

        self._attr_preset_modes = [PRESET_SCHEDULE, PRESET_MANUAL, PRESET_AWAY]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        # Runtime state.
        default_mode = HVACMode.HEAT if self._heaters else (
            HVACMode.COOL if self._coolers else HVACMode.OFF
        )
        self._attr_hvac_mode: HVACMode = default_mode
        self._attr_preset_mode: str = PRESET_SCHEDULE
        self._attr_hvac_action: HVACAction = HVACAction.OFF
        self._manual_temp: float | None = None

    # --- Static helpers -------------------------------------------------

    @staticmethod
    def _time_to_minutes(value: str) -> int:
        hours, minutes = value.split(":")
        return int(hours) * 60 + int(minutes)

    # --- Schedule computation ------------------------------------------

    def _active_profile(self, moment: datetime) -> str | None:
        """Return the profile name active on the given day (overrides first)."""
        date = moment.strftime("%Y-%m-%d")
        for override in self._overrides:
            if override[CONF_START] <= date <= override[CONF_END]:
                return override[CONF_PROFILE]
        return self._schedule.get(WEEKDAYS[moment.weekday()])

    def _scheduled_target(self) -> float | None:
        """Return the target temperature from the schedule for the current time."""
        now = dt_util.now()
        profile_name = self._active_profile(now)
        slots = self._profiles.get(profile_name) if profile_name else None
        if not slots:
            return None
        now_minutes = now.hour * 60 + now.minute
        # Slots are sorted; the last one starting at or before now wins.
        # Before the first slot, wrap to the last slot (covers past midnight).
        temperature = slots[-1][1]
        for start_minutes, slot_temp in slots:
            if start_minutes <= now_minutes:
                temperature = slot_temp
            else:
                break
        return temperature

    # --- Climate properties --------------------------------------------

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature from the sensor."""
        state = self.hass.states.get(self._sensor)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the effective target temperature for the active preset."""
        if self._attr_preset_mode == PRESET_MANUAL:
            return self._manual_temp
        if self._attr_preset_mode == PRESET_AWAY:
            return self._away_temp
        return self._scheduled_target()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose scheduling details for dashboards and other automations."""
        return {
            "hysteresis": self._hysteresis,
            "active_profile": self._active_profile(dt_util.now()),
            "scheduled_temperature": self._scheduled_target(),
            "heaters": self._heaters,
            "coolers": self._coolers,
        }

    # --- Commands -------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode (off / heat / cool)."""
        if hvac_mode not in self._attr_hvac_modes:
            return
        self._attr_hvac_mode = hvac_mode
        await self._async_control()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode (schedule / manual / away)."""
        if preset_mode not in self._attr_preset_modes:
            return
        self._attr_preset_mode = preset_mode
        if preset_mode == PRESET_MANUAL and self._manual_temp is None:
            # Seed manual setpoint from the current scheduled target.
            self._manual_temp = self._scheduled_target()
        await self._async_control()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a manual target temperature (switches to the manual preset)."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._manual_temp = float(temperature)
        self._attr_preset_mode = PRESET_MANUAL
        await self._async_control()

    async def async_turn_on(self) -> None:
        """Turn the thermostat on, restoring a sensible HVAC mode."""
        if HVACMode.HEAT in self._attr_hvac_modes:
            await self.async_set_hvac_mode(HVACMode.HEAT)
        elif HVACMode.COOL in self._attr_hvac_modes:
            await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Turn the thermostat off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    # --- Lifecycle ------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore state and start tracking sensor changes and time."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            mode = last_state.state
            if mode in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(mode)
            preset = last_state.attributes.get("preset_mode")
            if preset in self._attr_preset_modes:
                self._attr_preset_mode = preset
            # Only the manual preset owns a user-defined setpoint.
            if self._attr_preset_mode == PRESET_MANUAL:
                manual = last_state.attributes.get(ATTR_TEMPERATURE)
                if manual is not None:
                    try:
                        self._manual_temp = float(manual)
                    except (TypeError, ValueError):
                        self._manual_temp = None

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._sensor], self._async_sensor_changed
            )
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_time_tick, UPDATE_INTERVAL
            )
        )
        await self._async_control(write_state=False)

    @callback
    def _async_sensor_changed(self, event: Event) -> None:
        """Handle temperature sensor updates."""
        self.hass.async_create_task(self._async_control())

    @callback
    def _async_time_tick(self, now: datetime) -> None:
        """Re-evaluate the schedule and control loop periodically."""
        self.hass.async_create_task(self._async_control())

    # --- Control loop ---------------------------------------------------

    async def _async_switch(self, entities: list[str], turn_on: bool) -> None:
        """Switch a set of actuators on or off."""
        if not entities:
            return
        await self.hass.services.async_call(
            "homeassistant",
            SERVICE_TURN_ON if turn_on else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entities},
            blocking=False,
        )

    async def _async_control(self, write_state: bool = True) -> None:
        """Evaluate hysteresis and drive the actuators accordingly."""
        if self._attr_hvac_mode == HVACMode.OFF:
            await self._async_switch(self._heaters + self._coolers, False)
            self._attr_hvac_action = HVACAction.OFF
            if write_state:
                self.async_write_ha_state()
            return

        current = self.current_temperature
        target = self.target_temperature
        if current is None or target is None:
            # Not enough information to decide safely: keep actuators off.
            await self._async_switch(self._heaters + self._coolers, False)
            self._attr_hvac_action = HVACAction.IDLE
            if write_state:
                self.async_write_ha_state()
            return

        if self._attr_hvac_mode == HVACMode.COOL:
            active, idle = self._coolers, self._heaters
            running_action = HVACAction.COOLING
            if current > target + self._hysteresis:
                demand = True
            elif current < target - self._hysteresis:
                demand = False
            else:
                demand = self._attr_hvac_action == HVACAction.COOLING
        else:  # HVACMode.HEAT
            active, idle = self._heaters, self._coolers
            running_action = HVACAction.HEATING
            if current < target - self._hysteresis:
                demand = True
            elif current > target + self._hysteresis:
                demand = False
            else:
                demand = self._attr_hvac_action == HVACAction.HEATING

        # Always switch off the actuators of the system that is not active.
        idle_only = [entity for entity in idle if entity not in active]
        await self._async_switch(idle_only, False)
        await self._async_switch(active, demand)

        self._attr_hvac_action = running_action if demand else HVACAction.IDLE
        if write_state:
            self.async_write_ha_state()
