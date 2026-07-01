"""The Weekly Thermostat integration.

A weekly, multi-zone programmable thermostat (chronothermostat) configured in
YAML. Reusable daily profiles are assigned to weekdays per zone, with optional
date-range overrides (holidays/absence). Each room becomes a ``climate`` entity
that regulates its own actuators (heating and/or cooling) with hysteresis,
following the target temperature computed from its zone's schedule.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

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
    DEFAULT_HYSTERESIS,
    DOMAIN,
    WEEKDAYS,
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

ROOM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_HEATERS, default=list): cv.entity_ids,
        vol.Optional(CONF_COOLERS, default=list): cv.entity_ids,
        vol.Optional(CONF_HYSTERESIS): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_SCHEDULE): {vol.In(WEEKDAYS): cv.string},
        vol.Optional(CONF_OVERRIDES, default=list): [OVERRIDE_SCHEMA],
        vol.Required(CONF_ROOMS): vol.Schema({cv.slug: ROOM_SCHEMA}),
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
                vol.Required(CONF_ZONES): vol.Schema({cv.slug: ZONE_SCHEMA}),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Weekly Thermostat integration from YAML."""
    conf = config[DOMAIN]

    # Validate that every referenced profile actually exists.
    profiles = conf[CONF_PROFILES]
    for zone_id, zone in conf[CONF_ZONES].items():
        referenced = set(zone[CONF_SCHEDULE].values())
        referenced.update(ov[CONF_PROFILE] for ov in zone[CONF_OVERRIDES])
        missing = referenced - set(profiles)
        if missing:
            raise vol.Invalid(
                f"Zone '{zone_id}' references unknown profile(s): "
                f"{', '.join(sorted(missing))}"
            )

    hass.data[DOMAIN] = conf

    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
    )
    return True
