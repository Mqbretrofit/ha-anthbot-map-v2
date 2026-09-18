const TEXT = {
  en: {
    schedule: "Schedule",
    nextMow: "Next mow",
    noNextMow: "No upcoming mow",
    override: "Temporary override",
    overrideNone: "No active override",
    overrideUntil: "until",
    durationHours: "Duration (hours)",
    mode: "Mowing mode",
    full: "Full lawn",
    zone: "Manual zones",
    auto_zone: "Automatic zones",
    region: "Mapped region",
    edge: "Outer edge",
    dock: "Dock surroundings",
    zones: "Zones",
    height: "Cutting height",
    mowNow: "Mow for this long",
    parkNow: "Stay parked for this long",
    clearOverride: "Clear override",
    weeklyRules: "ANTHBOT app schedules",
    nativeHint: "These schedules are read from and saved back to the ANTHBOT app.",
    nativeSource: "ANTHBOT app",
    addRule: "Add app schedule",
    editRule: "Edit rule",
    deleteRule: "Delete",
    noRules: "No schedule is currently stored in the ANTHBOT app.",
    name: "Name",
    weekdays: "Days",
    startTime: "Start time",
    calendarDuration: "Calendar duration (minutes)",
    enabled: "Enabled",
    weather: "Weather entity",
    noWeather: "Do not use weather",
    forecastHours: "Forecast guard (hours)",
    rainProbability: "Rain probability limit (%)",
    catchUpHours: "Catch-up window (hours)",
    save: "Save",
    cancel: "Cancel",
    saved: "Schedule sent to the ANTHBOT app",
    deleted: "Schedule deletion sent to the ANTHBOT app",
    overrideSaved: "Override applied",
    overrideCleared: "Override cleared",
    lastEvent: "Last mower event",
    none: "None",
    selectDay: "Select at least one day.",
    selectZone: "Select at least one zone for this mode.",
    confirmDelete: "Delete this weekly rule?",
    mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun",
  },
  hu: {
    schedule: "Ütemezés",
    nextMow: "Következő nyírás",
    noNextMow: "Nincs következő nyírás",
    override: "Ideiglenes felülírás",
    overrideNone: "Nincs aktív felülírás",
    overrideUntil: "eddig",
    durationHours: "Időtartam (óra)",
    mode: "Nyírási mód",
    full: "Teljes gyep",
    zone: "Kézi zónák",
    auto_zone: "Automatikus zónák",
    region: "Térképi régió",
    edge: "Külső szegély",
    dock: "Dokkoló környéke",
    zones: "Zónák",
    height: "Vágási magasság",
    mowNow: "Nyírj eddig",
    parkNow: "Maradj bent eddig",
    clearOverride: "Felülírás törlése",
    weeklyRules: "ANTHBOT app ütemezései",
    nativeHint: "Ezeket az ütemezéseket az ANTHBOT appból olvassa, és oda is menti vissza.",
    nativeSource: "ANTHBOT app",
    addRule: "Új app-ütemezés",
    editRule: "Szabály szerkesztése",
    deleteRule: "Törlés",
    noRules: "Az ANTHBOT appban jelenleg nincs ütemezés.",
    name: "Név",
    weekdays: "Napok",
    startTime: "Indulási idő",
    calendarDuration: "Naptári időtartam (perc)",
    enabled: "Engedélyezve",
    weather: "Időjárás-entitás",
    noWeather: "Ne használjon időjárást",
    forecastHours: "Előrejelzési tiltás (óra)",
    rainProbability: "Esővalószínűség határa (%)",
    catchUpHours: "Pótlási időablak (óra)",
    save: "Mentés",
    cancel: "Mégse",
    saved: "Ütemezés elküldve az ANTHBOT appnak",
    deleted: "Ütemezés törlése elküldve az ANTHBOT appnak",
    overrideSaved: "Felülírás bekapcsolva",
    overrideCleared: "Felülírás törölve",
    lastEvent: "Utolsó robotesemény",
    none: "Nincs",
    selectDay: "Válassz legalább egy napot.",
    selectZone: "Ehhez a módhoz válassz legalább egy zónát.",
    confirmDelete: "Törlöd ezt a heti szabályt?",
    mon: "H", tue: "K", wed: "Sze", thu: "Cs", fri: "P", sat: "Szo", sun: "V",
  },
};

