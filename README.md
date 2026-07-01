# Weekly Thermostat

A weekly, multi-zone programmable thermostat (chronothermostat) for
[Home Assistant](https://www.home-assistant.io/), installable via
[HACS](https://hacs.xyz/).

- **Reusable daily profiles** — time ranges → temperature, defined once
- **Weekly schedule** — assign a profile to each weekday, per zone
- **Date-range overrides** — holidays / absence replace the weekly schedule
- **Zones → rooms** — each room has one sensor and one or more actuators
- **Heating and/or cooling** per room, with separate actuators
- **Native `climate` entities** with `hvac_action`, presets and hysteresis

## Model

```
Zone (e.g. Home, Office)          -> Home Assistant device
 ├─ weekly schedule                -> a profile per weekday (mon..sun)
 ├─ date-range overrides           -> replace the profile in a period
 └─ Rooms
     └─ each room                  -> a climate entity
         ├─ 1 temperature sensor
         ├─ heaters (0..N)
         └─ coolers (0..N)

Daily profile = ordered list of { time: "HH:MM", temperature: °C }
```

Every room follows its zone's target temperature but regulates its **own**
actuators based on its **own** sensor, with hysteresis. Heating and cooling
are never active at the same time.

## Home Assistant mapping

| Concept | Home Assistant |
|---|---|
| Room (sensor + actuators) | a `climate` entity |
| Zone | a device grouping the rooms, providing the schedule |
| Schedule / manual / holiday | `preset_mode`: `schedule` / `manual` / `away` |
| Heating / cooling | `hvac_mode`: `heat` / `cool` / `off` |
| Demand | `hvac_action`: `heating` / `cooling` / `idle` / `off` |

- **`schedule`** preset: target follows the weekly program (and overrides).
- **`manual`** preset: target is the value you set (setting a temperature
  switches to this preset automatically).
- **`away`** preset: target is the room's `away_temperature`.

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
   - **Zones & weekly schedule** — assign a profile to each weekday and add
     date-range overrides
   - **Rooms** — pick the temperature sensor and the heating/cooling actuators
3. Choose **Save & close**. Changes are applied immediately (the entry
   reloads).

Order matters: create at least one **profile** before adding a **zone**, and a
**zone** before adding **rooms**.

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

  zones:
    home:
      name: Home
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
      rooms:
        living_room:
          name: Living Room
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
| `schedule` | zone | yes | Profile per weekday (`mon`..`sun`) |
| `overrides` | zone | no | `{ start, end, profile }`, dates inclusive |
| `rooms` | zone | yes | Rooms in the zone |
| `sensor` | room | yes | Temperature sensor entity |
| `heaters` | room | no `[]` | Actuators used for heating |
| `coolers` | room | no `[]` | Actuators used for cooling |
| `hysteresis` | room | no | Overrides the global hysteresis |
| `away_temperature` | room | no (16) | Target for the `away` preset |
| `min_temperature` / `max_temperature` | room | no | UI setpoint limits |

Notes:

- The first slot of every profile must start at `00:00`.
- `heaters` enables the `heat` mode; `coolers` enables the `cool` mode.
- In `cool` mode the profile temperature is the cooling setpoint (the
  hysteresis logic is inverted automatically).

## Entities

For each room you get a `climate` entity named `<Zone> <Room>` (e.g.
`climate.home_living_room`) with extra attributes:

- `hysteresis`, `active_profile`, `scheduled_temperature`, `heaters`, `coolers`

The rooms of a zone are grouped under a single device named after the zone.

## Localization

The UI is available in English and Italian (`translations/en.json`,
`translations/it.json`). Contributions for other languages are welcome.

## License

MIT — see [`LICENSE`](LICENSE).
