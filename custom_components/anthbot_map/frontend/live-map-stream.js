// ANTHBOT live-map transport v2.
//
// This patch deliberately leaves the proven card implementation untouched.
// It overlays high-frequency map/path/pose data received through a dedicated
// Home Assistant WebSocket subscription onto the compact Map entity metadata.
// If the backend marker is absent (for example after a downgrade), this file
// becomes a no-op and the legacy full-entity card path keeps working.

const ANTHBOT_LIVE_PROTOCOL = 2;
const ANTHBOT_LIVE_TYPE = "anthbot_map/subscribe_live";
const ANTHBOT_LIVE_RETRY_MIN_MS = 750;
const ANTHBOT_LIVE_RETRY_MAX_MS = 10000;

function baseMapEntity(card) {
  const entityId = card._activeEntityId || card.resolveMapEntityId?.() || card.config?.entity;
  return entityId && card._hass?.states ? card._hass.states[entityId] : null;
}

function liveStreamAvailable(card) {
  return baseMapEntity(card)?.attributes?.live_stream_available === true;
}

function cloneEntityWithLiveOverlay(card) {
  const base = baseMapEntity(card) || card.entity;
  if (!base) return null;
  const overlay = card._anthbotLiveOverlay;
  if (!overlay || typeof overlay !== "object") {
    card.entity = base;
    return base;
  }
  const merged = {
    ...base,
    attributes: {
      ...(base.attributes || {}),
      ...overlay,
    },
  };
  card.entity = merged;
  return merged;
}

function syncLiveCardFromHass(card) {
  const base = baseMapEntity(card);
  if (base) card.entity = base;
  cloneEntityWithLiveOverlay(card);
  card.updateRenderer?.();
}

function resetLiveState(card) {
  card._anthbotLiveOverlay = null;
  card._anthbotLivePath = null;
  card._anthbotLiveSequence = null;
}

function clearSubscriptionRetry(card) {
  if (card._anthbotLiveRetryTimer) {
    window.clearTimeout(card._anthbotLiveRetryTimer);
    card._anthbotLiveRetryTimer = null;
  }
}

function stopLiveSubscription(card) {
  card._anthbotLiveGeneration = (card._anthbotLiveGeneration || 0) + 1;
  const unsubscribe = card._anthbotLiveUnsubscribe;
  card._anthbotLiveUnsubscribe = null;
  card._anthbotLiveSubscribePromise = null;
  card._anthbotLiveSerial = null;
  if (typeof unsubscribe === "function") {
    try { unsubscribe(); } catch (_) { /* browser connection is already gone */ }
  }
}

function pathOverlay(card) {
  const live = card._anthbotLivePath;
  if (!live) return {};
  const points = live.points || [];
  const metadata = live.metadata || {};
  const definition = {
    ...metadata,
    path_id: live.pathId ?? metadata.path_id ?? null,
    point_count: points.length,
    _path_points: points,
  };
  if (Number.isInteger(live.startIndex)) {
    definition._m_series_first_index = live.startIndex;
  }
  if (Number.isInteger(live.endIndex)) {
    definition._m_series_last_index = live.endIndex;
  }
  return {
    path: points,
    cloud_path: points,
    cloudPath: points,
    mowed_path: points,
    trajectory: points,
    path_definition: definition,
    path_id: definition.path_id,
    path_start: metadata.start ?? null,
    path_task_type: metadata.task_type ?? null,
    path_point_count: points.length,
    path_coordinate_scale: metadata.coordinate_scale ?? null,
    path_first_point: points.length ? points[0] : null,
  };
}

