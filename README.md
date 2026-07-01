# Cronotermostato settimanale per Home Assistant

Package nativo (no custom component) per un cronotermostato multi-zona con:

- **Profili giornalieri riutilizzabili** (fasce orarie → temperatura)
- **Programmazione settimanale** (un profilo per ogni giorno, per ogni zona)
- **Override a periodo** (ferie/festività/assenza) che sostituiscono il profilo
- **Zone → stanze → 1 sensore + N attuatori** con controllo a isteresi
- **Riscaldamento o raffrescamento** selezionabile per zona
- **Isteresi configurabile** per zona
- **Modalità runtime** per zona: `auto` / `manuale` / `vacanza` / `off`

## Modello

```
Zona (es. Casa, Ufficio)
 ├─ programma settimanale  -> assegna un PROFILO a ogni giorno (Lun..Dom)
 ├─ override di periodo     -> sostituisce il profilo in un intervallo di date
 └─ Stanze
     ├─ 1 sensore di temperatura
     └─ 1..N attuatori (relè / valvole)

Profilo giornaliero = lista di fasce { "start": "HH:MM", "temp": °C }
```

Tutte le stanze di una zona seguono lo **stesso target** (calcolato dal
profilo attivo della zona), ma ognuna regola **i propri attuatori** in base
al **proprio sensore**.

## Installazione

1. Copia i file nella tua cartella di configurazione HA:
   - `config/custom_templates/cronotermostato.jinja` → `<config>/custom_templates/`
   - `config/packages/cronotermostato.yaml` → `<config>/packages/`
2. In `configuration.yaml` abilita i package (se non già fatto):
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
3. Riavvia Home Assistant (la prima volta serve per i custom templates).

## Configurare i profili, la settimana e gli override

Tutto in **`custom_templates/cronotermostato.jinja`**, blocco `config()`:

- `profiles`: definisci i profili. La prima fascia deve essere `00:00`;
  ogni fascia vale fino all'inizio della successiva.
- `zones[...].weekly`: assegna un profilo a ogni giorno (`0`=Lun … `6`=Dom).
- `zones[...].overrides`: periodi `{"start","end","profile"}` (date incluse)
  che sostituiscono il profilo settimanale.

Dopo ogni modifica al `.jinja`:
**Strumenti sviluppatori → YAML → "Ricarica Custom Jinja Templates"**
(oppure riavvia). Le modifiche al package YAML: **Ricarica template / automazioni**.

### Esempio "Casa" (già incluso, Lun–Ven)

| Orario | Temp |
|---|---|
| 00:00–06:30 | 18 |
| 06:30–08:30 | 21 |
| 08:30–12:00 | 18 |
| 12:00–16:00 | 21 |
| 16:00–22:00 | 20 |
| 22:00–24:00 | 18 |

### Esempio "Ufficio" (già incluso, Lun–Ven)

06:00–17:30 → 22 °C, fuori orario → 16 °C, weekend → profilo `assente` (16 °C).

## Aggiungere una ZONA

1. In `cronotermostato.jinja` aggiungi una voce in `zones` (con `weekly` e `overrides`).
2. In `cronotermostato.yaml` duplica, cambiando il suffisso zona:
   - gli `input_number` `crono_<zona>_manuale/vacanza/antigelo`
   - l'`input_select` `crono_<zona>_mode`
   - i 3 sensori template `Crono <Zona> profilo/target programma/target effettivo`

## Aggiungere una STANZA

Duplica un blocco `automation:` (es. "Crono Casa / Soggiorno") e cambia solo:

- `id` / `alias`
- `room_sensor` → il sensore della stanza
- `actuators` → uno o più attuatori della stanza
- `target_sensor` → `sensor.crono_<zona>_target_effettivo`

## Entità create (per zona, es. `casa`)

| Entità | Descrizione |
|---|---|
| `sensor.crono_casa_profilo_attivo` | nome profilo attivo ora |
| `sensor.crono_casa_target_programma` | target da programma |
| `sensor.crono_casa_target_effettivo` | target reale (considera la modalità) |
| `input_select.crono_casa_mode` | auto / manuale / vacanza / off |
| `input_number.crono_casa_manuale` | setpoint modalità manuale |
| `input_number.crono_casa_vacanza` | setpoint modalità vacanza |
| `input_number.crono_casa_antigelo` | setpoint modalità off (antigelo) |
| `input_number.crono_casa_isteresi` | isteresi della zona (°C) |
| `input_select.crono_casa_hvac` | riscaldamento / raffrescamento |

Globale: `input_boolean.cronotermostato_master` (on/off generale).

## Riscaldamento e raffrescamento

Ogni zona ha `input_select.crono_<zona>_hvac` con `riscaldamento` o
`raffrescamento`. La temperatura del profilo è il **setpoint** in entrambi i
casi; cambia solo il verso del controllo:

| Modalità | Attuatore ON | Attuatore OFF |
|---|---|---|
| riscaldamento | `temp < target − isteresi` | `temp > target + isteresi` |
| raffrescamento | `temp > target + isteresi` | `temp < target − isteresi` |

In estate crea profili con i setpoint di raffreddamento desiderati (o riusa
gli stessi) e assegnali nella settimana. In `raffrescamento`, la modalità
`off` spegne del tutto gli attuatori; in `riscaldamento`, `off` usa il
setpoint **antigelo** per la protezione dal gelo.

## Note / limiti

- Gli attuatori vengono ri-comandati almeno ogni 2 minuti (`time_pattern`),
  oltre che ad ogni variazione di sensore/target: robusto ai riavvii.
- L'isteresi è simmetrica e per zona: `input_number.crono_<zona>_isteresi`.
- Sostituisci gli `entity_id` di esempio (`sensor.temperatura_*`,
  `switch.rele_*`) con quelli reali del tuo impianto.

## Pubblicazione / installazione da parte di altri utenti

Il progetto è un **package YAML** (non un'integrazione HACS): si installa
copiando i file. Per distribuirlo:

1. Pubblica il repo su GitHub.
2. Gli utenti scaricano lo ZIP (o `git clone`) e copiano:
   - `config/custom_templates/cronotermostato.jinja` → `<config>/custom_templates/`
   - `config/packages/cronotermostato.yaml` → `<config>/packages/`
3. Abilitano i package in `configuration.yaml` (vedi sopra) e riavviano.

Licenza: MIT (vedi `LICENSE`).
