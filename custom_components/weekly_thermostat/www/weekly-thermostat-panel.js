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
    overrides: "Overrides (holidays / away)",
    tapHint: "Click to set manual or away",
    edit: "Edit",
    delete: "Delete",
    cancel: "Cancel",
    save: "Save",
    addProfile: "Add profile",
    addFloor: "Add floor",
    addArea: "Add area",
    addPeriod: "Add holiday period",
    settingsTitle: "Global settings",
    fHysteresis: "Default hysteresis (°C)",
    fShowPanel: "Show this panel in the sidebar",
    profileTitle: "Profile",
    profileNew: "New profile",
    floorTitle: "Floor",
    floorNew: "New floor",
    areaTitle: "Area",
    areaNew: "New area",
    fName: "Name",
    fSlots: "Time slots",
    slotsHint:
      'One slot per line: "HH:MM temperature" (e.g. "06:30 21"). The first slot must start at 00:00.',
    fHaFloor: "Home Assistant floor (optional)",
    fOverrides: "Holiday / away periods",
    fHaArea: "Home Assistant area (optional)",
    fSensor: "Temperature sensor",
    selectSensor: "— select —",
    fHeaters: "Heating actuators",
    fCoolers: "Cooling actuators",
    fHystHeat: "Heating hysteresis (°C)",
    fHystCool: "Cooling hysteresis (°C)",
    fAway: "Away temperature (°C)",
    fMin: "Min temperature (°C)",
    fMax: "Max temperature (°C)",
    errName: "Name is required.",
    errSlots: "Enter at least one time slot.",
    errSensor: "Select a temperature sensor.",
    today: "today",
    target: "target",
    active: "active",
    none: "—",
    noFloors: "No areas configured yet.",
    noFloorsHint:
      "Let Weekly Thermostat scan your Home Assistant areas for temperature sensors, or open the configuration to add them manually.",
    autodetect: "Auto-detect areas",
    openConfig: "Open configuration",
    detecting: "Detecting…",
    createdAreas: "Created {n} area(s).",
    createdNone: "No new areas with a temperature sensor were found.",
    detectError: "Auto-detection failed.",
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
    overrides: "Override (ferie / assenza)",
    tapHint: "Clicca per impostare manuale o assenza",
    edit: "Modifica",
    delete: "Elimina",
    cancel: "Annulla",
    save: "Salva",
    addProfile: "Aggiungi profilo",
    addFloor: "Aggiungi floor",
    addArea: "Aggiungi area",
    addPeriod: "Aggiungi periodo ferie",
    settingsTitle: "Impostazioni generali",
    fHysteresis: "Isteresi predefinita (°C)",
    fShowPanel: "Mostra questo pannello nel menu laterale",
    profileTitle: "Profilo",
    profileNew: "Nuovo profilo",
    floorTitle: "Floor",
    floorNew: "Nuovo floor",
    areaTitle: "Area",
    areaNew: "Nuova area",
    fName: "Nome",
    fSlots: "Fasce orarie",
    slotsHint:
      'Una fascia per riga: "HH:MM temperatura" (es. "06:30 21"). La prima fascia deve iniziare alle 00:00.',
    fHaFloor: "Floor di Home Assistant (opzionale)",
    fOverrides: "Periodi ferie / assenza",
    fHaArea: "Area di Home Assistant (opzionale)",
    fSensor: "Sensore di temperatura",
    selectSensor: "— seleziona —",
    fHeaters: "Attuatori riscaldamento",
    fCoolers: "Attuatori raffrescamento",
    fHystHeat: "Isteresi riscaldamento (°C)",
    fHystCool: "Isteresi raffrescamento (°C)",
    fAway: "Temperatura assenza (°C)",
    fMin: "Temperatura minima (°C)",
    fMax: "Temperatura massima (°C)",
    errName: "Il nome è obbligatorio.",
    errSlots: "Inserisci almeno una fascia oraria.",
    errSensor: "Seleziona un sensore di temperatura.",
    today: "oggi",
    target: "obiettivo",
    active: "attivo",
    none: "—",
    noFloors: "Nessuna area configurata.",
    noFloorsHint:
      "Lascia che Weekly Thermostat cerchi i sensori di temperatura nelle tue aree di Home Assistant, oppure apri la configurazione per aggiungerle manualmente.",
    autodetect: "Rileva automaticamente",
    openConfig: "Apri configurazione",
    detecting: "Rilevamento…",
    createdAreas: "Create {n} aree.",
    createdNone: "Nessuna nuova area con un sensore di temperatura trovata.",
    detectError: "Rilevamento automatico non riuscito.",
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
    this._notice = null;
    this._busy = false;
    this._modal = null;
    this._lists = null;
    // Delegated click handling survives innerHTML re-renders.
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
  }

  set hass(hass) {
    this._hass = hass;
    // Don't re-render while a form is open, or its inputs would be wiped.
    if (this._modal) return;
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

  _onClick(e) {
    const el = e.target.closest("[data-action]");
    if (el) {
      const a = el.getAttribute("data-action");
      const key = el.getAttribute("data-key");
      const floor = el.getAttribute("data-floor");
      const handlers = {
        autodetect: () => this._runAutodetect(),
        config: () => this._openConfig(),
        settings: () => this._openSettings(),
        "add-profile": () => this._openProfile(null),
        "edit-profile": () => this._openProfile(key),
        "add-floor": () => this._openFloor(null),
        "edit-floor": () => this._openFloor(key),
        "add-area": () => this._openArea(floor, null),
        "edit-area": () => this._openArea(floor, key),
        "modal-cancel": () => this._closeModal(),
        "modal-save": () => this._submitModal(),
        "modal-delete": () => this._deleteModal(),
        "ov-add": () => this._addOverrideRow(),
        "ov-del": () => this._removeOverrideRow(el),
      };
      if (handlers[a]) {
        e.stopPropagation();
        handlers[a]();
      }
      return;
    }
    const areaEl = e.target.closest(".area[data-entity]");
    if (areaEl) this._openEntity(areaEl.getAttribute("data-entity"));
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

  // --- Actions ----------------------------------------------------------

  async _runAutodetect() {
    if (this._busy) return;
    this._busy = true;
    this._notice = this._t().detecting;
    this._render();
    try {
      const res = await this._hass.connection.sendMessagePromise({
        type: "weekly_thermostat/autodetect",
      });
      const created = res && res.created_areas ? res.created_areas : 0;
      this._notice = created
        ? this._t().createdAreas.replace("{n}", created)
        : this._t().createdNone;
      // Options were updated server-side; reload the schedule structure.
      await this._reloadConfig();
      // The entry reloads asynchronously and creates the climate entities;
      // fetch once more shortly after so the tiles bind to their entity ids.
      if (created) {
        setTimeout(() => this._reloadConfig(), 2000);
      }
    } catch (err) {
      this._notice = this._t().detectError;
    } finally {
      this._busy = false;
      this._render();
    }
  }

  async _reloadConfig() {
    this._config = await this._hass.connection.sendMessagePromise({
      type: "weekly_thermostat/config",
    });
    this._signature = this._liveSignature();
    this._render();
  }

  _openConfig() {
    const path = "/config/integrations/integration/weekly_thermostat";
    history.pushState(null, "", path);
    this.dispatchEvent(
      new CustomEvent("location-changed", { bubbles: true, composed: true })
    );
  }

  _openEntity(entityId) {
    if (!entityId) return;
    // Opens Home Assistant's native climate dialog (manual / away / setpoint).
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      })
    );
  }

  // --- Editor -----------------------------------------------------------

  async _ensureLists() {
    if (!this._lists) {
      this._lists = await this._hass.connection.sendMessagePromise({
        type: "weekly_thermostat/lists",
      });
    }
    return this._lists;
  }

  _profileKeys() {
    return Object.keys(this._config.profiles || {});
  }

  _findFloor(key) {
    return (this._config.floors || []).find((f) => f.key === key) || null;
  }

  _openSettings() {
    this._modal = { type: "settings" };
    this._modalError = null;
    this._render();
  }

  _openProfile(key) {
    this._modal = { type: "profile", key };
    this._modalError = null;
    this._render();
  }

  async _openFloor(key) {
    await this._ensureLists();
    this._modal = { type: "floor", key };
    this._modalError = null;
    this._render();
  }

  async _openArea(floorKey, key) {
    await this._ensureLists();
    this._modal = { type: "area", floorKey, key };
    this._modalError = null;
    this._render();
  }

  _closeModal() {
    this._modal = null;
    this._render();
  }

  _showModalError(text) {
    const el = this.shadowRoot.querySelector(".modal-error");
    if (el) {
      el.textContent = text;
      el.style.display = text ? "block" : "none";
    }
  }

  _fieldValue(name) {
    const el = this.shadowRoot.querySelector(`[data-field="${name}"]`);
    if (!el) return undefined;
    if (el.type === "checkbox") return el.checked;
    if (el.multiple) return Array.from(el.selectedOptions).map((o) => o.value);
    return el.value;
  }

  _numOrNull(name) {
    const v = this._fieldValue(name);
    return v === "" || v == null ? null : Number(v);
  }

  _addOverrideRow() {
    const rows = this.shadowRoot.querySelector(".ov-rows");
    if (!rows) return;
    const div = document.createElement("div");
    div.className = "ov-row";
    div.innerHTML = this._overrideRowInner({});
    rows.appendChild(div);
  }

  _removeOverrideRow(el) {
    const row = el.closest(".ov-row");
    if (row) row.remove();
  }

  async _submitModal() {
    const m = this._modal;
    if (!m) return;
    let message;
    try {
      message = this._buildMessage(m);
    } catch (err) {
      this._showModalError(err.message);
      return;
    }
    const saveBtn = this.shadowRoot.querySelector('[data-action="modal-save"]');
    if (saveBtn) saveBtn.disabled = true;
    try {
      await this._hass.connection.sendMessagePromise(message);
      this._modal = null;
      await this._reloadConfig();
    } catch (err) {
      if (saveBtn) saveBtn.disabled = false;
      this._showModalError(err.message || err.code || "Error");
    }
  }

  _buildMessage(m) {
    const t = this._t();
    if (m.type === "settings") {
      return {
        type: "weekly_thermostat/settings/save",
        hysteresis: Number(this._fieldValue("hysteresis")),
        show_panel: !!this._fieldValue("show_panel"),
      };
    }
    if (m.type === "profile") {
      const slots = (this._fieldValue("slots_text") || "").trim();
      const name = m.key || (this._fieldValue("name") || "").trim();
      if (!name) throw new Error(t.errName);
      if (!slots) throw new Error(t.errSlots);
      const msg = {
        type: "weekly_thermostat/profile/save",
        name,
        slots_text: slots,
      };
      if (m.key) msg.key = m.key;
      return msg;
    }
    if (m.type === "floor") {
      const name = (this._fieldValue("name") || "").trim();
      if (!name) throw new Error(t.errName);
      const schedule = {};
      for (const d of WEEKDAYS) schedule[d] = this._fieldValue(`sched_${d}`);
      const rows = [...this.shadowRoot.querySelectorAll(".ov-row")];
      const overrides = rows
        .map((r) => ({
          start: r.querySelector('[data-ov="start"]').value,
          end: r.querySelector('[data-ov="end"]').value,
          profile: r.querySelector('[data-ov="profile"]').value,
        }))
        .filter((o) => o.start || o.end);
      const msg = {
        type: "weekly_thermostat/floor/save",
        name,
        ha_floor: this._fieldValue("ha_floor") || null,
        schedule,
        overrides,
      };
      if (m.key) msg.key = m.key;
      return msg;
    }
    if (m.type === "area") {
      const name = (this._fieldValue("name") || "").trim();
      const sensor = (this._fieldValue("sensor") || "").trim();
      if (!name) throw new Error(t.errName);
      if (!sensor) throw new Error(t.errSensor);
      const msg = {
        type: "weekly_thermostat/area/save",
        floor_key: m.floorKey,
        name,
        sensor,
        ha_area: this._fieldValue("ha_area") || null,
        heaters: this._fieldValue("heaters") || [],
        coolers: this._fieldValue("coolers") || [],
        hysteresis: this._numOrNull("hysteresis"),
        hysteresis_cool: this._numOrNull("hysteresis_cool"),
        away_temperature: this._numOrNull("away_temperature"),
        min_temperature: this._numOrNull("min_temperature"),
        max_temperature: this._numOrNull("max_temperature"),
      };
      if (m.key) msg.key = m.key;
      return msg;
    }
    throw new Error("Unknown editor");
  }

  async _deleteModal() {
    const m = this._modal;
    if (!m || !m.key) return;
    let message;
    if (m.type === "profile") {
      message = { type: "weekly_thermostat/profile/delete", key: m.key };
    } else if (m.type === "floor") {
      message = { type: "weekly_thermostat/floor/delete", key: m.key };
    } else if (m.type === "area") {
      message = {
        type: "weekly_thermostat/area/delete",
        floor_key: m.floorKey,
        key: m.key,
      };
    } else {
      return;
    }
    try {
      await this._hass.connection.sendMessagePromise(message);
      this._modal = null;
      await this._reloadConfig();
    } catch (err) {
      this._showModalError(err.message || err.code || "Error");
    }
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

  _todayStr() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
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

  _isAdmin() {
    return !!(this._hass && this._hass.user && this._hass.user.is_admin);
  }

  _render() {
    if (!this._config) return;
    const t = this._t();
    this._admin = this._isAdmin();
    const floors = this._config.floors || [];
    const profiles = this._config.profiles || {};

    const disabled = this._busy ? " disabled" : "";
    let body;
    let headerActions = "";
    if (!floors.length) {
      body = `<div class="empty">
          <ha-icon class="empty-icon" icon="mdi:home-thermometer-outline"></ha-icon>
          <h2>${esc(t.noFloors)}</h2>
          <p>${esc(t.noFloorsHint)}</p>
          <div class="actions">
            ${
              this._admin
                ? `<button class="btn primary" data-action="autodetect"${disabled}>
              <ha-icon icon="mdi:magnify-scan"></ha-icon>${esc(t.autodetect)}
            </button>`
                : ""
            }
            <button class="btn" data-action="config">
              <ha-icon icon="mdi:cog"></ha-icon>${esc(t.openConfig)}
            </button>
          </div>
        </div>`;
    } else {
      body = `${this._renderProfiles(profiles, t)}${floors
        .map((f) => this._renderFloor(f, profiles, t))
        .join("")}`;
      const adminActions = this._admin
        ? `<button class="btn small ghost" data-action="add-floor">＋ ${esc(
            t.addFloor
          )}</button>
          <button class="btn icon" data-action="autodetect"${disabled} title="${esc(
            t.autodetect
          )}"><ha-icon icon="mdi:magnify-scan"></ha-icon></button>
          <button class="btn icon" data-action="settings" title="${esc(
            t.settingsTitle
          )}"><ha-icon icon="mdi:tune"></ha-icon></button>`
        : "";
      headerActions = `<div class="header-actions">
          ${adminActions}
          <button class="btn icon" data-action="config" title="${esc(
            t.openConfig
          )}"><ha-icon icon="mdi:cog"></ha-icon></button>
        </div>`;
    }

    const notice = this._notice
      ? `<div class="notice">${esc(this._notice)}</div>`
      : "";

    this.shadowRoot.innerHTML = `${this._styles()}
      <div class="wrap">
        <div class="header">
          <ha-icon icon="mdi:calendar-clock"></ha-icon>
          <h1>${esc(t.title)}</h1>
          ${headerActions}
        </div>
        ${notice}
        ${body}
      </div>
      ${this._renderModal()}`;
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
        const editBtn = this._admin
          ? `<button class="mini" data-action="edit-profile" data-key="${esc(
              name
            )}" title="${esc(t.edit)}">✎</button>`
          : "";
        return `<div class="profile">
            <div class="profile-name">${esc(name)} ${editBtn}</div>
            <div class="bar">${segments}</div>
          </div>`;
      })
      .join("");
    const addBtn = this._admin
      ? `<button class="btn small ghost" data-action="add-profile">＋ ${esc(
          t.addProfile
        )}</button>`
      : "";
    return `<div class="card">
        <div class="card-title row">
          <span>${esc(t.profiles)}</span>
          ${addBtn}
        </div>
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
      ? floor.areas.map((area) => this._renderArea(area, floor.key, t)).join("")
      : "";

    const overrides = floor.overrides || [];
    const today = this._todayStr();
    const ovHtml = overrides.length
      ? `<div class="overrides">
          <div class="ov-title">${esc(t.overrides)}</div>
          ${overrides
            .map((o) => {
              const on = o.start <= today && today <= o.end;
              return `<div class="ov${on ? " active" : ""}">${esc(o.start)} → ${esc(
                o.end
              )} · <b>${esc(o.profile)}</b>${
                on ? ` <span class="ov-badge">${esc(t.active)}</span>` : ""
              }</div>`;
            })
            .join("")}
        </div>`
      : "";

    return `<div class="card">
        <div class="floor-head">
          <div class="card-title">${esc(floor.name)}</div>
          <div class="floor-actions">
            ${
              active
                ? `<div class="active-chip">${esc(t.active)}: ${esc(active)}</div>`
                : ""
            }
            ${
              this._admin
                ? `<button class="btn small ghost" data-action="add-area" data-floor="${esc(
                    floor.key
                  )}">＋ ${esc(t.addArea)}</button>
            <button class="mini" data-action="edit-floor" data-key="${esc(
              floor.key
            )}" title="${esc(t.edit)}">✎</button>`
                : ""
            }
          </div>
        </div>
        <div class="days">${days}</div>
        ${ovHtml}
        <div class="areas">${areas}</div>
      </div>`;
  }

  _renderArea(area, floorKey, t) {
    const st = this._areaState(area.entity_id);
    const open = area.entity_id
      ? ` class="area clickable" data-entity="${esc(area.entity_id)}" title="${esc(
          t.tapHint
        )}"`
      : ` class="area"`;
    const editBtn = this._admin
      ? `<button class="mini" data-action="edit-area" data-floor="${esc(
          floorKey
        )}" data-key="${esc(area.key)}" title="${esc(t.edit)}">✎</button>`
      : "";

    if (!st) {
      return `<div${open}>
          <div class="area-top">
            <div class="area-name">${esc(area.name)}</div>
            ${editBtn}
          </div>
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

    return `<div${open}>
        <div class="area-top">
          <div class="area-name">${esc(area.name)}</div>
          <div class="area-top-r">
            <div class="dot" style="background:${color}" title="${esc(actionLabel)}${esc(
      hystStr
    )}"></div>
            ${editBtn}
          </div>
        </div>
        <div class="area-cur">${esc(cur)}</div>
        <div class="area-sub">
          <span>${esc(t.target)}: <b>${esc(target)}</b></span>
          <span>${esc(preset)}</span>
        </div>
        <div class="area-action" style="color:${color}">${esc(actionLabel)}</div>
      </div>`;
  }

  // --- Modal / form rendering ------------------------------------------

  _renderModal() {
    const m = this._modal;
    if (!m) return "";
    const t = this._t();
    let title = "";
    let body = "";
    let canDelete = false;

    if (m.type === "settings") {
      title = t.settingsTitle;
      body =
        this._numField("hysteresis", t.fHysteresis, this._config.hysteresis, {
          min: 0.1,
          max: 3,
          step: 0.1,
        }) + this._checkField("show_panel", t.fShowPanel, this._config.show_panel);
    } else if (m.type === "profile") {
      canDelete = !!m.key;
      title = m.key ? `${t.profileTitle}: ${m.key}` : t.profileNew;
      const slotsText = m.key ? this._slotsText(this._config.profiles[m.key]) : "";
      body =
        (m.key ? "" : this._textField("name", t.fName, "")) +
        `<div class="hint">${esc(t.slotsHint)}</div>` +
        this._textAreaField("slots_text", t.fSlots, slotsText);
    } else if (m.type === "floor") {
      canDelete = !!m.key;
      const floor = m.key ? this._findFloor(m.key) || {} : {};
      title = m.key ? `${t.floorTitle}: ${floor.name}` : t.floorNew;
      body = this._floorForm(floor, t);
    } else if (m.type === "area") {
      canDelete = !!m.key;
      const floor = this._findFloor(m.floorKey) || {};
      const area = m.key ? (floor.areas || []).find((a) => a.key === m.key) || {} : {};
      title = m.key ? `${t.areaTitle}: ${area.name}` : t.areaNew;
      body = this._areaForm(area, t);
    }

    return `<div class="modal-overlay">
        <div class="modal-box">
          <div class="modal-head">${esc(title)}</div>
          <div class="modal-body">${body}</div>
          <div class="modal-error"></div>
          <div class="modal-foot">
            ${
              canDelete
                ? `<button class="btn danger" data-action="modal-delete">${esc(
                    t.delete
                  )}</button>`
                : ""
            }
            <span class="spacer"></span>
            <button class="btn" data-action="modal-cancel">${esc(t.cancel)}</button>
            <button class="btn primary" data-action="modal-save">${esc(t.save)}</button>
          </div>
        </div>
      </div>`;
  }

  _floorForm(floor, t) {
    const profiles = this._profileKeys().map((k) => ({ value: k, label: k }));
    const haFloors = (this._lists?.ha_floors || []).map((f) => ({
      value: f.floor_id,
      label: f.name,
    }));
    const schedule = floor.schedule || {};
    const fallback = profiles[0] ? profiles[0].value : "";
    const days = WEEKDAYS.map((d, i) =>
      this._selectField(`sched_${d}`, t.days[i], profiles, schedule[d] || fallback)
    ).join("");
    const haFloorField = haFloors.length
      ? this._selectField("ha_floor", t.fHaFloor, haFloors, floor.ha_floor || "", {
          emptyLabel: t.none,
        })
      : "";
    const ovRows = (floor.overrides || [])
      .map((o) => `<div class="ov-row">${this._overrideRowInner(o)}</div>`)
      .join("");
    return (
      this._textField("name", t.fName, floor.name || "") +
      haFloorField +
      `<div class="grid-days">${days}</div>` +
      `<div class="sec-title">${esc(t.fOverrides)}</div>` +
      `<div class="ov-rows">${ovRows}</div>` +
      `<button class="btn small ghost" data-action="ov-add">＋ ${esc(t.addPeriod)}</button>`
    );
  }

  _overrideRowInner(o) {
    const opts = this._profileKeys()
      .map((k) => `<option value="${esc(k)}"${k === o.profile ? " selected" : ""}>${esc(k)}</option>`)
      .join("");
    return `<input data-ov="start" type="date" value="${esc(o.start || "")}">
      <input data-ov="end" type="date" value="${esc(o.end || "")}">
      <select data-ov="profile">${opts}</select>
      <button class="mini danger" data-action="ov-del" title="✕">✕</button>`;
  }

  _areaForm(area, t) {
    const sensors = (this._lists?.temp_sensors || []).map((s) => ({
      value: s.entity_id,
      label: s.name,
    }));
    if (area.sensor && !sensors.some((o) => o.value === area.sensor)) {
      sensors.unshift({ value: area.sensor, label: area.sensor });
    }
    const actuators = (this._lists?.actuators || []).map((s) => ({
      value: s.entity_id,
      label: s.name,
    }));
    const haAreas = (this._lists?.ha_areas || []).map((a) => ({
      value: a.area_id,
      label: a.name,
    }));
    return (
      this._textField("name", t.fName, area.name || "") +
      (haAreas.length
        ? this._selectField("ha_area", t.fHaArea, haAreas, area.ha_area || "", {
            emptyLabel: t.none,
          })
        : "") +
      this._selectField("sensor", t.fSensor, sensors, area.sensor || "", {
        emptyLabel: t.selectSensor,
      }) +
      this._selectField("heaters", t.fHeaters, actuators, area.heaters || [], {
        multiple: true,
      }) +
      this._selectField("coolers", t.fCoolers, actuators, area.coolers || [], {
        multiple: true,
      }) +
      `<div class="grid2">` +
      this._numField("hysteresis", t.fHystHeat, area.hysteresis, { min: 0.1, max: 3, step: 0.1 }) +
      this._numField("hysteresis_cool", t.fHystCool, area.hysteresis_cool, { min: 0.1, max: 3, step: 0.1 }) +
      this._numField("away_temperature", t.fAway, area.away_temperature, { min: 5, max: 30, step: 0.5 }) +
      this._numField("min_temperature", t.fMin, area.min_temperature, { min: 5, max: 30, step: 0.5 }) +
      this._numField("max_temperature", t.fMax, area.max_temperature, { min: 5, max: 35, step: 0.5 }) +
      `</div>`
    );
  }

  _slotsText(slots) {
    return (slots || []).map((s) => `${s.time} ${s.temperature}`).join("\n");
  }

  _textField(name, label, value) {
    return `<label class="fld"><span>${esc(label)}</span>
      <input data-field="${name}" type="text" value="${esc(value == null ? "" : value)}"></label>`;
  }

  _numField(name, label, value, o = {}) {
    const attrs = [
      o.min != null ? `min="${o.min}"` : "",
      o.max != null ? `max="${o.max}"` : "",
      o.step != null ? `step="${o.step}"` : "",
    ].join(" ");
    return `<label class="fld"><span>${esc(label)}</span>
      <input data-field="${name}" type="number" ${attrs} value="${value == null ? "" : value}"></label>`;
  }

  _checkField(name, label, checked) {
    return `<label class="fld check"><input data-field="${name}" type="checkbox" ${
      checked ? "checked" : ""
    }><span>${esc(label)}</span></label>`;
  }

  _textAreaField(name, label, value) {
    return `<label class="fld"><span>${esc(label)}</span>
      <textarea data-field="${name}" rows="6">${esc(value == null ? "" : value)}</textarea></label>`;
  }

  _selectField(name, label, options, selected, opts = {}) {
    const empty =
      opts.emptyLabel != null ? `<option value="">${esc(opts.emptyLabel)}</option>` : "";
    const multiple = opts.multiple
      ? ` multiple size="${Math.min(6, Math.max(3, options.length))}"`
      : "";
    const selSet = opts.multiple ? new Set(selected || []) : null;
    const optionTags = options
      .map((o) => {
        const sel = opts.multiple
          ? selSet.has(o.value)
            ? " selected"
            : ""
          : o.value === selected
          ? " selected"
          : "";
        return `<option value="${esc(o.value)}"${sel}>${esc(o.label)}</option>`;
      })
      .join("");
    return `<label class="fld"><span>${esc(label)}</span>
      <select data-field="${name}"${multiple}>${empty}${optionTags}</select></label>`;
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
      .header-actions { margin-left: auto; display: flex; gap: 6px; }
      .status { padding: 32px; text-align: center; color: var(--secondary-text-color); }
      .notice {
        padding: 10px 14px; margin-bottom: 12px; border-radius: 8px;
        background: var(--secondary-background-color, #f1f1f1);
        color: var(--primary-text-color); font-size: 14px;
      }
      .empty {
        text-align: center; padding: 48px 16px; color: var(--secondary-text-color);
      }
      .empty-icon { --mdc-icon-size: 56px; color: var(--primary-color); opacity: .8; }
      .empty h2 { margin: 12px 0 4px; font-size: 18px; color: var(--primary-text-color); }
      .empty p { margin: 0 auto 20px; max-width: 460px; }
      .actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
      .btn {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 8px 16px; border-radius: 22px; cursor: pointer;
        border: 1px solid var(--divider-color, #e0e0e0);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color); font-size: 14px;
      }
      .btn:hover { background: var(--secondary-background-color, #f1f1f1); }
      .btn[disabled] { opacity: .6; cursor: default; }
      .btn.primary {
        background: var(--primary-color); color: var(--text-primary-color, #fff);
        border-color: var(--primary-color);
      }
      .btn.icon { padding: 6px; border-radius: 50%; }
      .btn.ghost { background: transparent; }
      .btn.small { padding: 5px 12px; font-size: 13px; }
      .btn.danger { color: var(--error-color, #db4437); border-color: var(--error-color, #db4437); }
      .btn ha-icon { --mdc-icon-size: 20px; }
      .mini {
        border: none; background: transparent; cursor: pointer; font-size: 14px;
        color: var(--secondary-text-color); padding: 2px 4px; border-radius: 4px;
        line-height: 1;
      }
      .mini:hover { background: var(--secondary-background-color, #f1f1f1); color: var(--primary-text-color); }
      .mini.danger { color: var(--error-color, #db4437); }
      .card-title.row { display: flex; align-items: center; justify-content: space-between; }
      .floor-actions { display: flex; align-items: center; gap: 8px; }
      .area-top-r { display: flex; align-items: center; gap: 6px; }
      /* Modal */
      .modal-overlay {
        position: fixed; inset: 0; z-index: 9; display: flex;
        align-items: center; justify-content: center; padding: 16px;
        background: rgba(0, 0, 0, .5);
      }
      .modal-box {
        background: var(--card-background-color, #fff); color: var(--primary-text-color);
        border-radius: 14px; width: 100%; max-width: 520px; max-height: 90vh;
        display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0,0,0,.35);
      }
      .modal-head { font-size: 18px; font-weight: 600; padding: 16px 18px 8px; }
      .modal-body { padding: 4px 18px 8px; overflow: auto; }
      .modal-error {
        display: none; margin: 4px 18px; padding: 8px 12px; border-radius: 8px;
        background: var(--error-color, #db4437); color: #fff; font-size: 13px;
      }
      .modal-foot {
        display: flex; align-items: center; gap: 8px; padding: 12px 18px 16px;
      }
      .modal-foot .spacer { flex: 1; }
      .fld { display: block; margin: 10px 0; font-size: 13px; color: var(--secondary-text-color); }
      .fld > span { display: block; margin-bottom: 4px; }
      .fld input[type=text], .fld input[type=number], .fld input[type=date],
      .fld textarea, .fld select {
        width: 100%; box-sizing: border-box; padding: 8px 10px; font-size: 14px;
        border-radius: 8px; border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff); color: var(--primary-text-color);
      }
      .fld.check { display: flex; align-items: center; gap: 8px; }
      .fld.check input { width: auto; }
      .fld.check > span { margin: 0; }
      .hint { font-size: 12px; color: var(--secondary-text-color); margin: 4px 0; }
      .sec-title { font-weight: 600; margin: 14px 0 6px; color: var(--primary-text-color); }
      .grid-days { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
      .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
      .ov-rows { display: flex; flex-direction: column; gap: 6px; }
      .ov-row {
        display: grid; grid-template-columns: 1fr 1fr auto auto; gap: 6px; align-items: center;
      }
      .ov-row input, .ov-row select {
        padding: 6px 8px; font-size: 13px; border-radius: 6px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff); color: var(--primary-text-color);
      }
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
      .area.clickable { cursor: pointer; transition: border-color .15s; }
      .area.clickable:hover { border-color: var(--primary-color); }
      .overrides {
        margin: 0 0 14px; padding: 8px 12px; border-radius: 8px;
        background: var(--secondary-background-color, #f1f1f1);
      }
      .ov-title { font-size: 12px; color: var(--secondary-text-color); margin-bottom: 4px; }
      .ov { font-size: 13px; padding: 1px 0; }
      .ov.active { font-weight: 600; }
      .ov-badge {
        font-size: 10px; padding: 1px 6px; border-radius: 8px; margin-left: 4px;
        background: var(--primary-color); color: var(--text-primary-color, #fff);
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