const MODES = ["full", "zone", "auto_zone", "edge", "dock"];
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);

export function anthbotScheduleText(card, key) {
  return TEXT[card.language]?.[key] || TEXT.en[key] || key;
}

function entity(card, domain, suffix) {
  const entityId = card.findEntity?.(domain, [suffix]);
  return entityId ? card._hass?.states?.[entityId] : null;
}

function nextMowEntity(card) {
  const states = card._hass?.states || {};
  const configured = card.config?.entities?.nextMow;
  if (configured && states[configured]) return states[configured];

  const activeId = String(card._activeEntityId || card.config?.entity || "");
  const mapMatch = activeId.match(/^sensor\.(.*)_map(?:_(\d+))?$/);
  const base = mapMatch?.[1] || card.entityBase?.();
  const ordinal = mapMatch?.[2] || "";
  if (base) {
    const exactId = `sensor.${base}_next_mow${ordinal ? `_${ordinal}` : ""}`;
    if (states[exactId]) return states[exactId];
  }

  // A disabled schedule deliberately makes the timestamp sensor `unknown`,
  // but its `schedules` attribute is still the authoritative app plan.  The
  // generic entity resolver filters unknown states, so resolve this sensor by
  // mower serial before falling back to its state value.
  const mapState = states[activeId] || card.entity;
  const serial = String(mapState?.attributes?.serial_number || "");
  if (serial) {
    const serialMatch = Object.values(states).find((state) => (
      state?.entity_id?.startsWith("sensor.")
      && state.entity_id.includes("next_mow")
      && String(state.attributes?.serial_number || "") === serial
    ));
    if (serialMatch) return serialMatch;
  }

  return card.getRelatedEntity?.("nextMow") || entity(card, "sensor", "next_mow");
}

function targetEntity(card) {
  const serial = String(card.entity?.attributes?.serial_number || "");
  const entries = Object.entries(card._hass?.states || {});
  const serialMatch = entries.find(([entityId, state]) => (
    entityId.startsWith("lawn_mower.")
    && serial
    && String(state.attributes?.serial_number || "") === serial
  ));
  if (serialMatch) return serialMatch[0];
  const base = card.entityBase?.();
  const baseMatch = entries.find(([entityId, state]) => (
    entityId.startsWith(`lawn_mower.${base}`) && state.state !== "unavailable"
  ));
  return baseMatch?.[0] || card._activeEntityId || card.config.entity;
}

function zonesFor(card, mode) {
  if (mode === "zone") return card.currentZones?.() || [];
  if (mode === "auto_zone") return card.currentAutoZones?.() || [];
  return [];
}

function selectedValues(select) {
  return [...(select?.selectedOptions || [])].map((option) => option.value).filter(Boolean);
}

function zoneSelectHtml(card, mode, selected = []) {
  const selectedSet = new Set(String(selected || "").split(",").map((item) => item.trim()));
  return zonesFor(card, mode).map((zone) => {
    const value = String(zone.id ?? zone.name ?? "");
    const label = zone.name || `${anthbotScheduleText(card, "zone")} ${value}`;
    return `<option value="${esc(value)}" ${selectedSet.has(value) ? "selected" : ""}>${esc(label)}</option>`;
  }).join("");
}

function modeOptions(card, selected = "full", modes = MODES) {
  return modes.map((mode) => (
    `<option value="${mode}" ${mode === selected ? "selected" : ""}>${esc(anthbotScheduleText(card, mode))}</option>`
  )).join("");
}

function heightOptions(selected = 50, allowEmpty = true) {
  const values = [];
  if (allowEmpty) values.push(`<option value="">—</option>`);
  for (let value = 30; value <= 70; value += 5) {
    values.push(`<option value="${value}" ${Number(selected) === value ? "selected" : ""}>${value} mm</option>`);
  }
  return values.join("");
}

