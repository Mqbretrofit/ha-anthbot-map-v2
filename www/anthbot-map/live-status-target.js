// Keep the beta3 live mowing status tied to the map's own mower.
//
// Home Assistant appends _2/_3 to duplicate entity ids. The beta3 card removes
// the map suffix when it builds the common entity base, so with multiple Anthbot
// mowers it can accidentally resolve the other mower's mowing_progress/status
// entity. Every integration entity already exposes serial_number, therefore use
// that stable device identity before falling back to the original beta3 lookup.

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

const RELATED_ENTITY_MAP = {
  battery: ["sensor", ["battery_level"]],
  status: ["sensor", ["mower_status"]],
  charging: ["binary_sensor", ["charging"]],
  connection: ["binary_sensor", ["connection"]],
  cuttingHeight: ["sensor", ["cutting_height"]],
  mowingArea: ["sensor", ["mowing_area_session", "mowing_area"]],
  mowingProgress: ["sensor", ["mowing_progress", "mowing_progress_test"]],
  mowingTime: ["sensor", ["mowing_time_session", "mowing_time"]],
  rtkFix: ["sensor", ["rtk_fix_state"]],
  totalArea: ["sensor", ["total_mapped_area"]],
  errorDescription: ["sensor", ["error_description"]],
  cuttingComponentsLife: ["sensor", ["cutting_components_life"]],
  cuttingLineLife: ["sensor", ["cutting_line_life"]],
  rechargeContactLife: ["sensor", ["recharge_contact_life"]],
  wifi: ["binary_sensor", ["wifi_connected"]],
  bluetooth: ["binary_sensor", ["bluetooth_active"]],
  firmware: ["sensor", ["firmware_version"]],
  gpsLatitude: ["sensor", ["gps_latitude"]],
  gpsLongitude: ["sensor", ["gps_longitude"]],
  poseYaw: ["sensor", ["pose_yaw"]],
  shadowUpdated: ["sensor", ["shadow_last_updated"]],
};

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[_\s-]+/g, "");
}

function slug(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
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

function scopedRelatedEntity(card, kind) {
  const spec = RELATED_ENTITY_MAP[kind];
  const serial = String(card?.entity?.attributes?.serial_number || "").trim();
  if (!spec || !serial || !card?._hass?.states) return null;

  const [domain, suffixes] = spec;
  const candidates = Object.entries(card._hass.states)
    .filter(([entityId, state]) =>
      entityId.startsWith(`${domain}.`)
      && state?.state !== "unavailable"
      && String(state?.attributes?.serial_number || "") === serial
    );

  for (const suffix of suffixes) {
    const suffixSlug = slug(suffix);
    const match = candidates.find(([entityId, state]) => {
      const entitySlug = slug(entityId.slice(domain.length + 1));
      const friendlySlug = slug(state?.attributes?.friendly_name);
      return entitySlug.endsWith(`_${suffixSlug}`)
        || entitySlug.includes(`_${suffixSlug}_`)
        || friendlySlug.endsWith(`_${suffixSlug}`)
        || friendlySlug.includes(suffixSlug);
    });
    if (match) return match[1];
  }
  return null;
}

function rememberedTaskTarget(card, progressEntity) {
  const task = card?.entity?.attributes?.last_mowing_task;
  const type = String(task?.type || "");
  if (!type) return "";

  if (type === "full") return card.t?.("fullArea") || "Full area";
  if (type === "edge") return card.t?.("commandOuterEdge") || "Outer edge";
  if (type === "dock_edge") return card.t?.("dockEdgeLabel") || "Dock edge";

  if (type === "manual_zone") {
    const rawIds = task?.data?.id;
    const ids = (Array.isArray(rawIds) ? rawIds : rawIds == null ? [] : [rawIds]).map(String);
    if (!ids.length) return "";

    const debugZones = Array.isArray(progressEntity?.attributes?.zones_debug)
      ? progressEntity.attributes.zones_debug
      : [];
    const names = new Map(
      debugZones
        .filter((zone) => zone?.id !== undefined && zone?.id !== null)
        .map((zone) => [String(zone.id), String(zone.name || "").trim()])
    );
    try {
      for (const zone of card.currentZones?.() || []) {
        if (zone?.id !== undefined && zone?.id !== null) {
          names.set(String(zone.id), String(zone.name || "").trim());
        }
      }
    } catch (_error) {}

    return ids.map((id) => names.get(id) || `${card.t?.("zone") || "Zone"} ${id}`).join(" + ");
  }

  return "";
}

customElements.whenDefined("anthbot-map-card").then(() => {
  const Card = customElements.get("anthbot-map-card");
  if (!Card) return;

  if (!Card.prototype.__anthbotSerialEntityScopeInstalled) {
    const originalGetRelatedEntity = Card.prototype.getRelatedEntity;
    if (typeof originalGetRelatedEntity === "function") {
      Card.prototype.getRelatedEntity = function (kind) {
        const original = originalGetRelatedEntity.call(this, kind);
        const serial = String(this?.entity?.attributes?.serial_number || "").trim();
        if (!serial) return original;
        if (String(original?.attributes?.serial_number || "") === serial) return original;
        return scopedRelatedEntity(this, kind) || original;
      };
      Card.prototype.__anthbotSerialEntityScopeInstalled = true;
    }
  }

  if (Card.prototype.__anthbotMowingTargetPersistenceInstalled) return;
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

      if (active && currentTarget && currentTarget !== translatedCurrentStatus) {
        writeTarget(this, currentTarget);
        continue;
      }

      if (finished && Number.isFinite(displayedProgress) && displayedProgress >= 95) {
        const remembered = rememberedTaskTarget(this, progressEntity);
        const savedTarget = readTarget(this);
        const target = remembered || savedTarget;
        if (target) {
          targetNode.textContent = target;
          writeTarget(this, target);
        }
      }
    }
  };

  Card.prototype.__anthbotMowingTargetPersistenceInstalled = true;
});