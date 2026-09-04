// Keep automatically resolved entities/controls scoped to the mower represented
// by this card. Command execution itself stays on the card's original beta3
// handleCommand()/button.press path; do not add a second global command router.

if (typeof customElements !== "undefined") {
  customElements.whenDefined("anthbot-map-card").then(() => {
    const Card = customElements.get("anthbot-map-card");
    const proto = Card?.prototype;
    if (!proto || proto.__anthbotSerialEntityResolverPatch === true) return;

    // The beta3 feedback capture handler stops propagation and runs a second,
    // global target resolver. That resolver is unsafe with two mowers because
    // HA's _2 suffix can cross devices. Remove only that global interception;
    // every command button already has the card-native click handler attached.
    const disableGlobalCommandCapture = () => {
      if (typeof document === "undefined" || typeof window === "undefined") return;
      const handler = window.__anthbotFeedbackClickHandler;
      if (handler) {
        document.removeEventListener("click", handler, true);
        window.__anthbotFeedbackClickHandler = null;
      }
    };
    queueMicrotask(disableGlobalCommandCapture);
    window.setTimeout(disableGlobalCommandCapture, 0);

    const normalize = (value) => String(value ?? "")
      .toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");

    const mapIdentity = (card) => {
      const entityId = String(card?._activeEntityId || card?.config?.entity || "");
      const local = entityId.replace(/^sensor\./, "");
      const match = local.match(/^(.*)_map(?:_(\d+))?$/);
      return {
        base: match?.[1] || card?.entityBase?.() || "",
        ordinal: match?.[2] || "",
        serial: String(
          card?.entity?.attributes?.serial_number
            ?? card?.entity?.attributes?.serial
            ?? "",
        ).trim(),
      };
    };

    const serialOf = (state) => String(
      state?.attributes?.serial_number ?? state?.attributes?.serial ?? "",
    ).trim();

    const originalFindEntity = proto.findEntity;
    if (typeof originalFindEntity === "function") {
      proto.findEntity = function (domain, suffixes) {
        const states = this._hass?.states || {};
        const identity = mapIdentity(this);
        const wantedSuffixes = Array.isArray(suffixes) ? suffixes : [];

        // Prefer an exact serial match. All Anthbot entities expose the mower
        // serial, so Genie and M9/M9 Pro cannot select one another's controls.
        if (identity.serial) {
          for (const suffix of wantedSuffixes) {
            const suffixSlug = normalize(suffix);
            const matches = Object.entries(states)
              .filter(([entityId, state]) =>
                entityId.startsWith(`${domain}.`)
                && state?.state !== "unavailable"
                && serialOf(state) === identity.serial,
              )
              .map(([entityId, state]) => {
                const idSlug = normalize(entityId.slice(domain.length + 1));
                const friendlySlug = normalize(state?.attributes?.friendly_name);
                let score = 0;
                if (idSlug.endsWith(`_${suffixSlug}`) || idSlug === suffixSlug) score = 1000;
                else if (idSlug.includes(suffixSlug)) score = 500;
                if (friendlySlug.includes(suffixSlug)) score += 100;
                return { entityId, score };
              })
              .filter((item) => item.score > 0)
              .sort((a, b) => b.score - a.score || a.entityId.localeCompare(b.entityId));
            if (matches.length) return matches[0].entityId;
          }
        }

        // Compatibility fallback: preserve the map entity's HA duplicate
        // ordinal (map -> unsuffixed controls, map_2 -> controls ending _2).
        if (identity.base) {
          for (const suffix of wantedSuffixes) {
            const suffixSlug = normalize(suffix);
            if (!suffixSlug) continue;
            const exactId = `${domain}.${identity.base}_${suffixSlug}${identity.ordinal ? `_${identity.ordinal}` : ""}`;
            const state = states[exactId];
            if (state && state.state !== "unavailable") return exactId;
          }
        }

        return originalFindEntity.call(this, domain, suffixes);
      };
    }

    // Keep direct anthbot_map service fallbacks on this card's current map
    // entity. The normal path remains button.press when a native button exists.
    const originalHandleCommand = proto.handleCommand;
    if (typeof originalHandleCommand === "function") {
      proto.handleCommand = async function (command) {
        const oldConfigEntity = this.config?.entity;
        if (this.config && this._activeEntityId) this.config.entity = this._activeEntityId;
        try {
          return await originalHandleCommand.call(this, command);
        } finally {
          if (this.config) this.config.entity = oldConfigEntity;
        }
      };
    }

    proto.__anthbotSerialEntityResolverPatch = true;
  });
}
