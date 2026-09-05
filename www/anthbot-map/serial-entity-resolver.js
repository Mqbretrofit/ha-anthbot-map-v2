// Multi-mower control/entity scoping for the clean model-split rebuild.
//
// Prefer explicit serial metadata whenever it exists. Older setting entities
// (notably number/switch) predate that metadata, so they may fall back only to
// the exact Home Assistant duplicate ordinal of this card's map entity. This
// keeps Genie / M-series isolated without making valid legacy settings vanish.

const ANTHBOT_CONTROL_ROUTER_VERSION = "2026-09-05-control-v11";

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

    // Treat Home Assistant's two no-data states as unavailable capabilities.
    // Keep valid falsy values such as 0 and "off" visible and usable.
    const isAvailable = (state) => {
      if (!state) return false;
      const value = String(state.state ?? "").trim().toLowerCase();
      return Boolean(value) && value !== "unavailable" && value !== "unknown";
    };

    const exactOrdinalEntity = (card, domain, suffix) => {
      const states = card?._hass?.states || {};
      const identity = mapIdentity(card);
      if (!identity.base) return null;
      const slug = normalize(suffix);
      if (!slug) return null;
      const entityId = `${domain}.${identity.base}_${slug}${identity.ordinal ? `_${identity.ordinal}` : ""}`;
      const state = states[entityId];
      if (!isAvailable(state)) return null;
      const candidateSerial = serialOf(state);
      if (candidateSerial && identity.serial && candidateSerial !== identity.serial) return null;
      return entityId;
    };

    // Never jump from one mower's configured map to another map entity.
    proto.resolveMapEntityId = function () {
      return String(this.config?.entity || "");
    };

    proto.findEntity = function (domain, suffixes) {
      const states = this._hass?.states || {};
      const identity = mapIdentity(this);
      const wanted = Array.isArray(suffixes) ? suffixes.filter(Boolean) : [];

      // First choice: explicit per-mower serial metadata.
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
      }

      // Legacy number/switch/select entities may have no serial attribute.
      // Fall back ONLY to the exact duplicate ordinal belonging to this map.
      for (const suffix of wanted) {
        const exact = exactOrdinalEntity(this, domain, suffix);
        if (exact) return exact;
      }
      return null;
    };

    // Resolve zone settings only for this exact mower and zone.
    proto.findZoneSettingEntity = function (domain, kind, zone, settingLabel) {
      const states = this._hass?.states || {};
      const identity = mapIdentity(this);
      if (!identity.serial) return null;
      const wantedKind = kind === "auto" ? "auto" : "manual";
      const wantedZoneId = zone?.id == null ? "" : String(zone.id);
      if (!wantedZoneId) return null;
      const key = {
        "mowing passes": "mow_count",
        "cutting height": "cutter_height",
        "obstacle sensitivity": "obstacle_avoid_level",
        "mowing direction": "mow_head",
        "visual obstacle detection": "visual_obstacle",
        "custom mowing direction": "custom_direction",
        "mowing mode": "mowing_mode",
      }[String(settingLabel || "").trim().toLowerCase()] || "";
      if (!key) return null;
      for (const [entityId, state] of Object.entries(states)) {
        if (!entityId.startsWith(`${domain}.`) || !state) continue;
        const stateValue = String(state.state ?? "").trim().toLowerCase();
        if (stateValue === "unavailable") continue;
        if (domain !== "select" && !isAvailable(state)) continue;
        if (serialOf(state) !== identity.serial) continue;
        const a = state.attributes || {};
        if (String(a.zone_kind || "").toLowerCase() !== wantedKind) continue;
        if (String(a.zone_id ?? "") !== wantedZoneId) continue;
        if (String(a.setting || "").toLowerCase() !== key) continue;
        return entityId;
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
          && (!identity.serial || !serialOf(state) || serialOf(state) === identity.serial),
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
          const candidateSerial = serialOf(states[explicit]);
          if (!identity.serial || !candidateSerial || candidateSerial === identity.serial) return explicit;
        }
        if (!identity.serial) return null;

        const zoneId = zone?.id === undefined || zone?.id === null ? "" : String(zone.id);
        const zoneName = normalize(zone?.name);
        const match = Object.entries(states).find(([entityId, state]) => {
          if (!entityId.startsWith("button.") || !isAvailable(state)) return false;
          const candidateSerial = serialOf(state);
          if (candidateSerial && candidateSerial !== identity.serial) return false;
          const attrs = state.attributes || {};
          const candidateId = attrs.id ?? attrs.zone_id;
          const candidateName = normalize(attrs.name || state.attributes?.friendly_name);
          return (zoneId && String(candidateId) === zoneId)
            || (zoneName && candidateName.includes(zoneName));
        });
        return match?.[0] || null;
      };
    }

    // Add the mower serial to every anthbot_map service call. Keep entity_id
    // too for backwards compatibility with the beta3 service handlers.
    const originalCallAnthbotService = proto.callAnthbotService;
    if (typeof originalCallAnthbotService === "function") {
      proto.callAnthbotService = async function (service, data = {}) {
        const identity = mapIdentity(this);
        const result = await originalCallAnthbotService.call(
          this,
          service,
          identity.serial ? { ...data, serial_number: identity.serial } : { ...data },
        );

        // Keep a few best-effort command confirmations for older Genie
        // firmware. Live Genie status itself is now pushed by the backend via
        // the same coordinator update path as M-series telemetry.
        for (const delay of [250, 700, 1400, 2500, 4500]) {
          window.setTimeout(() => {
            try {
              this.syncEntityAndRenderer?.();
              this.scheduleRefresh?.(0);
            } catch (_error) {
              // Refresh is best-effort; never turn a successful mower command
              // into a UI error.
            }
          }, delay);
        }
        return result;
      };
    }

    // Stop/Dock keep the proven beta3 command path. The dynamic primary tile
    // (Start/Pause/Resume) calls the native services directly.
    const originalPrimaryAction = proto.handlePrimaryMowingAction;
    if (typeof originalPrimaryAction === "function") {
      proto.handlePrimaryMowingAction = async function (action) {
        disableLegacyCommandRouter();

        const customAction = typeof this.effectiveCustomButtonAction === "function"
          ? this.effectiveCustomButtonAction(action)
          : null;
        if (customAction) {
          await this.callCustomButtonAction(action, customAction);
          return;
        }

        if (action === "pause") {
          await this.callAnthbotService("pause_mow");
          return;
        }
        if (action === "resume") {
          await this.callAnthbotService("resume_mow");
          return;
        }
        if (action !== "start") {
          return originalPrimaryAction.call(this, action);
        }

        const selected = this.selectedMowingTarget || { type: "full" };
        if (selected.type === "zone-set" && selected.zones?.length) {
          await this.callAnthbotService("start_zone_mow", {
            zones: selected.zones.map((zone) => zone.id ?? zone.name),
          });
          return;
        }
        if (selected.type === "auto-zone-set" && selected.zones?.length) {
          await this.callAnthbotService("start_auto_zone_mow", {
            auto_zones: selected.zones.map((zone) => zone.id ?? zone.name),
          });
          return;
        }
        if (selected.type === "edge") {
          await this.callAnthbotService("start_outer_edge_mow");
          return;
        }
        if (selected.type === "dock-edge") {
          await this.callAnthbotService("start_dock_edge_mow");
          return;
        }
        await this.callAnthbotService("start_full_mow");
      };
    }

    // Battery saver must never resolve to another same-serial switch such as
    // rain/obstacle control. Use its exact semantic suffix.
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

    // Every mower dashboard should expose only capabilities that currently
    // have real Home Assistant data. This is model-independent: Genie, M5,
    // M9 and M9 Pro all follow the same visibility rules.
    const emptyFragment = () => document.createDocumentFragment();
    const entityIdAvailable = (card, entityId) => isAvailable(card?._hass?.states?.[entityId]);

    const wrapEntityControl = (methodName, resolveEntityId) => {
      const original = proto[methodName];
      if (typeof original !== "function") return;
      proto[methodName] = function (...args) {
        const entityId = resolveEntityId.call(this, ...args);
        if (!entityIdAvailable(this, entityId)) return emptyFragment();
        return original.apply(this, args);
      };
    };

    wrapEntityControl("createMowHeightControl", function () {
      return this.getNumberEntity?.("mowHeight");
    });
    wrapEntityControl("createObstacleLevelControl", function () {
      return this.getNumberEntity?.("visualObstacleLevel");
    });
    wrapEntityControl("createNumberControl", function (_label, key) {
      return this.getNumberEntity?.(key);
    });
    wrapEntityControl("createSwitchControl", function (_label, key) {
      return this.getSwitchEntity?.(key);
    });
    wrapEntityControl("createInfoTile", function (_label, key) {
      const entity = this.getRelatedEntity?.(key);
      return entity?.entity_id;
    });
    wrapEntityControl("createDirectNumberControl", function (_label, entityId) {
      return entityId;
    });
    // A zone mowing-mode select may be `unknown` until mow_mode is reported.
    // Keep Normal/Efficient usable, but still hide a truly unavailable entity.
    const originalDirectSelect = proto.createDirectSelectControl;
    if (typeof originalDirectSelect === "function") {
      proto.createDirectSelectControl = function (...args) {
        const entityId = args[1];
        const state = this?._hass?.states?.[entityId];
        const stateValue = String(state?.state ?? "").trim().toLowerCase();
        if (!state || stateValue === "unavailable") return emptyFragment();
        return originalDirectSelect.apply(this, args);
      };
    }
    wrapEntityControl("createDirectSwitchControl", function (_label, entityId) {
      return entityId;
    });

    const originalDirectObstacle = proto.createDirectObstacleControl;
    if (typeof originalDirectObstacle === "function") {
      proto.createDirectObstacleControl = function (switchEntityId, levelEntityId) {
        if (!entityIdAvailable(this, switchEntityId) || !entityIdAvailable(this, levelEntityId)) {
          return emptyFragment();
        }
        return originalDirectObstacle.call(this, switchEntityId, levelEntityId);
      };
    }

    const maintenanceDefinitions = (card) => [
      [card.t("bladeMaintenance"), "blade", card.t("resetBlade"), "reset-blade", "cuttingComponentsLife"],
      [card.t("cameraMaintenance"), "camera", card.t("resetCamera"), "reset-camera", "cuttingLineLife"],
      [card.t("dockContactMaintenance"), "contact", card.t("resetDockContact"), "reset-contact", "rechargeContactLife"],
    ];

    const hasMaintenanceContent = (card) => maintenanceDefinitions(card)
      .some((item) => Boolean(card.getRelatedEntity?.(item[4])));

    const hasStatusContent = (card) => [
      "battery", "status", "charging", "connection", "cuttingHeight",
      "mowingArea", "mowingTime", "rtkFix", "totalArea", "errorDescription",
    ].some((key) => Boolean(card.getRelatedEntity?.(key)))
      || Boolean(card.getSwitchEntity?.("batterySaver"));

    const hasDiagnosticsContent = (card) => {
      const entityContent = [
        "cuttingComponentsLife", "cuttingLineLife", "rechargeContactLife",
        "wifi", "bluetooth", "firmware", "gpsLatitude", "gpsLongitude", "shadowUpdated",
      ].some((key) => Boolean(card.getRelatedEntity?.(key)));
      const attrs = card.entity?.attributes || {};
      const records = Array.isArray(attrs.mowing_records?.data)
        ? attrs.mowing_records.data
        : Array.isArray(attrs.mowing_records) ? attrs.mowing_records : [];
      const errors = Array.isArray(attrs.error_history) ? attrs.error_history : [];
      return entityContent || records.length > 0 || errors.length > 0;
    };

    const panelAvailable = (card, panel) => {
      if (panel === "maintenance") return hasMaintenanceContent(card);
      if (panel === "status") return hasStatusContent(card);
      if (panel === "diagnostics") return hasDiagnosticsContent(card);
      return true;
    };

    const syncPanelTabs = (card) => {
      card.shadowRoot?.querySelectorAll?.("button[data-panel]").forEach((button) => {
        const available = panelAvailable(card, button.dataset.panel);
        button.hidden = !available;
        button.style.display = available ? "" : "none";
      });
    };

    const removeEmptySettingSections = (card) => {
      if (card.activePanel !== "settings") return;
      card.shadowRoot?.querySelectorAll?.("details.zone-settings").forEach((details) => {
        const body = details.querySelector(".zone-settings-body");
        if (body && !body.querySelector(".panel-tile, button, input, select")) details.remove();
      });
      card.shadowRoot?.querySelectorAll?.("details.settings-section").forEach((details) => {
        if (details.dataset.settingsKey === "custom-button-actions") return;
        const body = details.querySelector(".settings-section-body");
        if (body && !body.querySelector(".panel-tile, button, input, select, details")) details.remove();
      });
    };

    const originalMaintenancePanel = proto.renderMaintenancePanel;
    if (typeof originalMaintenancePanel === "function") {
      proto.renderMaintenancePanel = function (body) {
        body.innerHTML = "";
        const grid = this.createPanelGrid();
        for (const [title, kind, resetLabel, command, entityKey] of maintenanceDefinitions(this)) {
          if (!this.getRelatedEntity?.(entityKey)) continue;
          grid.appendChild(this.createMaintenanceTile(title, kind, resetLabel, command));
        }
        if (grid.childElementCount) body.appendChild(grid);
      };
    }

    const originalRenderAppPanel = proto.renderAppPanel;
    if (typeof originalRenderAppPanel === "function") {
      proto.renderAppPanel = function (...args) {
        if (!panelAvailable(this, this.activePanel)) {
          this.activePanel = "control";
        }
        const result = originalRenderAppPanel.apply(this, args);
        removeEmptySettingSections(this);
        syncPanelTabs(this);
        return result;
      };
    }

    const availabilitySignature = (card) => {
      const identity = mapIdentity(card);
      const states = card?._hass?.states || {};
      if (identity.serial) {
        return Object.entries(states)
          .filter(([, state]) => serialOf(state) === identity.serial)
          .map(([entityId, state]) => `${entityId}:${isAvailable(state) ? "1" : "0"}`)
          .sort()
          .join("|");
      }
      return Object.entries(states)
        .filter(([entityId]) => entityId === identity.entityId || entityId === identity.configuredId)
        .map(([entityId, state]) => `${entityId}:${isAvailable(state) ? "1" : "0"}`)
        .sort()
        .join("|");
    };

    const originalUpdateRenderer = proto.updateRenderer;
    if (typeof originalUpdateRenderer === "function") {
      proto.updateRenderer = function (...args) {
        const result = originalUpdateRenderer.apply(this, args);
        const signature = availabilitySignature(this);
        if (signature !== this.__anthbotAvailabilitySignature) {
          const hadSignature = this.__anthbotAvailabilitySignature !== undefined;
          this.__anthbotAvailabilitySignature = signature;
          if (hadSignature && this.shadowRoot?.querySelector?.('[data-role="panel-body"]')) {
            this.renderAppPanel?.();
          } else {
            syncPanelTabs(this);
          }
        }
        return result;
      };
    }

    proto.__anthbotUnifiedControlRouterVersion = ANTHBOT_CONTROL_ROUTER_VERSION;
    console.info(`[ANTHBOT] unified control router ${ANTHBOT_CONTROL_ROUTER_VERSION}`);
  });
}
