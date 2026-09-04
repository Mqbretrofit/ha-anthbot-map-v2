// Scope every automatically resolved entity/control to the mower represented by
// this card. Home Assistant adds _2, _3... to duplicate entity_ids; the old
// resolver stripped that ordinal and could mix Genie and M-series entities.

const anthbotCardFromEvent = (event) => {
  const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
  return path.find((node) => String(node?.tagName || "").toLowerCase() === "anthbot-map-card") || null;
};

const anthbotCommandFromEvent = (event) => {
  const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
  for (const node of path) {
    const command = node?.dataset?.command ?? node?.getAttribute?.("data-command");
    if (command) return String(command);
  }
  return "";
};

if (typeof window !== "undefined" && window.__anthbotScopedCommandCaptureInstalled !== true) {
  window.__anthbotScopedCommandCaptureInstalled = true;
  window.addEventListener("click", async (event) => {
    const command = anthbotCommandFromEvent(event);
    if (!new Set(["start", "pause", "resume"]).has(command)) return;
    const card = anthbotCardFromEvent(event);
    if (!card?._hass?.callService) return;
    if (card.effectiveCustomButtonAction?.(command)) return;

    const serial = String(
      card?.entity?.attributes?.serial_number
        ?? card?.entity?.attributes?.serial
        ?? "",
    ).trim();
    if (!serial) return;

    const service = {
      start: "start_full_mow",
      pause: "pause_mow",
      resume: "resume_mow",
    }[command];
    if (!service) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    try {
      card.notify?.(card.feedback?.("commandSentWaiting", card.commandLabel?.(service) || service));
      await card._hass.callService("anthbot_map", service, { serial_number: serial });
      card.scheduleRefresh?.(100);
    } catch (error) {
      console.error(`Anthbot ${service} failed`, error);
      card.notify?.(String(error?.message || error));
    }
  }, true);
}

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

        if (identity.base) {
          for (const suffix of wantedSuffixes) {
            const suffixSlug = normalize(suffix);
            if (!suffixSlug) continue;
            const exactId = `${domain}.${identity.base}_${suffixSlug}${identity.ordinal ? `_${identity.ordinal}` : ""}`;
            const exactState = states[exactId];
            if (exactState && exactState.state !== "unavailable") return exactId;
          }
        }

        return originalFindEntity.call(this, domain, suffixes);
      };
    }

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