function ensureStyle(card) {
  if (card.shadowRoot.querySelector("style[data-anthbot-schedule]")) return;
  const style = document.createElement("style");
  style.dataset.anthbotSchedule = "";
  style.textContent = `
    .anthbot-schedule-overview{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px}
    .anthbot-schedule-card{padding:14px;border:1px solid rgba(255,255,255,.14);border-radius:14px;background:rgba(7,15,23,.32)}
    .anthbot-schedule-card>span{display:block;color:#aeb7c2;font-size:12px}.anthbot-schedule-card>strong{display:block;margin-top:6px;font-size:16px;overflow-wrap:anywhere}
    .anthbot-schedule-block{margin:10px 0;padding:14px;border:1px solid rgba(255,255,255,.14);border-radius:15px;background:rgba(7,15,23,.25)}
    .anthbot-schedule-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.anthbot-schedule-head h3{margin:0;font-size:18px}
    .anthbot-schedule-form{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.anthbot-schedule-form label,.anthbot-rule-grid label{display:grid;gap:5px;color:#aeb7c2;font-size:12px}
    .anthbot-schedule-form input,.anthbot-schedule-form select,.anthbot-rule-grid input,.anthbot-rule-grid select{box-sizing:border-box;width:100%;min-width:0;min-height:42px;padding:8px 10px;border:1px solid rgba(255,255,255,.18);border-radius:10px;background:rgba(8,16,24,.84);color:#fff;font:inherit}
    .anthbot-schedule-form select[multiple]{min-height:84px}.anthbot-schedule-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.anthbot-schedule-actions button,.anthbot-schedule-head button,.anthbot-rule-actions button,.anthbot-rule-footer button{min-height:40px;padding:8px 13px;border:1px solid rgba(255,255,255,.18);border-radius:10px;background:rgba(255,255,255,.10);color:#fff;font:inherit;font-weight:800;cursor:pointer}.anthbot-schedule-actions button:first-child,.anthbot-schedule-head button,.anthbot-rule-footer .primary{background:linear-gradient(145deg,#31bf62,#249c4d);border:0}
    .anthbot-schedule-actions button.danger,.anthbot-rule-actions button.danger{background:rgba(190,50,50,.28)}
    .anthbot-rule-list{display:grid;gap:9px}.anthbot-rule-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:12px;border:1px solid rgba(255,255,255,.12);border-radius:12px;background:rgba(255,255,255,.045)}.anthbot-rule-row small{display:block;margin-top:4px;color:#aeb7c2}.anthbot-rule-actions{display:flex;gap:7px}
    .anthbot-rule-backdrop{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:16px;background:rgba(0,0,0,.60);backdrop-filter:blur(8px)}.anthbot-rule-modal{width:min(820px,100%);max-height:calc(100dvh - 32px);overflow:auto;box-sizing:border-box;padding:20px;border:1px solid rgba(255,255,255,.18);border-radius:22px;background:linear-gradient(145deg,rgba(18,27,34,.99),rgba(10,17,23,.99));color:#fff;box-shadow:0 24px 70px rgba(0,0,0,.55)}
    .anthbot-rule-title{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:16px}.anthbot-rule-title h2{margin:0}.anthbot-rule-close{width:42px;height:42px;border:1px solid rgba(255,255,255,.16);border-radius:50%;background:rgba(255,255,255,.08);color:#fff;font-size:25px;cursor:pointer}.anthbot-rule-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.anthbot-rule-grid .wide{grid-column:1/-1}.anthbot-weekdays{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px}.anthbot-weekdays label{display:flex;align-items:center;justify-content:center;gap:5px;min-height:42px;border:1px solid rgba(255,255,255,.15);border-radius:9px;background:rgba(255,255,255,.05);color:#fff}.anthbot-weekdays input{width:auto;min-height:0}.anthbot-rule-footer{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}
    .anthbot-empty{padding:15px;text-align:center;color:#aeb7c2;border:1px dashed rgba(255,255,255,.16);border-radius:12px}
    @media(max-width:760px){.anthbot-schedule-overview{grid-template-columns:1fr}.anthbot-schedule-form,.anthbot-rule-grid{grid-template-columns:1fr}.anthbot-rule-grid .wide{grid-column:auto}.anthbot-rule-row{grid-template-columns:1fr}.anthbot-rule-actions{justify-content:flex-end}.anthbot-weekdays{grid-template-columns:repeat(4,minmax(0,1fr))}.anthbot-rule-backdrop{padding:7px;align-items:end}.anthbot-rule-modal{max-height:calc(100dvh - 10px);border-radius:20px 20px 10px 10px;padding:15px}}
  `;
  card.shadowRoot.appendChild(style);
}

function refreshPanel(card, delay = 350) {
  card.scheduleRefresh?.(100);
  window.setTimeout(() => {
    if (card.activePanel === "schedule") {
      const body = card.shadowRoot.querySelector('[data-role="panel-body"]');
      if (body) renderAnthbotSchedulePanel(card, body);
    }
  }, delay);
}

