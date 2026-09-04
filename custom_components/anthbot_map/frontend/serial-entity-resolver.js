// Multi-mower control/entity scoping for the clean model-split rebuild.
//
// Keep the proven beta3 card handlers as the single command path. The old
// document-level feedback router duplicates command dispatch and can select a
// sibling mower when Home Assistant appends _2/_3 to duplicate entity IDs.
// Remove that router and scope every automatic lookup to this card's mower.

const ANTHBOT_CONTROL_ROUTER_VERSION = "2026-09-04-control-v3";

const disableLegacyCommandRouter = () => {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const handler = window.__anthbotFeedbackClickHandler;
  if (typeof handler === "function") {
    document.removeEventListener("click", handler, true);
  }
};

// This module is imported while anthbot-map-card.js is still evaluating, while
// the legacy handler is registered near the end of that file. Keep removing it
// for a short grace period so load-order timing cannot resurrect it.
if (typeof window !== "undefined" && typeof document !== "undefined") {
  disableLegacyCommandRouter();
  const removalTimer = window.setInterval(disableLegacyCommandRouter, 25);
  for (const delay of [0, 50, 100, 250, 500, 1000, 2000]) {
    window.setTimeout(disableLegacyCommandRouter, delay);
  }
  window.setTimeout(() => window.clearInterval(removalTimer), 2500);
  window.addEventListener("pageshow", disableLegacyCommandRouter);
}

