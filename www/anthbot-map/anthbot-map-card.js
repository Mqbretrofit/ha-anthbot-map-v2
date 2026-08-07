import { AnthbotMapRenderer } from "./renderer.js?v=140";
import { LANGUAGES, resolveLanguage, translate } from "./i18n.js?v=138";
import {
  adjustCalibration,
  cardToYaml,
  readCalibration,
  readDecodedBoundaryCalibration,
  readRobotCalibration,
  resetCalibration,
} from "./calibration.js?v=138";

const ENTITY_MAP = {
  battery: ["sensor", ["battery_level"]],
  status: ["sensor", ["mower_status"]],
  charging: ["binary_sensor", ["charging"]],
  connection: ["binary_sensor", ["connection"]],
  cuttingHeight: ["sensor", ["cutting_height"]],
  mowingArea: ["sensor", ["mowing_area_session", "mowing_area"]],
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

const NUMBER_MAP = {
  mowHeight: ["mow_height", "mow_height_setting", "mow height"],
  mowDirection: ["custom_mowing_direction", "custom_mowing_direction_setting", "custom mowing direction"],
  rainContinue: ["rain_continue_time", "rain_continue_time_setting", "rain continue time"],
  voiceVolume: ["voice_volume", "voice_volume_setting", "voice volume"],
};

const SWITCH_MAP = {
  rain: ["rain_perception", "rain_perception_enabled", "rain perception"],
  customDirection: ["custom_mowing_direction_enabled", "custom mowing direction"],
};

class AnthbotMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.config = {};
    this.entity = null;
    this.calibration = resetCalibration();
    this.robotCalibration = resetCalibration();
    this.decodedBoundaryCalibration = resetCalibration();
    this.renderer = null;
    this.activePanel = "control";
    this.refreshTimer = null;
    this.refreshInFlight = false;
    this.mapExpanded = false;
    this.showDecodedBoundary = true;
    this.showZones = true;
    this.showNoGoZones = true;
    this.showNoGoLabels = true;
    this.mapOverlayOverrides = {};
    this.mapOnly = false;
    this.themeBackground = false;
    this.transparentBackground = false;
    this.glassBackground = false;
    this.optimisticSettings = new Map();
    this.commandConfirmationToken = 0;
    this.suppressMapExpandClickUntil = 0;
    this.selectedLanguage = "auto";
    this.languageOverride = false;
    this.floatingMenuOpen = false;
  }

  setConfig(config) {
    if (!config?.entity) {
      throw new Error("Anthbot map card requires an entity");
    }

    this.config = config;
    const savedInterface = this.readInterfaceSettings(config.entity);
    this.mapOnly = typeof config.map_only === "boolean"
      ? config.map_only
      : typeof config.mapOnly === "boolean" ? config.mapOnly : Boolean(savedInterface.mapOnly);
    this.themeBackground = typeof config.theme_background === "boolean"
      ? config.theme_background
      : typeof config.themeBackground === "boolean"
        ? config.themeBackground
        : Boolean(savedInterface.themeBackground);
    this.transparentBackground = typeof config.transparent_background === "boolean"
      ? config.transparent_background
      : typeof config.transparentBackground === "boolean"
        ? config.transparentBackground
        : Boolean(savedInterface.transparentBackground);
    this.glassBackground = typeof config.glass_background === "boolean"
      ? config.glass_background
      : typeof config.glassBackground === "boolean"
        ? config.glassBackground
        : Boolean(savedInterface.glassBackground);
    this.languageOverride = savedInterface.languageOverride === true;
    this.selectedLanguage = this.languageOverride
      ? savedInterface.language || "auto"
      : config.language
        || savedInterface.language
        || window.localStorage.getItem("anthbot-map-language")
        || "auto";
    this.stopRefreshTimer();
    window.clearTimeout(this.pendingRefreshTimer);
    this.calibration = readCalibration(config);
    this.robotCalibration = readRobotCalibration(config);
    this.decodedBoundaryCalibration = readDecodedBoundaryCalibration(config);
    this.mapOverlayOverrides = savedInterface.mapOverlayOverrides && typeof savedInterface.mapOverlayOverrides === "object"
      ? { ...savedInterface.mapOverlayOverrides }
      : {};
    const overlaySetting = (key, snakeKey, camelKey) => {
      if (this.mapOverlayOverrides[key] === true && typeof savedInterface[key] === "boolean") {
        return savedInterface[key];
      }
      if (typeof config[snakeKey] === "boolean") {
        return config[snakeKey];
      }
      if (typeof config[camelKey] === "boolean") {
        return config[camelKey];
      }
      return true;
    };
    this.showDecodedBoundary = overlaySetting("showDecodedBoundary", "show_decoded_boundary", "showDecodedBoundary");
    this.showZones = overlaySetting("showZones", "show_zones", "showZones");
    this.showNoGoZones = overlaySetting("showNoGoZones", "show_no_go_zones", "showNoGoZones");
    this.showNoGoLabels = overlaySetting("showNoGoLabels", "show_no_go_labels", "showNoGoLabels");
    this.render();
  }

  set hass(hass) {
    const previousLanguage = this.language;
    this._hass = hass;
    this.entity = hass.states[this.config.entity];
    this.startRefreshTimer();
    if (previousLanguage !== this.language) {
      this.render();
    } else {
      this.updateRenderer();
    }
  }

  get language() {
    return resolveLanguage(this.selectedLanguage, this._hass);
  }

  t(key) {
    return translate(this.language, key);
  }

  disconnectedCallback() {
    this.stopRefreshTimer();
    window.clearTimeout(this.pendingRefreshTimer);
    this.resizeObserver?.disconnect();
    this.renderer?.destroy();
    this.renderer = null;
  }

  getCardSize() {
    return 8;
  }

  render() {
    const root = this.shadowRoot;
    const mapOnly = this.mapOnly;
    const themeBackground = this.themeBackground;
    const transparentBackground = this.transparentBackground;
    const glassBackground = this.glassBackground;
    const cardClasses = [
      mapOnly ? "map-only" : "",
      themeBackground ? "theme-background" : "",
      glassBackground ? "glass-background" : "",
      transparentBackground ? "transparent-background" : "",
    ]
      .filter(Boolean)
      .join(" ");
    root.innerHTML = `
      <ha-card class="${cardClasses}">
        <link rel="stylesheet" href="${this.resolveAsset("styles.css?v=138")}">
        <style>
          .anthbot-menu-toggle { position:absolute; z-index:40; min-height:46px; padding:9px 15px; border:1px solid rgba(255,255,255,.38); border-radius:999px; background:rgba(10,18,26,.48); color:#fff; backdrop-filter:blur(10px); box-shadow:0 8px 28px rgba(0,0,0,.26); font:inherit; font-weight:800; cursor:pointer; }
          .anthbot-menu-toggle { right:14px; bottom:14px; }
          .anthbot-glass-panel { display:none; position:absolute; z-index:39; right:12px; bottom:70px; width:min(920px,calc(100% - 24px)); max-height:calc(100% - 84px); overflow:auto; border:1px solid rgba(255,255,255,.34); border-radius:18px; background:rgba(9,18,27,.18); color:#fff; backdrop-filter:blur(10px) saturate(115%); box-shadow:0 16px 44px rgba(0,0,0,.24); overscroll-behavior:contain; }
          .anthbot-glass-panel.open { display:block; }
          .anthbot-glass-head { position:sticky; top:0; z-index:5; display:flex; align-items:center; justify-content:space-between; padding:9px 12px 4px; background:linear-gradient(rgba(9,18,27,.62),rgba(9,18,27,0)); }
          .anthbot-glass-close { width:36px; height:36px; border:0; border-radius:50%; background:rgba(255,255,255,.14); color:#fff; font-size:22px; cursor:pointer; }
          .anthbot-glass-panel .app-shell, .anthbot-glass-panel .app-panel { background:transparent !important; border:0 !important; }
          .anthbot-glass-panel .top-menu { background:rgba(7,15,23,.30) !important; border:1px solid rgba(255,255,255,.10); border-radius:14px; margin:2px 10px 8px; }
          .anthbot-glass-panel .panel-tabs { padding-inline:10px; }
          .cloud-status { font-size:12px; font-weight:800; color:#aeb7c2; }
          .cloud-status[data-state="online"] { color:#55e58a; }
          .cloud-status[data-state="waiting"] { color:#ffd45c; }
          .cloud-status[data-state="offline"] { color:#ff6b6b; }
          .anthbot-glass-panel .command-dock { display:block !important; position:static !important; inset:auto !important; transform:none !important; margin:8px 10px 12px; background:rgba(6,14,22,.24) !important; }
          @media (max-width:720px) { .anthbot-glass-panel { left:8px; right:8px; bottom:66px; width:auto; max-height:72%; } .anthbot-menu-toggle { right:10px; bottom:10px; } }
        </style>
        <section class="app-shell">
          <div class="top-menu">
            <div>
              <div class="menu-title">${this.config.name || "Anthbot Map"}</div>
              <div class="menu-subtitle" data-role="state">${this.t("waiting")}</div>
            </div>
            <div class="mini-status">
              <div class="battery-ring" data-role="battery-ring">
                <span data-role="battery-value">--</span>
              </div>
              <div class="status-copy">
                <span class="status-label">${this.t("status")}</span>
                <strong data-role="mower-status">-</strong>
                <span class="cloud-status" data-role="cloud-status">${this.t("cloudChecking")}</span>
              </div>
            </div>
          </div>
          <div class="panel-tabs">
            <button type="button" data-panel="control">${this.t("control")}</button>
            <button type="button" data-panel="settings">${this.t("robotSettings")}</button>
            <button type="button" data-panel="interface">${this.t("interfaceSettings")}</button>
            <button type="button" data-panel="status">${this.t("status")}</button>
            <button type="button" data-panel="diagnostics">${this.t("diagnostics")}</button>
          </div>
        </section>
        <div class="canvas-wrap">
          <canvas></canvas>
          <div class="map-overlay map-title">
            <div class="name">${this.config.name || "Anthbot Map"}</div>
            <div class="state" data-role="map-state">${this.t("waiting")}</div>
          </div>
          <div class="map-overlay preview-hint">
            <strong>${this.t("map")}</strong>
            <span>${this.t("expand")}</span>
          </div>
          <button type="button" class="map-close" data-action="close-map" title="${this.t("close")}">&times;</button>
          <div class="map-overlay map-actions">
            <button type="button" data-action="zoom-in" title="${this.t("zoomIn")}">+</button>
            <button type="button" data-action="zoom-out" title="${this.t("zoomOut")}">-</button>
          </div>
          <div class="map-overlay map-badges">
            <span data-role="zone-count">${this.t("zones")}: -</span>
            <span data-role="pose">${this.t("position")}: -</span>
            <span data-role="heading">${this.t("heading")}: -</span>
            <span class="cloud-status" data-role="map-cloud-status">${this.t("cloudChecking")}</span>
          </div>
          <div class="map-overlay command-dock">
            <div class="zone-strip" data-role="zone-controls"></div>
            <div class="mower-controls">
              <button class="command start" type="button" data-command="start">
                <span class="command-icon">${this.t("start")}</span>
                <span>${this.t("startLabel")}</span>
              </button>
              <button class="command stop" type="button" data-command="stop">
                <span class="command-icon">${this.t("stop")}</span>
                <span>${this.t("stopLabel")}</span>
              </button>
              <button class="command dock" type="button" data-command="dock">
                <span class="command-icon">${this.t("home")}</span>
                <span>${this.t("homeLabel")}</span>
              </button>
            </div>
          </div>
          <button type="button" class="anthbot-menu-toggle" data-floating-menu="toggle">&#9776; ${this.t("menu")}</button>
          <section class="anthbot-glass-panel">
            <div class="anthbot-glass-head"><strong>Anthbot ${this.t("control")}</strong><button type="button" class="anthbot-glass-close" data-floating-menu="close">&times;</button></div>
          </section>
        </div>
        <section class="app-panel">
          <div class="panel-body" data-role="panel-body"></div>
        </section>
        <details class="calibration">
          <summary>${this.t("calibration")}</summary>
          <div class="calibration-title">${this.t("mapFit")}</div>
          <div class="calibration-grid">
            <button type="button" data-calibration="up">${this.t("up")}</button>
            <button type="button" data-calibration="left">${this.t("left")}</button>
            <button type="button" data-calibration="right">${this.t("right")}</button>
            <button type="button" data-calibration="down">${this.t("down")}</button>
            <button type="button" data-calibration="narrower">${this.t("narrower")}</button>
            <button type="button" data-calibration="wider">${this.t("wider")}</button>
            <button type="button" data-calibration="shorter">${this.t("shorter")}</button>
            <button type="button" data-calibration="taller">${this.t("taller")}</button>
            <button type="button" data-calibration="rotate-left">${this.t("rotation")} -</button>
            <button type="button" data-calibration="rotate-right">${this.t("rotation")} +</button>
          </div>
          <div class="calibration-title">${this.t("robotFit")}</div>
          <div class="calibration-grid">
            <button type="button" data-robot-calibration="up">${this.t("up")}</button>
            <button type="button" data-robot-calibration="left">${this.t("left")}</button>
            <button type="button" data-robot-calibration="right">${this.t("right")}</button>
            <button type="button" data-robot-calibration="down">${this.t("down")}</button>
            <button type="button" data-robot-calibration="narrower">${this.t("narrower")}</button>
            <button type="button" data-robot-calibration="wider">${this.t("wider")}</button>
            <button type="button" data-robot-calibration="rotate-left">${this.t("rotation")} -</button>
            <button type="button" data-robot-calibration="rotate-right">${this.t("rotation")} +</button>
            <button type="button" data-robot-calibration="rotate-left-large">${this.t("robotDirection")} -15°</button>
            <button type="button" data-robot-calibration="rotate-right-large">${this.t("robotDirection")} +15°</button>
            <button type="button" data-robot-calibration="rotate-around">${this.t("robotDirection")} 180°</button>
            <button type="button" data-action="reset-robot">${this.t("reset")}</button>
          </div>
          <div class="calibration-title">${this.t("boundaryFit")}</div>
          <div class="calibration-grid">
            <button type="button" data-boundary-calibration="up">${this.t("up")}</button>
            <button type="button" data-boundary-calibration="left">${this.t("left")}</button>
            <button type="button" data-boundary-calibration="right">${this.t("right")}</button>
            <button type="button" data-boundary-calibration="down">${this.t("down")}</button>
            <button type="button" data-boundary-calibration="narrower">${this.t("narrower")}</button>
            <button type="button" data-boundary-calibration="wider">${this.t("wider")}</button>
            <button type="button" data-boundary-calibration="shorter">${this.t("shorter")}</button>
            <button type="button" data-boundary-calibration="taller">${this.t("taller")}</button>
            <button type="button" data-boundary-calibration="rotate-left">${this.t("rotation")} -</button>
            <button type="button" data-boundary-calibration="rotate-right">${this.t("rotation")} +</button>
            <button type="button" data-action="reset-boundary">${this.t("reset")}</button>
          </div>
          <div class="yaml-row">
            <textarea readonly data-role="yaml"></textarea>
            <button type="button" data-action="copy-yaml">${this.t("yamlCopy")}</button>
          </div>
        </details>
      </ha-card>
    `;

    const glassPanel = root.querySelector(".anthbot-glass-panel");
    [
      root.querySelector(".app-shell"),
      root.querySelector(".app-panel"),
      root.querySelector(".command-dock"),
    ].forEach((element) => { if (element) glassPanel?.appendChild(element); });
    glassPanel?.classList.toggle("open", this.floatingMenuOpen);

    root.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", () => this.handleAction(button.dataset.action));
    });
    root.querySelectorAll("button[data-command]").forEach((button) => {
      button.addEventListener("click", () => this.handleCommand(button.dataset.command));
    });
    root.querySelectorAll("button[data-panel]").forEach((button) => {
      button.addEventListener("click", () => this.setPanel(button.dataset.panel));
    });
    root.querySelectorAll("button[data-calibration]").forEach((button) => {
      button.addEventListener("click", () => this.handleCalibration(button.dataset.calibration));
    });
    root.querySelectorAll("button[data-robot-calibration]").forEach((button) => {
      button.addEventListener("click", () => this.handleRobotCalibration(button.dataset.robotCalibration));
    });
    root.querySelectorAll("button[data-boundary-calibration]").forEach((button) => {
      button.addEventListener("click", () => this.handleBoundaryCalibration(button.dataset.boundaryCalibration));
    });
    root.querySelectorAll("button[data-floating-menu]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        this.floatingMenuOpen = button.dataset.floatingMenu === "close" ? false : !this.floatingMenuOpen;
        glassPanel?.classList.toggle("open", this.floatingMenuOpen);
      });
    });
    const canvas = root.querySelector("canvas");
    const canvasWrap = root.querySelector(".canvas-wrap");
    this.applyAutomaticMapSize(canvasWrap);
    const pointerStarts = new Map();
    let mapGestureMoved = false;
    canvasWrap?.addEventListener("pointerdown", (event) => {
      pointerStarts.set(event.pointerId, { x: event.clientX, y: event.clientY });
    });
    canvasWrap?.addEventListener("pointermove", (event) => {
      const start = pointerStarts.get(event.pointerId);
      if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) {
        mapGestureMoved = true;
      }
    });
    const finishMapGesture = (event) => {
      pointerStarts.delete(event.pointerId);
      if (mapGestureMoved) {
        this.suppressMapExpandClickUntil = Date.now() + 250;
      }
      if (!pointerStarts.size) {
        mapGestureMoved = false;
      }
    };
    canvasWrap?.addEventListener("pointerup", finishMapGesture);
    canvasWrap?.addEventListener("pointercancel", finishMapGesture);
    canvasWrap?.addEventListener("click", (event) => {
      if (event.composedPath().includes(glassPanel)) return;
      if (Date.now() < this.suppressMapExpandClickUntil) return;
      if (!mapOnly && !this.mapExpanded && !event.target.closest("button")) {
        this.setMapExpanded(true);
      }
    });
    canvasWrap?.addEventListener("dblclick", () => {
      if (this.mapOnly) this.setInterfaceOption("mapOnly", false);
    });

    this.renderer?.destroy();
    this.renderer = new AnthbotMapRenderer(canvas, this.rendererOptions());
    this.resizeObserver?.disconnect();
    this.resizeObserver = new ResizeObserver(() => this.renderer?.resize());
    this.resizeObserver.observe(canvas);
    requestAnimationFrame(() => this.renderer?.resize());
    this.setMapExpanded(this.mapExpanded);
    this.updateRenderer();
  }

  applyAutomaticMapSize(canvasWrap) {
    if (!canvasWrap) return;

    const configuredHeight = Number(this.config.height);
    if (Number.isFinite(configuredHeight) && configuredHeight > 0) {
      canvasWrap.classList.remove("auto-map-size");
      canvasWrap.style.setProperty("--anthbot-map-height", `${configuredHeight}px`);
      return;
    }

    canvasWrap.classList.add("auto-map-size");
    const imageUrl = this.config.image;
    if (!imageUrl) return;

    const probe = new Image();
    probe.onload = () => {
      if (!canvasWrap.isConnected || !probe.naturalWidth || !probe.naturalHeight) return;
      canvasWrap.style.setProperty(
        "--anthbot-map-aspect-ratio",
        `${probe.naturalWidth} / ${probe.naturalHeight}`,
      );
      this.renderer?.resize();
    };
    probe.src = imageUrl;
  }

  updateRenderer() {
    if (!this.renderer || !this.entity) {
      return;
    }

    const attributes = this.entity.attributes || {};
    const rawPose = attributes.pose && typeof attributes.pose === "object" ? attributes.pose : {};
    const coordinatePose = [attributes.cur_pose, attributes.map_scan_pose, rawPose].find((candidate) =>
      Number.isFinite(Number(candidate?.x)) && Number.isFinite(Number(candidate?.y)),
    );
    const poseYawEntity = this.getRelatedEntity("poseYaw");
    const fallbackYaw = [
      coordinatePose?.yaw,
      coordinatePose?.heading,
      rawPose.yaw,
      rawPose.heading,
      poseYawEntity?.state,
    ].find((value) => Number.isFinite(Number(value)));
    const pose = coordinatePose
      ? { ...rawPose, ...coordinatePose, yaw: fallbackYaw }
      : { ...rawPose, yaw: fallbackYaw };
    this.renderer.setOptions(this.rendererOptions());
    this.renderer.setState({
      pose,
      raw_pose: rawPose,
      cur_pose: attributes.cur_pose,
      map_scan_pose: attributes.map_scan_pose,
      path: attributes.path,
      mowed_path: attributes.mowed_path,
      mowedPath: attributes.mowedPath,
      mowing_path: attributes.mowing_path,
      mowingPath: attributes.mowingPath,
      track: attributes.track,
      tracks: attributes.tracks,
      trajectory: attributes.trajectory,
      cloud_path: attributes.cloud_path,
      cloudPath: attributes.cloudPath,
      path_id: attributes.path_id,
      path_start: attributes.path_start,
      path_task_type: attributes.path_task_type,
      path_point_count: attributes.path_point_count,
      path_coordinate_scale: attributes.path_coordinate_scale,
      path_first_point: attributes.path_first_point,
      path_time: attributes.path_time,
      history_path_info: attributes.history_path_info,
      history_path_source: attributes.history_path_source,
      map_raster: attributes.map_raster,
      map_definition: attributes.map_definition,
      path_definition: attributes.path_definition,
      map_binary_paths: attributes.map_binary_paths,
      path_binary_paths: attributes.path_binary_paths,
      mower_status: this.getRelatedEntity("status")?.state || attributes.mower_status || this.entity.state,
      robot_status_raw: attributes.robot_status_raw,
      charging: this.getRelatedEntity("charging")?.state === "on",
      history_path_live_refresh: attributes.history_path_live_refresh,
      area_definition: attributes.area_definition,
    });

    const state = this.shadowRoot.querySelector('[data-role="state"]');
    if (state) {
      state.textContent = `${this.entity.entity_id} - ${this.entity.state}`;
    }
    const mapState = this.shadowRoot.querySelector('[data-role="map-state"]');
    if (mapState) {
      mapState.textContent = `${this.entity.entity_id} - ${this.entity.state}`;
    }

    this.updateMapBadges(attributes);
    this.updateBatteryAndStatus();
    this.renderZoneControls(attributes.area_definition);
    if (!this.isPanelControlActive()) {
      this.renderAppPanel();
    }
    this.updateYaml();
  }

  isPanelControlActive() {
    const activeElement = this.shadowRoot?.activeElement;
    if (!activeElement?.closest?.('[data-role="panel-body"]')) {
      return false;
    }
    return ["SELECT", "INPUT", "BUTTON"].includes(activeElement.tagName);
  }

  updateMapBadges(attributes) {
    this.updateCloudStatus(attributes);
    const customAreas = Array.isArray(attributes.area_definition?.custom_areas)
      ? attributes.area_definition.custom_areas.length
      : 0;
    const noGoAreas =
      (Array.isArray(attributes.area_definition?.forbid_areas)
        ? attributes.area_definition.forbid_areas.length
        : 0) +
      (Array.isArray(attributes.area_definition?.remote_forbid_areas)
        ? attributes.area_definition.remote_forbid_areas.length
        : 0);

    const zoneCount = this.shadowRoot.querySelector('[data-role="zone-count"]');
    if (zoneCount) {
      zoneCount.textContent = `${this.t("zones")}: ${customAreas} / ${this.t("forbidden")}: ${noGoAreas}`;
    }

    const poseBadge = this.shadowRoot.querySelector('[data-role="pose"]');
    if (poseBadge) {
      const x = Number(attributes.pose?.x);
      const y = Number(attributes.pose?.y);
      poseBadge.textContent =
        Number.isFinite(x) && Number.isFinite(y)
          ? `${this.t("position")}: ${Math.round(x)}, ${Math.round(y)}`
          : `${this.t("position")}: -`;
    }

    const headingBadge = this.shadowRoot.querySelector('[data-role="heading"]');
    if (headingBadge) {
      const headingValue = [
        attributes.cur_pose?.heading,
        attributes.map_scan_pose?.heading,
        attributes.pose?.heading,
      ].find((value) => Number.isFinite(Number(value)));
      const yawValue = [
        attributes.cur_pose?.yaw,
        attributes.map_scan_pose?.yaw,
        attributes.pose?.yaw,
        this.getRelatedEntity("poseYaw")?.state,
      ].find((value) => Number.isFinite(Number(value)));
      const heading = Number.isFinite(Number(headingValue))
        ? normalizeHeadingDegrees(headingValue)
        : Number.isFinite(Number(yawValue))
          ? milliRadiansToDegrees(yawValue)
          : null;
      headingBadge.textContent = Number.isFinite(heading)
        ? `${this.t("heading")}: ${Math.round(normalizeSignedDegrees(heading))}°`
        : `${this.t("heading")}: -`;
    }
  }

  updateBatteryAndStatus() {
    const batteryRing = this.shadowRoot.querySelector('[data-role="battery-ring"]');
    const batteryValue = this.shadowRoot.querySelector('[data-role="battery-value"]');
    const batteryEntity = this.getRelatedEntity("battery");
    const batteryPercent = Number(batteryEntity?.state);

    if (batteryValue) {
      batteryValue.textContent = Number.isFinite(batteryPercent) ? `${batteryPercent}` : "--";
    }
    if (batteryRing) {
      const percent = Number.isFinite(batteryPercent) ? Math.max(0, Math.min(100, batteryPercent)) : 0;
      batteryRing.style.setProperty("--battery", `${percent * 3.6}deg`);
      batteryRing.classList.toggle("low", percent > 0 && percent < 25);
      batteryRing.classList.toggle("charging", this.getRelatedEntity("charging")?.state === "on");
    }

    const mowerStatus = this.shadowRoot.querySelector('[data-role="mower-status"]');
    if (mowerStatus) {
      const statusEntity = this.getRelatedEntity("status");
      mowerStatus.textContent = statusEntity ? this.translateStatus(statusEntity.state) : "-";
    }
  }

  setPanel(panel) {
    this.activePanel = panel;
    this.renderAppPanel();
  }

  renderAppPanel() {
    const body = this.shadowRoot.querySelector('[data-role="panel-body"]');
    if (!body || !this._hass) {
      return;
    }

    this.shadowRoot.querySelectorAll("button[data-panel]").forEach((button) => {
      button.classList.toggle("active", button.dataset.panel === this.activePanel);
    });

    if (this.activePanel === "settings") {
      this.renderSettingsPanel(body);
    } else if (this.activePanel === "interface") {
      this.renderInterfacePanel(body);
    } else if (this.activePanel === "status") {
      this.renderStatusPanel(body);
    } else if (this.activePanel === "diagnostics") {
      this.renderDiagnosticsPanel(body);
    } else {
      this.renderControlPanel(body);
    }
  }

  renderControlPanel(body) {
    body.innerHTML = "";
    const grid = this.createPanelGrid();
    grid.append(
      this.createCommandTile(this.t("startLabel"), this.t("startSub"), "start"),
      this.createCommandTile(this.t("stopLabel"), this.t("stopSub"), "stop"),
      this.createCommandTile(this.t("homeLabel"), this.t("homeSub"), "dock"),
      this.createCommandTile(this.t("outerEdgeLabel"), this.t("outerEdgeSub"), "outer-edge"),
      this.createCommandTile(this.t("dockEdgeLabel"), this.t("dockEdgeSub"), "dock-edge"),
    );

    for (const zone of this.currentZones()) {
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = "panel-tile zone-tile";
      tile.innerHTML = `<strong>${zone.name || `${this.t("zone")} ${zone.id}`}</strong><span>${this.t("zoneStart")}</span>`;
      tile.addEventListener("click", () => this.startZone(zone));
      grid.appendChild(tile);
    }

    body.appendChild(grid);
  }

  renderSettingsPanel(body) {
    body.innerHTML = "";
    const grid = this.createPanelGrid();
    grid.append(
      this.createCommandTile(this.t("cloud"), this.t("cloudSub"), "connect"),
      this.createMowHeightControl(),
      this.createNumberControl(this.t("customDirection"), "mowDirection", 0, 180, 1, "deg"),
      this.createNumberControl(this.t("rainDelay"), "rainContinue", 0, 8, 1, "h"),
      this.createNumberControl(this.t("volume"), "voiceVolume", 0, 100, 1, "%"),
      this.createSwitchControl(this.t("rainDetection"), "rain"),
      this.createSwitchControl(this.t("customCutDirection"), "customDirection"),
    );
    body.appendChild(grid);
  }

  renderInterfacePanel(body) {
    body.innerHTML = "";
    const grid = this.createPanelGrid();
    grid.append(
      this.createLanguageControl(),
      this.createInterfaceSwitch(this.t("mapOnly"), "mapOnly"),
      this.createInterfaceSwitch(this.t("themeBackground"), "themeBackground"),
      this.createInterfaceSwitch(this.t("glassBackground"), "glassBackground"),
      this.createInterfaceSwitch(this.t("transparentBackground"), "transparentBackground"),
      this.createMapOverlaySwitch(this.t("showZones"), "showZones"),
      this.createMapOverlaySwitch(this.t("showBoundary"), "showDecodedBoundary"),
      this.createMapOverlaySwitch(this.t("showNoGoZones"), "showNoGoZones"),
      this.createMapOverlaySwitch(this.t("showNoGoLabels"), "showNoGoLabels"),
    );
    body.appendChild(grid);
  }

  renderStatusPanel(body) {
    body.innerHTML = "";
    const grid = this.createPanelGrid();
    for (const item of [
      [this.t("battery"), "battery"],
      [this.t("status"), "status"],
      [this.t("charging"), "charging"],
      [this.t("connection"), "connection"],
      [this.t("cutHeight"), "cuttingHeight"],
      [this.t("mowedArea"), "mowingArea"],
      [this.t("mowingTime"), "mowingTime"],
      ["RTK", "rtkFix"],
      [this.t("totalArea"), "totalArea"],
      [this.t("error"), "errorDescription"],
    ]) {
      grid.appendChild(this.createInfoTile(item[0], item[1]));
    }
    body.appendChild(grid);
  }

  renderDiagnosticsPanel(body) {
    body.innerHTML = "";
    const grid = this.createPanelGrid();
    for (const item of [
      [this.t("bladeLife"), "cuttingComponentsLife"],
      [this.t("lineLife"), "cuttingLineLife"],
      [this.t("dockContact"), "rechargeContactLife"],
      ["WiFi", "wifi"],
      ["Bluetooth", "bluetooth"],
      [this.t("firmware"), "firmware"],
      [this.t("gpsLatitude"), "gpsLatitude"],
      [this.t("gpsLongitude"), "gpsLongitude"],
      [this.t("lastUpdate"), "shadowUpdated"],
    ]) {
      grid.appendChild(this.createInfoTile(item[0], item[1]));
    }
    body.appendChild(grid);
  }

  createPanelGrid() {
    const grid = document.createElement("div");
    grid.className = "panel-grid";
    return grid;
  }

  createCommandTile(title, subtitle, command) {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = `panel-tile command-tile ${command}`;
    tile.innerHTML = `<strong>${title}</strong><span>${subtitle}</span>`;
    tile.addEventListener("click", () => this.handleCommand(command));
    return tile;
  }

  createInfoTile(label, key) {
    const entity = this.getRelatedEntity(key);
    const tile = document.createElement("div");
    tile.className = "panel-tile info-tile";
    tile.innerHTML = `<span>${label}</span><strong>${this.formatEntity(entity, key)}</strong>`;
    return tile;
  }

  createLanguageControl() {
    const tile = document.createElement("label");
    tile.className = "panel-tile language-tile";
    const title = document.createElement("span");
    title.textContent = this.t("language");
    const select = document.createElement("select");
    select.setAttribute("aria-label", this.t("language"));
    for (const [code, name] of LANGUAGES) {
      const option = document.createElement("option");
      option.value = code;
      option.textContent = code === "auto" ? this.t("automatic") : name;
      option.selected = code === this.selectedLanguage;
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      this.selectedLanguage = select.value;
      this.languageOverride = true;
      this.config = { ...this.config, language: select.value };
      window.localStorage.setItem("anthbot-map-language", select.value);
      this.saveInterfaceSettings();
      this.render();
    });
    tile.append(title, select);
    return tile;
  }

  createMowHeightControl() {
    const key = "mowHeight";
    const entityId = this.getNumberEntity(key);
    const entity = entityId ? this._hass.states[entityId] : null;
    const value = this.displayedNumberValue(key, Number(entity?.state));
    const selected = Number.isFinite(value) ? Math.max(30, Math.min(70, Math.round(value / 5) * 5)) : 50;
    const tile = document.createElement("div");
    tile.className = "panel-tile control-tile mow-height-tile";
    tile.innerHTML = `
      <div class="control-head">
        <span>${this.t("cutHeight")}</span>
        <strong>${selected} mm</strong>
      </div>
      <div class="height-options" role="group" aria-label="${this.t("cutHeight")}"></div>
    `;
    const options = tile.querySelector(".height-options");
    for (let height = 30; height <= 70; height += 5) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "height-option";
      button.textContent = String(height);
      button.classList.toggle("active", height === selected);
      button.disabled = !(entityId || this.hasSettingFallback(key));
      button.addEventListener("click", () => {
        options.querySelectorAll(".height-option").forEach((item) => item.classList.toggle("active", item === button));
        this.applyOptimisticNumber(key, height, button);
        this.setNumberEntity(key, entityId, height, button);
      });
      options.appendChild(button);
    }
    return tile;
  }

  createNumberControl(label, key, min, max, step, unit) {
    const entityId = this.getNumberEntity(key);
    const entity = entityId ? this._hass.states[entityId] : null;
    const value = this.displayedNumberValue(key, Number(entity?.state));
    const tile = document.createElement("div");
    tile.className = "panel-tile control-tile";
    tile.innerHTML = `
      <div class="control-head">
        <span>${label}</span>
        <strong>${Number.isFinite(value) ? value : "-"} ${unit}</strong>
      </div>
      <input type="range" min="${min}" max="${max}" step="${step}" value="${Number.isFinite(value) ? value : min}" ${entityId || this.hasSettingFallback(key) ? "" : "disabled"}>
    `;
    const input = tile.querySelector("input");
    input.addEventListener("input", () => this.applyOptimisticNumber(key, Number(input.value), input));
    input.addEventListener("change", () => this.setNumberEntity(key, entityId, Number(input.value), input));
    return tile;
  }

  createSwitchControl(label, key) {
    const entityId = this.getSwitchEntity(key);
    const entity = entityId ? this._hass.states[entityId] : null;
    const checked = entity?.state === "on";
    const tile = document.createElement("label");
    tile.className = "panel-tile switch-tile";
    tile.title = entityId || this.t("switchMissing");
    tile.innerHTML = `
      <span>${label}</span>
      <input type="checkbox" ${checked ? "checked" : ""} ${entityId ? "" : "disabled"}>
    `;
    const input = tile.querySelector("input");
    input.addEventListener("change", () => this.toggleSwitchEntity(key, entityId, input.checked, input));
    return tile;
  }

  createMapOverlaySwitch(label, key) {
    const checked = Boolean(this[key]);
    const tile = document.createElement("label");
    tile.className = "panel-tile switch-tile";
    tile.innerHTML = `
      <span>${label}</span>
      <input type="checkbox" ${checked ? "checked" : ""}>
    `;
    const input = tile.querySelector("input");
    input.addEventListener("change", () => this.setMapOverlayVisibility(key, input.checked));
    return tile;
  }

  createInterfaceSwitch(label, key) {
    const tile = document.createElement("label");
    tile.className = "panel-tile switch-tile";
    tile.innerHTML = `
      <span>${label}</span>
      <input type="checkbox" ${this[key] ? "checked" : ""}>
    `;
    tile.querySelector("input").addEventListener("change", (event) => {
      this.setInterfaceOption(key, event.target.checked);
    });
    return tile;
  }

  renderZoneControls(areaDefinition = {}) {
    const container = this.shadowRoot.querySelector('[data-role="zone-controls"]');
    if (!container) {
      return;
    }

    container.innerHTML = "";
    for (const zone of this.currentZones(areaDefinition)) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = zone.name || `${this.t("zone")} ${zone.id}`;
      button.addEventListener("click", () => this.startZone(zone));
      container.appendChild(button);
    }
  }

  currentZones(areaDefinition = this.entity?.attributes?.area_definition || {}) {
    const zones = Array.isArray(areaDefinition?.custom_areas) ? areaDefinition.custom_areas : [];
    return zones.filter((zone) => zone?.id !== undefined && zone?.id !== null);
  }

  rendererOptions() {
    return {
      image: this.config.image,
      bounds: this.config.bounds,
      fit: this.config.fit || "cover",
      rotation: degreesToRadians(Number(this.config.rotation) || 0),
      calibration: this.calibration,
      robotCalibration: this.robotCalibration,
      decodedBoundaryCalibration: this.decodedBoundaryCalibration,
      robotImage: this.config.robot_image || this.config.robotImage || this.resolveAsset("robot.png?v=133"),
      noGoLabel: this.t("forbidden"),
      showNoGoZones: this.showNoGoZones,
      showNoGoLabels: this.showNoGoLabels,
      robotSize: this.config.robot_size ?? this.config.robotSize,
      robotImageRotation: this.config.robot_image_rotation ?? this.config.robotImageRotation,
      robotHeadingSource: this.config.robot_heading_source || this.config.robotHeadingSource,
      robotHeadingOffset: this.config.robot_heading_offset ?? this.config.robotHeadingOffset,
      robotMowingHeadingOffset: this.config.robot_mowing_heading_offset ?? this.config.robotMowingHeadingOffset,
      showMowedPath: this.config.show_mowed_path !== false,
      showMowedCoverage: this.config.show_mowed_coverage !== false && this.config.showMowedCoverage !== false,
      // The official Anthbot app renders the downloaded cloud task path.  Do
      // not mix it with a browser-generated live trail or a cached fallback.
      mowedPathSource: "cloud",
      mowedPathColor: this.config.mowed_path_color || this.config.mowedPathColor,
      mowedPathWidth: this.config.mowed_path_width ?? this.config.mowedPathWidth,
      mowedCoverageColor: this.config.mowed_coverage_color || this.config.mowedCoverageColor,
      mowedCoverageWidth: this.config.mowed_coverage_width ?? this.config.mowedCoverageWidth,
      mowedPathStorageKey: null,
      showBoundary: this.config.show_boundary !== false,
      showLegacyBoundary: this.config.show_legacy_boundary === true || this.config.showLegacyBoundary === true,
      showDecodedBoundary: this.showDecodedBoundary,
      showZones: this.showZones,
      transparentBackground: this.transparentBackground,
      boundaryColor: this.config.boundary_color || this.config.boundaryColor,
      boundaryWidth: this.config.boundary_width ?? this.config.boundaryWidth,
      charger: this.config.charger,
    };
  }

  startRefreshTimer() {
    if (!this._hass || this.refreshTimer || this.config.refresh_interval === 0) {
      return;
    }

    const interval = Math.max(1, Number(this.config.refresh_interval ?? this.config.refreshInterval ?? 2)) * 1000;
    this.refreshTimer = window.setInterval(() => this.refreshEntities(), interval);
  }

  stopRefreshTimer() {
    if (this.refreshTimer) {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  async refreshEntities() {
    if (!this._hass || this.refreshInFlight || !this.config.entity) {
      return;
    }

    this.refreshInFlight = true;
    try {
      await this._hass.callService("homeassistant", "update_entity", {
        entity_id: this.refreshEntityIds(),
      });
    } catch (error) {
      console.warn("Anthbot map refresh failed", error);
    } finally {
      this.refreshInFlight = false;
      this.syncEntityAndRenderer();
      window.setTimeout(() => this.syncEntityAndRenderer(), 750);
      window.setTimeout(() => this.syncEntityAndRenderer(), 1800);
    }
  }

  updateCloudStatus(attributes = {}) {
    const cloudConnected = attributes.cloud_connected;
    const robotOnline = attributes.robot_online;
    const state = cloudConnected === false ? "offline" : robotOnline === true ? "online" : "waiting";
    const text = cloudConnected === false
      ? this.t("cloudDisconnected")
      : robotOnline === true
        ? this.t("cloudRobotOnline")
        : cloudConnected === true
          ? this.t("cloudRobotNoResponse")
          : this.t("cloudChecking");
    for (const role of ["cloud-status", "map-cloud-status"]) {
      const badge = this.shadowRoot?.querySelector(`[data-role="${role}"]`);
      if (badge) {
        badge.textContent = text;
        badge.dataset.state = state;
      }
    }
  }

  syncEntityAndRenderer() {
    if (!this._hass || !this.config?.entity) {
      return;
    }
    const latestEntity = this._hass.states[this.config.entity];
    if (latestEntity) {
      this.entity = latestEntity;
      this.updateRenderer();
    }
  }

  refreshEntityIds() {
    return [
      this.config.entity,
      this.getRelatedEntity("status")?.entity_id,
      this.getRelatedEntity("battery")?.entity_id,
      this.getRelatedEntity("charging")?.entity_id,
      this.getRelatedEntity("mowingArea")?.entity_id,
      this.getRelatedEntity("mowingTime")?.entity_id,
      this.getRelatedEntity("poseYaw")?.entity_id,
    ].filter(Boolean);
  }

  async handleCommand(command) {
    const customAction = this.config.button_actions?.[command] || this.config.buttonActions?.[command];
    if (customAction) {
      await this.callCustomButtonAction(command, customAction);
      return;
    }

    const serviceByCommand = {
      connect: "connect_cloud",
      start: "start_full_mow",
      stop: "stop_mow",
      dock: "return_to_dock",
      "outer-edge": "start_outer_edge_mow",
      "dock-edge": "start_dock_edge_mow",
    };
    const service = serviceByCommand[command];
    if (service) {
      await this.callAnthbotService(service);
    }
  }

  async startZone(zone) {
    await this.callAnthbotService("start_zone_mow", { zones: String(zone.id ?? zone.name) });
  }

  async callAnthbotService(service, data = {}) {
    try {
      await this._hass.callService("anthbot_map", service, {
        ...data,
        entity_id: this.config.entity,
      });
      this.notify(this.feedback("commandSentWaiting", this.commandLabel(service)));
      this.scheduleRefresh(200);
      void this.waitForCommandConfirmation(service);
    } catch (error) {
      this.notify(this.feedback("commandFailed", this.commandLabel(service)));
      throw error;
    }
  }

  commandLabel(service) {
    return ({
      start_full_mow: this.t("startLabel"),
      start_zone_mow: this.t("zoneStart"),
      start_outer_edge_mow: this.t("commandOuterEdge"),
      start_dock_edge_mow: this.t("commandDockEdge"),
      stop_mow: this.t("stopLabel"),
      return_to_dock: this.t("homeLabel"),
      connect_cloud: this.t("cloud"),
    })[service] || service;
  }

  feedback(key, command) {
    return this.t(key).replaceAll("{command}", command);
  }

  commandStatusValues() {
    const entity = this._hass?.states?.[this.config?.entity];
    const attributes = entity?.attributes || {};
    const robotState = attributes.robot_sta;
    return [
      this.getRelatedEntity("status")?.state,
      attributes.mower_status,
      attributes.robot_status_raw,
      typeof robotState === "object" ? robotState?.value : robotState,
      entity?.state,
    ].map((value) => String(value || "").toLowerCase().replace(/[\s_-]+/g, ""));
  }

  commandIsConfirmed(service) {
    const expected = ({
      start_full_mow: ["mowing", "globalmowing", "working", "cutting"],
      start_zone_mow: ["mowing", "zonemowing", "regionmowing", "working", "cutting"],
      start_outer_edge_mow: ["mowing", "bordermowing", "edgecutting", "working"],
      start_dock_edge_mow: ["mowing", "nestmowing", "working"],
      stop_mow: ["paused", "pause", "standby", "idle"],
      return_to_dock: ["returning", "backtodock", "docking", "charging", "charge"],
    })[service];
    return Array.isArray(expected) && this.commandStatusValues().some((status) =>
      expected.some((value) => status.includes(value)),
    );
  }

  async waitForCommandConfirmation(service) {
    if (service === "connect_cloud") return;
    const token = ++this.commandConfirmationToken;
    const deadline = Date.now() + 20000;
    while (token === this.commandConfirmationToken && Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      await this.refreshEntities();
      if (this.commandIsConfirmed(service)) {
        this.notify(this.feedback("commandConfirmed", this.commandLabel(service)));
        return;
      }
    }
    if (token === this.commandConfirmationToken) {
      this.notify(this.feedback("commandNotConfirmed", this.commandLabel(service)));
    }
  }

  async setNumberEntity(kind, entityId, value, input) {
    if (!Number.isFinite(value)) {
      return;
    }
    this.applyOptimisticNumber(kind, value, input);
    try {
      if (this.hasSettingFallback(kind)) {
        await this.callSettingFallback(kind, value);
      } else if (entityId) {
        await this._hass.callService("number", "set_value", { entity_id: entityId, value });
        this.scheduleRefresh();
      } else {
        throw new Error(`No setting target found for ${kind}`);
      }
    } catch (error) {
      if (input) {
        const previous = this.getNumberEntity(kind);
        const state = previous ? this._hass.states[previous] : null;
        if (state) {
          input.value = Number(state.state);
        }
      }
      this.notify(`${this.t("settingFailed")}: ${entityId || kind}`);
      throw error;
    }
  }

  async toggleSwitchEntity(kind, entityId, checked, input) {
    if (!entityId && !this.hasSwitchFallback(kind)) {
      this.notify(`${this.t("switchMissing")}: ${kind}`);
      return;
    }
    try {
      if (this.hasSwitchFallback(kind)) {
        await this.callSwitchFallback(kind, checked);
      } else {
        await this._hass.callService("switch", checked ? "turn_on" : "turn_off", { entity_id: entityId });
        this.scheduleRefresh();
      }
    } catch (error) {
      if (input) {
        input.checked = !checked;
      }
      this.notify(`${this.t("operationFailed")}: ${entityId}`);
      throw error;
    }
  }

  hasSettingFallback(kind) {
    return ["mowHeight", "mowDirection", "rainContinue", "voiceVolume"].includes(kind);
  }

  async callSettingFallback(kind, value) {
    const fallback = {
      mowHeight: ["set_mow_height", { mow_height: value }],
      mowDirection: ["set_custom_mowing_direction", { mow_direction: value, enable_custom_direction: true }],
      rainContinue: ["set_rain_continue_time", { rain_continue_time: value }],
      voiceVolume: ["set_voice_volume", { voice_volume: value }],
    }[kind];
    if (!fallback) {
      throw new Error(`No fallback service for ${kind}`);
    }
    await this.callAnthbotService(fallback[0], fallback[1]);
    this.scheduleRefresh();
  }

  hasSwitchFallback(kind) {
    return ["rain", "customDirection"].includes(kind);
  }

  async callSwitchFallback(kind, checked) {
    const fallback = {
      rain: ["set_rain_perception", { enable_rain_perception: checked }],
      customDirection: ["set_custom_mowing_direction", {
        mow_direction: Number(this.getNumberEntity("mowDirection") ? this._hass.states[this.getNumberEntity("mowDirection")]?.state : 0) || 0,
        enable_custom_direction: checked,
      }],
    }[kind];
    if (!fallback) {
      throw new Error(`No fallback service for ${kind}`);
    }
    await this.callAnthbotService(fallback[0], fallback[1]);
    this.scheduleRefresh();
  }

  applyOptimisticNumber(kind, value, input) {
    if (Number.isFinite(value)) {
      this.optimisticSettings.set(kind, { value, until: Date.now() + 10000 });
    }
    const tile = input?.closest(".control-tile");
    const valueLabel = tile?.querySelector(".control-head strong");
    const units = {
      mowHeight: "mm",
      mowDirection: "deg",
      rainContinue: "h",
      voiceVolume: "%",
    };
    if (valueLabel) {
      valueLabel.textContent = `${value} ${units[kind] || ""}`.trim();
    }
  }

  async callCustomButtonAction(command, action) {
    const definition = typeof action === "string" ? { service: action } : action;
    const serviceName = definition?.service;
    if (typeof serviceName !== "string" || !serviceName.includes(".")) {
      throw new Error(`Invalid custom action for ${command}`);
    }

    const separator = serviceName.indexOf(".");
    const domain = serviceName.slice(0, separator);
    const service = serviceName.slice(separator + 1);
    const data = definition.data || definition.service_data || {};
    const target = definition.target || {};

    try {
      await this._hass.callService(domain, service, data, target);
    } catch (error) {
      this.notify(`${this.t("operationFailed")}: ${serviceName}`);
      throw error;
    }
  }

  displayedNumberValue(kind, entityValue) {
    const optimistic = this.optimisticSettings.get(kind);
    if (optimistic && optimistic.until > Date.now()) {
      return optimistic.value;
    }
    this.optimisticSettings.delete(kind);
    return entityValue;
  }

  scheduleRefresh(delay = 1200) {
    window.clearTimeout(this.pendingRefreshTimer);
    this.pendingRefreshTimer = window.setTimeout(() => this.refreshEntities(), delay);
  }

  async connectCloudQuietly() {
    try {
      await this._hass.callService("anthbot_map", "connect_cloud", {
        entity_id: this.config.entity,
      });
    } catch (error) {
      console.warn("Anthbot cloud connect failed before setting update", error);
    }
  }

  handleAction(action) {
    if (action === "zoom-in") {
      this.renderer.view.zoom = Math.min(8, this.renderer.view.zoom * 1.15);
      this.renderer.draw();
    } else if (action === "zoom-out") {
      this.renderer.view.zoom = Math.max(0.2, this.renderer.view.zoom / 1.15);
      this.renderer.draw();
    } else if (action === "rotate-left") {
      this.renderer.rotate(-Math.PI / 18);
    } else if (action === "rotate-right") {
      this.renderer.rotate(Math.PI / 18);
    } else if (action === "reset") {
      this.calibration = resetCalibration();
      this.robotCalibration = resetCalibration();
      this.renderer.setCalibration(this.calibration);
      this.renderer.setRobotCalibration(this.robotCalibration);
      this.renderer.resetView();
      this.updateYaml();
    } else if (action === "reset-robot") {
      this.robotCalibration = resetCalibration();
      this.renderer.setRobotCalibration(this.robotCalibration);
      this.updateYaml();
    } else if (action === "reset-boundary") {
      this.decodedBoundaryCalibration = resetCalibration();
      this.renderer?.setDecodedBoundaryCalibration(this.decodedBoundaryCalibration);
      this.updateYaml();
    } else if (action === "copy-yaml") {
      this.copyYaml();
    } else if (action === "close-map") {
      this.setMapExpanded(false);
    }
  }

  setMapOverlayVisibility(key, visible) {
    this[key] = Boolean(visible);
    this.mapOverlayOverrides[key] = true;
    this.renderer?.setOptions({
      showDecodedBoundary: this.showDecodedBoundary,
      showZones: this.showZones,
      showNoGoZones: this.showNoGoZones,
      showNoGoLabels: this.showNoGoLabels,
    });
    this.saveInterfaceSettings();
    this.updateYaml();
  }

  interfaceStorageKey(entity = this.config.entity) {
    return `anthbot-map-interface:${entity || "default"}`;
  }

  mowedPathStorageKey(entity = this.config.entity) {
    return `anthbot-map-mowed-path:${entity || "default"}`;
  }

  readInterfaceSettings(entity) {
    try {
      return JSON.parse(window.localStorage.getItem(this.interfaceStorageKey(entity)) || "{}") || {};
    } catch (_error) {
      return {};
    }
  }

  saveInterfaceSettings() {
    window.localStorage.setItem(this.interfaceStorageKey(), JSON.stringify({
      mapOnly: this.mapOnly,
      themeBackground: this.themeBackground,
      glassBackground: this.glassBackground,
      transparentBackground: this.transparentBackground,
      language: this.selectedLanguage,
      languageOverride: this.languageOverride,
      showDecodedBoundary: this.showDecodedBoundary,
      showZones: this.showZones,
      showNoGoZones: this.showNoGoZones,
      showNoGoLabels: this.showNoGoLabels,
      mapOverlayOverrides: this.mapOverlayOverrides,
    }));
  }

  setInterfaceOption(key, enabled) {
    this[key] = Boolean(enabled);
    if (enabled && key === "glassBackground") this.transparentBackground = false;
    if (enabled && key === "transparentBackground") this.glassBackground = false;
    if (key === "mapOnly") this.config = { ...this.config, map_only: this.mapOnly };
    if (key === "themeBackground") {
      this.config = { ...this.config, theme_background: this.themeBackground };
    }
    if (key === "glassBackground") {
      this.config = { ...this.config, glass_background: this.glassBackground, transparent_background: false };
    }
    if (key === "transparentBackground") {
      this.config = { ...this.config, transparent_background: this.transparentBackground, glass_background: false };
    }
    this.saveInterfaceSettings();
    this.render();
  }

  setMapExpanded(expanded) {
    this.mapExpanded = Boolean(expanded);
    this.shadowRoot?.querySelector("ha-card")?.classList.toggle("map-expanded", this.mapExpanded);
    requestAnimationFrame(() => this.renderer?.resize());
  }

  handleCalibration(action) {
    this.calibration = adjustCalibration(this.calibration, action, 1);
    this.renderer.setCalibration(this.calibration);
    this.updateYaml();
  }

  handleRobotCalibration(action) {
    this.robotCalibration = adjustCalibration(this.robotCalibration, action, 1);
    this.renderer.setRobotCalibration(this.robotCalibration);
    this.updateYaml();
  }

  handleBoundaryCalibration(action) {
    this.decodedBoundaryCalibration = adjustCalibration(this.decodedBoundaryCalibration, action, 1);
    this.renderer?.setDecodedBoundaryCalibration(this.decodedBoundaryCalibration);
    this.updateYaml();
  }

  updateYaml() {
    const yaml = this.shadowRoot?.querySelector('[data-role="yaml"]');
    if (yaml) {
      yaml.value = cardToYaml(
        this.configForYaml(),
        this.calibration,
        this.robotCalibration,
        this.decodedBoundaryCalibration,
      );
    }
  }

  async copyYaml() {
    const yaml = cardToYaml(
      this.configForYaml(),
      this.calibration,
      this.robotCalibration,
      this.decodedBoundaryCalibration,
    );
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(yaml);
      return;
    }

    const input = this.shadowRoot?.querySelector('[data-role="yaml"]');
    input?.select();
    document.execCommand("copy");
  }

  configForYaml() {
    return {
      ...this.config,
      map_only: this.mapOnly,
      theme_background: this.themeBackground,
      glass_background: this.glassBackground,
      transparent_background: this.transparentBackground,
      language: this.selectedLanguage,
      show_decoded_boundary: this.showDecodedBoundary,
      show_zones: this.showZones,
      show_no_go_zones: this.showNoGoZones,
      show_no_go_labels: this.showNoGoLabels,
    };
  }

  getControlEntity(command) {
    const configured = this.config.controls?.[command];
    if (configured && this._hass.states[configured]) {
      return configured;
    }

    const suffixByCommand = {
      start: ["start_full_mow"],
      stop: ["stop_mow"],
      dock: ["return_to_dock"],
    };
    return this.findEntity("button", suffixByCommand[command] || []);
  }

  getZoneButtonEntity(zone) {
    const configured = this.config.zoneButtons?.[zone.id] || this.config.zoneButtons?.[zone.name];
    if (configured && this._hass.states[configured]) {
      return configured;
    }

    const zoneId = zone.id === undefined || zone.id === null ? null : String(zone.id);
    const zoneName = String(zone.name || "").trim();
    const normalizedName = slugify(zoneName);

    for (const [entityId, state] of Object.entries(this._hass.states || {})) {
      if (!entityId.startsWith("button.")) {
        continue;
      }
      const attrs = state.attributes || {};
      if (attrs.zone_type && zoneId !== null && String(attrs.id) === zoneId) {
        return entityId;
      }
      if (attrs.zone_type && normalizedName && slugify(attrs.name) === normalizedName) {
        return entityId;
      }
    }

    const base = this.entityBase();
    const visibleNumber = zoneName.match(/\d+/)?.[0];
    const suffixes = [
      zoneId ? `manual_zone_${zoneId}` : "",
      zoneId ? `auto_zone_${zoneId}` : "",
      zoneId ? `zone_${zoneId}` : "",
      normalizedName ? `zone_${normalizedName}` : "",
      normalizedName ? normalizedName : "",
      visibleNumber ? `zone_zone_${visibleNumber}` : "",
      visibleNumber ? `zone_${visibleNumber}` : "",
    ].filter(Boolean);

    for (const suffix of suffixes) {
      for (const candidate of [`button.${base}_${suffix}`, `button.${base}_${suffix}_2`]) {
        if (this._hass.states[candidate]) {
          return candidate;
        }
      }
    }

    for (const [entityId, state] of Object.entries(this._hass.states || {})) {
      if (!entityId.startsWith("button.") || !entityId.includes(base)) {
        continue;
      }
      const friendlyName = slugify(state.attributes?.friendly_name);
      if (normalizedName && friendlyName.includes(normalizedName)) {
        return entityId;
      }
    }

    return null;
  }

  getRelatedEntity(kind) {
    const configured = this.config.entities?.[kind];
    if (configured && this._hass.states[configured]) {
      return this._hass.states[configured];
    }

    const mapped = ENTITY_MAP[kind];
    if (!mapped) {
      return null;
    }
    const entityId = this.findEntity(mapped[0], mapped[1]);
    return entityId ? this._hass.states[entityId] : null;
  }

  getNumberEntity(kind) {
    const configured = this.config.numbers?.[kind];
    if (configured && this._hass.states[configured]) {
      return configured;
    }
    return this.findEntity("number", NUMBER_MAP[kind] || []);
  }

  getSwitchEntity(kind) {
    const configured = this.config.switches?.[kind];
    if (configured && this._hass.states[configured]) {
      return configured;
    }

    return this.findEntity("switch", SWITCH_MAP[kind] || []);
  }

  findEntity(domain, suffixes) {
    const base = this.entityBase();
    for (const suffix of suffixes) {
      for (const candidate of [
        `${domain}.${base}_${suffix}`,
        `${domain}.${base}_${suffix}_2`,
      ]) {
        if (this._hass.states[candidate]) {
          return candidate;
        }
      }
    }

    for (const suffix of suffixes) {
      const wanted = slugify(`${base}_${suffix}`);
      for (const [entityId, state] of Object.entries(this._hass.states || {})) {
        if (!entityId.startsWith(`${domain}.`)) {
          continue;
        }
        const entitySlug = slugify(entityId.slice(domain.length + 1));
        const friendlySlug = slugify(state.attributes?.friendly_name);
        const suffixSlug = slugify(suffix);
        if (entitySlug === wanted || entitySlug.endsWith(`_${suffixSlug}`) || friendlySlug.includes(suffixSlug)) {
          return entityId;
        }
      }
    }
    return null;
  }

  entityBase() {
    return String(this.config.entity || "")
      .replace(/^sensor\./, "")
      .replace(/_map$/, "");
  }

  formatEntity(entity, key = "") {
    if (!entity) {
      return "-";
    }
    if (key === "shadowUpdated") {
      return this.formatLocalDateTime(entity.state);
    }
    const unit = entity.attributes?.unit_of_measurement;
    const value = this.translateStatus(entity.state);
    return unit ? `${value} ${unit}` : value;
  }

  formatLocalDateTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value || "-";
    }

    const options = {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    };
    const timeZone = this._hass?.config?.time_zone;
    if (timeZone) {
      options.timeZone = timeZone;
    }

    try {
      return new Intl.DateTimeFormat(this.language, options).format(date);
    } catch (_error) {
      delete options.timeZone;
      return new Intl.DateTimeFormat(undefined, options).format(date);
    }
  }

  translateStatus(status) {
    const key = `status_${status}`;
    const value = this.t(key);
    return value === key ? status : value;
  }

  resolveAsset(fileName) {
    const script = document.currentScript?.src || import.meta.url;
    return new URL(fileName, script).toString();
  }

  notify(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", {
        detail: { message },
        bubbles: true,
        composed: true,
      }),
    );
  }
}

function degreesToRadians(degrees) {
  return (degrees * Math.PI) / 180;
}

function milliRadiansToDegrees(value) {
  return (Number(value) * 180) / (Math.PI * 1000);
}

function normalizeHeadingDegrees(value) {
  const heading = Number(value) || 0;
  return Math.abs(heading) > 360 ? heading / 100 : heading;
}

function normalizeSignedDegrees(value) {
  return ((Number(value) + 180) % 360 + 360) % 360 - 180;
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

customElements.define("anthbot-map-card", AnthbotMapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "anthbot-map-card",
  name: "Anthbot Map Card",
  description: "Canvas map display and controls for Anthbot map sensors",
});









