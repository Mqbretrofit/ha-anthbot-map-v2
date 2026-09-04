// Preserve the mowing target label while the completion percentage remains
// visible during return-to-dock, charging, docked and standby states.
//
// The beta3 card already latches a completed task at 100%, but once the robot
// changes from e.g. global_mowing/zone_mowing to charging it can no longer
// derive the target from the current status. Without a saved target the card
// falls back to the current mower status, producing labels such as
// "Charging 100.0%". Keep the last real mowing target per map entity instead.

const STORAGE_PREFIX = "anthbot-map-last-mowing-target:";
const ACTIVE_MOWING = [
  "mowing", "zonemowing", "regionmowing", "globalmowing", "nestmowing",
  "edgemowing", "bordermowing", "pointmowing", "spotmowing",
];
const FINISHED = [
  "returningtodock", "backtodock", "returntodock", "returning", "docking",
  "charging", "charge", "docked", "standby", "idle",
  "visszaatoltore", "toltes", "dokkolva", "keszenlet",
];

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[_\s-]+/g, "");
}

function storageKey(card) {
  const entityId = String(card?.config?.entity || card?.entity?.entity_id || "default");
  return `${STORAGE_PREFIX}${entityId}`;
}

function readTarget(card) {
  try {
    return String(window.localStorage.getItem(storageKey(card)) || "").trim();
  } catch (_error) {
    return "";
  }
}

function writeTarget(card, target) {
  const value = String(target || "").trim();
  if (!value) return;
  try {
    window.localStorage.setItem(storageKey(card), value);
  } catch (_error) {
    // localStorage can be unavailable in restricted browser contexts.
  }
}

function currentRawStatus(card, progressEntity, statusEntity) {
  const mapAttrs = card?.entity?.attributes || {};
  return normalize(
    mapAttrs.robot_status_raw
    ?? progressEntity?.attributes?.robot_status_raw
    ?? statusEntity?.attributes?.robot_status_raw
    ?? statusEntity?.state
    ?? ""
  );
}

customElements.whenDefined("anthbot-map-card").then(() => {
  const Card = customElements.get("anthbot-map-card");
  if (!Card || Card.prototype.__anthbotMowingTargetPersistenceInstalled) return;

  const originalUpdate = Card.prototype.updateMowingProgressStatus;
  if (typeof originalUpdate !== "function") return;

  Card.prototype.updateMowingProgressStatus = function (...args) {
    originalUpdate.apply(this, args);

    const lines = Array.from(
      this.shadowRoot?.querySelectorAll?.('[data-role="mowing-live-line"]') || []
    );
    if (!lines.length) return;

    const progressEntity = this.getRelatedEntity?.("mowingProgress");
    const statusEntity = this.getRelatedEntity?.("status");
    const rawStatus = currentRawStatus(this, progressEntity, statusEntity);
    const active = ACTIVE_MOWING.some((value) => rawStatus.includes(value));
    const canonicalStatus = normalize(statusEntity?.state);
    const finished = FINISHED.some((value) =>
      canonicalStatus.includes(value) || rawStatus.includes(value)
    );
    const translatedCurrentStatus = String(
      this.translateStatus?.(statusEntity?.state || "") || statusEntity?.state || ""
    ).trim();

    for (const line of lines) {
      if (line.hidden) continue;
      const targetNode = line.querySelector('[data-role="mowing-live-target"]');
      const progressNode = line.querySelector('[data-role="mowing-live-progress"]');
      if (!targetNode || !progressNode) continue;

      const currentTarget = String(targetNode.textContent || "").trim();
      const displayedProgress = Number.parseFloat(progressNode.textContent);

      // While actually mowing, the original beta3 logic has the authoritative
      // target (full area, edge, dock edge, or the selected zone names).
      if (active && currentTarget && currentTarget !== translatedCurrentStatus) {
        writeTarget(this, currentTarget);
        continue;
      }

      // When a completed task remains latched at ~100%, replace the current
      // status fallback (e.g. Charging) with the last mowing target. For a
      // session that was already complete before this patch was loaded, use
      // Full area as a one-time safe fallback instead of showing Charging.
      if (finished && Number.isFinite(displayedProgress) && displayedProgress >= 95) {
        const savedTarget = readTarget(this);
        targetNode.textContent = savedTarget || this.t?.("fullArea") || "Full area";
      }
    }
  };

  Card.prototype.__anthbotMowingTargetPersistenceInstalled = true;
});