async function call(card, service, data, successText, button) {
  if (button) button.disabled = true;
  try {
    await card._hass.callService("anthbot_map", service, {
      ...data,
      entity_id: targetEntity(card),
    });
    card.notify(successText);
    refreshPanel(card);
    return true;
  } catch (error) {
    card.notify(`${card.t("settingFailed")}: ${error?.message || error}`);
    return false;
  } finally {
    if (button) button.disabled = false;
  }
}

function ruleSummary(card, rule) {
  const days = (rule.weekdays || []).map((day) => anthbotScheduleText(card, WEEKDAYS[Number(day)])).join(", ");
  const start = rule.repeating === false && rule.start_datetime
    ? card.formatLocalDateTime(rule.start_datetime)
    : rule.start_time;
  const details = [days, start, anthbotScheduleText(card, rule.mode || "full")];
  if (rule.zones) details.push(`${anthbotScheduleText(card, "zones")}: ${rule.zones}`);
  if (rule.mow_height) details.push(`${rule.mow_height} mm`);
  return details.filter(Boolean).join(" · ");
}

function weatherOptions(card, selected) {
  const options = [`<option value="">${esc(anthbotScheduleText(card, "noWeather"))}</option>`];
  for (const [entityId, state] of Object.entries(card._hass?.states || {})) {
    if (!entityId.startsWith("weather.")) continue;
    const label = state.attributes?.friendly_name || entityId;
    options.push(`<option value="${esc(entityId)}" ${entityId === selected ? "selected" : ""}>${esc(label)}</option>`);
  }
  return options.join("");
}

