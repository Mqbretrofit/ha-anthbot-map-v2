// Keep every dashboard control/status bound to the mower represented by its map entity.
// This prevents _map / _map_2 Home Assistant entity-id suffixes from crossing devices.
if (typeof customElements !== "undefined") {
  customElements.whenDefined("anthbot-map-card").then(() => {
    const Card = customElements.get("anthbot-map-card");
    const proto = Card?.prototype;
    if (!proto || proto.__anthbotSerialEntityResolverPatch === true) return;

    const RELATED = {
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
    const NUMBERS = {
      mowHeight: ["mow_height", "mow_height_setting", "mow height"],
      mowCount: ["mow_count", "mow_count_setting", "mowing passes"],
      visualObstacleLevel: ["visual_obstacle_level", "visual_obstacle_level_setting", "visual obstacle sensitivity"],
      mowDirection: ["custom_mowing_direction", "custom_mowing_direction_setting", "custom mowing direction"],
      rainContinue: ["rain_continue_time", "rain_continue_time_setting", "rain continue time"],
      voiceVolume: ["voice_volume", "voice_volume_setting", "voice volume"],
    };
    const SWITCHES = {
      rain: ["rain_perception", "rain_perception_enabled", "rain perception"],
      visualObstacle: ["visual_obstacle_detection", "visual_obstacle_detection_enabled", "visual obstacle detection"],
      customDirection: ["custom_mowing_direction_enabled", "custom mowing direction"],
      edgeReturn: ["edge_following_return_enabled", "edge-following return"],
      autoDockMow: ["automatic_dock_mowing_enabled", "automatic dock-area mowing"],
      batterySaver: ["battery_saver_mode", "battery saver mode"],
    };

    const normalize = (value) => String(value ?? "")
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");

    const mowerSerial = (card) => String(
      card?.entity?.attributes?.serial_number
        ?? card?.entity?.attributes?.serial
        ?? "",
    ).trim();

    const resolve = (card, domain, suffixes) => {
      const serial = mowerSerial(card);
      if (!serial || !card?._hass?.states) return null;
      const wanted = (suffixes || []).map(normalize).filter(Boolean);
      const matches = [];
      for (const [entityId, state] of Object.entries(card._hass.states)) {
        if (!entityId.startsWith(`${domain}.`) || state?.state === "unavailable") continue;
        const candidateSerial = String(
          state?.attributes?.serial_number
            ?? state?.attributes?.serial
            ?? "",
        ).trim();
        if (candidateSerial !== serial) continue;
        const idSlug = normalize(entityId.slice(domain.length + 1));
        const friendlySlug = normalize(state?.attributes?.friendly_name);
        let score = 0;
        for (const suffix of wanted) {
          if (idSlug.endsWith(`_${suffix}`) || idSlug === suffix) score = Math.max(score, 100 + suffix.length);
          else if (idSlug.includes(suffix)) score = Math.max(score, 50 + suffix.length);
          if (friendlySlug.includes(suffix)) score = Math.max(score, 25 + suffix.length);
        }
        if (score > 0 || wanted.length === 0) matches.push({ entityId, state, score });
      }
      matches.sort((a, b) => b.score - a.score || a.entityId.localeCompare(b.entityId));
      return matches[0] || null;
    };

    const originalRelated = proto.getRelatedEntity;
    if (typeof originalRelated === "function") {
      proto.getRelatedEntity = function (kind) {
        const configured = this.config?.entities?.[kind];
        if (this.isEntityAvailable?.(configured)) return this._hass.states[configured];
        const descriptor = RELATED[kind];
        if (descriptor) {
          const found = resolve(this, descriptor[0], descriptor[1]);
          if (found) return found.state;
        }
        return originalRelated.call(this, kind);
      };
    }

    const originalNumber = proto.getNumberEntity;
    if (typeof originalNumber === "function") {
      proto.getNumberEntity = function (kind) {
        const configured = this.config?.numbers?.[kind];
        if (this.isEntityAvailable?.(configured)) return configured;
        const found = resolve(this, "number", NUMBERS[kind] || []);
        if (found) return found.entityId;
        return originalNumber.call(this, kind);
      };
    }

    const originalSwitch = proto.getSwitchEntity;
    if (typeof originalSwitch === "function") {
      proto.getSwitchEntity = function (kind) {
        const configured = this.config?.switches?.[kind];
        if (this.isEntityAvailable?.(configured)) return configured;
        const found = resolve(this, "switch", SWITCHES[kind] || []);
        if (found) return found.entityId;
        return originalSwitch.call(this, kind);
      };
    }

    proto.__anthbotSerialEntityResolverPatch = true;
  });
}
