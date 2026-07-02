/**
 * Weekly Thermostat sidebar panel.
 *
 * A dependency-free custom element (no build step). It combines the static
 * schedule structure fetched over the websocket API ("weekly_thermostat/config")
 * with the live climate entity states, and renders, per floor:
 *   - the daily profiles as 24h colour bars,
 *   - the profile assigned to each weekday (today highlighted),
 *   - a tile per area with its live temperature, target, mode and action.
 */

const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

const TR = {
  en: {
    title: "Weekly Thermostat",
    profiles: "Daily profiles",
    schedule: "Weekly schedule",
    today: "today",
    target: "target",
    active: "active",
    none: "—",
    noFloors:
      "No floors configured yet. Add profiles, floors and areas from the integration options.",
    loading: "Loading…",
    error: "Could not load the configuration.",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    action: { heating: "Heating", cooling: "Cooling", idle: "Idle", off: "Off" },
    preset: { schedule: "Schedule", manual: "Manual", away: "Away" },
  },
  it: {
    title: "Termostato settimanale",
    profiles: "Profili giornalieri",
    schedule: "Programma settimanale",
    today: "oggi",
    target: "obiettivo",
    active: "attivo",
    none: "—",
    noFloors:
      "Nessun floor configurato. Aggiungi profili, floor e aree dalle opzioni dell'integrazione.",
    loading: "Caricamento…",
    error: "Impossibile caricare la configurazione.",
    days: ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
    action: { heating: "Riscalda", cooling: "Raffresca", idle: "In attesa", off: "Spento" },
    preset: { schedule: "Programmato", manual: "Manuale", away: "Assente" },
  },
};

const ACTION_COLOR = {
  heating: "#e8590c",
  cooling: "#1c7ed6",
  idle: "var(--secondary-text-color)",
  off: "var(--disabled-text-color, #9e9e9e)",
};

class WeeklyThermostatPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._loading = false;
    this._error = null;
    this._signature = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config === null && !this._loading && !this._error) {
      this._loadConfig();
      return;
    }
    if (this._config) {
      const sig = this._liveSignature();
      if (sig !== this._signature) {
        this._signature = sig;
        this._render();
      }
    }
  }

  get hass() {
    return this._hass;
  }

  async _loadConfig() {
    this._loading = true;
    this._renderStatus(this._t().loading);
    try {
      this._config = await this._hass.connection.sendMessagePromise({
        type: "weekly_thermostat/config",
      });
    } catch (err) {
      this._error = err;
      this._renderStatus(this._t().error);
      return;
    } finally {
      this._loading = false;
    }
    this._signature = this._liveSignature();
    this._render();
  }

  // --- Helpers ----------------------------------------------------------

  _t() {
    const lang = this._hass && this._hass.language ? this._hass.language : "en";
    return TR[lang.split("-")[0]] || TR.en;
  }

  _todayIndex() {
    // JS getDay(): 0 = Sunday .. 6 = Saturday; WEEKDAYS starts on Monday.
    const js = new Date().getDay();
    return (js + 6) % 7;
  }

  _timeToMinutes(value) {
    const [h, m] = String(value).split(":");
    return parseInt(h, 10) * 60 + parseInt(m, 10);
  }

  _tempColor(temp) {
    const t = Math.max(14, Math.min(26, Number(temp)));
    const ratio = (t - 14) / 12;
    const hue = 210 - ratio * 210;
    return `hsl(${hue}, 65%, 52%)`;
  }

  _areaState(entityId) {
    if (!entityId || !this._hass) return null;
    return this._hass.states[entityId] || null;
  }

  _floorActiveProfile(floor) {
    // Prefer the server-computed value from any of the floor's entities.
    for (const area of floor.areas) {
      const st = this._areaState(area.entity_id);
      if (st && st.attributes && st.attributes.active_profile) {
        return st.attributes.active_profile;
      }
    }
    return (floor.schedule || {})[WEEKDAYS[this._todayIndex()]] || null;
  }

  _liveSignature() {
    if (!this._config || !this._hass) return "";
    const parts = [];
    for (const floor of this._config.floors) {
      for (const area of floor.areas) {
        const st = this._areaState(area.entity_id);
        if (!st) {
          parts.push(`${area.entity_id}:none`);
          continue;
        }
        const a = st.attributes || {};
        parts.push(
          [
            area.entity_id,
            st.state,
            a.current_temperature,
            a.temperature,
            a.hvac_action,
            a.preset_mode,
            a.active_profile,
          ].join("|")
        );
      }
    }
    return parts.join("~");
  }

  // --- Rendering --------------------------------------------------------

  _renderStatus(text) {
    this.shadowRoot.innerHTML = `${this._styles()}<div class="wrap"><div class="status">${esc(
      text
    )}</div></div>`;
  }

  _render() {
    if (!this._config) return;
    const t = this._t();
    const floors = this._config.floors || [];
    const profiles = this._config.profiles || {};

    let body;
    if (!floors.length) {
      body = `<div class="status">${esc(t.noFloors)}</div>`;
    } else {
      body = `${this._renderProfiles(profiles, t)}${floors
        .map((f) => this._renderFloor(f, profiles, t))
        .join("")}`;
    }

    this.shadowRoot.innerHTML = `${this._styles()}
      <div class="wrap">
        <div class="header">
          <ha-icon icon="mdi:calendar-clock"></ha-icon>
          <h1>${esc(t.title)}</h1>
        </div>
        ${body}
      </div>`;
  }

  _renderProfiles(profiles, t) {
    const keys = Object.keys(profiles);
    if (!keys.length) return "";
    const rows = keys
      .map((name) => {
        const slots = [...profiles[name]].sort(
          (a, b) => this._timeToMinutes(a.time) - this._timeToMinutes(b.time)
        );
        const segments = slots
          .map((slot, i) => {
            const start = this._timeToMinutes(slot.time);
            const end = i + 1 < slots.length ? this._timeToMinutes(slots[i + 1].time) : 1440;
            const width = ((end - start) / 1440) * 100;
            return `<div class="seg" style="width:${width}%;background:${this._tempColor(
              slot.temperature
            )}" title="${esc(slot.time)} · ${esc(slot.temperature)}°"><span>${esc(
              slot.temperature
            )}°</span></div>`;
          })
          .join("");
        return `<div class="profile">
            <div class="profile-name">${esc(name)}</div>
            <div class="bar">${segments}</div>
          </div>`;
      })
      .join("");
    return `<div class="card">
        <div class="card-title">${esc(t.profiles)}</div>
        ${rows}
      </div>`;
  }

  _renderFloor(floor, profiles, t) {
    const todayIdx = this._todayIndex();
    const active = this._floorActiveProfile(floor);
    const schedule = floor.schedule || {};

    const days = WEEKDAYS.map((day, i) => {
      const prof = schedule[day] || t.none;
      const isToday = i === todayIdx;
      return `<div class="day${isToday ? " today" : ""}">
          <div class="day-name">${esc(t.days[i])}</div>
          <div class="day-profile">${esc(prof)}</div>
        </div>`;
    }).join("");

    const areas = floor.areas.length
      ? floor.areas.map((area) => this._renderArea(area, t)).join("")
      : "";

    return `<div class="card">
        <div class="floor-head">
          <div class="card-title">${esc(floor.name)}</div>
          ${
            active
              ? `<div class="active-chip">${esc(t.active)}: ${esc(active)}</div>`
              : ""
          }
        </div>
        <div class="days">${days}</div>
        <div class="areas">${areas}</div>
      </div>`;
  }

  _renderArea(area, t) {
    const st = this._areaState(area.entity_id);
    if (!st) {
      return `<div class="area">
          <div class="area-name">${esc(area.name)}</div>
          <div class="area-cur">${t.none}</div>
        </div>`;
    }
    const a = st.attributes || {};
    const action = a.hvac_action || (st.state === "off" ? "off" : "idle");
    const color = ACTION_COLOR[action] || ACTION_COLOR.idle;
    const cur =
      a.current_temperature != null ? `${a.current_temperature}°` : t.none;
    const target = a.temperature != null ? `${a.temperature}°` : t.none;
    const preset = t.preset[a.preset_mode] || a.preset_mode || "";
    const actionLabel = t.action[action] || action;
    // The relevant dead-band depends on the current mode.
    const hyst = st.state === "cool" ? a.hysteresis_cool : a.hysteresis;
    const hystStr = hyst != null ? ` · ±${hyst}°` : "";

    return `<div class="area">
        <div class="area-top">
          <div class="area-name">${esc(area.name)}</div>
          <div class="dot" style="background:${color}" title="${esc(actionLabel)}${esc(
      hystStr
    )}"></div>
        </div>
        <div class="area-cur">${esc(cur)}</div>
        <div class="area-sub">
          <span>${esc(t.target)}: <b>${esc(target)}</b></span>
          <span>${esc(preset)}</span>
        </div>
        <div class="area-action" style="color:${color}">${esc(actionLabel)}</div>
      </div>`;
  }

  _styles() {
    return `<style>
      :host { display: block; }
      .wrap {
        padding: 16px;
        max-width: 1100px;
        margin: 0 auto;
        color: var(--primary-text-color);
        font-family: var(--paper-font-body1_-_font-family, sans-serif);
      }
      .header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
      .header h1 { font-size: 22px; font-weight: 500; margin: 0; }
      .header ha-icon { color: var(--primary-color); }
      .status { padding: 32px; text-align: center; color: var(--secondary-text-color); }
      .card {
        background: var(--card-background-color, #fff);
        border-radius: 12px;
        box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.1));
        padding: 16px;
        margin-bottom: 16px;
      }
      .card-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
      .floor-head { display: flex; align-items: center; justify-content: space-between; }
      .active-chip {
        font-size: 12px; padding: 3px 10px; border-radius: 12px;
        background: var(--primary-color); color: var(--text-primary-color, #fff);
      }
      .profile { margin-bottom: 10px; }
      .profile-name { font-size: 13px; color: var(--secondary-text-color); margin-bottom: 4px; }
      .bar { display: flex; height: 26px; border-radius: 6px; overflow: hidden; }
      .seg {
        display: flex; align-items: center; justify-content: center;
        min-width: 0; overflow: hidden;
      }
      .seg span { color: #fff; font-size: 11px; text-shadow: 0 1px 1px rgba(0,0,0,.4); white-space: nowrap; }
      .days {
        display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; margin: 6px 0 16px;
      }
      .day {
        text-align: center; padding: 8px 4px; border-radius: 8px;
        background: var(--secondary-background-color, #f1f1f1);
      }
      .day.today { outline: 2px solid var(--primary-color); }
      .day-name { font-size: 12px; color: var(--secondary-text-color); }
      .day-profile { font-size: 12px; font-weight: 600; margin-top: 2px; word-break: break-word; }
      .areas {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px;
      }
      .area {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 10px; padding: 10px 12px;
      }
      .area-top { display: flex; align-items: center; justify-content: space-between; }
      .area-name { font-weight: 600; font-size: 14px; }
      .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
      .area-cur { font-size: 26px; font-weight: 500; margin: 4px 0; }
      .area-sub {
        display: flex; justify-content: space-between; gap: 6px;
        font-size: 12px; color: var(--secondary-text-color);
      }
      .area-action { font-size: 12px; font-weight: 600; margin-top: 6px; }
    </style>`;
  }
}

function esc(value) {
  if (value == null) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

customElements.define("weekly-thermostat-panel", WeeklyThermostatPanel);
