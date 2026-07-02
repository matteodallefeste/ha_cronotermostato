# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses calendar versioning (`YY.M.patch`). The version in
`custom_components/weekly_thermostat/manifest.json` must always match the Git
tag and the GitHub Release — HACS shows the GitHub Release notes as the
changelog to users.

## [Unreleased]

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
