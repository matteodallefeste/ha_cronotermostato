"""Constants for the Weekly Thermostat integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "weekly_thermostat"

# --- Configuration keys ---
CONF_HYSTERESIS = "hysteresis"
CONF_SHOW_PANEL = "show_panel"
CONF_PROFILES = "profiles"
CONF_FLOORS = "floors"
CONF_SCHEDULE = "schedule"
CONF_OVERRIDES = "overrides"
CONF_AREAS = "areas"
CONF_AREA = "area"
CONF_FLOOR = "floor"
CONF_SENSOR = "sensor"
CONF_HEATERS = "heaters"
CONF_COOLERS = "coolers"
CONF_HYSTERESIS_COOL = "hysteresis_cool"
CONF_TIME = "time"
CONF_TEMPERATURE = "temperature"
CONF_START = "start"
CONF_END = "end"
CONF_PROFILE = "profile"
CONF_NAME = "name"
CONF_AWAY_TEMP = "away_temperature"
CONF_MIN_TEMP = "min_temperature"
CONF_MAX_TEMP = "max_temperature"

# --- Defaults ---
DEFAULT_HYSTERESIS = 0.3
DEFAULT_SHOW_PANEL = True
DEFAULT_AWAY_TEMP = 16.0
DEFAULT_MIN_TEMP = 5.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_TARGET_STEP = 0.5

# --- Preset modes (in addition to Home Assistant's built-in PRESET_AWAY) ---
PRESET_SCHEDULE = "schedule"
PRESET_MANUAL = "manual"

# Weekday keys used in a zone schedule (Monday .. Sunday).
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# How often the schedule/control loop is re-evaluated (covers slot boundaries).
UPDATE_INTERVAL = timedelta(seconds=60)

# Translation key shared by all thermostat entities.
TRANSLATION_KEY = "weekly_thermostat"

# --- Sidebar panel ---
PANEL_URL_PATH = "weekly-thermostat"
PANEL_TITLE = "Weekly Thermostat"
PANEL_ICON = "mdi:calendar-clock"
PANEL_STATIC_URL = "/weekly_thermostat/panel.js"
PANEL_JS_FILENAME = "weekly-thermostat-panel.js"
# Bump when the panel JS changes, to bust the browser cache.
PANEL_JS_VERSION = "2"
WS_TYPE_CONFIG = "weekly_thermostat/config"
