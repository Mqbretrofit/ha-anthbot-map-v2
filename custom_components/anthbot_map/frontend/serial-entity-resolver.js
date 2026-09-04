// Scope every automatically resolved entity/control to the mower represented by
// this card. Home Assistant adds _2, _3... to duplicate entity_ids; the old
// resolver stripped that ordinal and could mix Genie and M-series entities.
if (typeof customElements !== "undefined") {
  customElements.whenDefined("anthbot-map-card").then(() => {
    const Card = customElements.get("anthbot-map-card");
    const proto = Card?.prototype;
    if (!proto || proto.__anthbotSerialEntityResolverPatch === true) return;

    const normalize = (value) => String(value ?? "")
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");

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
      state?.attributes?.serial_number
        ?? state?.attributes?.serial
        ?? "",
    ).trim();

    const originalFindEntity = proto.findEntity;
    if (typeof originalFindEntity === "function") {
      proto.findEntity = function (domain, suffixes) {
        const states = this._hass?.states || {};
        const identity = mapIdentity(this);
        const wantedSuffixes = Array.isArray(suffixes) ? suffixes : [];

        // 1) Strongest key: exact mower serial when the entity exposes it.
        if (identity.serial) {
          for (const suffix of wantedSuffixes) {
            const suffixSlug = normalize(suffix);
            const serialMatches = Object.entries(states)
              .filter(([entityId, state]) =>
                entityId.startsWith(`${domain}.`)
                && state?.state !== "unavailable"
                && serialOf(state) === identity.serial,
              )
              .map(([entityId, state]) => {
                const idSlug = normalize(entityId.slice(domain.length + 1));
                const friendlySlug = normalize(state?.attributes?.friendly_name);
                let score = 0;
                if (idSlug.endsWith(`_${suffixSlug}`)) score = 1000;
                else if (idSlug.includes(suffixSlug)) score = 500;
                if (friendlySlug.includes(suffixSlug)) score += 100;
                return { entityId, score };
              })
              .filter((item) => item.score > 0)
              .sort((a, b) => b.score - a.score || a.entityId.localeCompare(b.entityId));
            if (serialMatches.length) return serialMatches[0].entityId;
          }
        }

        // 2) Preserve the HA duplicate ordinal of the map entity. map -> no
        // suffix; map_2 -> related entity _2; map_3 -> related entity _3, etc.
        if (identity.base) {
          for (const suffix of wantedSuffixes) {
            const suffixSlug = normalize(suffix);
            if (!suffixSlug) continue;
            const exactId = `${domain}.${identity.base}_${suffixSlug}${identity.ordinal ? `_${identity.ordinal}` : ""}`;
            const exactState = states[exactId];
            if (exactState && exactState.state !== "unavailable") return exactId;

            const escapedBase = identity.base.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            const escapedSuffix = suffixSlug.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            const ordinal = identity.ordinal
              ? `_${identity.ordinal}`
              : "";
            const pattern = new RegExp(`^${domain}\\.${escapedBase}_${escapedSuffix}${ordinal}$`);
            const exact = Object.entries(states)
              .find(([entityId, state]) => pattern.test(entityId) && state?.state !== "unavailable");
            if (exact) return exact[0];
          }
        }

        // Compatibility fallback for old/single-mower installations.
        return originalFindEntity.call(this, domain, suffixes);
      };
    }

    // Service handlers already target the resolved button entity where one
    // exists. With findEntity fixed, pause/resume/start/stop/dock now stay on
    // the same mower. For direct domain services, keep the active map entity
    // as the target instead of a stale configured fallback.
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
