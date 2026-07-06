# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Matteo Dalle Feste

"""Admin-only websocket write API backing the panel's editor.

The panel is a thin UI: it sends intents (save/delete a profile, floor, area or
the global settings) and these handlers validate them server-side using the
same rules as the options flow, then write the config entry (which reloads).
This keeps a single source of truth for validation — no logic is duplicated in
the frontend.
"""

from __future__ import annotations

import copy
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar

from . import autodetect
from .autodetect import list_actuators, list_temperature_sensors
from .const import (
    CONF_AREA,
    CONF_AREAS,
    CONF_AWAY_TEMP,
    CONF_COOLERS,
    CONF_FLOOR,
    CONF_FLOORS,
    CONF_HEATERS,
    CONF_HYSTERESIS,
    CONF_HYSTERESIS_COOL,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_OVERRIDES,
    CONF_PROFILES,
    CONF_SCHEDULE,
    CONF_SENSOR,
    CONF_SHOW_PANEL,
    DEFAULT_AWAY_TEMP,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_SHOW_PANEL,
    DOMAIN,
    WEEKDAYS,
    WS_TYPE_AREA_DELETE,
    WS_TYPE_AREA_SAVE,
    WS_TYPE_FLOOR_DELETE,
    WS_TYPE_FLOOR_SAVE,
    WS_TYPE_LISTS,
    WS_TYPE_PROFILE_DELETE,
    WS_TYPE_PROFILE_SAVE,
    WS_TYPE_SETTINGS_SAVE,
)
from .schedule import parse_slots, unique_key, validate_overrides

try:  # Floors were introduced in newer Home Assistant releases.
    from homeassistant.helpers import floor_registry as fr
except ImportError:  # pragma: no cover - older HA without floors
    fr = None

_FLAG = "edit_ws_registered"
_OptionalNumber = vol.Any(vol.Coerce(float), None)


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the editor websocket commands once."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_FLAG):
        return
    for command in (
        _ws_lists,
        _ws_settings_save,
        _ws_profile_save,
        _ws_profile_delete,
        _ws_floor_save,
        _ws_floor_delete,
        _ws_area_save,
        _ws_area_delete,
    ):
        websocket_api.async_register_command(hass, command)
    data[_FLAG] = True


# --- Helpers ------------------------------------------------------------


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _load_options(entry: ConfigEntry) -> dict[str, Any]:
    options = copy.deepcopy(dict(entry.options))
    options.setdefault(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
    options.setdefault(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL)
    options.setdefault(CONF_PROFILES, {})
    options.setdefault(CONF_FLOORS, {})
    return options


def _save(hass: HomeAssistant, entry: ConfigEntry, options: dict[str, Any]) -> None:
    hass.config_entries.async_update_entry(entry, options=options)


# --- Read: lists to populate the editor's pickers -----------------------


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_LISTS})
@websocket_api.require_admin
@callback
def _ws_lists(hass, connection, msg):
    """Return HA floors/areas and candidate sensor/actuator entities."""
    floors = []
    if fr is not None:
        floors = [
            {"floor_id": floor.floor_id, "name": floor.name}
            for floor in fr.async_get(hass).async_list_floors()
        ]
    areas = [
        {
            "area_id": area.id,
            "name": area.name,
            "floor_id": getattr(area, "floor_id", None),
        }
        for area in ar.async_get(hass).async_list_areas()
    ]

    def _named(entity_id: str) -> dict[str, str]:
        state = hass.states.get(entity_id)
        name = state.attributes.get("friendly_name") if state else None
        return {"entity_id": entity_id, "name": name or entity_id}

    connection.send_result(
        msg["id"],
        {
            "ha_floors": floors,
            "ha_areas": areas,
            "temp_sensors": [_named(e) for e in list_temperature_sensors(hass)],
            "actuators": [_named(e) for e in list_actuators(hass)],
        },
    )


# --- Settings -----------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SETTINGS_SAVE,
        vol.Required("hysteresis"): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        vol.Required("show_panel"): bool,
    }
)
@websocket_api.require_admin
@callback
def _ws_settings_save(hass, connection, msg):
    entry = _entry(hass)
    if not entry:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return
    options = _load_options(entry)
    options[CONF_HYSTERESIS] = msg["hysteresis"]
    options[CONF_SHOW_PANEL] = msg["show_panel"]
    _save(hass, entry, options)
    connection.send_result(msg["id"], {})


# --- Profiles -----------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PROFILE_SAVE,
        vol.Optional("key"): str,
        vol.Required("name"): str,
        vol.Required("slots_text"): str,
    }
)
@websocket_api.require_admin
@callback
def _ws_profile_save(hass, connection, msg):
    entry = _entry(hass)
    if not entry:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return
    options = _load_options(entry)
    profiles = options[CONF_PROFILES]
    try:
        slots = parse_slots(msg["slots_text"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_slots", str(err))
        return
    key = msg.get("key")
    if not key or key not in profiles:
        key = unique_key(msg["name"], profiles)
    profiles[key] = slots
    _save(hass, entry, options)
    connection.send_result(msg["id"], {"key": key})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_TYPE_PROFILE_DELETE, vol.Required("key"): str}
)
@websocket_api.require_admin
@callback
def _ws_profile_delete(hass, connection, msg):
    entry = _entry(hass)
    if not entry:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return
    options = _load_options(entry)
    if msg["key"] not in options[CONF_PROFILES]:
        connection.send_result(msg["id"], {})
        return
    # Refuse to delete a profile still referenced by a floor schedule/override.
    for floor in options[CONF_FLOORS].values():
        referenced = set(floor.get(CONF_SCHEDULE, {}).values())
        referenced.update(o["profile"] for o in floor.get(CONF_OVERRIDES, []))
        if msg["key"] in referenced:
            connection.send_error(msg["id"], "profile_in_use", "Profile is in use")
            return
    options[CONF_PROFILES].pop(msg["key"], None)
    _save(hass, entry, options)
    connection.send_result(msg["id"], {})