function applyPathMessage(card, path) {
  if (!path || typeof path !== "object") return true;
  const op = String(path.op || "");
  const incoming = Array.isArray(path.points) ? path.points : [];

  if (op === "reset") {
    card._anthbotLivePath = {
      pathId: path.path_id ?? null,
      startIndex: Number.isInteger(path.start_index) ? path.start_index : null,
      endIndex: Number.isInteger(path.end_index) ? path.end_index : null,
      metadata: { ...(path.metadata || {}) },
      points: incoming.slice(),
    };
    return true;
  }

  if (op !== "append" || !card._anthbotLivePath) return false;
  const live = card._anthbotLivePath;
  if (
    path.path_id != null && live.pathId != null
    && String(path.path_id) !== String(live.pathId)
  ) {
    return false;
  }

  const windowStart = Number.isInteger(path.window_start_index)
    ? path.window_start_index
    : null;
  const appendFrom = Number.isInteger(path.append_from_index)
    ? path.append_from_index
    : null;

  if (windowStart !== null) {
    if (!Number.isInteger(live.startIndex)) return false;
    const trimCount = windowStart - live.startIndex;
    if (trimCount < 0 || trimCount > live.points.length) return false;
    if (trimCount) live.points = live.points.slice(trimCount);
    live.startIndex = windowStart;
    const expected = live.startIndex + live.points.length;
    if (appendFrom !== expected) return false;
  } else {
    if (Number.isInteger(live.startIndex)) return false;
    if (appendFrom !== live.points.length) return false;
  }

  if (incoming.length) live.points.push(...incoming);
  live.endIndex = Number.isInteger(path.end_index)
    ? path.end_index
    : (Number.isInteger(live.startIndex)
      ? live.startIndex + live.points.length - 1
      : null);
  live.metadata = { ...live.metadata, ...(path.metadata || {}) };
  if (path.path_id != null) live.pathId = path.path_id;
  return true;
}

function scheduleResubscribe(card, reason) {
  if (!card.isConnected) return;
  stopLiveSubscription(card);
  resetLiveState(card);
  card._anthbotLiveResyncTimer && window.clearTimeout(card._anthbotLiveResyncTimer);
  card._anthbotLiveResyncTimer = window.setTimeout(() => {
    card._anthbotLiveResyncTimer = null;
    ensureLiveSubscription(card);
  }, 100);
  if (reason && card._anthbotLiveLastResyncReason !== reason) {
    card._anthbotLiveLastResyncReason = reason;
    console.debug(`[ANTHBOT live-map] resync: ${reason}`);
  }
}

function scheduleSubscriptionRetry(card, reason) {
  if (!card.isConnected) return;
  clearSubscriptionRetry(card);
  const previous = Number(card._anthbotLiveRetryDelayMs);
  const delay = Number.isFinite(previous)
    ? Math.min(Math.max(previous, ANTHBOT_LIVE_RETRY_MIN_MS), ANTHBOT_LIVE_RETRY_MAX_MS)
    : ANTHBOT_LIVE_RETRY_MIN_MS;
  card._anthbotLiveRetryDelayMs = Math.min(delay * 2, ANTHBOT_LIVE_RETRY_MAX_MS);
  card._anthbotLiveRetryTimer = window.setTimeout(() => {
    card._anthbotLiveRetryTimer = null;
    if (!card.isConnected) return;
    ensureLiveSubscription(card);
  }, delay);
  if (reason && card._anthbotLiveLastRetryReason !== reason) {
    card._anthbotLiveLastRetryReason = reason;
    console.debug(`[ANTHBOT live-map] retry in ${delay} ms: ${reason}`);
  }
}

function markSubscriptionHealthy(card) {
  clearSubscriptionRetry(card);
  card._anthbotLiveRetryDelayMs = ANTHBOT_LIVE_RETRY_MIN_MS;
}

function lastMowingProgressStorageKey(card) {
  const entityId = String(card.config?.entity || card.entity?.entity_id || "default");
  return `anthbot-map-last-mowing-progress:${entityId}`;
}

