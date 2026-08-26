const registry = window.customElements;
const originalDefine = registry.define;
let defineOverridden = false;

try {
  registry.define = function(name, constructor, options) {
    if (name === "anthbot-map-card" && registry.get(name)) {
      return;
    }
    return originalDefine.call(registry, name, constructor, options);
  };
  defineOverridden = true;
  await import("./anthbot-map-card-core.js?v=2.4.1-beta");
} finally {
  if (defineOverridden) {
    try {
      delete registry.define;
    } catch {
      registry.define = originalDefine;
    }
  }
}

const AnthbotMapCard = registry.get("anthbot-map-card");
if (AnthbotMapCard && !AnthbotMapCard.__batterySaverDialogTogglePatched) {
  const proto = AnthbotMapCard.prototype;
  const originalCreateSwitchControl = proto.createSwitchControl;
  const originalOpenBatterySaverDialog = proto.openBatterySaverDialog;

  proto.createSwitchControl = function(label, key) {
    if (key !== "batterySaver") {
      return originalCreateSwitchControl.call(this, label, key);
    }

    const entityId = this.getSwitchEntity(key);
    const entity = entityId ? this._hass.states[entityId] : null;
    const checked = entity?.state === "on";
    const tile = document.createElement("label");
    tile.className = "panel-tile switch-tile battery-saver-open-tile";
    tile.title = entityId || this.t("switchMissing");
    tile.tabIndex = entityId ? 0 : -1;
    tile.innerHTML = `
      <span>${label}</span>
      <input type="checkbox" ${checked ? "checked" : ""} ${entityId ? "" : "disabled"} tabindex="-1" aria-hidden="true">
    `;
    const openDialog = (event) => {
      event?.preventDefault?.();
      if (!entityId) return;
      this.openBatterySaverDialog(entityId);
    };
    tile.addEventListener("click", openDialog);
    tile.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") openDialog(event);
    });
    return tile;
  };

  proto.openBatterySaverDialog = function(entityId) {
    originalOpenBatterySaverDialog.call(this, entityId);
    const root = this.shadowRoot || document.body;
    const dialogs = root.querySelectorAll(".battery-saver-dialog");
    const dialog = dialogs[dialogs.length - 1];
    if (!dialog || dialog.querySelector('[data-role="battery-saver-enabled"]')) return;

    const state = entityId ? this._hass.states[entityId] : null;
    const enabled = state?.state === "on";
    const modeRow = document.createElement("label");
    modeRow.className = "battery-saver-check";
    modeRow.dataset.role = "battery-saver-enabled";
    modeRow.style.marginTop = "14px";
    modeRow.innerHTML = `
      <span><strong>${this.t("batterySaverMode")}</strong><small style="display:block;opacity:.68;margin-top:3px">${this.t("batterySaverDescription")}</small></span>
      <input type="checkbox" ${enabled ? "checked" : ""}>
    `;
    const header = dialog.querySelector(".mowing-record-detail-head");
    header?.insertAdjacentElement("afterend", modeRow);

    const input = modeRow.querySelector("input");
    input.addEventListener("change", async () => {
      input.disabled = true;
      try {
        await this.toggleSwitchEntity("batterySaver", entityId, input.checked, input);
        this.scheduleRefresh(200);
      } catch (error) {
        input.checked = !input.checked;
        throw error;
      } finally {
        input.disabled = false;
      }
    });
  };

  AnthbotMapCard.__batterySaverDialogTogglePatched = true;
}

window.customCards = window.customCards || [];
let anthbotMapCardSeen = false;
window.customCards = window.customCards.filter((card) => {
  if (card?.type !== "anthbot-map-card") return true;
  if (anthbotMapCardSeen) return false;
  anthbotMapCardSeen = true;
  return true;
});
