// M9/M9 Pro frontend compatibility wrapper.
// Stable card implementation is preserved byte-for-byte in anthbot-map-card-core.js.
import "./anthbot-map-card-core.js?v=2492-m9-visual-core1";

const AnthbotMapCard = customElements.get("anthbot-map-card");
if (AnthbotMapCard && !AnthbotMapCard.prototype.__m9VisualFrontendPatch) {
  AnthbotMapCard.prototype.__m9VisualFrontendPatch = true;
  const previousRefreshOpenPanelValues = AnthbotMapCard.prototype.refreshOpenPanelValues;

  AnthbotMapCard.prototype.createDirectObstacleControl = function (switchEntityId, levelEntityId) {
    const enabled = switchEntityId && this._hass?.states?.[switchEntityId]?.state === "on";
    const tile = document.createElement("div");
    tile.className = `panel-tile obstacle-combined ${enabled ? "" : "disabled"}`;
    tile.dataset.visualObstacleControl = "true";
    if (switchEntityId) tile.dataset.switchEntityId = switchEntityId;
    if (levelEntityId) tile.dataset.levelEntityId = levelEntityId;

    const row = document.createElement("label");
    row.className = "switch-tile";
    row.innerHTML = `<span>${this.t("visualObstacle")}</span><input data-visual-obstacle-switch type="checkbox" ${enabled ? "checked" : ""} ${switchEntityId ? "" : "disabled"}>`;
    const levels = document.createElement("div");
    levels.className = "obstacle-levels";
    const levelControl = this.createDirectObstacleLevelControl(levelEntityId);
    levelControl.dataset.visualObstacleLevelControl = "true";
    levels.appendChild(levelControl);

    const input = row.querySelector("input");
    input.addEventListener("change", async () => {
      if (!switchEntityId) return;
      const requested = input.checked;
      input.disabled = true;
      tile.classList.toggle("disabled", !requested);
      try {
        await this._hass.callService("switch", requested ? "turn_on" : "turn_off", { entity_id: switchEntityId });
        try {
          await this._hass.callService("homeassistant", "update_entity", {
            entity_id: [switchEntityId, levelEntityId].filter(Boolean),
          });
        } catch (_error) {}
        this.scheduleRefresh(150);
      } catch (error) {
        input.checked = !requested;
        tile.classList.toggle("disabled", requested);
        this.notify(`${this.t("operationFailed")}: ${switchEntityId}`);
        throw error;
      } finally {
        input.disabled = false;
      }
    });
    tile.append(row, levels);
    return tile;
  };

  AnthbotMapCard.prototype.refreshOpenPanelValues = function (...args) {
    previousRefreshOpenPanelValues?.apply(this, args);
    this.shadowRoot?.querySelectorAll('[data-visual-obstacle-control="true"]').forEach((tile) => {
      const switchEntityId = tile.dataset.switchEntityId || "";
      const levelEntityId = tile.dataset.levelEntityId || "";
      const enabled = switchEntityId && this._hass?.states?.[switchEntityId]?.state === "on";
      const checkbox = tile.querySelector('[data-visual-obstacle-switch]');
      if (checkbox && this.shadowRoot?.activeElement !== checkbox) checkbox.checked = enabled;
      tile.classList.toggle("disabled", !enabled);

      const rawLevel = Number(levelEntityId ? this._hass?.states?.[levelEntityId]?.state : NaN);
      if (!Number.isFinite(rawLevel)) return;
      const level = Math.max(0, Math.min(2, Math.round(rawLevel)));
      const labels = [this.t("low"), this.t("medium"), this.t("high")];
      const control = tile.querySelector('[data-visual-obstacle-level-control="true"]');
      const value = control?.querySelector(".control-head strong");
      if (value) value.textContent = labels[level];
      control?.querySelectorAll(".height-option").forEach((button, index) => {
        button.classList.toggle("active", index === level);
      });
    });
  };
}