function openRuleModal(card, existing = {}) {
  ensureStyle(card);
  card.shadowRoot.querySelector(".anthbot-rule-backdrop")?.remove();
  const t = (key) => anthbotScheduleText(card, key);
  const backdrop = document.createElement("div");
  backdrop.className = "anthbot-rule-backdrop";
  const modal = document.createElement("div");
  modal.className = "anthbot-rule-modal";
  const selectedDays = new Set((existing.weekdays || [0, 1, 2, 3, 4, 5, 6]).map(Number));
  const currentMode = existing.mode || "full";
  const scheduleModes = ["full", "zone", "auto_zone"];
  // Region appointments can be created by the app with area_points.  Keep
  // them editable without offering an empty region to new rules.
  if (currentMode === "region") scheduleModes.push("region");
  modal.innerHTML = `
    <div class="anthbot-rule-title"><h2>${esc(existing.id ? t("editRule") : t("addRule"))}</h2><button type="button" class="anthbot-rule-close">×</button></div>
    <div class="anthbot-rule-grid">
      <label>${esc(t("name"))}<input name="summary" value="${esc(existing.summary || "ANTHBOT app schedule")}"></label>
      <label>${esc(t("startTime"))}<input name="start_time" type="time" value="${esc(existing.start_time || "09:00")}"></label>
      <div class="wide"><span style="display:block;margin-bottom:6px;color:#aeb7c2;font-size:12px">${esc(t("weekdays"))}</span><div class="anthbot-weekdays">${WEEKDAYS.map((key, day) => `<label><input type="checkbox" name="weekday" value="${day}" ${selectedDays.has(day) ? "checked" : ""}>${esc(t(key))}</label>`).join("")}</div></div>
      <label>${esc(t("mode"))}<select name="mode">${modeOptions(card, currentMode, scheduleModes)}</select></label>
      <label data-role="rule-zones">${esc(t("zones"))}<select name="zones" multiple>${zoneSelectHtml(card, currentMode, existing.zones)}</select></label>
      <label>${esc(t("height"))}<select name="mow_height">${heightOptions(existing.mow_height)}</select></label>
      <label>${esc(t("calendarDuration"))}<input name="duration_minutes" type="number" min="15" max="720" step="15" value="${Number(existing.duration_minutes) || 60}"></label>
      <label>${esc(t("weather"))}<select name="weather_entity">${weatherOptions(card, existing.weather_entity)}</select></label>
      <label>${esc(t("forecastHours"))}<input name="forecast_guard_hours" type="number" min="0" max="24" step="1" value="${Number(existing.forecast_guard_hours) || 0}"></label>
      <label>${esc(t("rainProbability"))}<input name="rain_probability" type="number" min="1" max="100" step="5" value="${Number(existing.rain_probability) || 50}"></label>
      <label>${esc(t("catchUpHours"))}<input name="catch_up_hours" type="number" min="0" max="72" step="1" value="${Number(existing.catch_up_hours) || 0}"></label>
      <label class="wide" style="display:flex;grid-template-columns:auto 1fr;align-items:center"><input name="enabled" type="checkbox" style="width:auto" ${existing.enabled !== false ? "checked" : ""}>${esc(t("enabled"))}</label>
    </div>
    <div class="anthbot-rule-footer"><button type="button" class="cancel">${esc(t("cancel"))}</button><button type="button" class="primary">${esc(t("save"))}</button></div>
  `;
  const close = () => backdrop.remove();
  modal.querySelector(".anthbot-rule-close").addEventListener("click", close);
  modal.querySelector(".cancel").addEventListener("click", close);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });
  const mode = modal.querySelector('[name="mode"]');
  const zoneSelect = modal.querySelector('[name="zones"]');
  const updateZones = () => {
    zoneSelect.innerHTML = zoneSelectHtml(card, mode.value, selectedValues(zoneSelect).join(","));
    modal.querySelector('[data-role="rule-zones"]').style.display = ["zone", "auto_zone"].includes(mode.value) ? "grid" : "none";
  };
  mode.addEventListener("change", updateZones);
  updateZones();
  modal.querySelector(".primary").addEventListener("click", async (event) => {
    const weekdays = [...modal.querySelectorAll('[name="weekday"]:checked')].map((input) => input.value);
    if (!weekdays.length) {
      card.notify(t("selectDay"));
      return;
    }
    const data = {
      summary: modal.querySelector('[name="summary"]').value || "ANTHBOT app schedule",
      weekdays,
      start_time: modal.querySelector('[name="start_time"]').value,
      mode: mode.value,
      zones: selectedValues(zoneSelect).join(","),
      duration_minutes: Number(modal.querySelector('[name="duration_minutes"]').value),
      enabled: modal.querySelector('[name="enabled"]').checked,
      weather_entity: modal.querySelector('[name="weather_entity"]').value || undefined,
      forecast_guard_hours: Number(modal.querySelector('[name="forecast_guard_hours"]').value),
      rain_probability: Number(modal.querySelector('[name="rain_probability"]').value),
      catch_up_hours: Number(modal.querySelector('[name="catch_up_hours"]').value),
    };
    if (["zone", "auto_zone"].includes(mode.value) && !data.zones) {
      card.notify(t("selectZone"));
      return;
    }
    const height = modal.querySelector('[name="mow_height"]').value;
    if (height) data.mow_height = Number(height);
    if (existing.id) data.schedule_id = String(existing.id);
    if (await call(card, "add_ha_schedule", data, t("saved"), event.currentTarget)) close();
  });
  backdrop.appendChild(modal);
  card.shadowRoot.appendChild(backdrop);
}

function overrideBlock(card, override) {
  const t = (key) => anthbotScheduleText(card, key);
  const block = document.createElement("section");
  block.className = "anthbot-schedule-block";
  block.innerHTML = `
    <div class="anthbot-schedule-head"><h3>${esc(t("override"))}</h3><span>${override ? `${esc(override.action)} ${esc(t("overrideUntil"))} ${esc(card.formatLocalDateTime(override.expires))}` : esc(t("overrideNone"))}</span></div>
    <div class="anthbot-schedule-form">
      <label>${esc(t("durationHours"))}<input name="duration" type="number" min="0.25" max="72" step="0.25" value="2"></label>
      <label>${esc(t("mode"))}<select name="mode">${modeOptions(card, "full")}</select></label>
      <label data-role="override-zones">${esc(t("zones"))}<select name="zones" multiple></select></label>
      <label>${esc(t("height"))}<select name="height">${heightOptions(null)}</select></label>
    </div>
    <div class="anthbot-schedule-actions"><button type="button" data-action="mow">${esc(t("mowNow"))}</button><button type="button" data-action="park">${esc(t("parkNow"))}</button><button type="button" class="danger" data-action="clear">${esc(t("clearOverride"))}</button></div>
  `;
  const mode = block.querySelector('[name="mode"]');
  const zoneSelect = block.querySelector('[name="zones"]');
  const updateZones = () => {
    zoneSelect.innerHTML = zoneSelectHtml(card, mode.value);
    block.querySelector('[data-role="override-zones"]').style.display = ["zone", "auto_zone"].includes(mode.value) ? "grid" : "none";
  };
  mode.addEventListener("change", updateZones);
  updateZones();
  block.querySelectorAll("button[data-action]").forEach((button) => button.addEventListener("click", async () => {
    const action = button.dataset.action;
    const data = { action };
    if (action !== "clear") data.duration_hours = Number(block.querySelector('[name="duration"]').value) || 2;
    if (action === "mow") {
      data.mode = mode.value;
      data.zones = selectedValues(zoneSelect).join(",");
      if (["zone", "auto_zone"].includes(data.mode) && !data.zones) {
        card.notify(t("selectZone"));
        return;
      }
      const height = block.querySelector('[name="height"]').value;
      if (height) data.mow_height = Number(height);
    }
    await call(card, "override_schedule", data, action === "clear" ? t("overrideCleared") : t("overrideSaved"), button);
  }));
  return block;
}

