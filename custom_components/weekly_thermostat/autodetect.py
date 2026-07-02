"""Shared auto-detection logic.

Scans Home Assistant areas for temperature sensors and builds a ready-made
scaffold (a default profile plus floors and areas grouped by HA floor). The
same functions back both the options-flow "Auto-detect" step and the panel's
"Auto-detect" button (via a websocket command), so the rules live in one place.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
try:  # Floors were introduced in newer Home Assistant releases.
    from homeassistant.helpers import floor_registry as fr
except ImportError:  # pragma: no cover - older HA without floors
    fr = None

from .schedule import unique_key as _unique_key

from .const import (
    CONF_AREA,
    CONF_AREAS,
    CONF_AWAY_TEMP,
    CONF_COOLERS,
    CONF_FLOOR,
    CONF_FLOORS,
    CONF_HEATERS,
    CONF_HYSTERESIS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_OVERRIDES,
    CONF_PROFILES,
    CONF_SCHEDULE,
    CONF_SENSOR,
    CONF_TEMPERATURE,
    CONF_TIME,
    DEFAULT_AWAY_TEMP,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    WEEKDAYS,
)

_ACTUATOR_DOMAINS = ["switch", "input_boolean"]
PROFILE_NAME = "comfort"
PROFILE_TEMP = 20.0
NO_FLOOR_NAME = "Home"

# Derived "temperature" sensors that are not an ambient room temperature.
# They share device_class "temperature" but must not be picked as the sensor.
_EXCLUDE_KEYWORDS = (
    "dewpoint",
    "dew_point",
    "rugiada",
    "apparent",
    "feels",
    "perceived",
    "percep",
    "wet_bulb",
    "wetbulb",
    "heat_index",
    "humidex",
)


def floor_name(hass: HomeAssistant, floor_id: str | None) -> str | None:
    """Return the friendly name of a Home Assistant floor, if available."""
    if not floor_id or fr is None:
        return None
    floor = fr.async_get(hass).async_get_floor(floor_id)
    return floor.name if floor else None


def _is_temperature_sensor(hass: HomeAssistant, entry: Any) -> bool:
    """Return True if a registry entry is an ambient temperature sensor.

    Classifies from the entity registry first (so it works even when the entity
    is momentarily unavailable), falling back to the live state. Derived
    "temperature" sensors such as dew point or apparent temperature are
    excluded by name even though they share ``device_class: temperature``.
    """
    haystack = f"{entry.entity_id} {entry.name or ''} {entry.original_name or ''}".lower()
    if any(keyword in haystack for keyword in _EXCLUDE_KEYWORDS):
        return False

    device_class = entry.device_class or entry.original_device_class
    unit = entry.unit_of_measurement
    if device_class is None or unit is None:
        state = hass.states.get(entry.entity_id)
        if state:
            device_class = device_class or state.attributes.get("device_class")
            unit = unit or state.attributes.get("unit_of_measurement")
    return device_class == "temperature" or unit in ("°C", "°F")


def area_candidates(
    hass: HomeAssistant, area_id: str | None
) -> tuple[list[str], list[str]]:
    """Return (temperature sensors, switch actuators) found in an HA area."""
    if not area_id:
        return [], []
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entries: dict[str, Any] = {
        entry.entity_id: entry
        for entry in er.async_entries_for_area(ent_reg, area_id)
    }
    for device in dr.async_entries_for_area(dev_reg, area_id):
        for entry in er.async_entries_for_device(ent_reg, device.id):
            if entry.area_id is None:
                entries.setdefault(entry.entity_id, entry)

    temp_sensors: list[str] = []
    switches: list[str] = []
    for entry in entries.values():
        if entry.disabled_by is not None:
            continue
        domain = entry.domain
        if domain == "sensor":
            if _is_temperature_sensor(hass, entry):
                temp_sensors.append(entry.entity_id)
        elif domain in _ACTUATOR_DOMAINS:
            switches.append(entry.entity_id)
    return sorted(temp_sensors), sorted(switches)


def list_temperature_sensors(hass: HomeAssistant) -> list[str]:
    """Return every ambient temperature sensor entity id, registry-wide."""
    ent_reg = er.async_get(hass)
    out = [
        entry.entity_id
        for entry in ent_reg.entities.values()
        if entry.domain == "sensor"
        and entry.disabled_by is None
        and _is_temperature_sensor(hass, entry)
    ]
    return sorted(out)


def list_actuators(hass: HomeAssistant) -> list[str]:
    """Return every switch/input_boolean entity id that can drive an actuator."""
    ent_reg = er.async_get(hass)
    out = [
        entry.entity_id
        for entry in ent_reg.entities.values()
        if entry.domain in _ACTUATOR_DOMAINS and entry.disabled_by is None
    ]
    return sorted(out)


def build_proposal(hass: HomeAssistant, options: dict[str, Any]) -> dict[str, Any]:
    """Propose floors/areas to create from Home Assistant registries.

    Only areas that hold a temperature sensor and are not already configured
    become candidates. They are grouped by their Home Assistant floor; when a
    configured floor is already linked to that HA floor the new areas are
    attached to it instead of creating a duplicate.
    """
    floors_cfg = options.get(CONF_FLOORS, {})
    used_area_ids = {
        area.get(CONF_AREA)
        for floor in floors_cfg.values()
        for area in floor.get(CONF_AREAS, {}).values()
        if area.get(CONF_AREA)
    }
    existing_by_ha_floor = {
        floor.get(CONF_FLOOR): key
        for key, floor in floors_cfg.items()
        if floor.get(CONF_FLOOR)
    }

    grouped: dict[str | None, dict[str, Any]] = {}
    for area in ar.async_get(hass).async_list_areas():
        if area.id in used_area_ids:
            continue
        temp_sensors, _ = area_candidates(hass, area.id)
        if not temp_sensors:
            continue
        floor_id = getattr(area, "floor_id", None)
        group = grouped.setdefault(
            floor_id,
            {
                "floor_id": floor_id,
                "floor_name": floor_name(hass, floor_id) or NO_FLOOR_NAME,
                "existing_key": existing_by_ha_floor.get(floor_id),
                "areas": [],
            },
        )
        group["areas"].append(
            {
                "area_id": area.id,
                "name": area.name,
                "sensor": temp_sensors[0],
                "ambiguous": len(temp_sensors) > 1,
            }
        )

    groups = sorted(grouped.values(), key=lambda g: g["floor_name"].lower())

    profiles = options.get(CONF_PROFILES, {})
    if profiles:
        profile_key = next(iter(profiles))
        seed_profile = False
    else:
        profile_key = _unique_key(PROFILE_NAME, profiles)
        seed_profile = True

    return {
        "seed_profile": seed_profile,
        "profile_key": profile_key,
        "groups": groups,
    }


def count_new_areas(proposal: dict[str, Any]) -> int:
    """Return how many new areas the proposal would create."""
    return sum(len(group["areas"]) for group in proposal["groups"])


def filter_proposal(
    proposal: dict[str, Any], selected_area_ids: set[str]
) -> dict[str, Any]:
    """Return a copy of the proposal keeping only the selected areas."""
    groups = []
    for group in proposal["groups"]:
        areas = [a for a in group["areas"] if a["area_id"] in selected_area_ids]
        if areas:
            groups.append({**group, "areas": areas})
    return {**proposal, "groups": groups}


def apply_proposal(options: dict[str, Any], proposal: dict[str, Any]) -> None:
    """Write the proposed profile, floors and areas into ``options`` in place."""
    profiles = options.setdefault(CONF_PROFILES, {})
    floors = options.setdefault(CONF_FLOORS, {})
    global_hysteresis = options.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
    profile_key = proposal["profile_key"]

    if proposal["seed_profile"]:
        profiles[profile_key] = [
            {CONF_TIME: "00:00", CONF_TEMPERATURE: PROFILE_TEMP}
        ]

    for group in proposal["groups"]:
        floor_key = group["existing_key"]
        if floor_key is None:
            floor_key = _unique_key(group["floor_name"], floors)
            floors[floor_key] = {
                CONF_NAME: group["floor_name"],
                CONF_FLOOR: group["floor_id"],
                CONF_SCHEDULE: {day: profile_key for day in WEEKDAYS},
                CONF_OVERRIDES: [],
                CONF_AREAS: {},
            }
        areas = floors[floor_key].setdefault(CONF_AREAS, {})
        for detected in group["areas"]:
            area_key = detected["area_id"]
            if area_key in areas:
                continue
            areas[area_key] = {
                CONF_NAME: detected["name"],
                CONF_AREA: detected["area_id"],
                CONF_SENSOR: detected["sensor"],
                CONF_HEATERS: [],
                CONF_COOLERS: [],
                CONF_HYSTERESIS: global_hysteresis,
                CONF_AWAY_TEMP: DEFAULT_AWAY_TEMP,
                CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
                CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
            }
