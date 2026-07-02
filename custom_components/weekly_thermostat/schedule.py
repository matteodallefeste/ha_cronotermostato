"""Pure helpers for validating and (de)serialising schedule configuration.

Shared by the options flow and the panel's write API so both enforce identical
rules (the config entry stays the single source of truth for validation).
"""

from __future__ import annotations

import re
from typing import Any

from homeassistant.util import slugify

from .const import CONF_END, CONF_PROFILE, CONF_START, CONF_TEMPERATURE, CONF_TIME

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def unique_key(base: str, existing: dict[str, Any]) -> str:
    """Return a slug-based key that does not collide with existing keys."""
    base = slugify(base) or "item"
    key = base
    index = 2
    while key in existing:
        key = f"{base}_{index}"
        index += 1
    return key


def parse_slots(text: str) -> list[dict[str, Any]]:
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


def slots_to_text(slots: list[dict[str, Any]]) -> str:
    """Render profile slots back to an editable multi-line string."""
    return "\n".join(f"{s[CONF_TIME]} {s[CONF_TEMPERATURE]}" for s in slots)


def parse_overrides(text: str, profiles: dict[str, Any]) -> list[dict[str, Any]]:
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


def overrides_to_text(overrides: list[dict[str, Any]]) -> str:
    """Render overrides back to an editable multi-line string."""
    return "\n".join(
        f"{o[CONF_START]} {o[CONF_END]} {o[CONF_PROFILE]}" for o in overrides
    )


def validate_overrides(
    overrides: list[dict[str, Any]], profiles: dict[str, Any]
) -> list[dict[str, Any]]:
    """Validate a structured overrides list (e.g. from the panel editor)."""
    cleaned: list[dict[str, Any]] = []
    for item in overrides:
        start = str(item.get(CONF_START, "")).strip()
        end = str(item.get(CONF_END, "")).strip()
        profile = str(item.get(CONF_PROFILE, "")).strip()
        if not DATE_RE.match(start) or not DATE_RE.match(end):
            raise ValueError(f"Invalid override dates: '{start}' – '{end}'")
        if end < start:
            raise ValueError(f"Override end before start: '{start}' > '{end}'")
        if profile not in profiles:
            raise ValueError(f"Unknown profile in override: '{profile}'")
        cleaned.append({CONF_START: start, CONF_END: end, CONF_PROFILE: profile})
    return cleaned