# --- Floors -------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_FLOOR_SAVE,
        vol.Optional("key"): str,
        vol.Required("name"): str,
        vol.Optional("ha_floor"): vol.Any(str, None),
        vol.Required("schedule"): {str: str},
        vol.Optional("overrides", default=list): [dict],
    }
)
@websocket_api.require_admin
@callback
def _ws_floor_save(hass, connection, msg):
    entry = _entry(hass)
    if not entry:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return
    options = _load_options(entry)
    profiles = options[CONF_PROFILES]
    floors = options[CONF_FLOORS]
    name = msg["name"].strip()
    if not name:
        connection.send_error(msg["id"], "invalid_name", "Name is required")
        return
    if not profiles:
        connection.send_error(msg["id"], "no_profiles", "Create a profile first")
        return

    schedule_in = msg["schedule"]
    schedule: dict[str, str] = {}
    for day in WEEKDAYS:
        prof = schedule_in.get(day)
        if prof not in profiles:
            connection.send_error(msg["id"], "invalid_schedule", f"Bad profile for {day}")
            return
        schedule[day] = prof

    try:
        overrides = validate_overrides(msg.get("overrides", []), profiles)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_overrides", str(err))
        return

    key = msg.get("key")
    existing = floors.get(key, {}) if key and key in floors else {}
    if not existing:
        key = unique_key(name, floors)
    floors[key] = {
        CONF_NAME: name,
        CONF_FLOOR: msg.get("ha_floor") or None,
        CONF_SCHEDULE: schedule,
        CONF_OVERRIDES: overrides,
        CONF_AREAS: existing.get(CONF_AREAS, {}),
    }
    _save(hass, entry, options)
    connection.send_result(msg["id"], {"key": key})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_TYPE_FLOOR_DELETE, vol.Required("key"): str}
)
@websocket_api.require_admin
@callback
def _ws_floor_delete(hass, connection, msg):
    entry = _entry(hass)
    if not entry:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return
    options = _load_options(entry)
    options[CONF_FLOORS].pop(msg["key"], None)
    _save(hass, entry, options)
    connection.send_result(msg["id"], {})


# --- Areas --------------------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_AREA_SAVE,
        vol.Required("floor_key"): str,
        vol.Optional("key"): str,
        vol.Optional("ha_area"): vol.Any(str, None),
        vol.Required("name"): str,
        vol.Required("sensor"): str,
        vol.Optional("heaters", default=list): [str],
        vol.Optional("coolers", default=list): [str],
        vol.Optional("hysteresis"): _OptionalNumber,
        vol.Optional("hysteresis_cool"): _OptionalNumber,
        vol.Optional("away_temperature"): _OptionalNumber,
        vol.Optional("min_temperature"): _OptionalNumber,
        vol.Optional("max_temperature"): _OptionalNumber,
    }
)
@websocket_api.require_admin
@callback
def _ws_area_save(hass, connection, msg):
    entry = _entry(hass)
    if not entry:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return
    options = _load_options(entry)
    floor = options[CONF_FLOORS].get(msg["floor_key"])
    if floor is None:
        connection.send_error(msg["id"], "not_found", "Unknown floor")
        return
    areas = floor.setdefault(CONF_AREAS, {})
    name = msg["name"].strip()
    sensor = msg["sensor"].strip()
    if not name or not sensor:
        connection.send_error(msg["id"], "invalid", "Name and sensor are required")
        return

    key = msg.get("key")
    if not key or key not in areas:
        key = msg.get("ha_area") or unique_key(name, areas)
        if key in areas:
            key = unique_key(name, areas)

    hysteresis = msg.get("hysteresis")
    areas[key] = {
        CONF_NAME: name,
        CONF_AREA: msg.get("ha_area") or None,
        CONF_SENSOR: sensor,
        CONF_HEATERS: msg.get("heaters", []),
        CONF_COOLERS: msg.get("coolers", []),
        CONF_HYSTERESIS: hysteresis if hysteresis is not None else options[CONF_HYSTERESIS],
        CONF_HYSTERESIS_COOL: msg.get("hysteresis_cool"),
        CONF_AWAY_TEMP: msg.get("away_temperature") or DEFAULT_AWAY_TEMP,
        CONF_MIN_TEMP: msg.get("min_temperature") or DEFAULT_MIN_TEMP,
        CONF_MAX_TEMP: msg.get("max_temperature") or DEFAULT_MAX_TEMP,
    }
    _save(hass, entry, options)
    connection.send_result(msg["id"], {"key": key, "floor_key": msg["floor_key"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_AREA_DELETE,
        vol.Required("floor_key"): str,
        vol.Required("key"): str,
    }
)
@websocket_api.require_admin
@callback
def _ws_area_delete(hass, connection, msg):
    entry = _entry(hass)
    if not entry:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return
    options = _load_options(entry)
    floor = options[CONF_FLOORS].get(msg["floor_key"])
    if floor is not None:
        floor.get(CONF_AREAS, {}).pop(msg["key"], None)
        _save(hass, entry, options)
    connection.send_result(msg["id"], {})
