"""Sidebar panel registration and websocket API for Weekly Thermostat.

The optional custom panel shows the whole weekly schedule at a glance (daily
profiles, the profile assigned to each weekday per floor, and the live state
of every area). It is a plain custom element served as a static JS file, so no
build step is required.

The panel needs data that lives in the config entry (profiles and floor
schedules) rather than in entity states, so a small websocket command exposes
that structure, resolving each area to its ``climate`` entity id.
"""

from __future__ import annotations

import copy
import os
from typing import Any

import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.frontend import async_remove_panel
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from . import autodetect, edit
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
    DEFAULT_HYSTERESIS,
    DEFAULT_SHOW_PANEL,
    DOMAIN,
    PANEL_ICON,
    PANEL_JS_FILENAME,
    PANEL_JS_VERSION,
    PANEL_STATIC_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
    WS_TYPE_AUTODETECT,
    WS_TYPE_CONFIG,
)

WEBCOMPONENT_NAME = "weekly-thermostat-panel"
_STATIC_FLAG = "static_registered"
_WS_FLAG = "ws_registered"


# --- Websocket API ------------------------------------------------------


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the config websocket command once."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_WS_FLAG):
        return
    websocket_api.async_register_command(hass, _ws_get_config)
    websocket_api.async_register_command(hass, _ws_autodetect)
    edit.async_register(hass)
    data[_WS_FLAG] = True


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_CONFIG})
@callback
def _ws_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the schedule structure (profiles + floors) for the panel."""
    entries = hass.config_entries.async_entries(DOMAIN)
    options: dict[str, Any] = dict(entries[0].options) if entries else {}
    ent_reg = er.async_get(hass)

    floors_out: list[dict[str, Any]] = []
    for floor_id, floor in options.get(CONF_FLOORS, {}).items():
        areas_out: list[dict[str, Any]] = []
        for area_id, area in floor.get(CONF_AREAS, {}).items():
            unique_id = f"{DOMAIN}_{floor_id}_{area_id}"
            entity_id = ent_reg.async_get_entity_id("climate", DOMAIN, unique_id)
            areas_out.append(
                {
                    "key": area_id,
                    "name": area.get(CONF_NAME) or area_id,
                    "entity_id": entity_id,
                    "ha_area": area.get(CONF_AREA),
                    "sensor": area.get(CONF_SENSOR, ""),
                    "heaters": area.get(CONF_HEATERS, []),
                    "coolers": area.get(CONF_COOLERS, []),
                    "hysteresis": area.get(CONF_HYSTERESIS),
                    "hysteresis_cool": area.get(CONF_HYSTERESIS_COOL),
                    "away_temperature": area.get(CONF_AWAY_TEMP),
                    "min_temperature": area.get(CONF_MIN_TEMP),
                    "max_temperature": area.get(CONF_MAX_TEMP),
                }
            )
        floors_out.append(
            {
                "key": floor_id,
                "name": floor.get(CONF_NAME) or floor_id,
                "ha_floor": floor.get(CONF_FLOOR),
                "schedule": floor.get(CONF_SCHEDULE, {}),
                "overrides": floor.get(CONF_OVERRIDES, []),
                "areas": areas_out,
            }
        )

    connection.send_result(
        msg["id"],
        {
            "hysteresis": options.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS),
            "show_panel": options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL),
            "profiles": options.get(CONF_PROFILES, {}),
            "floors": floors_out,
        },
    )


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_AUTODETECT})
@websocket_api.require_admin
@callback
def _ws_autodetect(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run auto-detection and write the result into the config entry.

    Reuses the same logic as the options-flow step. Non-destructive: only new
    areas (with a temperature sensor, not already configured) are added. The
    entry reloads via its update listener, so the panel repopulates.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_found", "No config entry")
        return

    entry = entries[0]
    options = copy.deepcopy(dict(entry.options))
    options.setdefault(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
    options.setdefault(CONF_PROFILES, {})
    options.setdefault(CONF_FLOORS, {})

    proposal = autodetect.build_proposal(hass, options)
    created = autodetect.count_new_areas(proposal)
    if created:
        autodetect.apply_proposal(options, proposal)
        hass.config_entries.async_update_entry(entry, options=options)

    connection.send_result(msg["id"], {"created_areas": created})


# --- Panel registration -------------------------------------------------


async def _async_register_static(hass: HomeAssistant) -> None:
    """Serve the panel JS as a static file (once)."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_STATIC_FLAG):
        return
    path = os.path.join(os.path.dirname(__file__), "www", PANEL_JS_FILENAME)
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_URL, path, True)]
        )
    except ImportError:  # pragma: no cover - older HA
        hass.http.register_static_path(PANEL_STATIC_URL, path, True)
    data[_STATIC_FLAG] = True


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register (or re-register) the sidebar panel."""
    await _async_register_static(hass)
    async_remove_panel_if_present(hass)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=WEBCOMPONENT_NAME,
        frontend_url_path=PANEL_URL_PATH,
        module_url=f"{PANEL_STATIC_URL}?v={PANEL_JS_VERSION}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
    )


@callback
def async_remove_panel_if_present(hass: HomeAssistant) -> None:
    """Remove the sidebar panel if it is currently registered."""
    async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
