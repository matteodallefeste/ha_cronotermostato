# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses calendar versioning (`YY.M.patch`). The version in
`custom_components/weekly_thermostat/manifest.json` must always match the Git
tag and the GitHub Release — HACS shows the GitHub Release notes as the
changelog to users.

## [Unreleased]

### Fixed
- **Integration icon/logo now shows up without waiting on home-assistant/brands.**
  The brand images are bundled locally in
  `custom_components/weekly_thermostat/brand/` (`icon`, `logo`, and their `@2x`
  variants). On Home Assistant 2026.3+ these local images take priority over
  the brands CDN, so the "icon not available" placeholder is gone. See the
  [brands proxy API announcement](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/).

## [26.7.3.1] - 2026-07-02

### Added
- **The sidebar panel is now a full editor.** Profiles, floors (weekday
  schedule + holiday/away periods), areas (sensor, actuators, hysteresis…) and
  global settings can all be created, edited and deleted directly from the
  panel — no need to open the integration options. Editing is admin-only and
  validated server-side (the config entry stays the single source of truth).
- The panel's empty state offers in-place actions: **Auto-detect areas** and
  **Open configuration**; once configured, editing/add shortcuts appear inline.
- The options-flow auto-detect step is now a **checklist**: detected areas can
  be unchecked before confirming, so false positives are never created.
- The panel shows each floor's **date-range overrides** (holidays / away),
  highlighting the one active today, and lets you add/edit them.
- Clicking an area tile opens Home Assistant's native climate dialog, so a room
  can be switched to **manual or away** (and its setpoint changed) from the
  panel.

### Changed
- Auto-detection and schedule-validation logic extracted into shared modules
  (`autodetect`, `schedule`) reused by the options flow and the panel's write
  API, so validation lives in one place.
- **License changed** from MIT to PolyForm Noncommercial 1.0.0 with additional
  terms: free for noncommercial use, redistribution only within open-source
  projects, all rights reserved by the author, commercial use by written
  agreement only.

### Fixed
- Auto-detection no longer picks derived "temperature" sensors (dew point,
  apparent/feels-like, wet-bulb, humidex…) as a room's temperature sensor.
- Sensors are now classified from the entity registry (with a live-state
  fallback), so real temperature sensors that are momentarily unavailable are
  still detected; disabled entities are skipped.

## [26.7.3] - 2026-07-02

### Added
- **Auto-detect areas**: an options-flow step that scans Home Assistant areas
  for a temperature sensor and proposes a ready-made scaffold — a default daily
  profile, floors grouped by HA floor, and one area per detected room. Existing
  areas are left untouched; heating/cooling actuators are never guessed.
- **Sidebar schedule panel** (opt-in, enabled by default; toggle under Global
  settings): a dependency-free custom panel showing the weekly schedule at a
  glance — daily profiles as 24h colour bars, the profile per weekday (today
  highlighted) per floor, and a live tile per area.
- **Separate cooling hysteresis** per area (`hysteresis_cool`): falls back to
  the heating `hysteresis` when omitted. Exposed as a `climate` attribute.

### Changed
- Minimum Home Assistant version raised to **2024.4.0** (introduces floors),
  declared in `hacs.json`.

## [26.7.2] - 2026-07-01

### Added
- Initial Weekly Thermostat integration: reusable daily profiles assigned per
  weekday and per floor, with date-range overrides.
- Config flow and menu-driven options editor (no YAML required); optional YAML
  import.
- A `climate` entity per area regulating its own actuators with hysteresis,
  with separate heating/cooling actuators (heating and cooling never run at the
  same time).
- Floors/areas bound to Home Assistant floors and areas; English and Italian
  translations.

[Unreleased]: https://github.com/matteodallefeste/ha_cronotermostato/compare/26.7.3...HEAD
[26.7.3]: https://github.com/matteodallefeste/ha_cronotermostato/compare/26.7.2...26.7.3
[26.7.2]: https://github.com/matteodallefeste/ha_cronotermostato/releases/tag/26.7.2
