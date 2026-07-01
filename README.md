# Weekly Thermostat

A weekly, multi-floor programmable thermostat (chronothermostat) for
[Home Assistant](https://www.home-assistant.io/), installable via
[HACS](https://hacs.xyz/).

- **Reusable daily profiles** — time ranges → temperature, defined once
- **Weekly schedule** — assign a profile to each weekday, per floor
- **Date-range overrides** — holidays / absence replace the weekly schedule
- **Floors → areas** — mapped to Home Assistant floors and areas
- **Heating and/or cooling** per area, with separate actuators
- **Native `climate` entities** with `hvac_action`, presets and hysteresis

## Model

```
Floor (e.g. Ground Floor, Office)  -> weekly-schedule group
 ├─ (optional) linked HA floor
 ├─ weekly schedule                 -> a profile per weekday (mon..sun)
 ├─ date-range overrides            -> replace the profile in a period
 └─ Areas
     └─ each area                   -> a climate entity, placed in the HA area
         ├─ 1 temperature sensor
         ├─ heaters (0..N)
         └─ coolers (0..N)

Daily profile = ordered list of { time: "HH:MM", temperature: °C }
```

Every area follows its floor's target temperature but regulates its **own**
actuators based on its **own** sensor, with hysteresis. Heating and cooling
are never active at the same time.

## Home Assistant mapping

The terminology mirrors Home Assistant on purpose:

| Concept | Home Assistant |
|---|---|
| Area (sensor + actuators) | a Home Assistant **area** → one `climate` entity |
| Floor (weekly-schedule group) | a Home Assistant **floor** (optional link) |
| Schedule / manual / holiday | `preset_mode`: `schedule` / `manual` / `away` |
| Heating / cooling | `hvac_mode`: `heat` / `cool` / `off` |
| Demand | `hvac_action`: `heating` / `cooling` / `idle` / `off` |

> Note: Home Assistant "zones" are GPS presence zones — a different concept —
> so this integration uses **floors** for the schedule grouping instead.

- **`schedule`** preset: target follows the weekly program (and overrides).
- **`manual`** preset: target is the value you set (setting a temperature
  switches to this preset automatically).
- **`away`** preset: target is the area's `away_temperature`.

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → *Custom repositories*.
2. Add `https://github.com/matteodallefeste/ha_cronotermostato` as an
   **Integration**.
3. Install **Weekly Thermostat** and restart Home Assistant.

### Manual

Copy `custom_components/weekly_thermostat/` into your Home Assistant
`config/custom_components/` folder and restart.

## Configuration

### Via the UI (recommended)

1. **Settings → Devices & Services → Add Integration → Weekly Thermostat.**
2. Open the integration's **Configure** button to manage everything from a
   menu:
   - **Global settings** — default hysteresis
   - **Daily profiles** — add/edit/remove profiles (one `HH:MM temperature`
     slot per line)
   - **Floors & weekly schedule** — assign a profile to each weekday, optionally
     link a Home Assistant floor, and add date-range overrides
   - **Areas** — pick a Home Assistant area; its temperature sensor and switches
     are auto-suggested, then confirm the heating/cooling actuators
3. Choose **Save & close**. Changes are applied immediately (the entry
   reloads).

Order matters: create at least one **profile** before adding a **floor**, and a
**floor** before adding **areas**. Each area is placed in its Home Assistant
area automatically.

### Via YAML (optional)

You can also bootstrap the configuration from YAML — it is imported into the
integration on start (see
[`examples/configuration.yaml`](examples/configuration.yaml) for a full
example). Add a `weekly_thermostat:` block to your `configuration.yaml`:

```yaml
weekly_thermostat:
  hysteresis: 0.3            # global default (°C), optional

  profiles:
    home_weekday:
      - { time: "00:00", temperature: 18 }
      - { time: "06:30", temperature: 21 }
      - { time: "08:30", temperature: 18 }
      - { time: "22:00", temperature: 18 }

  floors:
    ground_floor:
      name: Ground Floor
      # floor: ground_floor      # optional HA floor id link
      schedule:
        mon: home_weekday
        tue: home_weekday
        wed: home_weekday
        thu: home_weekday
        fri: home_weekday
        sat: home_weekday
        sun: home_weekday
      overrides:
        - { start: "2026-08-01", end: "2026-08-20", profile: home_weekday }
      areas:
        living_room:
          name: Living Room
          area: living_room      # optional HA area id link
          sensor: sensor.living_room_temperature
          heaters:
            - switch.living_room_valve
```

### Options

| Key | Level | Required | Description |
|---|---|---|---|
| `hysteresis` | root | no (0.3) | Default hysteresis in °C |
| `profiles` | root | yes | Named daily profiles (list of slots) |
| `time` / `temperature` | slot | yes | Slot start (`HH:MM`) and setpoint |
| `floor` | floor | no | Linked Home Assistant floor id |
| `schedule` | floor | yes | Profile per weekday (`mon`..`sun`) |
| `overrides` | floor | no | `{ start, end, profile }`, dates inclusive |
| `areas` | floor | yes | Areas on the floor |
| `area` | area | no | Linked Home Assistant area id (entity placement) |
| `sensor` | area | yes | Temperature sensor entity |
| `heaters` | area | no `[]` | Actuators used for heating |
| `coolers` | area | no `[]` | Actuators used for cooling |
| `hysteresis` | area | no | Overrides the global hysteresis |
| `away_temperature` | area | no (16) | Target for the `away` preset |
| `min_temperature` / `max_temperature` | area | no | UI setpoint limits |

Notes:

- The first slot of every profile must start at `00:00`.
- `heaters` enables the `heat` mode; `coolers` enables the `cool` mode.
- In `cool` mode the profile temperature is the cooling setpoint (the
  hysteresis logic is inverted automatically).

## Entities

For each area you get a `climate` entity named `<Floor> <Area>` (e.g.
`climate.ground_floor_living_room`), placed in its Home Assistant area, with
extra attributes:

- `hysteresis`, `active_profile`, `scheduled_temperature`, `heaters`, `coolers`

## Localization

The UI is available in English and Italian (`translations/en.json`,
`translations/it.json`). Contributions for other languages are welcome.

## License

MIT — see [`LICENSE`](LICENSE).