export function renderAnthbotSchedulePanel(card, body) {
  ensureStyle(card);
  const t = (key) => anthbotScheduleText(card, key);
  body.innerHTML = "";
  const next = nextMowEntity(card);
  const attrs = next?.attributes || {};
  const rules = Array.isArray(attrs.schedules) ? attrs.schedules : [];
  const activeOverride = attrs.active_override && typeof attrs.active_override === "object" ? attrs.active_override : null;
  const mowerEvent = entity(card, "event", "mower_events");
  const nextText = next && !["unknown", "unavailable", "none", ""].includes(String(next.state).toLowerCase())
    ? card.formatLocalDateTime(next.state)
    : t("noNextMow");
  const overview = document.createElement("div");
  overview.className = "anthbot-schedule-overview";
  overview.innerHTML = `
    <div class="anthbot-schedule-card"><span>${esc(t("nextMow"))}</span><strong>${esc(nextText)}</strong></div>
    <div class="anthbot-schedule-card"><span>${esc(t("override"))}</span><strong>${esc(activeOverride?.action || t("overrideNone"))}</strong></div>
    <div class="anthbot-schedule-card"><span>${esc(t("lastEvent"))}</span><strong>${esc(mowerEvent?.attributes?.event_type || mowerEvent?.state || t("none"))}</strong></div>
  `;
  body.appendChild(overview);
  body.appendChild(overrideBlock(card, activeOverride));

  const rulesBlock = document.createElement("section");
  rulesBlock.className = "anthbot-schedule-block";
  rulesBlock.innerHTML = `<div class="anthbot-schedule-head"><div><h3>${esc(t("weeklyRules"))}</h3><small>${esc(t("nativeHint"))}</small></div><button type="button">＋ ${esc(t("addRule"))}</button></div><div class="anthbot-rule-list"></div>`;
  rulesBlock.querySelector(".anthbot-schedule-head button").addEventListener("click", () => openRuleModal(card));
  const list = rulesBlock.querySelector(".anthbot-rule-list");
  if (!rules.length) {
    list.innerHTML = `<div class="anthbot-empty">${esc(t("noRules"))}</div>`;
  } else {
    for (const rule of rules) {
      const row = document.createElement("div");
      row.className = "anthbot-rule-row";
      const canEdit = rule.repeating !== false && ["full", "zone", "auto_zone", "region"].includes(rule.mode || "full");
      row.innerHTML = `<div><strong>${esc(rule.summary || "ANTHBOT app schedule")}${rule.enabled === false ? " ⏸" : ""}</strong><small>${esc(t("nativeSource"))} · ${esc(ruleSummary(card, rule))}</small></div><div class="anthbot-rule-actions">${canEdit ? `<button type="button" class="edit">${esc(t("editRule"))}</button>` : ""}<button type="button" class="danger">${esc(t("deleteRule"))}</button></div>`;
      row.querySelector(".edit")?.addEventListener("click", () => openRuleModal(card, rule));
      row.querySelector(".danger").addEventListener("click", async (event) => {
        if (!window.confirm(t("confirmDelete"))) return;
        await call(card, "delete_ha_schedule", { schedule_id: String(rule.id) }, t("deleted"), event.currentTarget);
      });
      list.appendChild(row);
    }
  }
  body.appendChild(rulesBlock);
}
