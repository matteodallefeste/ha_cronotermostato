# Weekly Thermostat

[English](README.md) · **Italiano**

Un cronotermostato settimanale multi-piano programmabile per
[Home Assistant](https://www.home-assistant.io/), installabile tramite
[HACS](https://hacs.xyz/).

- **Profili giornalieri riutilizzabili** — fasce orarie → temperatura, definite
  una volta sola
- **Programma settimanale** — assegna un profilo a ogni giorno della settimana,
  per ogni piano
- **Override per periodo** — ferie / assenze sostituiscono il programma
  settimanale
- **Piani → aree** — mappati sui piani e sulle aree di Home Assistant
- **Riscaldamento e/o raffrescamento** per area, con attuatori separati
- **Entità `climate` native** con `hvac_action`, preset e isteresi

## Modello

```
Piano (es. Piano Terra, Ufficio)   -> gruppo con programma settimanale
 ├─ (opzionale) piano HA collegato
 ├─ programma settimanale           -> un profilo per giorno (lun..dom)
 ├─ override per periodo            -> sostituiscono il profilo in un intervallo
 └─ Aree
     └─ ogni area                   -> un'entità climate, posta nell'area HA
         ├─ 1 sensore di temperatura
         ├─ elementi riscaldanti (0..N)
         └─ elementi raffrescanti (0..N)

Profilo giornaliero = elenco ordinato di { time: "HH:MM", temperature: °C }
```

Ogni area segue la temperatura target del proprio piano ma regola i **propri**
attuatori in base al **proprio** sensore, con isteresi. Riscaldamento e
raffrescamento non sono mai attivi contemporaneamente.

## Corrispondenza con Home Assistant

La terminologia rispecchia volutamente quella di Home Assistant:

| Concetto | Home Assistant |
|---|---|
| Area (sensore + attuatori) | un'**area** di Home Assistant → un'entità `climate` |
| Piano (gruppo del programma settimanale) | un **floor** di Home Assistant (collegamento opzionale) |
| Programma / manuale / ferie | `preset_mode`: `schedule` / `manual` / `away` |
| Riscaldamento / raffrescamento | `hvac_mode`: `heat` / `cool` / `off` |
| Richiesta | `hvac_action`: `heating` / `cooling` / `idle` / `off` |

> Nota: le "zone" di Home Assistant sono zone di presenza GPS — un concetto
> diverso — quindi questa integrazione usa i **floor** (piani) per raggruppare
> il programma.

- Preset **`schedule`**: il target segue il programma settimanale (e gli
  override).
- Preset **`manual`**: il target è il valore che imposti (impostare una
  temperatura passa automaticamente a questo preset).
- Preset **`away`**: il target è la `away_temperature` dell'area.

## Installazione

### HACS (consigliato)

1. HACS → Integrazioni → ⋮ → *Repository personalizzati*.
2. Aggiungi `https://github.com/matteodallefeste/ha_cronotermostato` come
   **Integrazione**.
3. Installa **Weekly Thermostat** e riavvia Home Assistant.

### Manuale

Copia `custom_components/weekly_thermostat/` nella cartella
`config/custom_components/` di Home Assistant e riavvia.

## Configurazione

### Dall'interfaccia (consigliato)

1. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Weekly
   Thermostat.**
2. Apri il pulsante **Configura** dell'integrazione per gestire tutto da un
   menu:
   - **Rilevamento automatico aree** — analizza le aree di Home Assistant alla
     ricerca di un sensore di temperatura e propone una struttura pronta (un
     profilo predefinito più piani e aree raggruppati per floor HA); gli
     attuatori restano da confermare
   - **Impostazioni globali** — isteresi predefinita e attivazione del pannello
     laterale
   - **Profili giornalieri** — aggiungi/modifica/rimuovi profili (una fascia
     `HH:MM temperatura` per riga)
   - **Piani e programma settimanale** — assegna un profilo a ogni giorno della
     settimana, collega facoltativamente un floor di Home Assistant e aggiungi
     override per periodo
   - **Aree** — scegli un'area di Home Assistant; il suo sensore di temperatura
     e i suoi interruttori vengono suggeriti automaticamente, poi conferma gli
     attuatori di riscaldamento/raffrescamento
3. Scegli **Salva e chiudi**. Le modifiche vengono applicate subito (la voce si
   ricarica).

L'ordine conta: crea almeno un **profilo** prima di aggiungere un **piano**, e
un **piano** prima di aggiungere le **aree**. Ogni area viene collocata
automaticamente nella sua area di Home Assistant.

### Tramite YAML (opzionale)

Puoi anche inizializzare la configurazione da YAML — viene importata
nell'integrazione all'avvio (vedi
[`examples/configuration.yaml`](examples/configuration.yaml) per un esempio
completo). Aggiungi un blocco `weekly_thermostat:` al tuo
`configuration.yaml`:

```yaml
weekly_thermostat:
  hysteresis: 0.3            # default globale (°C), opzionale

  profiles:
    home_weekday:
      - { time: "00:00", temperature: 18 }
      - { time: "06:30", temperature: 21 }
      - { time: "08:30", temperature: 18 }
      - { time: "22:00", temperature: 18 }

  floors:
    ground_floor:
      name: Piano Terra
      # floor: ground_floor      # id opzionale del floor HA collegato
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
          name: Soggiorno
          area: living_room      # id opzionale dell'area HA collegata
          sensor: sensor.living_room_temperature
          heaters:
            - switch.living_room_valve
```

### Opzioni

| Chiave | Livello | Obbligatoria | Descrizione |
|---|---|---|---|
| `hysteresis` | root | no (0.3) | Isteresi predefinita in °C |
| `profiles` | root | sì | Profili giornalieri con nome (elenco di fasce) |
| `time` / `temperature` | fascia | sì | Inizio fascia (`HH:MM`) e setpoint |
| `floor` | piano | no | Id del floor di Home Assistant collegato |
| `schedule` | piano | sì | Profilo per giorno della settimana (`mon`..`sun`) |
| `overrides` | piano | no | `{ start, end, profile }`, date incluse |
| `areas` | piano | sì | Aree del piano |
| `area` | area | no | Id dell'area HA collegata (posizionamento entità) |
| `sensor` | area | sì | Entità sensore di temperatura |
| `heaters` | area | no `[]` | Attuatori usati per il riscaldamento |
| `coolers` | area | no `[]` | Attuatori usati per il raffrescamento |
| `hysteresis` | area | no | Sovrascrive l'isteresi globale (usata per il riscaldamento) |
| `hysteresis_cool` | area | no | Isteresi separata per il raffrescamento (ripiega su `hysteresis`) |
| `away_temperature` | area | no (16) | Target per il preset `away` |
| `min_temperature` / `max_temperature` | area | no | Limiti del setpoint nell'UI |

Note:

- La prima fascia di ogni profilo deve iniziare a `00:00`.
- `heaters` abilita la modalità `heat`; `coolers` abilita la modalità `cool`.
- In modalità `cool` la temperatura del profilo è il setpoint di raffrescamento
  (la logica dell'isteresi viene invertita automaticamente). Imposta
  `hysteresis_cool` quando il sistema di raffrescamento richiede una banda morta
  diversa da quella del riscaldamento; se omessa, riusa `hysteresis`.

## Entità

Per ogni area ottieni un'entità `climate` chiamata `<Piano> <Area>` (es.
`climate.ground_floor_living_room`), collocata nella sua area di Home
Assistant, con attributi aggiuntivi:

- `hysteresis`, `hysteresis_cool`, `active_profile`, `scheduled_temperature`,
  `heaters`, `coolers`

## Pannello laterale

Un pannello **Weekly Thermostat** opzionale viene aggiunto alla barra laterale
(attivo di default; si disattiva in **Impostazioni globali**). Completa le card
`climate` native mostrando ciò che loro non possono: l'intero programma
settimanale a colpo d'occhio — i profili giornalieri come barre colorate su 24h,
il profilo assegnato a ogni giorno della settimana per piano (oggi evidenziato)
e una tessera live per ogni area.

## Localizzazione

L'interfaccia è disponibile in inglese e italiano (`translations/en.json`,
`translations/it.json`). Contributi per altre lingue sono benvenuti.

## Licenza

Concesso in licenza sotto la **GNU General Public License v3.0** — vedi [`LICENSE`](LICENSE).

In breve:

- **Libero** di usare, studiare, condividere e modificare.
- Ogni copia distribuita o opera derivata deve restare **open source sotto la
  GPL-3.0** e includere il sorgente completo corrispondente.
- Fornito **senza alcuna garanzia**.
