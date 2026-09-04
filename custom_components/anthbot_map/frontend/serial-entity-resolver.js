// Multi-mower control/entity scoping for the clean model-split rebuild.
//
// The card keeps model/serial-scoped entity discovery for display/settings, but
// mower commands are sent directly through anthbot_map services. This mirrors
// the working Home Assistant Developer Tools action path and removes the
// button.press layer that could swallow or misroute commands in multi-mower
// installations.

const ANTHBOT_CONTROL_ROUTER_VERSION = "2026-09-04-control-v5";

const disableLegacyCommandRouter = () => {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const handler = window.__anthbotFeedbackClickHandler;
  if (typeof handler === "function") {
    document.removeEventListener("click", handler, true);
  }
};

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

    // Never jump from one mower's map to a sibling map merely because an entity
    // is temporarily unavailable. The configured map remains authoritative.
    proto.resolveMapEntityId = function () {
      return String(this.config?.entity || "");
    };

    // Serial first. Without serial metadata, use only this card's exact HA
    // duplicate ordinal. Never fall through to a different mower.
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
        if (!identity.serial) return null;

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
      };
    }

    // Every direct service call carries this card's mower serial. entity_id is
    // still supplied by the original callAnthbotService for compatibility.
    const originalCallAnthbotService = proto.callAnthbotService;
    if (typeof originalCallAnthbotService === "function") {
      proto.callAnthbotService = function (service, data = {}) {
        const identity = mapIdentity(this);
        return originalCallAnthbotService.call(
          this,
          service,
          identity.serial ? { ...data, serial_number: identity.serial } : { ...data },
        );
      };
    }

    // IMPORTANT: standard mower controls now bypass button.press entirely.
    // Home Assistant Developer Tools proves these anthbot_map services work;
    // sending them directly removes the unreliable frontend button indirection.
    const directServiceByCommand = {
      connect: "connect_cloud",
      start: "start_full_mow",
      stop: "stop_mow",
      dock: "return_to_dock",
      pause: "pause_mow",
      resume: "resume_mow",
      "outer-edge": "start_outer_edge_mow",
      "dock-edge": "start_dock_edge_mow",
      "reset-blade": "reset_blade_maintenance",
      "reset-camera": "reset_camera_maintenance",
      "reset-contact": "reset_dock_contact_maintenance",
    };

    const originalHandleCommand = proto.handleCommand;
    if (typeof originalHandleCommand === "function") {
      proto.handleCommand = async function (command) {
        disableLegacyCommandRouter();

        if (String(command).startsWith("reset-") && !window.confirm(this.t("resetCounterWarning"))) {
          return;
        }

        const customAction = typeof this.effectiveCustomButtonAction === "function"
          ? this.effectiveCustomButtonAction(command)
          : null;
        if (customAction) {
          await this.callCustomButtonAction(command, customAction);
          return;
        }

        const service = directServiceByCommand[command];
        if (service) {
          await this.callAnthbotService(service);
          return;
        }

        return originalHandleCommand.call(this, command);
      };
    }

    // Single-zone start follows the same direct service path. Multi-zone and
    // auto-zone methods in the card already call anthbot_map services directly.
    proto.startZone = async function (zone) {
      await this.callAnthbotService("start_zone_mow", {
        zones: String(zone?.id ?? zone?.name ?? ""),
      });
    };

    // calibration.js historically selected the first same-serial switch for
    // battery saver. Restrict it to the actual battery_saver_mode switch.
    const baseGetSwitchEntity = proto.getSwitchEntity;
    if (typeof baseGetSwitchEntity === "function") {
      window.setTimeout(() => {
        proto.getSwitchEntity = function (kind) {
          if (kind === "batterySaver") {
            const configured = this.config?.switches?.[kind];
            if (configured && isAvailable(this._hass?.states?.[configured])) {
              const identity = mapIdentity(this);
              const configuredSerial = serialOf(this._hass.states[configured]);
              if (!identity.serial || !configuredSerial || configuredSerial === identity.serial) {
                return configured;
              }
            }
            return this.findEntity("switch", ["battery_saver_mode", "battery saver mode"]);
          }
          return baseGetSwitchEntity.call(this, kind);
        };
        proto.__anthbotStrictBatterySaverResolver = true;
      }, 0);
    }

    proto.__anthbotUnifiedControlRouterVersion = ANTHBOT_CONTROL_ROUTER_VERSION;
    console.info(`[ANTHBOT] unified control router ${ANTHBOT_CONTROL_ROUTER_VERSION}`);
  });
}