if (typeof customElements !== "undefined") {
  customElements.whenDefined("anthbot-map-card").then(() => {
    disableLegacyCommandRouter();

    const Card = customElements.get("anthbot-map-card");
    const proto = Card?.prototype;
    if (!proto || proto.__anthbotUnifiedControlRouterVersion === ANTHBOT_CONTROL_ROUTER_VERSION) return;

    const normalize = (value) => String(value ?? "")
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");

    const serialOf = (state) => String(
      state?.attributes?.serial_number
        ?? state?.attributes?.serial
        ?? "",
    ).trim();

    const mapIdentity = (card) => {
      const states = card?._hass?.states || {};
      const entityId = String(card?._activeEntityId || card?.config?.entity || "");
      const configuredId = String(card?.config?.entity || entityId);
      const local = entityId.replace(/^sensor\./, "");
      const configuredLocal = configuredId.replace(/^sensor\./, "");
      const match = local.match(/^(.*)_map(?:_(\d+))?$/)
        || configuredLocal.match(/^(.*)_map(?:_(\d+))?$/);
      const state = states[entityId] || states[configuredId] || card?.entity;
      return {
        entityId,
        configuredId,
        base: match?.[1] || "",
        ordinal: match?.[2] || "",
        serial: serialOf(state) || serialOf(card?.entity),
      };
    };

    const isAvailable = (state) => Boolean(state && state.state !== "unavailable");

    // Never jump from sensor.foo_map to sensor.foo_map_2 (or back) simply
    // because one mower is briefly unavailable. A missing mower is safer than
    // controlling the wrong mower.
    proto.resolveMapEntityId = function () {
      const configured = String(this.config?.entity || "");
      if (!configured) return configured;
      return configured;
    };

    // Serial first. If serial metadata is not available yet, use only the exact
    // Home Assistant ordinal belonging to this map card. Never fall back to a
    // different ordinal or a global friendly-name match.
    proto.findEntity = function (domain, suffixes) {
      const states = this._hass?.states || {};
      const identity = mapIdentity(this);
      const wanted = Array.isArray(suffixes) ? suffixes.filter(Boolean) : [];

      if (identity.serial) {
        for (const suffix of wanted) {
          const suffixSlug = normalize(suffix);
          const matches = Object.entries(states)
            .filter(([entityId, state]) =>
              entityId.startsWith(`${domain}.`)
              && isAvailable(state)
              && serialOf(state) === identity.serial,
            )
            .map(([entityId, state]) => {
              const idSlug = normalize(entityId.slice(domain.length + 1));
              const friendlySlug = normalize(state?.attributes?.friendly_name);
              let score = 0;
              if (idSlug.endsWith(`_${suffixSlug}`) || idSlug === suffixSlug) score = 1000;
              else if (idSlug.includes(`_${suffixSlug}_`)) score = 900;
              else if (idSlug.includes(suffixSlug)) score = 500;
              if (friendlySlug.includes(suffixSlug)) score += 100;
              return { entityId, score };
            })
            .filter((item) => item.score > 0)
            .sort((a, b) => b.score - a.score || a.entityId.localeCompare(b.entityId));
          if (matches.length) return matches[0].entityId;
        }
        return null;
      }

      if (!identity.base) return null;
      for (const suffix of wanted) {
        const suffixSlug = normalize(suffix);
        if (!suffixSlug) continue;
        const exact = `${domain}.${identity.base}_${suffixSlug}${identity.ordinal ? `_${identity.ordinal}` : ""}`;
        if (isAvailable(states[exact])) return exact;
      }
      return null;
    };

    // Zone fallback also needs serial scoping. This is used when area geometry
    // is temporarily absent and the card rebuilds tiles from HA button entities.
    proto.discoverZoneButtons = function () {
      const states = this._hass?.states || {};
      const identity = mapIdentity(this);
      return Object.entries(states)
        .filter(([entityId, state]) =>
          entityId.startsWith("button.")
          && isAvailable(state)
          && (!identity.serial || serialOf(state) === identity.serial),
        )
        .map(([entityId, state]) => {
          const attrs = state.attributes || {};
          const zoneId = attrs.id ?? attrs.zone_id;
          const zoneType = attrs.zone_type ?? attrs.zone_kind;
          if (zoneId === undefined || zoneId === null || !zoneType) return null;
          return {
            id: Number.isFinite(Number(zoneId)) ? Number(zoneId) : zoneId,
            name: attrs.name || state.attributes?.friendly_name || `Zone ${zoneId}`,
            entity_id: entityId,
          };
        })
        .filter(Boolean)
        .sort((left, right) => Number(left.id) - Number(right.id));
    };

    const originalGetZoneButtonEntity = proto.getZoneButtonEntity;
    if (typeof originalGetZoneButtonEntity === "function") {
      proto.getZoneButtonEntity = function (zone) {
        const states = this._hass?.states || {};
        const identity = mapIdentity(this);
        const explicit = zone?.entity_id
          || this.config?.zoneButtons?.[zone?.id]
          || this.config?.zoneButtons?.[zone?.name];
        if (explicit && isAvailable(states[explicit])) {
          const serial = serialOf(states[explicit]);
          if (!identity.serial || !serial || serial === identity.serial) return explicit;
        }

        if (identity.serial) {
          const zoneId = zone?.id === undefined || zone?.id === null ? "" : String(zone.id);
          const zoneName = normalize(zone?.name);
          const match = Object.entries(states).find(([entityId, state]) => {
            if (!entityId.startsWith("button.") || !isAvailable(state)) return false;
            if (serialOf(state) !== identity.serial) return false;
            const attrs = state.attributes || {};
            const candidateId = attrs.id ?? attrs.zone_id;
            const candidateName = normalize(attrs.name || state.attributes?.friendly_name);
            return (zoneId && String(candidateId) === zoneId)
              || (zoneName && candidateName.includes(zoneName));
          });
          return match?.[0] || null;
        }
        return null;
      };
    }

    // All direct anthbot_map service fallbacks carry the serial too. entity_id
    // remains present for compatibility, but serial_number is authoritative in
    // multi-mower accounts.
    const originalCallAnthbotService = proto.callAnthbotService;
    if (typeof originalCallAnthbotService === "function") {
      proto.callAnthbotService = function (service, data = {}) {
        const identity = mapIdentity(this);
        const scopedData = identity.serial
          ? { ...data, serial_number: identity.serial }
          : { ...data };
        return originalCallAnthbotService.call(this, service, scopedData);
      };
    }

    // Keep the original beta3 handleCommand()/button.press behavior. Its
    // automatic button lookup now resolves only this mower because findEntity
    // is serial-scoped above.
    const originalHandleCommand = proto.handleCommand;
    if (typeof originalHandleCommand === "function") {
      proto.handleCommand = async function (command) {
        disableLegacyCommandRouter();
        return originalHandleCommand.call(this, command);
      };
    }

    proto.__anthbotUnifiedControlRouterVersion = ANTHBOT_CONTROL_ROUTER_VERSION;
    console.info(`[ANTHBOT] unified control router ${ANTHBOT_CONTROL_ROUTER_VERSION}`);
  });
}
