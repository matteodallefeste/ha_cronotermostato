"""The Weekly Thermostat integration.

A weekly, multi-floor programmable thermostat (chronothermostat). Reusable
daily profiles are assigned to weekdays per floor, with optional date-range
overrides (holidays/absence). Each area becomes a ``climate`` entity that
regulates its own actuators (heating and/or cooling) with hysteresis,
following the target temperature computed from its floor's schedule.

Floors map to Home Assistant floors (a schedule group), and areas map to
Home Assistant areas (the room the thermostat lives in).
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

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
    CONF_HYSTERESIS_COOL,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_OVERRIDES,
    CONF_PROFILE,
    CONF_PROFILES,
    CONF_SCHEDULE,
    CONF_SENSOR,
    CONF_SHOW_PANEL,
    CONF_START,
    CONF_TEMPERATURE,
    CONF_TIME,
    DEFAULT_HYSTERESIS,
    DEFAULT_SHOW_PANEL,
    DOMAIN,
    WEEKDAYS,
)
from .panel import (
    async_register_panel,
    async_register_websocket,
    async_remove_panel_if_present,
)

PLATFORMS = [Platform.CLIMATE]

PROFILE_SLOT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TIME): cv.matches_regex(r"^([01]\d|2[0-3]):[0-5]\d$"),
        vol.Required(CONF_TEMPERATURE): vol.Coerce(float),
    }
)

OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): cv.matches_regex(r"^\d{4}-\d{2}-\d{2}$"),
        vol.Required(CONF_END): cv.matches_regex(r"^\d{4}-\d{2}-\d{2}$"),
        vol.Required(CONF_PROFILE): cv.string,
    }
)

AREA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_AREA): cv.string,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_HEATERS, default=list): cv.entity_ids,
        vol.Optional(CONF_COOLERS, default=list): cv.entity_ids,
        vol.Optional(CONF_HYSTERESIS): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        vol.Optional(CONF_HYSTERESIS_COOL): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    }
)

FLOOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_FLOOR): cv.string,
        vol.Required(CONF_SCHEDULE): {vol.In(WEEKDAYS): cv.string},
        vol.Optional(CONF_OVERRIDES, default=list): [OVERRIDE_SCHEMA],
        vol.Required(CONF_AREAS): vol.Schema({cv.string: AREA_SCHEMA}),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
                vol.Required(CONF_PROFILES): vol.Schema(
                    {cv.slug: [PROFILE_SLOT_SCHEMA]}
                ),
                vol.Required(CONF_FLOORS): vol.Schema({cv.string: FLOOR_SCHEMA}),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import YAML configuration (if any) into a config entry."""
    async_register_websocket(hass)

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Validate that every referenced profile actually exists.
    profiles = conf[CONF_PROFILES]
    for floor_id, floor in conf[CONF_FLOORS].items():
        referenced = set(floor[CONF_SCHEDULE].values())
        referenced.update(ov[CONF_PROFILE] for ov in floor[CONF_OVERRIDES])
        missing = referenced - set(profiles)
        if missing:
            raise vol.Invalid(
                f"Floor '{floor_id}' references unknown profile(s): "
                f"{', '.join(sorted(missing))}"
            )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Weekly Thermostat from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if entry.options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL):
        await async_register_panel(hass)
    else:
        async_remove_panel_if_present(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    async_remove_panel_if_present(hass)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry)