function readLastMowingProgress(card) {
  try {
    const raw = window.localStorage.getItem(lastMowingProgressStorageKey(card));
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (_) {
    return null;
  }
}

function writeLastMowingProgress(card, value) {
  try {
    window.localStorage.setItem(lastMowingProgressStorageKey(card), JSON.stringify(value));
  } catch (_) { /* localStorage can be disabled */ }
}

function canonicalMowingIsActive(card) {
  const statusEntity = card.getRelatedEntity?.("status");
  const canonical = String(statusEntity?.state || "")
    .trim().toLowerCase().replace(/[_\s-]+/g, "");
  if (canonical) {
    return canonical === "mowing" || canonical.endsWith("mowing") || canonical.includes("mowing");
  }
  const raw = String(
    card.entity?.attributes?.robot_status_raw
    ?? statusEntity?.attributes?.robot_status_raw
    ?? ""
  ).trim().toLowerCase().replace(/[_\s-]+/g, "");
  return [
    "mowing", "zonemowing", "regionmowing", "globalmowing", "nestmowing",
    "edgemowing", "bordermowing", "pointmowing", "spotmowing",
  ].some((value) => raw.includes(value));
}

function stoppedMowingLabel(card) {
  const translated = String(card.t?.("mowedArea") || "").trim();
  return translated && translated !== "mowedArea" ? translated : "Mowed area";
}

function preserveStoppedMowingProgress(card) {
  const lines = Array.from(card.shadowRoot?.querySelectorAll?.('[data-role="mowing-live-line"]') || []);
  if (!lines.length) return;

  const progressEntity = card.getRelatedEntity?.("mowingProgress");
  const progress = Number(progressEntity?.state);
  const activeMowing = canonicalMowingIsActive(card);
  const visible = lines.find((line) => !line.hidden);
  const saved = readLastMowingProgress(card);
  const stoppedLabel = stoppedMowingLabel(card);

  if (visible) {
    const targetNode = visible.querySelector('[data-role="mowing-live-target"]');
    const progressNode = visible.querySelector('[data-role="mowing-live-progress"]');
    const displayedProgress = Number(String(progressNode?.textContent || "").replace("%", ""));
    if (!activeMowing && targetNode) targetNode.textContent = stoppedLabel;
    if (Number.isFinite(displayedProgress)) {
      writeLastMowingProgress(card, {
        target: activeMowing
          ? String(targetNode?.textContent || "").trim()
          : stoppedLabel,
        progress: displayedProgress,
      });
    }
    return;
  }

  // Starting a genuinely new task must never resurrect the previous task's
  // percentage while the new progress sensor is still warming up.
  if (activeMowing) return;

  const currentProgress = Number.isFinite(progress) && progress > 0
    ? Math.max(0, Math.min(100, progress))
    : NaN;
  const savedProgress = Number(saved?.progress);
  const displayProgress = Number.isFinite(currentProgress)
    ? currentProgress
    : savedProgress;
  if (!Number.isFinite(displayProgress)) return;

  lines.forEach((line) => {
    const targetNode = line.querySelector('[data-role="mowing-live-target"]');
    const progressNode = line.querySelector('[data-role="mowing-live-progress"]');
    if (!targetNode || !progressNode) return;
    targetNode.textContent = stoppedLabel;
    progressNode.textContent = `${Math.max(0, Math.min(100, displayProgress)).toFixed(1)}%`;
    line.hidden = false;
  });
}

function applyLiveMessage(card, message) {
  if (!message || Number(message.protocol) !== ANTHBOT_LIVE_PROTOCOL) {
    scheduleResubscribe(card, "protocol mismatch");
    return;
  }

  const kind = String(message.kind || "");
  const sequence = Number(message.sequence);
  if (!Number.isInteger(sequence) || sequence < 0) {
    scheduleResubscribe(card, "invalid sequence");
    return;
  }

  markSubscriptionHealthy(card);

  if (kind === "snapshot") {
    card._anthbotLiveOverlay = { ...(message.attributes || {}) };
    card._anthbotLiveSequence = sequence;
    if (!applyPathMessage(card, message.path)) {
      scheduleResubscribe(card, "invalid snapshot path");
      return;
    }
    Object.assign(card._anthbotLiveOverlay, pathOverlay(card));
    cloneEntityWithLiveOverlay(card);
    // A snapshot can introduce zone geometry used by controls created during
    // render(), so rebuild the card once. Subsequent trajectory deltas only
    // redraw the renderer and do not churn the DOM.
    card.render?.();
    return;
  }

  if (kind !== "delta") return;
  if (!Number.isInteger(card._anthbotLiveSequence)) {
    scheduleResubscribe(card, "delta before snapshot");
    return;
  }
  if (sequence !== card._anthbotLiveSequence + 1) {
    scheduleResubscribe(card, `sequence gap ${card._anthbotLiveSequence}->${sequence}`);
    return;
  }

  const attributes = message.attributes && typeof message.attributes === "object"
    ? message.attributes
    : {};
  if (!card._anthbotLiveOverlay) card._anthbotLiveOverlay = {};
  Object.assign(card._anthbotLiveOverlay, attributes);
  if (message.path && !applyPathMessage(card, message.path)) {
    scheduleResubscribe(card, "path continuity mismatch");
    return;
  }
  if (message.path) Object.assign(card._anthbotLiveOverlay, pathOverlay(card));
  card._anthbotLiveSequence = sequence;
  cloneEntityWithLiveOverlay(card);

  const geometryChanged = Object.prototype.hasOwnProperty.call(attributes, "area_definition")
    || Object.prototype.hasOwnProperty.call(attributes, "map_raster")
    || Object.prototype.hasOwnProperty.call(attributes, "ridable_areas");
  if (geometryChanged) card.render?.();
  else card.updateRenderer?.();
}

function ensureLiveSubscription(card) {
  const hass = card._hass;
  const base = baseMapEntity(card);
  const attributes = base?.attributes || {};

  // Critical downgrade/compatibility guard: a stale Lovelace resource must
  // never take over an integration version that still serves full map data
  // through the entity state.
  if (attributes.live_stream_available !== true) {
    clearSubscriptionRetry(card);
    if (card._anthbotLiveSerial || card._anthbotLiveUnsubscribe) {
      stopLiveSubscription(card);
      resetLiveState(card);
    }
    return;
  }

  const serial = attributes.serial_number;
  if (!serial || !hass?.connection?.subscribeMessage) return;
  if (
    card._anthbotLiveSerial === serial
    && (card._anthbotLiveUnsubscribe || card._anthbotLiveSubscribePromise)
  ) {
    return;
  }

  stopLiveSubscription(card);
  resetLiveState(card);
  const generation = card._anthbotLiveGeneration;
  card._anthbotLiveSerial = serial;
  const promise = hass.connection.subscribeMessage(
    (message) => {
      if (card._anthbotLiveGeneration !== generation || card._anthbotLiveSerial !== serial) return;
      applyLiveMessage(card, message);
    },
    { type: ANTHBOT_LIVE_TYPE, serial_number: serial },
  );
  card._anthbotLiveSubscribePromise = promise;
  Promise.resolve(promise)
    .then((unsubscribe) => {
      if (card._anthbotLiveGeneration !== generation || card._anthbotLiveSerial !== serial) {
        if (typeof unsubscribe === "function") unsubscribe();
        return;
      }
      card._anthbotLiveUnsubscribe = unsubscribe;
      card._anthbotLiveSubscribePromise = null;
      markSubscriptionHealthy(card);
    })
    .catch((error) => {
      if (card._anthbotLiveGeneration !== generation) return;
      card._anthbotLiveSubscribePromise = null;
      card._anthbotLiveUnsubscribe = null;
      console.warn("[ANTHBOT live-map] subscription failed", error);
      scheduleSubscriptionRetry(card, "subscription failed");
    });
}

customElements.whenDefined("anthbot-map-card").then(() => {
  const Card = customElements.get("anthbot-map-card");
  if (!Card || Card.prototype.__anthbotLiveMapStreamV2) return;
  const proto = Card.prototype;
  Object.defineProperty(proto, "__anthbotLiveMapStreamV2", { value: true });

  const originalStartRefreshTimer = proto.startRefreshTimer;
  if (typeof originalStartRefreshTimer === "function") {
    proto.startRefreshTimer = function patchedStartRefreshTimer(...args) {
      // Keep the proven lightweight presentation cadence alive. The patched
      // refreshEntities below turns live-mode ticks into local HA-state redraws
      // instead of homeassistant.update_entity calls.
      return originalStartRefreshTimer.apply(this, args);
    };
  }

  const originalRefreshEntityIds = proto.refreshEntityIds;
  if (typeof originalRefreshEntityIds === "function") {
    proto.refreshEntityIds = function patchedRefreshEntityIds(...args) {
      const ids = originalRefreshEntityIds.apply(this, args) || [];
      if (!liveStreamAvailable(this)) return ids;
      const mapEntityId = this._activeEntityId || this.resolveMapEntityId?.() || this.config?.entity;
      return ids.filter((entityId) => entityId && entityId !== mapEntityId);
    };
  }

  const originalRefreshEntities = proto.refreshEntities;
  if (typeof originalRefreshEntities === "function") {
    proto.refreshEntities = function patchedRefreshEntities(...args) {
      if (liveStreamAvailable(this)) {
        // Never turn the presentation timer back into cloud/coordinator I/O.
        // HA already pushes the related sensor states; simply re-read them and
        // redraw the card while the map/path/pose continue over WebSocket.
        syncLiveCardFromHass(this);
        return Promise.resolve();
      }
      return originalRefreshEntities.apply(this, args);
    };
  }

  const hassDescriptor = Object.getOwnPropertyDescriptor(proto, "hass");
  const originalHassSetter = hassDescriptor?.set;
  if (typeof originalHassSetter === "function") {
    Object.defineProperty(proto, "hass", {
      configurable: true,
      enumerable: hassDescriptor.enumerable,
      set(hass) {
        originalHassSetter.call(this, hass);
        cloneEntityWithLiveOverlay(this);
        this.updateMowingProgressStatus?.();
        ensureLiveSubscription(this);
      },
    });
  }

  const originalSetConfig = proto.setConfig;
  if (typeof originalSetConfig === "function") {
    proto.setConfig = function patchedSetConfig(config) {
      const previousEntity = this.config?.entity;
      if (previousEntity && previousEntity !== config?.entity) {
        clearSubscriptionRetry(this);
        stopLiveSubscription(this);
        resetLiveState(this);
      }
      return originalSetConfig.call(this, config);
    };
  }

  const originalRender = proto.render;
  if (typeof originalRender === "function") {
    proto.render = function patchedRender(...args) {
      cloneEntityWithLiveOverlay(this);
      return originalRender.apply(this, args);
    };
  }

  const originalUpdateRenderer = proto.updateRenderer;
  if (typeof originalUpdateRenderer === "function") {
    proto.updateRenderer = function patchedUpdateRenderer(...args) {
      cloneEntityWithLiveOverlay(this);
      return originalUpdateRenderer.apply(this, args);
    };
  }

  const originalUpdateMowingProgressStatus = proto.updateMowingProgressStatus;
  if (typeof originalUpdateMowingProgressStatus === "function") {
    proto.updateMowingProgressStatus = function patchedUpdateMowingProgressStatus(...args) {
      const result = originalUpdateMowingProgressStatus.apply(this, args);
      preserveStoppedMowingProgress(this);
      return result;
    };
  }

  const originalDisconnected = proto.disconnectedCallback;
  proto.disconnectedCallback = function patchedDisconnected(...args) {
    this._anthbotLiveResyncTimer && window.clearTimeout(this._anthbotLiveResyncTimer);
    this._anthbotLiveResyncTimer = null;
    clearSubscriptionRetry(this);
    stopLiveSubscription(this);
    resetLiveState(this);
    if (typeof originalDisconnected === "function") {
      return originalDisconnected.apply(this, args);
    }
    return undefined;
  };
});
