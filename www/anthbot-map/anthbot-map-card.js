import { AnthbotMapRenderer } from "./renderer.js?v=2411";
import { getZones, getZonePoints, createGeometry, getWorldBounds, getBoundaryPaths } from "./geometry.js?v=2411";
import { renderAnthbotEdgeSettings } from "./edge-settings.js?v=2411";
import { LANGUAGES, resolveLanguage, translate } from "./i18n.js?v=243b2-mowing-mode-help3";
import {
  adjustCalibration,
  cardToYaml,
  readCalibration,
  readDecodedBoundaryCalibration,
  readMowingPathCalibration,
  readRobotCalibration,
  resetCalibration,
} from "./calibration.js?v=2411";

const ENTITY_MAP = {
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

const NUMBER_MAP = {
  mowHeight: ["mow_height", "mow_height_setting", "mow height"],
  mowCount: ["mow_count", "mow_count_setting", "mowing passes"],
  visualObstacleLevel: ["visual_obstacle_level", "visual_obstacle_level_setting", "visual obstacle sensitivity"],
  mowDirection: ["custom_mowing_direction", "custom_mowing_direction_setting", "custom mowing direction"],
  rainContinue: ["rain_continue_time", "rain_continue_time_setting", "rain continue time"],
  voiceVolume: ["voice_volume", "voice_volume_setting", "voice volume"],
};

const SWITCH_MAP = {
  rain: ["rain_perception", "rain_perception_enabled", "rain perception"],
  visualObstacle: ["visual_obstacle_detection", "visual_obstacle_detection_enabled", "visual obstacle detection"],
  customDirection: ["custom_mowing_direction_enabled", "custom mowing direction"],
  edgeReturn: ["edge_following_return_enabled", "edge-following return"],
  autoDockMow: ["automatic_dock_mowing_enabled", "automatic dock-area mowing"],
  batterySaver: ["battery_saver_mode", "battery saver mode"],
};

class AnthbotMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.config = {};
    this.entity = null;
    this.calibration = resetCalibration();
    this.robotCalibration = resetCalibration();
    this.mowingPathCalibration = resetCalibration();
    this.robotHeadingOffset = 0;
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
    this.commandFeedbackTimer = null;
    this.feedbackToastId = `anthbot-command-feedback-${Math.random().toString(36).slice(2)}`;
    this.suppressMapExpandClickUntil = 0;
    this.selectedLanguage = "auto";
    this.languageOverride = false;
    this.floatingMenuOpen = false;
    this.defaultSubmenu = "";
    this.selectedMowingTarget = { type: "full" };
    this.mowingZoneGroupsOpen = { "zone-set": true, "auto-zone-set": false };
    this.panelInteractionUntil = 0;
    this.customButtonActions = {};
    this.customButtonActionsEnabled = false;
    this.customButtonServerConfigured = false;
    this.customButtonSavePending = 0;
    this.customButtonSaveQueue = Promise.resolve();
    // Keep a near-complete task at 100% after the mower has accepted it as
    // finished. The cloud may keep a final geometry value such as 98.8%
    // after return/charge transitions into standby.
    this.mowingCompletionLatched = null;
  }

  setConfig(config) {
    if (!config?.entity) {
      throw new Error("Anthbot map card requires an entity");
    }

    this.config = config;
    const validPanels = new Set(["control", "settings", "interface", "status", "maintenance", "diagnostics"]);
    const configuredPanel = String(config.default_panel ?? config.defaultPanel ?? "control").trim();
    this.activePanel = validPanels.has(configuredPanel) ? configuredPanel : "control";
    this.floatingMenuOpen = typeof config.menu_open === "boolean"
      ? config.menu_open
      : typeof config.menuOpen === "boolean" ? config.menuOpen : false;
    this.defaultSubmenu = String(config.default_submenu ?? config.defaultSubmenu ?? "").trim();
    this.mowingZoneGroupsOpen = this.defaultSubmenu === "auto-zone-set"
      ? { "zone-set": false, "auto-zone-set": true }
      : this.defaultSubmenu === "zone-set"
        ? { "zone-set": true, "auto-zone-set": false }
        : { "zone-set": true, "auto-zone-set": false };
    const savedInterface = this.readInterfaceSettings(config.entity);
    const configuredButtonActions = config.button_actions || config.buttonActions || {};
    this.customButtonActions = { ...configuredButtonActions };
    this.customButtonActionsEnabled = Object.keys(configuredButtonActions).length > 0;
    this.customButtonServerConfigured = false;
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
    this.mowingPathCalibration = readMowingPathCalibration(config);
    this.robotHeadingOffset = Number(config.robot_heading_offset ?? config.robotHeadingOffset) || 0;
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
    this._activeEntityId = this.resolveMapEntityId();
    this.entity = hass.states[this._activeEntityId];
    const customButtonsChanged = this.syncCustomButtonActionsFromServer();
    this.startRefreshTimer();
    if (previousLanguage !== this.language || customButtonsChanged) {
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
    window.clearTimeout(this.commandFeedbackTimer);
    document.getElementById(this.feedbackToastId)?.remove();
    this.resizeObserver?.disconnect();
    this.mapLiveStatusResizeObserver?.disconnect();
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
        <link rel="stylesheet" href="${this.resolveAsset("styles.css?v=2411")}">
        <style>
          .anthbot-menu-toggle { position:absolute; right:14px; bottom:14px; z-index:40; min-height:46px; padding:9px 15px; border:1px solid rgba(255,255,255,.38); border-radius:999px; background:rgba(10,18,26,.66); color:#fff; backdrop-filter:blur(12px); box-shadow:0 8px 28px rgba(0,0,0,.32); font:inherit; font-weight:800; cursor:pointer; }
          .anthbot-glass-panel { display:none; position:absolute; z-index:39; right:12px; bottom:70px; width:min(1100px,calc(100% - 24px)); max-height:calc(100% - 84px); overflow:auto; border:1px solid rgba(255,255,255,.34); border-radius:18px; background:rgba(9,18,27,.16); color:#fff; backdrop-filter:blur(9px) saturate(115%); box-shadow:0 16px 44px rgba(0,0,0,.24); overscroll-behavior:contain; }
          .anthbot-glass-panel.open { display:block; }
          .anthbot-glass-head { position:sticky; top:0; z-index:5; display:flex; align-items:center; justify-content:space-between; padding:9px 12px 0; background:linear-gradient(rgba(9,18,27,.64),rgba(9,18,27,0)); }
          .anthbot-glass-head strong { font-size:15px; }
          .anthbot-glass-close { width:36px; height:36px; border:0; border-radius:50%; background:rgba(255,255,255,.12); color:#fff; font-size:22px; cursor:pointer; }
          .anthbot-glass-panel .app-shell, .anthbot-glass-panel .app-panel { background:transparent !important; border:0 !important; }
          .anthbot-glass-panel .top-menu { background:rgba(255,255,255,.07) !important; border-radius:14px; margin:0 10px; }
          .anthbot-glass-panel .panel-tabs { padding-inline:10px; }
          .cloud-status { font-size:12px; font-weight:800; color:#aeb7c2; }
          .cloud-status[data-state="online"] { color:#55e58a; }
          .cloud-status[data-state="waiting"] { color:#ffd45c; }
          .cloud-status[data-state="offline"] { color:#ff6b6b; }
          .mowing-live-line { display:flex; align-items:center; gap:7px; margin-top:4px; min-width:0; font-size:12px; line-height:1.25; color:#cbd5df; }
          .mowing-live-line[hidden] { display:none !important; }
          .mowing-live-line .mowing-live-target { min-width:0; max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
          .mowing-live-line .mowing-live-progress { flex:0 0 auto; padding:2px 7px; border-radius:999px; background:rgba(85,229,138,.14); border:1px solid rgba(85,229,138,.34); color:#72efa0; font-weight:900; }
          .map-live-status { position:absolute; top:12px; right:12px; z-index:36; display:flex; align-items:center; gap:10px; max-width:calc(100% - 24px); box-sizing:border-box; padding:8px 11px; border:1px solid rgba(255,255,255,.38); border-radius:17px; background:rgba(10,18,26,.72); color:#fff; backdrop-filter:blur(12px) saturate(115%); box-shadow:0 8px 28px rgba(0,0,0,.30); pointer-events:auto; cursor:grab; touch-action:none; user-select:none; -webkit-user-select:none; }
          .map-live-status.dragging { cursor:grabbing; }
          .map-live-status .battery-ring { flex:0 0 auto; width:46px; height:46px; }
          .map-live-status .status-copy { min-width:0; }
          .map-live-status .status-label { font-size:10px; opacity:.72; }
          .map-live-status [data-role="mower-status"] { display:block; max-width:230px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; line-height:1.15; }
          .map-live-status .mowing-live-line { margin-top:3px; font-size:11px; }
          .map-live-status .mowing-live-line .mowing-live-target { max-width:185px; }
          @media (max-width:720px) {
            .map-live-status:not([data-user-positioned="true"]) { top:9px; right:9px; padding:7px 9px; gap:8px; border-radius:15px; }
            .map-live-status[data-user-positioned="true"] { padding:7px 9px; gap:8px; border-radius:15px; }
            .map-live-status .battery-ring { width:42px; height:42px; }
            .map-live-status [data-role="mower-status"] { max-width:180px; font-size:13px; }
            .map-live-status .mowing-live-line .mowing-live-target { max-width:130px; }
          }
          .mowing-target-tile { border:1px solid rgba(255,255,255,.15) !important; transition:none !important; }
          .mowing-target-tile:hover { background:var(--anthbot-secondary-background) !important; }
          .mowing-target-tile.active,.mowing-target-tile.active:hover { background:linear-gradient(145deg,#5ee083,#43c96c) !important; border-color:#8cf2aa !important; color:#07140c !important; box-shadow:0 0 0 2px rgba(114,239,160,.30) inset,0 8px 24px rgba(0,0,0,.22); }
          .mowing-target-tile.active strong,.mowing-target-tile.active span { color:#07140c !important; }
          .mowing-zone-group { margin:10px 0; }
          .mowing-zone-group > summary span { opacity:.75; font-size:13px; }
          .mowing-order { display:flex; flex-direction:column; gap:7px; margin-top:10px; }
          .mowing-order-title { font-weight:800; margin:2px 0; }
          .mowing-order-row { display:grid; grid-template-columns:32px 1fr 42px 42px; align-items:center; gap:7px; padding:7px 9px; border-radius:11px; background:rgba(255,255,255,.08); }
          .mowing-order-row button { min-height:36px; border:1px solid rgba(255,255,255,.18); border-radius:9px; background:rgba(255,255,255,.10); color:#fff; font-size:19px; cursor:pointer; }
          .mowing-order-row button:disabled { opacity:.32; cursor:default; }
          .task-action-tile.start,.task-action-tile.resume { background:linear-gradient(145deg,#31bf62,#249c4d) !important; }
          .task-action-tile.pause { background:linear-gradient(145deg,#f0a829,#d77f16) !important; }
          .settings-section, .zone-settings { margin:10px 0; border:1px solid rgba(255,255,255,.14); border-radius:14px; background:rgba(7,15,23,.22); overflow:hidden; }
          .settings-section > summary, .zone-settings > summary { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 16px; cursor:pointer; font-weight:800; list-style:none; user-select:none; }
          .settings-section > summary::-webkit-details-marker, .zone-settings > summary::-webkit-details-marker { display:none; }
          .settings-section > summary::after, .zone-settings > summary::after { content:"⌄"; font-size:20px; transition:transform .18s ease; }
          .settings-section[open] > summary::after, .zone-settings[open] > summary::after { transform:rotate(180deg); }
          .settings-section-body, .zone-settings-body { padding:0 10px 12px; }
          .zone-settings { margin:8px 0; background:rgba(7,15,23,.28); }
          .custom-button-actions-note { margin:0 2px 12px; color:#aeb7c2; font-size:12px; line-height:1.45; }
          .custom-button-action-grid { display:grid; gap:10px; }
          .custom-button-action-row { display:grid; grid-template-columns:minmax(120px,.7fr) minmax(190px,1.5fr) minmax(170px,1.1fr); gap:9px; align-items:end; padding:11px; border:1px solid rgba(255,255,255,.14); border-radius:13px; background:rgba(255,255,255,.055); }
          .custom-button-action-row label { display:grid; gap:5px; min-width:0; }
          .custom-button-action-row label > span { font-size:11px; color:#aeb7c2; }
          .custom-button-action-row strong { align-self:center; font-size:14px; overflow-wrap:anywhere; }
          .custom-button-action-row input { box-sizing:border-box; width:100%; min-width:0; min-height:38px; padding:7px 9px; border:1px solid rgba(255,255,255,.18); border-radius:9px; background:rgba(8,16,24,.76); color:#fff; font:inherit; }
          .custom-button-action-row input::placeholder { color:rgba(255,255,255,.42); }
          .custom-button-action-enabled { margin-bottom:10px; }
          .custom-button-actions-disabled .custom-button-action-grid { opacity:.45; pointer-events:none; }
          .custom-button-actions-footer { display:flex; justify-content:flex-end; gap:8px; margin-top:11px; }
          .custom-button-actions-footer button { min-height:38px; padding:7px 12px; border:1px solid rgba(255,255,255,.18); border-radius:10px; background:rgba(255,255,255,.10); color:#fff; font:inherit; font-weight:800; cursor:pointer; }
          @media (max-width:720px) { .custom-button-action-row { grid-template-columns:1fr; } }
          .obstacle-combined .obstacle-levels { margin-top:12px; }
          .obstacle-combined.disabled .obstacle-levels { display:none; }
          .maintenance-tile { display:flex; flex-direction:column; align-items:stretch; gap:10px; }
          .maintenance-value { font-size:22px; font-weight:900; color:#55e58a; }
          .maintenance-reset { min-height:42px; border:1px solid rgba(255,255,255,.18); border-radius:12px; background:rgba(255,255,255,.10); color:#fff; font:inherit; font-weight:800; cursor:pointer; }
          .mowing-history-summary { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
          .mowing-history-summary-item { flex:1 1 140px; padding:10px 12px; border-radius:12px; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.14); }
          .mowing-history-summary-item span { display:block; font-size:11px; color:#aeb7c2; margin-bottom:2px; }
          .mowing-history-summary-item strong { font-size:16px; }
          .mowing-history-empty { padding:14px 4px; color:#aeb7c2; font-size:13px; }
          .mowing-history-list { display:flex; flex-direction:column; gap:10px; }
          .mowing-history-card { padding:12px 14px; border-radius:14px; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); }
          .mowing-history-head { margin-bottom:8px; font-size:14px; }
          .mowing-history-stats { display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:8px; margin-bottom:8px; }
          .mowing-history-stat { display:flex; flex-direction:column; gap:2px; }
          .mowing-history-stat span { font-size:11px; color:#aeb7c2; }
          .mowing-history-stat strong { font-size:14px; }
          .mowing-history-zones { display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; }
          .mowing-history-zone-chip { display:flex; flex-direction:column; gap:2px; padding:6px 10px; border-radius:10px; background:rgba(114,239,160,.10); border:1px solid rgba(114,239,160,.28); }
          .mowing-history-zone-chip strong { font-size:12px; }
          .mowing-history-zone-chip span { font-size:11px; color:#aeb7c2; }
          .mowing-history-raw { margin-top:8px; }
          .mowing-history-raw summary { font-size:11px; color:#aeb7c2; cursor:pointer; }
          .mowing-history-raw pre { margin:6px 0 0; max-height:220px; overflow:auto; font-size:11px; }
          @media (max-width:720px) {
            .canvas-wrap.auto-map-size { aspect-ratio:auto; height:calc(100dvh - 78px); min-height:0; max-height:none; }
            .preview-hint { max-width:52%; padding:8px 10px; border-radius:13px; }
            .preview-hint strong { font-size:14px; }
            .preview-hint span { font-size:11px; }
            .anthbot-glass-panel { left:8px; right:8px; bottom:60px; width:auto; max-height:76%; }
            .anthbot-menu-toggle { right:9px; bottom:9px; min-height:40px; padding:7px 11px; font-size:14px; }
          }
        
        .mowing-mode-info { border:0; background:transparent; color:var(--primary-color); cursor:pointer; font-size:16px; padding:0 2px; vertical-align:middle; }
        .mowing-mode-info-overlay { position:fixed; inset:0; z-index:10000; display:flex; align-items:center; justify-content:center; padding:20px; background:rgba(0,0,0,.45); }
        .mowing-mode-info-dialog { width:min(480px,100%); max-height:80vh; overflow:auto; box-sizing:border-box; padding:20px; border:1px solid rgba(255,255,255,.10); border-radius:18px; background:#1f1f1f; color:#f5f5f5; box-shadow:0 16px 44px rgba(0,0,0,.45); }
        .mowing-mode-info-dialog h3 { margin:0 0 18px; font-size:20px; }
        .mowing-mode-info-dialog > strong { display:block; margin-top:14px; }
        .mowing-mode-info-dialog p { margin:6px 0 0; line-height:1.5; color:#b8b8b8; }
        .mowing-mode-edge-highlight { color:#ffffff; font-weight:800; }
        .mowing-mode-info-close { width:100%; margin-top:20px; padding:11px 14px; border:0; border-radius:12px; background:#03a9d9; color:#ffffff; font-weight:700; cursor:pointer; }

          .mowing-mode-tile .control-head { gap:8px; }
          .mowing-mode-tile .control-head > span { display:flex; align-items:center; gap:5px; min-width:0; }
          .mowing-mode-tile .control-head > strong { flex:0 1 auto; min-width:0; text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
          .mowing-mode-options { display:grid !important; grid-template-columns:repeat(2,minmax(0,1fr)) !important; gap:8px !important; width:100%; }
          .mowing-mode-options .height-option { min-width:0 !important; width:100% !important; box-sizing:border-box; padding:9px 6px !important; white-space:nowrap !important; overflow:hidden; text-overflow:ellipsis; font-size:13px; }
          @media (max-width: 600px) {
            .mowing-mode-tile .control-head { align-items:flex-start; }
            .mowing-mode-tile .control-head > strong { font-size:14px; }
            .mowing-mode-options { gap:6px !important; }
            .mowing-mode-options .height-option { padding:8px 4px !important; font-size:12px !important; }
          }
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
                <span class="mowing-live-line" data-role="mowing-live-line" hidden>
                  <span class="mowing-live-target" data-role="mowing-live-target">-</span>
                  <strong class="mowing-live-progress" data-role="mowing-live-progress">--%</strong>
                </span>
                <span class="cloud-status" data-role="cloud-status">${this.t("cloudChecking")}</span>
              </div>
            </div>
          </div>
          <div class="panel-tabs">
            <button type="button" data-panel="control">${this.t("control")}</button>
            <button type="button" data-panel="settings">${this.t("robotSettings")}</button>
            <button type="button" data-panel="interface">${this.t("interfaceSettings")}</button>
            <button type="button" data-panel="status">${this.t("status")}</button>
            <button type="button" data-panel="maintenance">${this.t("maintenance")}</button>
            <button type="button" data-panel="diagnostics">${this.t("diagnostics")}</button>
          </div>
        </section>
        <div class="canvas-wrap">
          <canvas></canvas>
          <div class="map-live-status" data-role="map-live-status">
            <div class="battery-ring" data-role="battery-ring">
              <span data-role="battery-value">--</span>
            </div>
            <div class="status-copy">
              <span class="status-label">${this.t("status")}</span>
              <strong data-role="mower-status">-</strong>
              <span class="mowing-live-line" data-role="mowing-live-line" hidden>
                <span class="mowing-live-target" data-role="mowing-live-target">-</span>
                <strong class="mowing-live-progress" data-role="mowing-live-progress">--%</strong>
              </span>
            </div>
          </div>
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
            <button type="button" data-action="reset-robot">${this.t("reset")}</button>
          </div>
          <div class="calibration-title">${this.t("mowingPathFit")}</div>
          <div class="calibration-grid">
            <button type="button" data-mowing-path-calibration="up">${this.t("up")}</button>
            <button type="button" data-mowing-path-calibration="left">${this.t("left")}</button>
            <button type="button" data-mowing-path-calibration="right">${this.t("right")}</button>
            <button type="button" data-mowing-path-calibration="down">${this.t("down")}</button>
            <button type="button" data-mowing-path-calibration="narrower">${this.t("narrower")}</button>
            <button type="button" data-mowing-path-calibration="wider">${this.t("wider")}</button>
            <button type="button" data-mowing-path-calibration="shorter">${this.t("shorter")}</button>
            <button type="button" data-mowing-path-calibration="taller">${this.t("taller")}</button>
            <button type="button" data-mowing-path-calibration="rotate-left">${this.t("rotation")} -</button>
            <button type="button" data-mowing-path-calibration="rotate-right">${this.t("rotation")} +</button>
            <button type="button" data-action="reset-mowing-path">${this.t("reset")}</button>
          </div>
          <div class="calibration-title">${this.t("robotDirection")}</div>
          <div class="calibration-grid">
            <button type="button" data-robot-heading="left">-15°</button>
            <button type="button" data-robot-heading="right">+15°</button>
            <button type="button" data-robot-heading="around">180°</button>
            <button type="button" data-action="reset-robot-heading">${this.t("reset")}</button>
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
    root.querySelectorAll("button[data-mowing-path-calibration]").forEach((button) => {
      button.addEventListener("click", () => this.handleMowingPathCalibration(button.dataset.mowingPathCalibration));
    });
    root.querySelectorAll("button[data-robot-heading]").forEach((button) => {
      button.addEventListener("click", () => this.handleRobotHeading(button.dataset.robotHeading));
    });
    root.querySelectorAll("button[data-boundary-calibration]").forEach((button) => {
      button.addEventListener("click", () => this.handleBoundaryCalibration(button.dataset.boundaryCalibration));
    });
    const panelBody = root.querySelector('[data-role="panel-body"]');
    panelBody?.addEventListener("pointerdown", () => {
      // A live HA state update must not replace a pressed button between
      // pointerdown and click; otherwise the first press appears ignored.
      this.panelInteractionUntil = Date.now() + 1200;
    }, true);
    panelBody?.addEventListener("keydown", () => {
      this.panelInteractionUntil = Date.now() + 1200;
    }, true);
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
    this.setupMapLiveStatusDrag(canvasWrap);
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

  // Extracted out of updateRenderer() so the mowing-history detail popup
  // can compute the exact same live "pose" the live map renderer feeds
  // into getWorldBounds() -- reusing the identical logic here (rather than
  // a second, possibly-drifting copy) is what keeps the popup's world
  // bounds, and therefore its scale, in sync with the live map's.
  computeLivePose(attributes = this.entity?.attributes || {}) {
    const rawPose = attributes.pose && typeof attributes.pose === "object" ? attributes.pose : {};
    const coordinatePose = [rawPose, attributes.cur_pose, attributes.map_scan_pose].find((candidate) =>
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
    return coordinatePose
      ? { ...rawPose, ...coordinatePose, yaw: fallbackYaw }
      : { ...rawPose, yaw: fallbackYaw };
  }

  updateRenderer() {
    if (!this.renderer || !this.entity) {
      return;
    }

    // Keep the complete visual tree stable while the user edits zone
    // settings. Map, zone-button and status refreshes share the same
    // scrollable glass panel and can otherwise trigger browser scroll
    // anchoring even when the settings DOM itself is not rebuilt.
    if (
      this.activePanel === "settings"
      && this.shadowRoot?.querySelector('[data-role="panel-body"]')?.childElementCount
    ) {
      return;
    }

    const attributes = this.entity.attributes || {};
    const pose = this.computeLivePose(attributes);
    // computeLivePose() only returns the merged/fallback-filled pose (what
    // rendering needs); the state's own separate `raw_pose` field wants the
    // pre-merge raw value, so it's reconstructed the same trivial way here.
    const rawPose = attributes.pose && typeof attributes.pose === "object" ? attributes.pose : {};
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
    // Do not rebuild the settings/diagnostics DOM on every cloud refresh.
    // Replacing an open <details> tree (zone settings, or the mowing-history
    // / error-history sections on the Diagnostics tab) resets the panel
    // scroll position and collapses whatever the user just expanded.
    if (
      this.activePanel !== "settings"
      && this.activePanel !== "diagnostics"
      && Date.now() >= this.panelInteractionUntil
      && !this.isPanelControlActive()
    ) {
      this.renderAppPanel();
    }
    this.updateYaml();
  }

  isPanelControlActive() {
    const activeElement = this.shadowRoot?.activeElement;
    if (!activeElement?.closest?.('[data-role="panel-body"]')) {
      return false;
    }
    return ["SELECT", "INPUT"].includes(activeElement.tagName);
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

  mapLiveStatusStorageKey() {
    return `anthbot-map-live-status-position:${String(this.config?.entity || "default")}`;
  }

  readMapLiveStatusPosition() {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(this.mapLiveStatusStorageKey()) || "null");
      const x = Number(parsed?.x);
      const y = Number(parsed?.y);
      return Number.isFinite(x) && Number.isFinite(y)
        ? { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) }
        : null;
    } catch (_error) {
      return null;
    }
  }

  writeMapLiveStatusPosition(position) {
    try {
      window.localStorage.setItem(this.mapLiveStatusStorageKey(), JSON.stringify(position));
    } catch (_error) {
      // localStorage can be unavailable in restricted browser contexts.
    }
  }

  applyMapLiveStatusPosition(canvasWrap, status, position = this.readMapLiveStatusPosition()) {
    if (!canvasWrap || !status || !position) return false;
    const maxX = Math.max(0, canvasWrap.clientWidth - status.offsetWidth);
    const maxY = Math.max(0, canvasWrap.clientHeight - status.offsetHeight);
    status.style.left = `${Math.round(maxX * position.x)}px`;
    status.style.top = `${Math.round(maxY * position.y)}px`;
    status.style.right = "auto";
    status.style.bottom = "auto";
    status.dataset.userPositioned = "true";
    return true;
  }

  setupMapLiveStatusDrag(canvasWrap) {
    const status = this.shadowRoot.querySelector('[data-role="map-live-status"]');
    if (!canvasWrap || !status) return;

    const savedPosition = this.readMapLiveStatusPosition();
    requestAnimationFrame(() => this.applyMapLiveStatusPosition(canvasWrap, status, savedPosition));

    let drag = null;
    const move = (event) => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      event.preventDefault();
      event.stopPropagation();
      const dx = event.clientX - drag.clientX;
      const dy = event.clientY - drag.clientY;
      if (Math.hypot(dx, dy) > 3) drag.moved = true;
      const maxX = Math.max(0, canvasWrap.clientWidth - status.offsetWidth);
      const maxY = Math.max(0, canvasWrap.clientHeight - status.offsetHeight);
      const left = Math.max(0, Math.min(maxX, drag.left + dx));
      const top = Math.max(0, Math.min(maxY, drag.top + dy));
      status.style.left = `${Math.round(left)}px`;
      status.style.top = `${Math.round(top)}px`;
      status.style.right = "auto";
      status.style.bottom = "auto";
      status.dataset.userPositioned = "true";
    };

    const finish = (event) => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      event.preventDefault();
      event.stopPropagation();
      try { status.releasePointerCapture(event.pointerId); } catch (_error) {}
      status.classList.remove("dragging");
      if (drag.moved) {
        const maxX = Math.max(0, canvasWrap.clientWidth - status.offsetWidth);
        const maxY = Math.max(0, canvasWrap.clientHeight - status.offsetHeight);
        const left = Number.parseFloat(status.style.left) || 0;
        const top = Number.parseFloat(status.style.top) || 0;
        this.writeMapLiveStatusPosition({
          x: maxX > 0 ? Math.max(0, Math.min(1, left / maxX)) : 0,
          y: maxY > 0 ? Math.max(0, Math.min(1, top / maxY)) : 0,
        });
        this.suppressMapExpandClickUntil = Date.now() + 350;
      }
      drag = null;
    };

    status.addEventListener("pointerdown", (event) => {
      if (event.button !== undefined && event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      const wrapRect = canvasWrap.getBoundingClientRect();
      const statusRect = status.getBoundingClientRect();
      drag = {
        pointerId: event.pointerId,
        clientX: event.clientX,
        clientY: event.clientY,
        left: statusRect.left - wrapRect.left,
        top: statusRect.top - wrapRect.top,
        moved: false,
      };
      status.style.left = `${Math.round(drag.left)}px`;
      status.style.top = `${Math.round(drag.top)}px`;
      status.style.right = "auto";
      status.style.bottom = "auto";
      status.dataset.userPositioned = "true";
      status.classList.add("dragging");
      try { status.setPointerCapture(event.pointerId); } catch (_error) {}
    });
    status.addEventListener("pointermove", move);
    status.addEventListener("pointerup", finish);
    status.addEventListener("pointercancel", finish);
    status.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });

    const resizeObserver = new ResizeObserver(() => {
      const position = this.readMapLiveStatusPosition();
      if (position && !drag) this.applyMapLiveStatusPosition(canvasWrap, status, position);
    });
    resizeObserver.observe(canvasWrap);
    this.mapLiveStatusResizeObserver?.disconnect();
    this.mapLiveStatusResizeObserver = resizeObserver;
  }

  updateBatteryAndStatus() {
    const batteryEntity = this.getRelatedEntity("battery");
    const batteryPercent = Number(batteryEntity?.state);
    const percent = Number.isFinite(batteryPercent) ? Math.max(0, Math.min(100, batteryPercent)) : 0;
    const charging = this.getRelatedEntity("charging")?.state === "on";

    this.shadowRoot.querySelectorAll('[data-role="battery-value"]').forEach((batteryValue) => {
      batteryValue.textContent = Number.isFinite(batteryPercent) ? `${batteryPercent}` : "--";
    });
    this.shadowRoot.querySelectorAll('[data-role="battery-ring"]').forEach((batteryRing) => {
      batteryRing.style.setProperty("--battery", `${percent * 3.6}deg`);
      batteryRing.classList.toggle("low", percent > 0 && percent < 25);
      batteryRing.classList.toggle("charging", charging);
    });

    const statusEntity = this.getRelatedEntity("status");
    this.shadowRoot.querySelectorAll('[data-role="mower-status"]').forEach((mowerStatus) => {
      mowerStatus.textContent = statusEntity ? this.translateStatus(statusEntity.state) : "-";
    });

    this.updateMowingProgressStatus();
  }

  mowingCompletionStorageKey() {
    const entityId = String(this.config?.entity || this.entity?.entity_id || "default");
    return `anthbot-map-mowing-completion:${entityId}`;
  }

  readMowingCompletionLatch() {
    if (this.mowingCompletionLatched !== null) return this.mowingCompletionLatched === true;
    try {
      this.mowingCompletionLatched = window.localStorage.getItem(this.mowingCompletionStorageKey()) === "1";
    } catch (_error) {
      this.mowingCompletionLatched = false;
    }
    return this.mowingCompletionLatched === true;
  }

  setMowingCompletionLatch(enabled) {
    this.mowingCompletionLatched = Boolean(enabled);
    try {
      if (enabled) window.localStorage.setItem(this.mowingCompletionStorageKey(), "1");
      else window.localStorage.removeItem(this.mowingCompletionStorageKey());
    } catch (_error) {}
  }

  updateMowingProgressStatus() {
    const lines = Array.from(this.shadowRoot.querySelectorAll('[data-role="mowing-live-line"]'));
    if (!lines.length) return;

    const progressEntity = this.getRelatedEntity("mowingProgress");
    const progress = Number(progressEntity?.state);
    const attrs = progressEntity?.attributes || {};
    const mapAttrs = this.entity?.attributes || {};
    const statusEntity = this.getRelatedEntity("status");
    const rawStatus = String(
      mapAttrs.robot_status_raw
      ?? progressEntity?.attributes?.robot_status_raw
      ?? statusEntity?.attributes?.robot_status_raw
      ?? statusEntity?.state
      ?? ""
    ).trim().toLowerCase().replace(/[_\s-]+/g, "");

    const activeIdsRaw = attrs.active_zone_ids;
    const activeIds = Array.isArray(activeIdsRaw)
      ? activeIdsRaw.map(String)
      : String(activeIdsRaw ?? "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

    const debugZones = Array.isArray(attrs.zones_debug) ? attrs.zones_debug : [];
    const debugNamesById = new Map(
      debugZones
        .filter((zone) => zone && zone.id !== undefined && zone.id !== null)
        .map((zone) => [String(zone.id), String(zone.name || "").trim()])
    );
    const configuredNamesById = new Map(
      this.currentZones()
        .filter((zone) => zone && zone.id !== undefined && zone.id !== null)
        .map((zone) => [String(zone.id), String(zone.name || `${this.t("zone")} ${zone.id}`).trim()])
    );

    const zoneNames = activeIds.map((id) =>
      debugNamesById.get(id) || configuredNamesById.get(id) || `${this.t("zone")} ${id}`
    );

    let target = "";
    if (zoneNames.length) {
      target = zoneNames.join(" + ");
    } else if (rawStatus.includes("nestmowing")) {
      target = this.t("dockEdgeLabel");
    } else if (rawStatus.includes("edgemowing") || rawStatus.includes("bordermowing")) {
      target = this.t("commandOuterEdge");
    } else if (rawStatus.includes("pointmowing") || rawStatus.includes("spotmowing")) {
      target = this.translateStatus("point_mowing");
    } else if (rawStatus.includes("globalmowing") || rawStatus === "mowing") {
      target = this.t("fullArea");
    }

    const activeMowingStatus = [
      "mowing", "zonemowing", "regionmowing", "globalmowing", "nestmowing",
      "edgemowing", "bordermowing", "pointmowing", "spotmowing",
    ].some((value) => rawStatus.includes(value));
    const mowingLike = zoneNames.length > 0 || activeMowingStatus;

    const displayStatus = String(statusEntity?.state || "")
      .trim().toLowerCase().replace(/[_\s-]+/g, "");

    // IMPORTANT: robot_status_raw / active_zone_ids can remain stale after a
    // completed task (for example raw "zonemowing" while the real mower-status
    // entity is already "standby"). Never use that stale raw value to clear
    // the completion latch. Prefer the canonical HA mower_status entity for
    // lifecycle decisions and only fall back to raw status when it is missing.
    const hasCanonicalStatus = Boolean(statusEntity && String(statusEntity.state || "").trim());
    const lifecycleMowing = hasCanonicalStatus
      ? displayStatus === "mowing"
      : activeMowingStatus;
    const lifecycleFinished = hasCanonicalStatus
      ? [
          "returningtodock", "backtodock", "returntodock", "docking",
          "charging", "charge", "docked", "standby", "idle",
        ].some((value) => displayStatus.includes(value))
      : [
          "returning", "returningtodock", "backtodock", "returntodock",
          "docking", "charging", "charge", "docked", "standby", "idle",
          "visszaatoltore", "toltes", "dokkolva", "keszenlet",
        ].some((value) => rawStatus.includes(value));

    const boundedProgress = Number.isFinite(progress)
      ? Math.max(0, Math.min(100, progress))
      : NaN;

    // A genuinely new mowing task clears the previous completion latch. Once
    // a task has reached >=95% and the mower is in a finished/return/docked/
    // standby state, keep 100% latched until the next real mowing state starts.
    // Including standby here also repairs the latch if the browser missed the
    // short return/charging transition entirely.
    let completionLatched = this.readMowingCompletionLatch();
    if (lifecycleMowing) {
      if (completionLatched) this.setMowingCompletionLatch(false);
      completionLatched = false;
    } else if (lifecycleFinished && Number.isFinite(boundedProgress) && boundedProgress >= 95) {
      if (!completionLatched) this.setMowingCompletionLatch(true);
      completionLatched = true;
    }

    lines.forEach((line) => {
      const targetNode = line.querySelector('[data-role="mowing-live-target"]');
      const progressNode = line.querySelector('[data-role="mowing-live-progress"]');
      if (!targetNode || !progressNode) return;

      if (!Number.isFinite(progress) || (!mowingLike && !completionLatched)) {
        line.hidden = true;
        return;
      }

      targetNode.textContent = target || this.translateStatus(statusEntity?.state || "mowing");

      // Completion tolerance: once a >=95% task has been accepted as finished
      // during return/docking, keep showing 100% through charging and standby
      // until a new mowing state begins. A manual early return below 95% never
      // sets the latch and therefore keeps its actual percentage.
      const displayProgress = completionLatched ? 100 : boundedProgress;
      progressNode.textContent = `${displayProgress.toFixed(1)}%`;
      line.hidden = false;
    });
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
    } else if (this.activePanel === "maintenance") {
      this.renderMaintenancePanel(body);
    } else if (this.activePanel === "diagnostics") {
      this.renderDiagnosticsPanel(body);
    } else {
      this.renderControlPanel(body);
    }
  }

  renderControlPanel(body) {
    body.innerHTML = "";
    const targetGrid = this.createPanelGrid();
    targetGrid.classList.add("mowing-target-grid");
    const actionGrid = this.createPanelGrid();
    actionGrid.classList.add("mowing-action-grid");
    const action = this.primaryMowingAction();
    actionGrid.append(
      this.createPrimaryMowingTile(action),
      this.createCommandTile(this.t("stopLabel"), this.t("stopSub"), "stop"),
      this.createCommandTile(this.t("homeLabel"), this.t("homeSub"), "dock"),
    );

    const fullTile = document.createElement("button");
    fullTile.type = "button";
    fullTile.className = `panel-tile mowing-target-tile ${this.selectedMowingTarget?.type === "full" ? "active" : ""}`;
    fullTile.innerHTML = `<strong>${this.t("fullArea")}</strong><span>${this.t("selectMowingTarget")}</span>`;
    fullTile.addEventListener("click", () => {
      this.selectedMowingTarget = { type: "full" };
      this.renderControlPanel(body);
    });
    targetGrid.appendChild(fullTile);

    const edgeTile = document.createElement("button");
    edgeTile.type = "button";
    edgeTile.className = `panel-tile mowing-target-tile ${this.selectedMowingTarget?.type === "edge" ? "active" : ""}`;
    edgeTile.innerHTML = `<strong>${this.t("commandOuterEdge")}</strong><span>${this.t("selectMowingTarget")}</span>`;
    edgeTile.addEventListener("click", () => {
      this.selectedMowingTarget = { type: "edge" };
      this.renderControlPanel(body);
    });
    targetGrid.appendChild(edgeTile);

    const dockEdgeTile = document.createElement("button");
    dockEdgeTile.type = "button";
    dockEdgeTile.className = `panel-tile mowing-target-tile ${this.selectedMowingTarget?.type === "dock-edge" ? "active" : ""}`;
    dockEdgeTile.innerHTML = `<strong>${this.t("dockEdgeLabel")}</strong><span>${this.t("selectMowingTarget")}</span>`;
    dockEdgeTile.addEventListener("click", () => {
      this.selectedMowingTarget = { type: "dock-edge" };
      this.renderControlPanel(body);
    });
    targetGrid.appendChild(dockEdgeTile);

    body.appendChild(targetGrid);
    const manualZones = this.currentZones();
    if (manualZones.length) body.appendChild(this.createMowingZoneGroup("zone-set", this.t("manualZones"), manualZones, body));
    const automaticZones = this.currentAutoZones();
    if (automaticZones.length) body.appendChild(this.createMowingZoneGroup("auto-zone-set", this.t("autoZones"), automaticZones, body));
    body.appendChild(actionGrid);
  }

  createMowingZoneGroup(type, title, zones, body) {
    const selected = this.selectedMowingTarget?.type === type ? this.selectedMowingTarget.zones || [] : [];
    const details = document.createElement("details");
    details.className = "settings-section mowing-zone-group";
    details.open = Boolean(this.mowingZoneGroupsOpen[type]);
    details.innerHTML = `<summary>${title}<span>${selected.length} ${this.t("selectedCount")}</span></summary><div class="settings-section-body"></div>`;
    details.addEventListener("toggle", () => {
      this.mowingZoneGroupsOpen[type] = details.open;
    });
    const content = details.querySelector(".settings-section-body");
    const grid = this.createPanelGrid();
    for (const zone of zones) {
      const tile = document.createElement("button");
      tile.type = "button";
      const isSelected = selected.some((item) => String(item.id) === String(zone.id));
      tile.className = `panel-tile mowing-target-tile ${isSelected ? "active" : ""}`;
      tile.innerHTML = `<strong>${zone.name || `${type === "auto-zone-set" ? this.t("autoZone") : this.t("zone")} ${zone.id}`}</strong><span>${this.t("selectMowingTarget")}</span>`;
      tile.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const current = this.selectedMowingTarget?.type === type ? [...(this.selectedMowingTarget.zones || [])] : [];
        const index = current.findIndex((item) => String(item.id) === String(zone.id));
        if (index >= 0) current.splice(index, 1); else current.push(zone);
        this.selectedMowingTarget = current.length ? { type, zones: current } : { type: "full" };
        this.renderControlPanel(body);
      });
      grid.appendChild(tile);
    }
    content.appendChild(grid);
    if (selected.length) {
      const order = document.createElement("div");
      order.className = "mowing-order";
      order.innerHTML = `<div class="mowing-order-title">${this.t("mowingOrder")}</div>`;
      selected.forEach((zone, index) => {
        const row = document.createElement("div");
        row.className = "mowing-order-row";
        row.innerHTML = `<strong>${index + 1}.</strong><span>${zone.name || `${this.t("zone")} ${zone.id}`}</span>`;
        const up = document.createElement("button");
        up.type = "button"; up.textContent = "↑"; up.disabled = index === 0; up.title = this.t("moveUp");
        const down = document.createElement("button");
        down.type = "button"; down.textContent = "↓"; down.disabled = index === selected.length - 1; down.title = this.t("moveDown");
        up.addEventListener("click", () => this.moveSelectedZone(type, index, -1, body));
        down.addEventListener("click", () => this.moveSelectedZone(type, index, 1, body));
        row.append(up, down);
        order.appendChild(row);
      });
      content.appendChild(order);
    }
    return details;
  }

  moveSelectedZone(type, index, offset, body) {
    if (this.selectedMowingTarget?.type !== type) return;
    const zones = [...(this.selectedMowingTarget.zones || [])];
    const targetIndex = index + offset;
    if (targetIndex < 0 || targetIndex >= zones.length) return;
    [zones[index], zones[targetIndex]] = [zones[targetIndex], zones[index]];
    this.selectedMowingTarget = { type, zones };
    this.renderControlPanel(body);
  }

  renderSettingsPanel(body) {
    body.innerHTML = "";
    const globalSection = this.createSettingsSection(this.t("globalSettings"), "global", true);
    const grid = this.createPanelGrid();
    grid.append(
      this.createCommandTile(this.t("cloud"), this.t("cloudSub"), "connect"),
      this.createMowHeightControl(),
      this.createNumberControl(this.t("mowCount"), "mowCount", 1, 3, 1, "×"),
      this.createDirectObstacleControl(
        this.getSwitchEntity("visualObstacle"),
        this.getNumberEntity("visualObstacleLevel"),
      ),
      this.createNumberControl(this.t("customDirection"), "mowDirection", 0, 180, 1, "deg"),
      this.createNumberControl(this.t("rainDelay"), "rainContinue", 0, 8, 1, "h"),
      this.createNumberControl(this.t("volume"), "voiceVolume", 0, 100, 1, "%"),
      this.createSwitchControl(this.t("rainDetection"), "rain"),
      this.createSwitchControl(this.t("customCutDirection"), "customDirection"),
      this.createSwitchControl(this.t("edgeReturn"), "edgeReturn"),
      this.createSwitchControl(this.t("autoDockMow"), "autoDockMow"),
      this.createSwitchControl(this.t("batterySaverMode"), "batterySaver"),
    );
    globalSection.querySelector(".settings-section-body").appendChild(grid);
    body.appendChild(globalSection);
    body.appendChild(this.createCustomButtonActionsSection());
    renderAnthbotEdgeSettings(this, body);
    this.renderZoneSettings(body);
  }

  createCustomButtonActionsSection() {
    const section = this.createSettingsSection(this.t("customButtonActions"), "custom-button-actions");
    const content = section.querySelector(".settings-section-body");
    content.classList.toggle("custom-button-actions-disabled", !this.customButtonActionsEnabled);

    const enabled = document.createElement("label");
    enabled.className = "panel-tile switch-tile custom-button-action-enabled";
    enabled.innerHTML = `<span><strong>${escapeHtml(this.t("customButtonActionsEnable"))}</strong><small style="display:block;opacity:.68;margin-top:3px">${escapeHtml(this.t("customButtonActionsEnableNote"))}</small></span><input type="checkbox" ${this.customButtonActionsEnabled ? "checked" : ""}>`;
    const enabledInput = enabled.querySelector("input");
    enabledInput.addEventListener("change", async () => {
      this.customButtonActionsEnabled = enabledInput.checked;
      content.classList.toggle("custom-button-actions-disabled", !this.customButtonActionsEnabled);
      this.updateYaml();
      await this.persistCustomButtonActions();
    });
    content.appendChild(enabled);

    const note = document.createElement("div");
    note.className = "custom-button-actions-note";
    note.textContent = this.t("customButtonActionsNote");
    content.appendChild(note);

    const serviceListId = `anthbot-services-${this.entityBase()}-${Math.random().toString(36).slice(2, 8)}`;
    const entityListId = `anthbot-entities-${this.entityBase()}-${Math.random().toString(36).slice(2, 8)}`;
    const serviceList = document.createElement("datalist");
    serviceList.id = serviceListId;
    for (const serviceName of this.customButtonServiceSuggestions()) {
      const option = document.createElement("option");
      option.value = serviceName;
      serviceList.appendChild(option);
    }
    const entityList = document.createElement("datalist");
    entityList.id = entityListId;
    for (const entityId of Object.keys(this._hass?.states || {}).sort()) {
      const option = document.createElement("option");
      option.value = entityId;
      entityList.appendChild(option);
    }
    content.append(serviceList, entityList);

    const commandDefinitions = [
      ["start", this.t("startLabel")],
      ["stop", this.t("stopLabel")],
      ["dock", this.t("homeLabel")],
      ["pause", this.t("pauseTask")],
      ["resume", this.t("resumeTask")],
      ["outer-edge", this.t("commandOuterEdge")],
      ["dock-edge", this.t("commandDockEdge")],
      ["connect", this.t("cloud")],
      ["reset-blade", this.t("resetBlade")],
      ["reset-camera", this.t("resetCamera")],
      ["reset-contact", this.t("resetDockContact")],
    ];
    const rows = document.createElement("div");
    rows.className = "custom-button-action-grid";
    for (const [command, label] of commandDefinitions) {
      const current = this.normalizeCustomButtonAction(this.customButtonActions?.[command]);
      const row = document.createElement("div");
      row.className = "custom-button-action-row";
      row.dataset.command = command;
      row.innerHTML = `
        <strong>${escapeHtml(label)}</strong>
        <label><span>${escapeHtml(this.t("customButtonService"))}</span><input data-field="service" list="${serviceListId}" value="${escapeHtml(current.service || "")}" placeholder="script.anthbot_safe_start"></label>
        <label><span>${escapeHtml(this.t("customButtonTarget"))}</span><input data-field="target" list="${entityListId}" value="${escapeHtml(current.target?.entity_id || "")}" placeholder="${escapeHtml(this.t("customButtonTargetOptional"))}"></label>`;
      const saveRow = () => {
        const service = row.querySelector('[data-field="service"]').value.trim();
        const targetEntity = row.querySelector('[data-field="target"]').value.trim();
        if (!service) {
          delete this.customButtonActions[command];
        } else {
          const previous = this.normalizeCustomButtonAction(this.customButtonActions?.[command]);
          const definition = { ...previous, service };
          if (targetEntity) definition.target = { ...(previous.target || {}), entity_id: targetEntity };
          else delete definition.target;
          this.customButtonActions[command] = definition;
        }
        this.updateYaml();
        void this.persistCustomButtonActions();
      };
      row.querySelectorAll("input").forEach((input) => input.addEventListener("change", saveRow));
      rows.appendChild(row);
    }
    content.appendChild(rows);

    const footer = document.createElement("div");
    footer.className = "custom-button-actions-footer";
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = this.t("customButtonClear");
    clear.addEventListener("click", async () => {
      this.customButtonActions = {};
      this.customButtonActionsEnabled = false;
      this.updateYaml();
      await this.persistCustomButtonActions();
      const panelBody = this.shadowRoot.querySelector('[data-role="panel-body"]');
      if (panelBody && this.activePanel === "settings") this.renderSettingsPanel(panelBody);
    });
    footer.appendChild(clear);
    content.appendChild(footer);
    return section;
  }

  syncCustomButtonActionsFromServer() {
    if (this.customButtonSavePending > 0) return false;
    const attrs = this.entity?.attributes || {};
    const serverConfigured = attrs.custom_button_actions_configured === true;
    const yamlActions = this.config.button_actions || this.config.buttonActions || {};
    const nextActions = serverConfigured && attrs.custom_button_actions && typeof attrs.custom_button_actions === "object"
      ? attrs.custom_button_actions
      : yamlActions;
    const nextEnabled = serverConfigured
      ? attrs.custom_button_actions_enabled === true
      : Object.keys(yamlActions).length > 0;
    const before = JSON.stringify([this.customButtonServerConfigured, this.customButtonActionsEnabled, this.customButtonActions]);
    const after = JSON.stringify([serverConfigured, nextEnabled, nextActions]);
    if (before === after) return false;
    this.customButtonServerConfigured = serverConfigured;
    this.customButtonActionsEnabled = nextEnabled;
    this.customButtonActions = { ...nextActions };
    return true;
  }

  persistCustomButtonActions() {
    if (!this._hass?.callService) return Promise.resolve();
    const payload = {
      entity_id: this._activeEntityId || this.config.entity,
      enabled: this.customButtonActionsEnabled,
      actions: JSON.parse(JSON.stringify(this.customButtonActions || {})),
    };
    this.customButtonServerConfigured = true;
    this.customButtonSavePending += 1;
    const save = async () => {
      try {
        await this._hass.callService("anthbot_map", "set_custom_button_actions", payload);
        this.scheduleRefresh(100);
      } catch (error) {
        this.notify(this.t("settingFailed"));
        throw error;
      } finally {
        this.customButtonSavePending = Math.max(0, this.customButtonSavePending - 1);
      }
    };
    this.customButtonSaveQueue = this.customButtonSaveQueue.catch(() => {}).then(save);
    return this.customButtonSaveQueue;
  }

  normalizeCustomButtonAction(action) {
    if (typeof action === "string") return { service: action, target: {} };
    return action && typeof action === "object" ? action : { service: "", target: {} };
  }

  customButtonServiceSuggestions() {
    const preferred = [];
    const other = [];
    for (const [domain, services] of Object.entries(this._hass?.services || {})) {
      for (const service of Object.keys(services || {})) {
        const fullName = `${domain}.${service}`;
        if (domain === "script") preferred.push(fullName); else other.push(fullName);
      }
    }
    return [...new Set([...preferred.sort(), ...other.sort()])];
  }

  effectiveCustomButtonAction(command) {
    if (!this.customButtonActionsEnabled) return null;
    return this.customButtonActions?.[command] || null;
  }

  renderMaintenancePanel(body) {
    body.innerHTML = "";
    const maintenanceGrid = this.createPanelGrid();
    maintenanceGrid.append(
      this.createMaintenanceTile(this.t("bladeMaintenance"), "blade", this.t("resetBlade"), "reset-blade"),
      this.createMaintenanceTile(this.t("cameraMaintenance"), "camera", this.t("resetCamera"), "reset-camera"),
      this.createMaintenanceTile(this.t("dockContactMaintenance"), "contact", this.t("resetDockContact"), "reset-contact"),
    );
    body.appendChild(maintenanceGrid);
  }

  maintenanceValue(kind) {
    const raw = this.entity?.attributes?.maintenance || {};
    const aliases = {
      blade: ["rc_pecent", "rc_percent", "blade", "cutting_components_life"],
      camera: ["cl_pecent", "cl_percent", "camera", "camera_life"],
      contact: ["ccp_pecent", "ccp_percent", "charging_contact", "recharge_contact_life"],
    }[kind] || [];
    const value = aliases.map((key) => raw?.[key]).find((item) => item !== undefined && item !== null && item !== "");
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return this.t("maintenanceUnavailable");
    const percent = Math.max(0, Math.min(100, numeric));
    const maximumHours = kind === "camera" ? 480 : kind === "contact" ? 720 : null;
    const hours = maximumHours === null ? "" : ` · ${Math.floor(percent * maximumHours / 100)} h`;
    return `${Math.round(percent)}%${hours}`;
  }

  createMaintenanceTile(title, kind, resetLabel, command) {
    const tile = document.createElement("div");
    tile.className = "panel-tile maintenance-tile";
    tile.innerHTML = `<strong>${title}</strong><span>${this.t("remainingLife")}</span><span class="maintenance-value">${this.maintenanceValue(kind)}</span>`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `maintenance-reset ${command}`;
    button.textContent = resetLabel;
    button.addEventListener("click", () => this.handleCommand(command));
    tile.appendChild(button);
    return tile;
  }

  settingsStorageKey() {
    return `anthbot-map-open-settings-${this.entityBase()}`;
  }

  readOpenSettingsKey() {
    return window.localStorage.getItem(this.settingsStorageKey()) || "global";
  }

  createSettingsSection(title, key, defaultOpen = false) {
    const details = document.createElement("details");
    details.className = "settings-section";
    details.dataset.settingsKey = key;
    const configuredOpen = this.defaultSubmenu === key
      || ((key === "manual" || key === "auto") && this.defaultSubmenu.startsWith(`${key}-`));
    details.open = configuredOpen || (
      !this.defaultSubmenu
      && (this.readOpenSettingsKey() === key || (defaultOpen && !window.localStorage.getItem(this.settingsStorageKey())))
    );
    details.innerHTML = `<summary>${title}</summary><div class="settings-section-body"></div>`;
    details.addEventListener("toggle", () => {
      if (!details.open) return;
      window.localStorage.setItem(this.settingsStorageKey(), key);
      this.shadowRoot.querySelectorAll("details.settings-section").forEach((item) => {
        if (item !== details) item.open = false;
      });
    });
    return details;
  }

  renderZoneSettings(body) {
    const area = this.entity?.attributes?.area_definition || {};
    const groups = [
      ["manual", this.t("manualZones"), this.currentZones(area)],
      ["auto", this.t("autoZones"), this.currentAutoZones(area)],
    ];
    for (const [kind, groupTitle, zones] of groups) {
      if (!zones.length) continue;
      const section = this.createSettingsSection(groupTitle, kind);
      const sectionBody = section.querySelector(".settings-section-body");
      for (const zone of zones) {
        const zoneKey = `${kind}-${zone.id}`;
        const details = document.createElement("details");
        details.className = "zone-settings";
        details.open = this.defaultSubmenu === zoneKey || (
          !this.defaultSubmenu
          && window.localStorage.getItem(`${this.settingsStorageKey()}-zone`) === zoneKey
        );
        details.innerHTML = `<summary>${zone.name ? String(zone.name) : `${kind === "auto" ? this.t("autoZone") : this.t("zone")} ${zone.id}`}</summary><div class="zone-settings-body"></div>`;
        details.addEventListener("toggle", () => {
          if (!details.open) return;
          window.localStorage.setItem(`${this.settingsStorageKey()}-zone`, zoneKey);
          section.querySelectorAll("details.zone-settings").forEach((item) => {
            if (item !== details) item.open = false;
          });
        });
        const grid = this.createPanelGrid();
        const obstacleSwitch = this.findZoneSettingEntity("switch", kind, zone, "Visual obstacle detection");
        const obstacleLevel = this.findZoneSettingEntity("number", kind, zone, "Obstacle sensitivity");
        grid.append(
          this.createDirectNumberControl(this.t("mowCount"), this.findZoneSettingEntity("number", kind, zone, "Mowing passes"), 1, 3, 1, "×"),
          this.createDirectNumberControl(this.t("cutHeight"), this.findZoneSettingEntity("number", kind, zone, "Cutting height"), 30, 70, 5, "mm"),
          this.createDirectObstacleControl(obstacleSwitch, obstacleLevel),
          this.createDirectSelectControl(this.t("mowingMode"), this.findZoneSettingEntity("select", kind, zone, "Mowing mode"), [this.t("mowingModeNormal"), this.t("mowingModeEfficient")]),
          this.createDirectSwitchControl(this.t("customCutDirection"), this.findZoneSettingEntity("switch", kind, zone, "Custom mowing direction")),
          this.createDirectNumberControl(this.t("customDirection"), this.findZoneSettingEntity("number", kind, zone, "Mowing direction"), 0, 180, 1, "deg"),
        );
        details.querySelector(".zone-settings-body").appendChild(grid);
        sectionBody.appendChild(details);
      }
      body.appendChild(section);
    }
  }

  currentAutoZones(areaDefinition = this.entity?.attributes?.area_definition || {}) {
    for (const key of ["region_areas", "regionAreas", "auto_regions", "auto_zones"]) {
      if (Array.isArray(areaDefinition?.[key])) return areaDefinition[key];
    }
    return [];
  }

  findZoneSettingEntity(domain, kind, zone, settingLabel) {
    const kindLabel = kind === "auto" ? "auto zone" : "zone";
    const zoneLabel = String(zone.name || zone.id).toLowerCase();
    const setting = settingLabel.toLowerCase();
    for (const [entityId, state] of Object.entries(this._hass.states || {})) {
      if (!entityId.startsWith(`${domain}.`) || state.state === "unavailable") continue;
      const name = String(state.attributes?.friendly_name || "").toLowerCase();
      if (name.includes(kindLabel) && name.includes(zoneLabel) && name.includes(setting)) return entityId;
    }
    return null;
  }

  createDirectNumberControl(label, entityId, min, max, step, unit) {
    const value = Number(entityId ? this._hass.states[entityId]?.state : NaN);
    const tile = document.createElement("div");
    tile.className = "panel-tile control-tile";
    tile.innerHTML = `
      <div class="control-head"><span>${label}</span><strong>${Number.isFinite(value) ? value : "-"} ${unit}</strong></div>
      <input type="range" min="${min}" max="${max}" step="${step}" value="${Number.isFinite(value) ? value : min}" ${entityId ? "" : "disabled"}>
    `;
    const input = tile.querySelector("input");
    input.addEventListener("input", () => {
      tile.querySelector("strong").textContent = `${input.value} ${unit}`;
    });
    input.addEventListener("change", async () => {
      await this._hass.callService("number", "set_value", {entity_id: entityId, value: Number(input.value)});
      this.scheduleRefresh();
    });
    return tile;
  }

  createDirectSelectControl(label, entityId, translatedOptions = []) {
    const entity = entityId ? this._hass.states[entityId] : null;
    const current = String(entity?.state || "");
    const rawOptions = Array.isArray(entity?.attributes?.options)
      ? entity.attributes.options
      : ["Normal", "Efficient"];
    const tile = document.createElement("div");
    tile.className = "panel-tile control-tile mowing-mode-tile";
    tile.innerHTML = `
      <div class="control-head">
        <span>${label} <button type="button" class="mowing-mode-info" aria-label="${this.t("mowingModeInfoTitle")}">ⓘ</button></span>
        <strong>${translatedOptions[rawOptions.indexOf(current)] || current || "-"}</strong>
      </div>
      <div class="height-options mowing-mode-options" role="group" aria-label="${label}"></div>
    `;
    tile.querySelector(".mowing-mode-info")?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      this.showMowingModeInfo();
    });
    const options = tile.querySelector(".height-options");
    rawOptions.forEach((option, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "height-option";
      button.textContent = translatedOptions[index] || option;
      button.classList.toggle("active", option === current);
      button.disabled = !entityId;
      button.addEventListener("click", async () => {
        if (!entityId) return;
        options.querySelectorAll(".height-option").forEach((item) => {
          item.classList.toggle("active", item === button);
        });
        tile.querySelector(".control-head strong").textContent = translatedOptions[index] || option;
        await this._hass.callService("select", "select_option", {
          entity_id: entityId,
          option,
        });
        this.scheduleRefresh();
      });
      options.appendChild(button);
    });
    return tile;
  }

  showMowingModeInfo() {
    this.shadowRoot.querySelector(".mowing-mode-info-overlay")?.remove();
    const overlay = document.createElement("div");
    overlay.className = "mowing-mode-info-overlay";
    const dialog = document.createElement("div");
    dialog.className = "mowing-mode-info-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", this.t("mowingModeInfoTitle"));

    const title = document.createElement("h3");
    title.textContent = this.t("mowingModeInfoTitle");

    const normalTitle = document.createElement("strong");
    normalTitle.textContent = this.t("mowingModeNormal");
    const normalText = document.createElement("p");
    normalText.textContent = this.t("mowingModeNormalDescription");

    const efficientTitle = document.createElement("strong");
    efficientTitle.textContent = this.t("mowingModeEfficient");
    const efficientText = document.createElement("p");
    const efficientDescription = this.t("mowingModeEfficientDescription");
    const edgeText = this.t("mowingModeEfficientEdgeHighlight");
    const edgeIndex = efficientDescription.indexOf(edgeText);
    if (edgeText && edgeIndex >= 0) {
      efficientText.append(document.createTextNode(efficientDescription.slice(0, edgeIndex)));
      const highlight = document.createElement("strong");
      highlight.className = "mowing-mode-edge-highlight";
      highlight.textContent = `${this.t("mowingModeImportant")} ${edgeText}`;
      efficientText.append(highlight, document.createTextNode(efficientDescription.slice(edgeIndex + edgeText.length)));
    } else {
      efficientText.textContent = efficientDescription;
    }

    const close = document.createElement("button");
    close.type = "button";
    close.className = "mowing-mode-info-close";
    close.textContent = this.t("close");
    const dismiss = () => overlay.remove();
    close.addEventListener("click", dismiss);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) dismiss();
    });
    dialog.append(title, normalTitle, normalText, efficientTitle, efficientText, close);
    overlay.appendChild(dialog);
    this.shadowRoot.appendChild(overlay);
  }

  createDirectSwitchControl(label, entityId) {
    const checked = entityId && this._hass.states[entityId]?.state === "on";
    const tile = document.createElement("label");
    tile.className = "panel-tile switch-tile";
    tile.innerHTML = `<span>${label}</span><input type="checkbox" ${checked ? "checked" : ""} ${entityId ? "" : "disabled"}>`;
    const input = tile.querySelector("input");
    input.addEventListener("change", async () => {
      await this._hass.callService("switch", input.checked ? "turn_on" : "turn_off", {entity_id: entityId});
      this.scheduleRefresh();
    });
    return tile;
  }

  createDirectObstacleControl(switchEntityId, levelEntityId) {
    const enabled = switchEntityId && this._hass.states[switchEntityId]?.state === "on";
    const tile = document.createElement("div");
    tile.className = `panel-tile obstacle-combined ${enabled ? "" : "disabled"}`;
    const row = document.createElement("label");
    row.className = "switch-tile";
    row.innerHTML = `<span>${this.t("visualObstacle")}</span><input type="checkbox" ${enabled ? "checked" : ""} ${switchEntityId ? "" : "disabled"}>`;
    const levels = document.createElement("div");
    levels.className = "obstacle-levels";
    levels.appendChild(this.createDirectObstacleLevelControl(levelEntityId));
    const input = row.querySelector("input");
    input.addEventListener("change", async () => {
      await this._hass.callService("switch", input.checked ? "turn_on" : "turn_off", {entity_id: switchEntityId});
      tile.classList.toggle("disabled", !input.checked);
      this.scheduleRefresh();
    });
    tile.append(row, levels);
    return tile;
  }

  createDirectObstacleLevelControl(entityId) {
    const value = Number(entityId ? this._hass.states[entityId]?.state : 1);
    const selected = Number.isFinite(value) ? Math.max(0, Math.min(2, Math.round(value))) : 1;
    const labels = [this.t("low"), this.t("medium"), this.t("high")];
    const tile = document.createElement("div");
    tile.className = "panel-tile control-tile";
    tile.innerHTML = `<div class="control-head"><span>${this.t("visualObstacleLevel")}</span><strong>${labels[selected]}</strong></div><div class="height-options"></div>`;
    const options = tile.querySelector(".height-options");
    options.style.cssText = "display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px";
    labels.forEach((label, level) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "height-option";
      button.textContent = label;
      button.style.cssText = "min-width:0;width:100%;padding:8px 3px;font-size:12px;white-space:nowrap";
      button.disabled = !entityId;
      button.classList.toggle("active", level === selected);
      button.addEventListener("click", async () => {
        options.querySelectorAll(".height-option").forEach((item) => item.classList.toggle("active", item === button));
        tile.querySelector("strong").textContent = label;
        await this._hass.callService("number", "set_value", {entity_id: entityId, value: level});
        this.scheduleRefresh();
      });
      options.appendChild(button);
    });
    return tile;
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
    grid.appendChild(this.createShutdownGuardTile());
    body.appendChild(grid);
  }

  createShutdownGuardTile() {
    const tile = document.createElement("div");
    tile.className = "panel-tile info-tile shutdown-guard-tile";
    const label = this.t("batteryShutdownGuardStatusTitle");
    tile.innerHTML = `<span>${label}</span><strong>-</strong>`;
    const value = tile.querySelector("strong");

    const formatDuration = (seconds) => {
      const total = Math.max(0, Math.ceil(Number(seconds) || 0));
      const minutes = Math.floor(total / 60);
      const secs = total % 60;
      return `${minutes}:${String(secs).padStart(2, "0")}`;
    };

    const update = () => {
      if (!tile.isConnected) return;
      const entityId = this.getSwitchEntity("batterySaver");
      const entity = entityId ? this._hass?.states?.[entityId] : null;
      const attrs = entity?.attributes || {};
      const now = Date.now() / 1000;
      const dueAt = Number(attrs.shutdown_guard_due_at);
      const pulseUntil = Number(attrs.shutdown_guard_pulse_until);

      if (!entityId || !entity) {
        value.textContent = "-";
      } else if (entity.state !== "on") {
        value.textContent = this.t("batteryShutdownGuardDisabled");
      } else if (Number.isFinite(pulseUntil) && pulseUntil > now) {
        value.textContent = `${this.t("batteryShutdownGuardPulse")} ${formatDuration(pulseUntil - now)}`;
      } else if (Number.isFinite(dueAt) && dueAt > 0) {
        if (dueAt <= now) {
          value.textContent = this.t("batteryShutdownGuardDue");
        } else {
          value.textContent = `${this.t("batteryShutdownGuardNext")} ${formatDuration(dueAt - now)}`;
        }
      } else {
        const state = String(attrs.shutdown_guard_state || "");
        value.textContent = state === "inactive"
          ? this.t("batteryShutdownGuardInactive")
          : this.t("batteryShutdownGuardInitializing");
      }

      window.setTimeout(update, 1000);
    };

    window.setTimeout(update, 0);
    return tile;
  }

  renderDiagnosticsPanel(body) {
    body.innerHTML = "";
    const grid = this.createPanelGrid();
    for (const item of [
      [this.t("bladeLife"), "rechargeContactLife"],
      [this.t("cameraLife"), "cuttingLineLife"],
      [this.t("dockContact"), "cuttingComponentsLife"],
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
    const attrs = this.entity?.attributes || {};
    const recordsPayload = attrs.mowing_records || { data: [] };
    const recordsError = attrs.mowing_records_error;
    const errors = attrs.error_history || [];
    const history = this.createSettingsSection(this.t("mowingHistory"), "mowing-history");
    this.renderMowingHistoryList(history.querySelector(".settings-section-body"), recordsPayload, recordsError);
    body.appendChild(history);
    const errorHistory = this.createSettingsSection(this.t("errorHistory"), "error-history");
    errorHistory.querySelector(".settings-section-body").innerHTML = `<pre>${escapeHtml(JSON.stringify(errors, null, 2))}</pre>`;
    body.appendChild(errorHistory);
  }

  renderMowingHistoryList(container, recordsPayload, recordsError) {
    container.innerHTML = "";
    const records = Array.isArray(recordsPayload?.data)
      ? recordsPayload.data
      : Array.isArray(recordsPayload) ? recordsPayload : [];

    const summary = this.buildMowingHistorySummary(recordsPayload);
    if (summary) container.appendChild(summary);

    if (!records.length) {
      const empty = document.createElement("div");
      empty.className = "mowing-history-empty";
      empty.textContent = recordsError
        ? `${this.t("mowingHistoryEmpty")} (${recordsError})`
        : this.t("mowingHistoryEmpty");
      container.appendChild(empty);
      return;
    }

    const list = document.createElement("div");
    list.className = "mowing-history-list";
    for (const record of records) {
      list.appendChild(this.createMowingHistoryCard(record));
    }
    container.appendChild(list);
  }

  historyMapAreaM2() {
    const progressEntity = this.getRelatedEntity("mowingProgress");
    const candidates = [
      progressEntity?.attributes?.progress_map_area_m2,
      progressEntity?.attributes?.progress_test_map_area_m2,
      progressEntity?.attributes?.gross_calibrated_area_total_m2,
      this.entity?.attributes?.map_area,
      this.getRelatedEntity("totalArea")?.state,
    ];
    for (const value of candidates) {
      const number = Number(value);
      if (Number.isFinite(number) && number > 0) return number;
    }
    return null;
  }

  historyMowingModeKind(record) {
    const value = pickRecordValue(record, MOWING_RECORD_MODE_KEYS);
    const normalized = String(value ?? "").trim().toLowerCase();
    if (normalized === "1" || normalized.includes("zone") || normalized.includes("zona") || normalized.includes("zóna")) return "zones";
    if (normalized === "0" || normalized.includes("global") || normalized.includes("full") || normalized.includes("teljes")) return "full";
    return null;
  }

  historyRecordSelectedZones(record, areaDefinition) {
    const zones = getZones(areaDefinition || {}, ["custom_areas", "zones", "customAreas", "ridable_areas"]);
    if (!zones.length) return [];

    const byId = new Map();
    const byName = new Map();
    for (const zone of zones) {
      const id = zone?.id;
       if (id !== undefined && id !== null) byId.set(String(id), zone);
      const key = historyZoneMatchKey(zone?.name || zone?.label);
      if (key) byName.set(key, zone);
    }

    const selected = [];
    const add = (zone) => {
      if (!zone || selected.includes(zone)) return;
      selected.push(zone);
    };

    const zoneListRaw = pickRecordValue(record, MOWING_RECORD_ZONE_LIST_KEYS);
    const zoneList = Array.isArray(zoneListRaw) ? zoneListRaw : [];
    for (const item of zoneList) {
      if (item && typeof item === "object") {
        const id = pickRecordValue(item, ["id", "zone_id", "zoneId", "region_id", "regionId", "area_id", "areaId"]);
        if (id !== undefined && byId.has(String(id))) add(byId.get(String(id)));
        const name = pickRecordValue(item, MOWING_RECORD_ZONE_NAME_KEYS);
        const key = historyZoneMatchKey(name);
        if (key && byName.has(key)) add(byName.get(key));
      } else {
        const value = String(item ?? "").trim();
        if (byId.has(value)) add(byId.get(value));
        const key = historyZoneMatchKey(value);
        if (key && byName.has(key)) add(byName.get(key));
      }
    }

    for (const raw of historyRecordZoneIdCandidates(record)) {
      const value = String(raw ?? "").trim();
      if (byId.has(value)) add(byId.get(value));
      const key = historyZoneMatchKey(value);
      if (key && byName.has(key)) add(byName.get(key));
    }
    return selected;
  }

  historyLearnedMowingArea(kind, selectedZones) {
    const progressEntity = this.getRelatedEntity("mowingProgress");
    const profiles = progressEntity?.attributes?.learned_zone_mowing_profiles;
    if (!profiles || typeof profiles !== "object") return null;

    let key = null;
    if (kind === "full") {
      key = "full";
    } else if (kind === "zones" && Array.isArray(selectedZones) && selectedZones.length) {
      const ids = selectedZones
        .map((zone) => Number(zone?.id))
        .filter((id) => Number.isInteger(id))
        .sort((left, right) => left - right);
      if (ids.length === selectedZones.length) key = `manual:${[...new Set(ids)].join(",")}`;
    }
    if (!key) return null;

    const reference = Number(profiles[key]?.reference_m2);
    return Number.isFinite(reference) && reference > 0 ? reference : null;
  }

  calculateMowingHistoryProgress(record, areaDefinition = this.entity?.attributes?.area_definition || {}, selectedZonesOverride = null) {
    const mowedArea = Number(pickRecordValue(record, MOWING_RECORD_AREA_KEYS));
    if (!Number.isFinite(mowedArea) || mowedArea < 0) return null;

    const mapArea = this.historyMapAreaM2();
    if (!Number.isFinite(mapArea) || mapArea <= 0) return null;

    const allZones = getZones(areaDefinition || {}, ["custom_areas", "zones", "customAreas", "ridable_areas"])
      .filter((zone) => historyZonePoints(zone).length >= 3);
    if (!allZones.length) return null;

    const allPolygons = allZones.map(historyZonePoints);
    const allRaw = allPolygons.reduce((sum, points) => sum + historyPolygonAreaRaw(points), 0);
    if (!Number.isFinite(allRaw) || allRaw <= 0) return null;
    const scale = mapArea / allRaw;

    const kind = this.historyMowingModeKind(record);
    let selectedZones = Array.isArray(selectedZonesOverride) ? selectedZonesOverride : this.historyRecordSelectedZones(record, areaDefinition);
    if (kind === "full") selectedZones = allZones;
    if (!selectedZones.length) return null;

    const selectedPolygons = selectedZones
      .map(historyZonePoints)
      .filter((points) => points.length >= 3);
    if (!selectedPolygons.length) return null;

    const noGoZones = getZones(areaDefinition || {}, [
      "forbid_areas", "forbidAreas", "remote_forbid_areas", "remoteForbidAreas", "no_go_areas", "noGoAreas",
    ]);
    const noGoPolygons = noGoZones.map(historyZonePoints).filter((points) => points.length >= 3);
    const noGoOverlapRaw = historyPolygonUnionIntersectionAreaRaw(selectedPolygons, noGoPolygons);
    const noGoOverlapM2 = noGoOverlapRaw * scale;

    let grossTargetM2;
    if (kind === "full") {
      grossTargetM2 = mapArea;
    } else {
      grossTargetM2 = selectedPolygons.reduce((sum, points) => sum + historyPolygonAreaRaw(points), 0) * scale;
    }
    const geometricTargetM2 = Math.max(0, grossTargetM2 - noGoOverlapM2);
    const learnedTargetM2 = this.historyLearnedMowingArea(kind, selectedZones);
    const targetM2 = learnedTargetM2 ?? geometricTargetM2;
    if (!Number.isFinite(targetM2) || targetM2 <= 0) return null;

    const calculated = Math.max(0, Math.min(100, (mowedArea / targetM2) * 100));
    // Historical entries are already closed mowing tasks. The calculated area
    // can remain a few percent below the mower's own completion point because
    // trees, bushes and dynamically avoided obstacles are not represented by
    // No-Go polygons. Use the same 95% completion tolerance as the live badge:
    // a finished history record at >=95% is displayed as 100%.
    return calculated >= 95 ? 100 : calculated;
  }

  historyProgressNeedsDetail(record) {
    if (this.historyMowingModeKind(record) !== "zones") return false;
    const areaDefinition = this.entity?.attributes?.area_definition || {};
    if (this.historyRecordSelectedZones(record, areaDefinition).length) return false;
    return Boolean(
      pickRecordValue(record, MOWING_RECORD_PATH_URL_KEYS)
      && pickRecordValue(record, MOWING_RECORD_AREA_URL_KEYS)
    );
  }

  async fetchMowingHistoryDetailForProgress(record) {
    const cacheKey = historyRecordCacheKey(record);
    this._historyProgressDetailPromises ||= new Map();
    if (this._historyProgressDetailPromises.has(cacheKey)) return this._historyProgressDetailPromises.get(cacheKey);

    const promise = (async () => {
      if (!this._hass?.connection) return null;
      const serviceData = {};
      const areaUrl = pickRecordValue(record, MOWING_RECORD_AREA_URL_KEYS);
      const mapUrl = pickRecordValue(record, MOWING_RECORD_MAP_URL_KEYS);
      const pathUrl = pickRecordValue(record, MOWING_RECORD_PATH_URL_KEYS);
      if (areaUrl) serviceData.area_url = areaUrl;
      if (mapUrl) serviceData.map_url = mapUrl;
      if (pathUrl) serviceData.path_url = pathUrl;
      const entityId = this.entity?.entity_id;
      if (entityId) serviceData.entity_id = entityId;
      try {
        const result = await this._hass.connection.sendMessagePromise({
          type: "call_service",
          domain: "anthbot_map",
          service: "get_mowing_record_detail",
          service_data: serviceData,
          return_response: true,
        });
        return result?.response || null;
      } catch (_error) {
        return null;
      }
    })();
    this._historyProgressDetailPromises.set(cacheKey, promise);
    return promise;
  }

  inferMowingHistoryZonesFromDetail(record, detail) {
    const areaDefinition = detail?.area;
    if (!areaDefinition || typeof areaDefinition !== "object") return [];
    const zones = getZones(areaDefinition, ["custom_areas", "zones", "customAreas", "ridable_areas"])
      .filter((zone) => historyZonePoints(zone).length >= 3);
    if (!zones.length) return [];

    const anchorMetersX = Number(pickRecordValue(record, MOWING_RECORD_START_X_KEYS));
    const anchorMetersY = Number(pickRecordValue(record, MOWING_RECORD_START_Y_KEYS));
    const anchor = {
      x: Number.isFinite(anchorMetersX) ? anchorMetersX * 1000 : 0,
      y: Number.isFinite(anchorMetersY) ? anchorMetersY * 1000 : 0,
    };
    const pathPoints = extractDetailPathPoints(detail?.path, anchor);
    if (!pathPoints.length) return [];

    const scored = zones.map((zone) => {
      const polygon = historyZonePoints(zone);
      let inside = 0;
      // Sampling caps the work for very long historical paths while preserving
      // their spatial distribution.
      const step = Math.max(1, Math.floor(pathPoints.length / 2500));
      for (let index = 0; index < pathPoints.length; index += step) {
        if (historyPointInPolygon(pathPoints[index], polygon)) inside += 1;
      }
      return { zone, inside };
    });
    const maxInside = Math.max(0, ...scored.map((item) => item.inside));
    if (maxInside <= 0) return [];
    const threshold = Math.max(3, Math.ceil(maxInside * 0.12));
    return scored.filter((item) => item.inside >= threshold).map((item) => item.zone);
  }

  scheduleMowingHistoryProgressDetail(card, record, valueElement) {
    if (!card || !valueElement || !this.historyProgressNeedsDetail(record)) return;
    const cacheKey = historyRecordCacheKey(record);
    this._historyProgressCache ||= new Map();

    const applyValue = (value) => {
      if (!valueElement.isConnected) return;
      valueElement.textContent = Number.isFinite(value) ? formatCalculatedRecordPercent(value) : "–";
    };
    if (this._historyProgressCache.has(cacheKey)) {
      applyValue(this._historyProgressCache.get(cacheKey));
      return;
    }

    const load = async () => {
      const detail = await this.fetchMowingHistoryDetailForProgress(record);
      let value = null;
      if (detail) {
        const selected = this.inferMowingHistoryZonesFromDetail(record, detail);
        if (selected.length) {
          value = this.calculateMowingHistoryProgress(record, detail.area, selected);
        }
      }
      this._historyProgressCache.set(cacheKey, value);
      applyValue(value);
    };

    if (typeof IntersectionObserver !== "function") {
      load();
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      load();
    }, { root: null, rootMargin: "250px 0px" });
    observer.observe(card);
  }

  buildMowingHistorySummary(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
    const total = pickRecordValue(payload, ["total", "total_times", "totalTimes"]);
    const totalArea = pickRecordValue(payload, ["total_area", "totalArea"]);
    if (total === undefined && totalArea === undefined) return null;

    const summary = document.createElement("div");
    summary.className = "mowing-history-summary";
    const items = [];
    if (total !== undefined) items.push([this.t("mowingHistoryTotalCount"), String(total)]);
    if (totalArea !== undefined) items.push([this.t("mowingHistoryTotalArea"), formatRecordArea(totalArea)]);
    for (const [label, value] of items) {
      const item = document.createElement("div");
      item.className = "mowing-history-summary-item";
      item.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>`;
      summary.appendChild(item);
    }
    return summary;
  }

  createMowingHistoryCard(record) {
    const card = document.createElement("div");
    card.className = "mowing-history-card";

    const { start, end } = resolveMowingRecordTimeRange(record);
    const area = pickRecordValue(record, MOWING_RECORD_AREA_KEYS);
    const reportedPercent = pickRecordValue(record, MOWING_RECORD_PERCENT_KEYS);
    const durationEntry = pickRecordEntry(record, MOWING_RECORD_DURATION_KEYS);
    const rawDuration = durationEntry?.value;
    const mode = pickRecordValue(record, MOWING_RECORD_MODE_KEYS);
    const source = pickRecordValue(record, MOWING_RECORD_SOURCE_KEYS);
    const zoneListRaw = pickRecordValue(record, MOWING_RECORD_ZONE_LIST_KEYS);
    const zoneList = Array.isArray(zoneListRaw) ? zoneListRaw : [];

    const areaUrl = pickRecordValue(record, MOWING_RECORD_AREA_URL_KEYS);
    const mapUrl = pickRecordValue(record, MOWING_RECORD_MAP_URL_KEYS);
    const pathUrl = pickRecordValue(record, MOWING_RECORD_PATH_URL_KEYS);
    if (areaUrl || mapUrl || pathUrl) {
      card.classList.add("has-detail");
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      const openDetail = (event) => {
        event.stopPropagation();
        this.openMowingRecordDetail(record, { areaUrl, mapUrl, pathUrl });
      };
      card.addEventListener("click", openDetail);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openDetail(event);
        }
      });
    }

    const head = document.createElement("div");
    head.className = "mowing-history-head";
    head.innerHTML = `<strong>${escapeHtml(this.formatMowingDateRange(start, end))}</strong>`;
    card.appendChild(head);

    let durationSeconds = null;
    if (start && end) {
      durationSeconds = (end.getTime() - start.getTime()) / 1000;
    } else if (rawDuration !== undefined) {
      durationSeconds = normalizeRecordDurationSeconds(rawDuration, durationEntry?.key);
    }

    const calculatedProgress = this.calculateMowingHistoryProgress(record);
    const progressNeedsDetail = calculatedProgress === null && this.historyProgressNeedsDetail(record);
    const statItems = [];
    if (area !== undefined) statItems.push([this.t("mowingHistoryArea"), formatRecordArea(area), null]);
    statItems.push([
      this.t("mowingHistoryProgress"),
      Number.isFinite(calculatedProgress)
        ? formatCalculatedRecordPercent(calculatedProgress)
        : progressNeedsDetail ? "…" : "–",
      "calculated-progress",
    ]);
    if (durationSeconds !== null) {
      statItems.push([this.t("mowingHistoryDuration"), formatRecordDurationSeconds(durationSeconds), null]);
    }
    if (mode !== undefined) statItems.push([this.t("mowingHistoryMode"), this.formatRecordMode(mode), null]);
    if (source !== undefined) statItems.push([this.t("mowingHistoryStartedBy"), this.formatRecordSource(source), null]);

    let calculatedProgressElement = null;
    if (statItems.length) {
      const stats = document.createElement("div");
      stats.className = "mowing-history-stats";
      for (const [label, value, role] of statItems) {
        const stat = document.createElement("div");
        stat.className = "mowing-history-stat";
        stat.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong>`;
        if (role === "calculated-progress") {
          stat.dataset.progressSource = Number.isFinite(calculatedProgress) ? "calculated" : progressNeedsDetail ? "detail" : "unavailable";
          stat.title = Number.isFinite(calculatedProgress)
            ? "A lenyírt területből és a nettó (No-Go-val csökkentett) célterületből újraszámolva."
            : reportedPercent !== undefined
              ? `A gyári rekord ${formatRecordPercent(reportedPercent) || reportedPercent} értékét nem használjuk valódi területi százalékként.`
              : "A célterület ebből a rekordból nem állapítható meg biztosan.";
          calculatedProgressElement = stat.querySelector("strong");
        }
        stats.appendChild(stat);
      }
      card.appendChild(stats);
    }
    if (progressNeedsDetail && calculatedProgressElement) {
      this.scheduleMowingHistoryProgressDetail(card, record, calculatedProgressElement);
    }

    if (zoneList.length) {
      const zoneWrap = document.createElement("div");
      zoneWrap.className = "mowing-history-zones";
      for (const zone of zoneList) {
        const zoneName = pickRecordValue(zone, MOWING_RECORD_ZONE_NAME_KEYS);
        const width = pickRecordValue(zone, MOWING_RECORD_ZONE_WIDTH_KEYS);
        const height = pickRecordValue(zone, MOWING_RECORD_ZONE_HEIGHT_KEYS);
        const zoneArea = pickRecordValue(zone, MOWING_RECORD_ZONE_AREA_KEYS);
        let dims = "";
        if (width !== undefined && height !== undefined) {
          dims = `${formatRecordNumber(width)}m × ${formatRecordNumber(height)}m`;
        } else if (zoneArea !== undefined) {
          dims = formatRecordArea(zoneArea);
        }
        const chip = document.createElement("div");
        chip.className = "mowing-history-zone-chip";
        chip.innerHTML = `<strong>${escapeHtml(zoneName ? String(zoneName) : this.t("zone"))}</strong>${dims ? `<span>${escapeHtml(dims)}</span>` : ""}`;
        zoneWrap.appendChild(chip);
      }
      card.appendChild(zoneWrap);
    }

    const extraKeys = collectUnmappedRecordKeys(record, MOWING_RECORD_MAPPED_KEYS);
    if (extraKeys.length) {
      const extra = {};
      for (const key of extraKeys) extra[key] = record[key];
      const details = document.createElement("details");
      details.className = "mowing-history-raw";
      details.innerHTML = `<summary>${this.t("mowingHistoryRawFields")}</summary><pre>${escapeHtml(JSON.stringify(extra, null, 2))}</pre>`;
      card.appendChild(details);
    }

    return card;
  }

  async openMowingRecordDetail(record, { areaUrl, mapUrl, pathUrl } = {}) {
    const overlay = document.createElement("div");
    overlay.className = "mowing-record-detail-overlay";
    const dialog = document.createElement("div");
    dialog.className = "mowing-record-detail-dialog";
    overlay.appendChild(dialog);

    const closeOverlay = () => {
      overlay.remove();
      document.removeEventListener("keydown", onKeydown);
    };
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeOverlay();
    });
    const onKeydown = (event) => {
      if (event.key === "Escape") closeOverlay();
    };
    document.addEventListener("keydown", onKeydown);

    const { start, end } = resolveMowingRecordTimeRange(record);
    const titleText = this.formatMowingDateRange(start, end);

    dialog.innerHTML = `
      <div class="mowing-record-detail-head">
        <div class="mowing-record-detail-title">${escapeHtml(titleText)}</div>
        <button type="button" class="mowing-record-detail-close" aria-label="${escapeHtml(this.t("close"))}">×</button>
      </div>
      <div class="mowing-record-detail-body">
        <div class="mowing-record-detail-status">${escapeHtml(this.t("mowingHistoryDetailLoading"))}</div>
      </div>
    `;
    dialog.querySelector(".mowing-record-detail-close").addEventListener("click", closeOverlay);

    const root = this.shadowRoot || document.body;
    root.appendChild(overlay);

    const body = dialog.querySelector(".mowing-record-detail-body");

    try {
      if (!this._hass?.connection) {
        throw new Error("Home Assistant connection unavailable");
      }
      const serviceData = {};
      if (areaUrl) serviceData.area_url = areaUrl;
      if (mapUrl) serviceData.map_url = mapUrl;
      if (pathUrl) serviceData.path_url = pathUrl;
      const entityId = this.entity?.entity_id;
      if (entityId) serviceData.entity_id = entityId;

      // Called via the raw websocket connection (not this._hass.callService)
      // because the card installs a callService wrapper for command-toast
      // feedback that only forwards 4 positional args and would silently
      // drop the return_response flag this call depends on.
      const result = await this._hass.connection.sendMessagePromise({
        type: "call_service",
        domain: "anthbot_map",
        service: "get_mowing_record_detail",
        service_data: serviceData,
        return_response: true,
      });
      const detail = result?.response || {};
      // The record row's x/y came back as small numbers (e.g. -8.23/-5.10)
      // that only line up with the map raster's mm-based world bounds when
      // treated as METERS and converted to mm (raster bounds are mm) --
      // hence the *1000 here.
      const anchorMetersX = Number(pickRecordValue(record, MOWING_RECORD_START_X_KEYS));
      const anchorMetersY = Number(pickRecordValue(record, MOWING_RECORD_START_Y_KEYS));
      const anchor = {
        x: Number.isFinite(anchorMetersX) ? anchorMetersX * 1000 : 0,
        y: Number.isFinite(anchorMetersY) ? anchorMetersY * 1000 : 0,
      };
      // Same garden photo the live map card underlays behind the
      // boundary/zones (config.image) -- reused here so the history popup's
      // zone schematic sits on the same familiar backdrop. Preloaded (and
      // its natural pixel size read) *before* rendering so the image can be
      // placed with the exact same affine fit the live map uses (see
      // renderMowingRecordZonesSvg) instead of a naive stretch-to-fit.
      const backgroundImage = this.config?.image ? await loadImageElement(this.config.image) : null;

      // Mirrors renderer.js's own draw() exactly (confirmed by reading it):
      // the live map does NOT feed the same world bounds into every
      // geometry blindly -- it prefers an explicit `config.bounds` override
      // when the user has set one, only falling back to a freshly computed
      // getWorldBounds() otherwise. And critically, it fits BOTH its
      // "base" (image) and calibrated (zones/path) geometries using the
      // *photo's own* aspect ratio, and applies the same view rotation
      // (config.rotation, plus the mobile auto-rotate) to both. Any of
      // these three that differ between the popup and the live map would
      // reproduce the "photo looks aligned-ish but isn't really" bug even
      // with the correct calibration numbers -- so all three are threaded
      // through here instead of recomputed independently.
      const mobileViewport = typeof window !== "undefined" && window.matchMedia("(max-width: 720px)").matches;
      const mobileRotation = mobileViewport
        ? Number(this.config.mobile_map_rotation ?? this.config.mobileMapRotation ?? 90) || 0
        : 0;
      const rotation = degreesToRadians((Number(this.config.rotation) || 0) + mobileRotation);

      // A record's own `area_url` snapshot is what got mowed *then*, but it
      // can differ slightly from the property's current live boundary/zone
      // data (re-mapped since, edge points refined, etc.) -- if the popup
      // computed its world bounds from that historical snapshot while the
      // live map computes its bounds from the CURRENT live state, the two
      // would end up scaled just enough differently to visibly mismatch
      // (Attila's "squeeze it together horizontally" report) even with
      // identical calibration numbers. So world bounds are computed here
      // from the exact same live inputs `updateRenderer()` feeds the live
      // renderer -- not from the historical record's own area data -- and
      // handed down already resolved, matching renderer.js's own
      // `bounds = this.config.bounds || getWorldBounds(mapSource, pose)`.
      const liveAttributes = this.entity?.attributes || {};
      const liveMapSource = {
        ...(liveAttributes.area_definition || {}),
        map_raster: liveAttributes.map_raster,
        map_definition: liveAttributes.map_definition,
        path_definition: liveAttributes.path_definition,
        map_binary_paths: liveAttributes.map_binary_paths,
        path_binary_paths: liveAttributes.path_binary_paths,
      };
      const livePose = this.computeLivePose(liveAttributes);
      const bounds = this.config?.bounds || getWorldBounds(liveMapSource, livePose);
      // Attila asked for the lawn's own boundary outline to also be visible
      // in the popup. First attempt used getBoundaryPaths() (map_binary_paths
      // -- the raw wire-perimeter/travel-route data), but Attila noticed it
      // cuts straight across the driveway/parking area: that vector path is
      // the "legacy boundary" the live map itself only draws when
      // showLegacyBoundary is explicitly turned on (normally off). What the
      // live map actually shows BY DEFAULT is a pixel-traced outline of the
      // `map_raster` mask (drawDecodedBoundary/drawRasterBoundary in
      // renderer.js) -- the real mapped-lawn silhouette, not the wire route.
      // boundaryRaster carries that live raster through so the popup can
      // trace the same outline; boundaryPaths is kept only as a fallback
      // for the (rare) case no live map_raster is available.
      const boundaryRaster = liveMapSource.map_raster;
      const boundaryPaths = getBoundaryPaths(liveMapSource);

      // Attila: the zones/coverage still read "too tall" vertically vs. the
      // live map, even with identical bounds/calibration. Root cause: the
      // live map's own "map" rect (computeMapFit's width/height/center) is
      // fit against the live CANVAS's own pixel width/height -- whatever
      // the card's actual on-screen box happens to be, which (with the
      // default `fit: "cover"`, or any configured fixed `height:`) can have
      // a different aspect ratio than the photo, causing the live view to
      // crop/zoom rather than show the whole world uncropped. The popup was
      // instead sizing its own SVG canvas to exactly match the photo's own
      // aspect ratio (zero letterboxing by construction) -- a DIFFERENT fit
      // than the live map's, so even identical bounds/calibration produced
      // a differently-cropped/zoomed picture. Reading the live renderer's
      // *actual* current canvas pixel size (and its `fit` mode) and reusing
      // both here reproduces the exact same "map" rect the live view uses.
      const liveCanvas = this.renderer?.canvas;
      const liveDpr = this.renderer?.dpr || 1;
      const canvasSize =
        liveCanvas && liveCanvas.width > 0 && liveCanvas.height > 0
          ? { width: liveCanvas.width / liveDpr, height: liveCanvas.height / liveDpr }
          : null;
      const fit = this.renderer?.options?.fit || this.config?.fit || "cover";

      this.renderMowingRecordDetailBody(body, detail, {
        pathRequested: Boolean(pathUrl),
        anchor,
        mowedZoneInfo: mowedZoneInfoFromRecord(record),
        // The card's own calibration (from the "Map fit" controls) -- the
        // same one the live map applies -- so the zone/image placement here
        // matches the live map instead of an independent, uncalibrated fit.
        calibration: this.calibration,
        // Separate, additional calibration knob (from the live map's own
        // "decoded boundary" fit controls) applied only to the raster-
        // traced boundary outline -- distinct from the main `calibration`
        // used for zones/coverage/photo. Threading it through is what lets
        // the traced outline land exactly where it does on the live map.
        decodedBoundaryCalibration: this.decodedBoundaryCalibration,
        backgroundImage,
        bounds,
        boundaryRaster,
        boundaryPaths,
        canvasSize,
        fit,
        rotation,
      });
    } catch (error) {
      body.innerHTML = `<div class="mowing-record-detail-status mowing-record-detail-error">${escapeHtml(String(error?.message || error))}</div>`;
    }
  }

  renderMowingRecordDetailBody(
    body,
    detail,
    {
      pathRequested = true,
      anchor = null,
      mowedZoneInfo = null,
      calibration = null,
      decodedBoundaryCalibration = null,
      backgroundImage = null,
      bounds = null,
      boundaryRaster = null,
      boundaryPaths = null,
      canvasSize = null,
      fit = "cover",
      rotation = 0,
    } = {}
  ) {
    body.innerHTML = "";
    let rendered = false;

    // The map file is just the mower's static lawn boundary (the same
    // outline every session) -- it does NOT show what got mowed *this*
    // session. That comes from the path file's decoded trajectory points,
    // which get drawn as a coverage overlay on top of whichever background
    // (raster or zone schematic) is available, or on their own if neither is.
    const pathPoints = extractDetailPathPoints(detail?.path, anchor);

    // Sanity guard: the delta+anchor reconstruction (see
    // extractDetailPathPoints) can still drift wildly if the struct-layout
    // guess is wrong for this record's path format -- drawing that as a
    // "coverage" line would be actively misleading (a stray line shooting
    // across the whole map), worse than showing nothing. Only draw it if
    // its extent is in the same ballpark as the raster's own world size.
    let pathLooksSane = true;
    const mapRaster = detail?.map?._map_raster;
    if (mapRaster?.bounds && pathPoints.length) {
      const pb = boundingBoxOf(pathPoints);
      const rb = mapRaster.bounds;
      const rasterSpanX = Number(rb.max_x ?? rb.maxX) - Number(rb.min_x ?? rb.minX);
      const rasterSpanY = Number(rb.max_y ?? rb.maxY) - Number(rb.min_y ?? rb.minY);
      if (Number.isFinite(rasterSpanX) && rasterSpanX > 0 && Number.isFinite(rasterSpanY) && rasterSpanY > 0) {
        pathLooksSane = pb.maxX - pb.minX <= rasterSpanX * 4 && pb.maxY - pb.minY <= rasterSpanY * 4;
      }
    }

    // Prefer the zone schematic (labeled rectangles/polygons, with the
    // zone(s) this record actually mowed highlighted) when zone data is
    // available -- this is the layout Attila's reference screenshot (the
    // real app's own history detail screen) uses, and it reads much better
    // than the raw boundary raster. Fall back to the raster picture, then
    // to a bare path plot, when there's no zone data to work with.
    if (detail?.area && typeof detail.area === "object") {
      const svg = renderMowingRecordZonesSvg(detail.area, pathLooksSane ? pathPoints : [], mowedZoneInfo, {
        backgroundImage,
        calibration,
        decodedBoundaryCalibration,
        bounds,
        boundaryRaster,
        boundaryPaths,
        canvasSize,
        fit,
        rotation,
      });
      if (svg) {
        const wrap = document.createElement("div");
        wrap.className = "mowing-record-detail-canvas-wrap";
        wrap.appendChild(svg);
        body.appendChild(wrap);
        rendered = true;
      }
    }

    if (!rendered && mapRaster && Array.isArray(mapRaster.runs) && mapRaster.width && mapRaster.height) {
      const canvas = renderMowingRecordRasterCanvas(mapRaster);
      if (canvas) {
        if (pathPoints.length && pathLooksSane) {
          drawDetailPathOnRasterCanvas(canvas, mapRaster, pathPoints);
        }
        const wrap = document.createElement("div");
        wrap.className = "mowing-record-detail-canvas-wrap";
        wrap.appendChild(canvas);
        body.appendChild(wrap);
        rendered = true;
      }
    }

    if (!rendered && pathPoints.length && pathLooksSane) {
      const svg = renderMowingRecordPathOnlySvg(pathPoints);
      if (svg) {
        const wrap = document.createElement("div");
        wrap.className = "mowing-record-detail-canvas-wrap";
        wrap.appendChild(svg);
        body.appendChild(wrap);
        rendered = true;
      }
    }

    if (!rendered) {
      const status = document.createElement("div");
      status.className = "mowing-record-detail-status";
      status.textContent = this.t("mowingHistoryDetailUnavailable");
      body.appendChild(status);
    }

    const errors = detail?._errors;
    if (Array.isArray(errors) && errors.length) {
      const errBox = document.createElement("div");
      errBox.className = "mowing-record-detail-error";
      errBox.textContent = errors.join(" | ");
      body.appendChild(errBox);
    }

  }

  formatMowingDateRange(start, end) {
    if (!start && !end) return this.t("mowingHistoryUnknownTime");
    const locale = this.language && this.language !== "auto" ? this.language : undefined;
    const dateFmt = new Intl.DateTimeFormat(locale, { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    const timeFmt = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" });
    if (start && !end) return dateFmt.format(start);
    if (end && !start) return dateFmt.format(end);
    const startLabel = start ? dateFmt.format(start) : "?";
    const endLabel = end ? timeFmt.format(end) : "?";
    return `${startLabel} – ${endLabel}`;
  }

  formatRecordMode(value) {
    const normalized = String(value).toLowerCase();
    // Confirmed against the mobile app (2026-08-19): the cloud's numeric
    // mow_mode "1" is shown by the app as "Zónák" (zone mowing), not "Teljes
    // terület" as previously (incorrectly) guessed. "0" is assumed to be the
    // complementary full-area mow since it's the only other observed value.
    if (normalized === "1") return this.t("mowingModeZones");
    if (normalized === "0") return this.t("mowingModeGlobal");
    if (normalized.includes("zone") || normalized.includes("zona")) return this.t("mowingModeZones");
    if (normalized.includes("edge") || normalized.includes("border") || normalized.includes("szeg")) return this.t("mowingModeEdge");
    if (normalized.includes("dock")) return this.t("mowingModeDockEdge");
    if (normalized.includes("global") || normalized.includes("all") || normalized.includes("entire")) return this.t("mowingModeGlobal");
    return String(value);
  }

  formatRecordSource(value) {
    const normalized = String(value).toLowerCase();
    // Confirmed against the mobile app (2026-08-19): start_cause "1" is shown
    // by the app as "APP" (started from the mobile app).
    if (normalized === "1") return this.t("mowingSourceApp");
    if (normalized.includes("app")) return this.t("mowingSourceApp");
    if (normalized.includes("sched") || normalized.includes("plan") || normalized.includes("timer")) return this.t("mowingSourceSchedule");
    if (normalized.includes("button") || normalized.includes("key") || normalized.includes("manual")) return this.t("mowingSourceButton");
    if (normalized.includes("voice")) return this.t("mowingSourceVoice");
    return String(value).toUpperCase();
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

  primaryMowingAction() {
    const statuses = this.commandStatusValues();
    if (statuses.some((value) => ["paused", "pause", "szunetel", "szuneteltetve"].some((item) => value.includes(item)))) {
      return this.entity?.attributes?.last_mowing_task?.type ? "resume" : "start";
    }
    if (statuses.some((value) => ["mowing", "globalmowing", "zonemowing", "regionmowing", "working", "cutting", "nyiras", "funyiras"].some((item) => value.includes(item)))) {
      return "pause";
    }
    return "start";
  }

  createPrimaryMowingTile(action) {
    const labels = {
      start: [this.t("startLabel"), this.t("startSelectedTask")],
      pause: [this.t("pauseTask"), this.t("pauseTaskSub")],
      resume: [this.t("resumeTask"), this.t("resumeTaskSub")],
    };
    const tile = document.createElement("button");
    tile.type = "button";
    tile.dataset.primaryMowingAction = action;
    tile.className = `panel-tile task-action-tile ${action}`;
    tile.innerHTML = `<strong>${labels[action][0]}</strong><span>${labels[action][1]}</span>`;
    tile.addEventListener("click", () => this.handlePrimaryMowingAction(action));
    return tile;
  }

  async handlePrimaryMowingAction(action) {
    if (action === "pause" || action === "resume") {
      await this.handleCommand(action);
      return;
    }
    if (this.selectedMowingTarget?.type === "zone-set" && this.selectedMowingTarget.zones?.length) {
      if (this.selectedMowingTarget.zones.length === 1) {
        await this.startZone(this.selectedMowingTarget.zones[0]);
        return;
      }
      await this.startZones(this.selectedMowingTarget.zones);
      return;
    }
    if (this.selectedMowingTarget?.type === "auto-zone-set" && this.selectedMowingTarget.zones?.length) {
      if (this.selectedMowingTarget.zones.length === 1) {
        await this.startAutoZone(this.selectedMowingTarget.zones[0]);
        return;
      }
      await this.startAutoZones(this.selectedMowingTarget.zones);
      return;
    }
    if (this.selectedMowingTarget?.type === "edge") {
      await this.handleCommand("outer-edge");
      return;
    }
    if (this.selectedMowingTarget?.type === "dock-edge") {
      await this.handleCommand("dock-edge");
      return;
    }
    await this.handleCommand("start");
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

  createObstacleLevelControl() {
    const key = "visualObstacleLevel";
    const entityId = this.getNumberEntity(key);
    const entity = entityId ? this._hass.states[entityId] : null;
    const value = this.displayedNumberValue(key, Number(entity?.state));
    const selected = Number.isFinite(value) ? Math.max(0, Math.min(2, Math.round(value))) : 1;
    const labels = [this.t("low"), this.t("medium"), this.t("high")];
    const tile = document.createElement("div");
    tile.className = "panel-tile control-tile";
    tile.innerHTML = `
      <div class="control-head">
        <span>${this.t("visualObstacleLevel")}</span>
        <strong>${labels[selected]}</strong>
      </div>
      <div class="height-options" role="group" aria-label="${this.t("visualObstacleLevel")}"></div>
    `;
    const options = tile.querySelector(".height-options");
    labels.forEach((label, level) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "height-option";
      button.textContent = label;
      button.classList.toggle("active", level === selected);
      button.disabled = !entityId;
      button.addEventListener("click", () => {
        options.querySelectorAll(".height-option").forEach((item) => item.classList.toggle("active", item === button));
        tile.querySelector(".control-head strong").textContent = label;
        this.applyOptimisticNumber(key, level, button);
        this.setNumberEntity(key, entityId, level, button);
      });
      options.appendChild(button);
    });
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

    if (key === "batterySaver") {
      const tile = document.createElement("div");
      tile.className = "panel-tile switch-tile battery-saver-open-tile";
      tile.title = entityId || this.t("switchMissing");
      tile.tabIndex = entityId ? 0 : -1;
      tile.setAttribute("role", "button");
      tile.setAttribute("aria-disabled", entityId ? "false" : "true");
      tile.innerHTML = `<span>${label}</span>`;
      const openDialog = (event) => {
        event?.preventDefault?.();
        if (!entityId) return;
        this.openBatterySaverDialog(entityId);
      };
      tile.addEventListener("click", openDialog);
      tile.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") openDialog(event);
      });
      return tile;
    }

    const tile = document.createElement("label");
    tile.className = "panel-tile switch-tile";
    tile.title = entityId || this.t("switchMissing");
    tile.innerHTML = `
      <span>${label}</span>
      <input type="checkbox" ${checked ? "checked" : ""} ${entityId ? "" : "disabled"}>
    `;
    const input = tile.querySelector("input");
    input.addEventListener("change", async () => {
      await this.toggleSwitchEntity(key, entityId, input.checked, input);
    });
    return tile;
  }

  openBatterySaverDialog(entityId) {
    const state = entityId ? this._hass.states[entityId] : null;
    const attrs = state?.attributes || {};
    const overlay = document.createElement("div");
    overlay.className = "mowing-record-detail-overlay";
    const dialog = document.createElement("div");
    dialog.className = "mowing-record-detail-dialog battery-saver-dialog";
    overlay.appendChild(dialog);
    const close = () => overlay.remove();
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) close();
    });

    const currentChargerSwitch = attrs.charger_switch || "";
    const switchEntities = Object.keys(this._hass.states)
      .filter((id) => id.startsWith("switch."))
      .map((id) => ({
        id,
        name: this._hass.states[id]?.attributes?.friendly_name || id,
      }))
      .sort((left, right) => {
        if (left.id === currentChargerSwitch) return -1;
        if (right.id === currentChargerSwitch) return 1;
        return left.name.localeCompare(right.name);
      });
    const switchOptionsHtml = switchEntities
      .map((item) => {
        const selected = item.id === currentChargerSwitch ? " selected" : "";
        return `<option value="${escapeHtml(item.id)}"${selected}>${escapeHtml(item.name)} — ${escapeHtml(item.id)}</option>`;
      })
      .join("");

    const currentCharge = Number(attrs.charge_limit ?? 80);
    const currentMaintenance = Number(attrs.maintenance_level ?? 65);
    const currentResume = Number(attrs.resume_level ?? 50);
    const detectedProfile = (
      currentCharge === 80 && currentMaintenance === 60 && currentResume === 50 ? "max" :
      currentCharge === 80 && currentMaintenance === 65 && currentResume === 50 ? "balanced" :
      currentCharge === 90 && currentMaintenance === 80 && currentResume === 50 ? "ready" :
      "custom"
    );

    dialog.innerHTML = `
      <style>
        .battery-saver-dialog{width:min(920px,94vw);max-width:920px}
        .battery-saver-layout{display:grid;grid-template-columns:minmax(260px,.95fr) minmax(320px,1.25fr);gap:18px;margin-top:14px}
        .battery-profile-list,.battery-profile-details{display:flex;flex-direction:column;gap:10px}
        .battery-profile-card{display:grid;grid-template-columns:32px 1fr auto;align-items:center;gap:10px;padding:12px 14px;border:1px solid var(--divider-color,#3a4653);border-radius:12px;cursor:pointer;background:rgba(255,255,255,.02)}
        .battery-profile-card.active{border-color:var(--primary-color,#3b82f6);background:color-mix(in srgb,var(--primary-color,#3b82f6) 12%,transparent)}
        .battery-profile-card input{margin:0}
        .battery-profile-title{font-weight:700}
        .battery-profile-note{font-size:.85em;opacity:.72;margin-top:2px}
        .battery-profile-range{font-weight:700;white-space:nowrap}
        .battery-profile-range.max{color:#63d34e}.battery-profile-range.balanced{color:#55a6ff}.battery-profile-range.ready{color:#ffc23d}
        .battery-detail-row{display:grid;grid-template-columns:1fr 100px;align-items:center;gap:12px;padding:12px 14px;border:1px solid var(--divider-color,#3a4653);border-radius:12px}
        .battery-detail-row span{font-weight:600}
        .battery-detail-row small{display:block;opacity:.68;margin-top:3px}
        .battery-detail-row input[type=number]{width:88px;text-align:center}
        .battery-detail-row select{width:100%;min-width:0;max-width:100%;padding:8px;border-radius:8px;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color,#3a4653)}
        .battery-charger-row{grid-template-columns:minmax(160px,.75fr) minmax(240px,1.25fr)}
        .battery-anti-shutdown{padding:13px 14px;border:1px solid #7356b8;border-radius:12px;background:rgba(105,72,180,.10)}
        .battery-anti-shutdown strong{color:#a98cff}
        .battery-info-box{padding:12px 14px;border:1px solid color-mix(in srgb,var(--primary-color,#3b82f6) 55%,transparent);border-radius:12px;background:color-mix(in srgb,var(--primary-color,#3b82f6) 8%,transparent);font-size:.9em;line-height:1.45}
        .battery-saver-check{display:flex!important;justify-content:space-between;align-items:center;gap:12px;padding:12px 14px;border:1px solid var(--divider-color,#3a4653);border-radius:12px}
        .battery-saver-mode-toggle{margin-top:14px}
        .battery-saver-mode-toggle input[type=checkbox]{width:28px;height:28px;min-width:28px;min-height:28px;cursor:pointer;accent-color:var(--primary-color,#3b82f6)}
        .battery-saver-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:16px}
        @media(max-width:760px){.battery-saver-layout{grid-template-columns:1fr}.battery-detail-row{grid-template-columns:1fr 90px}}
      </style>
      <div class="mowing-record-detail-head">
        <div>
          <div class="mowing-record-detail-title">${escapeHtml(this.t("batterySaverMode"))}</div>
          <div style="opacity:.68;font-size:.9em;margin-top:3px">${escapeHtml(this.t("batterySaverDescription"))}</div>
        </div>
        <button type="button" class="mowing-record-detail-close" aria-label="${escapeHtml(this.t("close"))}">×</button>
      </div>
      <label class="battery-saver-check battery-saver-mode-toggle" data-role="battery-saver-enabled">
        <span><strong>${escapeHtml(this.t("batterySaverMode"))}</strong><small style="display:block;opacity:.68;margin-top:3px">${escapeHtml(this.t("batterySaverDescription"))}</small></span>
        <input name="battery_saver_enabled" type="checkbox" ${state?.state === "on" ? "checked" : ""}>
      </label>
      <div class="battery-saver-layout">
        <div class="battery-profile-list">
          <div style="font-weight:700;margin-bottom:2px">${escapeHtml(this.t("batteryProfileSelect"))}</div>
          <label class="battery-profile-card" data-profile="max">
            <input type="radio" name="battery_profile" value="max">
            <div><div class="battery-profile-title">🌿 ${escapeHtml(this.t("batteryProfileMax"))}</div><div class="battery-profile-note">${escapeHtml(this.t("batteryProfileMaxNote"))}</div></div>
            <div class="battery-profile-range max">60–80%</div>
          </label>
          <label class="battery-profile-card" data-profile="balanced">
            <input type="radio" name="battery_profile" value="balanced">
            <div><div class="battery-profile-title">⚖️ ${escapeHtml(this.t("batteryProfileBalanced"))}</div><div class="battery-profile-note">${escapeHtml(this.t("batteryProfileBalancedNote"))}</div></div>
            <div class="battery-profile-range balanced">65–80%</div>
          </label>
          <label class="battery-profile-card" data-profile="ready">
            <input type="radio" name="battery_profile" value="ready">
            <div><div class="battery-profile-title">⚡ ${escapeHtml(this.t("batteryProfileReady"))}</div><div class="battery-profile-note">${escapeHtml(this.t("batteryProfileReadyNote"))}</div></div>
            <div class="battery-profile-range ready">80–90%</div>
          </label>
          <label class="battery-profile-card" data-profile="custom">
            <input type="radio" name="battery_profile" value="custom">
            <div><div class="battery-profile-title">⚙️ ${escapeHtml(this.t("batteryProfileCustom"))}</div><div class="battery-profile-note">${escapeHtml(this.t("batteryProfileCustomNote"))}</div></div>
            <div class="battery-profile-range">${escapeHtml(this.t("batteryAdjustable"))}</div>
          </label>
          <div class="battery-info-box"><strong>${escapeHtml(this.t("batteryImportant"))}</strong> ${escapeHtml(this.t("batteryStandbyInfo"))}</div>
        </div>
        <div class="battery-profile-details">
          <div style="font-weight:700;margin-bottom:2px">${escapeHtml(this.t("batteryProfileDetails"))}</div>
          <label class="battery-detail-row battery-charger-row"><div><span>🔌 ${escapeHtml(this.t("chargerSmartPlug"))}</span><small>${escapeHtml(this.t("chargerSmartPlugNote"))}</small></div><select name="charger_switch">${switchOptionsHtml}</select></label>
          <label class="battery-detail-row"><div><span>${escapeHtml(this.t("batteryChargeLimit"))}</span><small>${escapeHtml(this.t("batteryChargeLimitNote"))}</small></div><input name="charge_limit" type="number" min="20" max="100" value="${currentCharge}"></label>
          <label class="battery-detail-row"><div><span>${escapeHtml(this.t("batteryMaintenanceLevel"))}</span><small>${escapeHtml(this.t("batteryMaintenanceLevelNote"))}</small></div><input name="maintenance_level" type="number" min="10" max="99" value="${currentMaintenance}"></label>
          <label class="battery-detail-row"><div><span>${escapeHtml(this.t("batteryResumeLevel"))}</span><small>${escapeHtml(this.t("batteryResumeLevelNote"))}</small></div><input name="resume_level" type="number" min="10" max="99" value="${currentResume}"></label>
          <label class="battery-saver-check"><span>${escapeHtml(this.t("sharedRtkPower"))}<small style="display:block;opacity:.68;margin-top:3px">${escapeHtml(this.t("sharedRtkPowerNote"))}</small></span><input name="shared_rtk_power" type="checkbox" ${attrs.shared_rtk_power ? "checked" : ""}></label>
          <div class="battery-anti-shutdown"><strong>◷ ${escapeHtml(this.t("batteryShutdownGuardTitle"))}</strong><div style="margin-top:5px;line-height:1.42">${escapeHtml(this.t("batteryShutdownGuardText"))}</div><div style="opacity:.68;font-size:.86em;margin-top:7px">${escapeHtml(this.t("batteryShutdownGuardNote"))}</div></div>
        </div>
      </div>
      <div class="battery-saver-actions">
        <button type="button" class="secondary">${escapeHtml(this.t("close"))}</button>
        <button type="button" class="primary">${escapeHtml(this.t("save"))}</button>
      </div>`;

    const profileValues = {
      max: { charge: 80, maintenance: 60, resume: 50 },
      balanced: { charge: 80, maintenance: 65, resume: 50 },
      ready: { charge: 90, maintenance: 80, resume: 50 },
    };
    const chargeInput = dialog.querySelector('[name="charge_limit"]');
    const maintenanceInput = dialog.querySelector('[name="maintenance_level"]');
    const resumeInput = dialog.querySelector('[name="resume_level"]');
    const chargerSwitchInput = dialog.querySelector('[name="charger_switch"]');
    const modeInput = dialog.querySelector('[name="battery_saver_enabled"]');
    modeInput?.addEventListener("change", async () => {
      modeInput.disabled = true;
      try {
        await this.toggleSwitchEntity("batterySaver", entityId, modeInput.checked, modeInput);
        this.scheduleRefresh(200);
      } catch (error) {
        // toggleSwitchEntity() already restores the checkbox and reports the failure.
        console.error("Battery saver mode toggle failed", error);
      } finally {
        modeInput.disabled = false;
      }
    });
    const selectProfile = (profile, applyValues = true) => {
      dialog.querySelectorAll('.battery-profile-card').forEach((card) => card.classList.toggle('active', card.dataset.profile === profile));
      const radio = dialog.querySelector(`[name="battery_profile"][value="${profile}"]`);
      if (radio) radio.checked = true;
      if (applyValues && profileValues[profile]) {
        chargeInput.value = profileValues[profile].charge;
        maintenanceInput.value = profileValues[profile].maintenance;
        resumeInput.value = profileValues[profile].resume;
      }
      const custom = profile === 'custom';
      chargeInput.disabled = !custom;
      maintenanceInput.disabled = !custom;
      resumeInput.disabled = !custom;
    };
    selectProfile(detectedProfile, false);
    dialog.querySelectorAll('[name="battery_profile"]').forEach((radio) => {
      radio.addEventListener('change', () => selectProfile(radio.value, true));
    });

    dialog.querySelector(".mowing-record-detail-close").addEventListener("click", close);
    dialog.querySelector(".secondary").addEventListener("click", close);
    dialog.querySelector(".primary").addEventListener("click", async () => {
      const chargeLimit = Number(chargeInput.value);
      const maintenanceLevel = Number(maintenanceInput.value);
      const resumeLevel = Number(resumeInput.value);
      if (!chargerSwitchInput.value) {
        this.notify(this.t("switchMissing"));
        return;
      }
      if (maintenanceLevel >= chargeLimit || resumeLevel >= chargeLimit) {
        this.notify(this.t("batteryLevelsInvalid"));
        return;
      }
      await this._hass.callService("anthbot_map", "set_battery_saver_config", {
        entity_id: this.config.entity,
        charger_switch: chargerSwitchInput.value,
        charge_limit: chargeLimit,
        maintenance_level: maintenanceLevel,
        resume_level: resumeLevel,
        shared_rtk_power: dialog.querySelector('[name="shared_rtk_power"]').checked,
      });
      this.scheduleRefresh();
      close();
    });
    (this.shadowRoot || document.body).appendChild(overlay);
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
    const validZones = zones.filter((zone) => zone?.id !== undefined && zone?.id !== null);
    if (validZones.length) {
      return validZones;
    }

    // The map entity can temporarily be unavailable while the native zone
    // buttons are already present. Rebuild the tiles directly from them.
    return this.discoverZoneButtons();
  }

  discoverZoneButtons() {
    const base = this.entityBase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`^button\\.${base}_zone_zone_(\\d+)(?:_\\d+)?$`);
    return Object.entries(this._hass?.states || {})
      .map(([entityId, state]) => ({ entityId, state, match: entityId.match(pattern) }))
      // Keep the configured zones visible during a temporary cloud outage.
      .filter(({ match }) => match)
      .map(({ entityId, state, match }) => ({
        id: Number(match[1]),
        name: state.attributes?.friendly_name || `Zone ${match[1]}`,
        entity_id: entityId,
      }))
      .sort((left, right) => left.id - right.id);
  }

  rendererOptions() {
    const mobileViewport = typeof window !== "undefined" && window.matchMedia("(max-width: 720px)").matches;
    const mobileRotation = mobileViewport ? Number(this.config.mobile_map_rotation ?? this.config.mobileMapRotation ?? 90) || 0 : 0;
    return {
      image: this.config.image,
      bounds: this.config.bounds,
      fit: mobileViewport ? this.config.mobile_map_fit || this.config.mobileMapFit || "contain" : this.config.fit || "cover",
      rotation: degreesToRadians((Number(this.config.rotation) || 0) + mobileRotation),
      calibration: this.calibration,
      robotCalibration: this.robotCalibration,
      mowingPathCalibration: this.mowingPathCalibration,
      decodedBoundaryCalibration: this.decodedBoundaryCalibration,
      robotImage: this.config.robot_image || this.config.robotImage || this.resolveAsset(
        String(this.entity?.attributes?.model || "").toLowerCase().includes("m9 pro")
          ? "m9-pro.png?v=244"
          : ["m5", "m9"].some((modelName) => String(this.entity?.attributes?.model || "").toLowerCase().includes(modelName))
            ? "m9.png?v=244"
            : "robot.png?v=2411"
      ),
      noGoLabel: this.t("forbidden"),
      showNoGoZones: this.showNoGoZones,
      showNoGoLabels: this.showNoGoLabels,
      robotSize: mobileViewport ? this.config.mobile_robot_size ?? this.config.mobileRobotSize ?? 24 : this.config.robot_size ?? this.config.robotSize,
      robotImageRotation: this.config.robot_image_rotation ?? this.config.robotImageRotation,
      robotHeadingSource: this.config.robot_heading_source || this.config.robotHeadingSource,
      robotHeadingOffset: this.robotHeadingOffset,
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
    const mqttConnected = attributes.live_shadow_connected;
    const state = cloudConnected === false || mqttConnected === false ? "offline" : robotOnline === true ? "online" : "waiting";
    const baseText = cloudConnected === false
      ? this.t("cloudDisconnected")
      : robotOnline === true
        ? this.t("cloudRobotOnline")
        : cloudConnected === true
          ? this.t("cloudRobotNoResponse")
          : this.t("cloudChecking");
    const mqttText = typeof mqttConnected === "boolean"
      ? ` · MQTT: ${mqttConnected ? "online" : "offline"}`
      : "";
    const text = `${baseText}${mqttText}`;
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
    this._activeEntityId = this.resolveMapEntityId();
    const latestEntity = this._hass.states[this._activeEntityId];
    if (latestEntity) {
      this.entity = latestEntity;
      this.updateRenderer();
    }
  }

  refreshEntityIds() {
    return [
      this._activeEntityId || this.config.entity,
      this.getRelatedEntity("status")?.entity_id,
      this.getRelatedEntity("battery")?.entity_id,
      this.getRelatedEntity("charging")?.entity_id,
      this.getRelatedEntity("mowingArea")?.entity_id,
      this.getRelatedEntity("mowingTime")?.entity_id,
      this.getRelatedEntity("poseYaw")?.entity_id,
    ].filter(Boolean);
  }

  async handleCommand(command) {
    if (String(command).startsWith("reset-") && !window.confirm(this.t("resetCounterWarning"))) {
      return;
    }
    const commandText = ({
      start: this.t("startLabel"),
      stop: this.t("stopLabel"),
      dock: this.t("homeLabel"),
      connect: this.t("cloud"),
      "outer-edge": this.t("commandOuterEdge"),
      "dock-edge": this.t("commandDockEdge"),
      pause: this.t("pauseTask"),
      resume: this.t("resumeTask"),
      "reset-blade": this.t("resetBlade"),
      "reset-camera": this.t("resetCamera"),
      "reset-contact": this.t("resetDockContact"),
    })[command] || String(command || this.t("control"));
    showAnthbotCommandToast(this.feedback("commandSentWaiting", commandText));
    const customAction = this.effectiveCustomButtonAction(command);
    if (customAction) {
      await this.callCustomButtonAction(command, customAction);
      return;
    }

    const buttonEntity = this.getControlEntity(command);
    if (buttonEntity) {
      await this.pressButtonEntity(buttonEntity, command);
      return;
    }

    const serviceByCommand = {
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
    const service = serviceByCommand[command];
    if (service) {
      await this.callAnthbotService(service);
    }
  }

  async startZone(zone) {
    showAnthbotCommandToast(this.feedback("commandSentWaiting", zone?.name || this.t("zoneStart")));
    const zoneButton = this.getZoneButtonEntity(zone);
    if (zoneButton) {
      await this.pressButtonEntity(zoneButton, "zone");
      return;
    }
    await this.callAnthbotService("start_zone_mow", { zones: String(zone.id ?? zone.name) });
  }

  async startZones(zones) {
    const labels = zones.map((zone) => zone.name || `${this.t("zone")} ${zone.id}`).join(", ");
    showAnthbotCommandToast(this.feedback("commandSentWaiting", labels));
    await this.callAnthbotService("start_zone_mow", {
      zones: zones.map((zone) => zone.id ?? zone.name),
    });
  }

  async startAutoZone(zone) {
    showAnthbotCommandToast(this.feedback("commandSentWaiting", zone?.name || this.t("autoZone")));
    await this.callAnthbotService("start_auto_zone_mow", {
      auto_zones: String(zone.id ?? zone.name),
    });
  }

  async startAutoZones(zones) {
    const labels = zones.map((zone) => zone.name || `${this.t("autoZone")} ${zone.id}`).join(", ");
    showAnthbotCommandToast(this.feedback("commandSentWaiting", labels));
    await this.callAnthbotService("start_auto_zone_mow", {
      auto_zones: zones.map((zone) => zone.id ?? zone.name),
    });
  }

  async pressButtonEntity(entityId, command) {
    const service = command === "zone" ? "start_zone_mow" : ({
      start: "start_full_mow",
      stop: "stop_mow",
      dock: "return_to_dock",
      pause: "pause_mow",
      resume: "resume_mow",
      "outer-edge": "start_outer_edge_mow",
      "dock-edge": "start_dock_edge_mow",
    })[command];
    const label = this.commandLabel(service || command);
    const stopRtkStatus = this.beginRtkInitializationStatus(service);
    if (!stopRtkStatus) this.notify(this.feedback("commandSentWaiting", label));
    try {
      await this._hass.callService("button", "press", { entity_id: entityId });
      stopRtkStatus?.();
      if (this.isMowingStartService(service)) this.notify(this.t("mowingStarting"));
      this.scheduleRefresh(200);
      if (service) void this.waitForCommandConfirmation(service);
    } catch (error) {
      stopRtkStatus?.();
      this.notify(this.feedback("commandFailed", label));
      throw error;
    }
  }

  async callAnthbotService(service, data = {}) {
    const label = this.commandLabel(service);
    const stopRtkStatus = this.beginRtkInitializationStatus(service);
    if (!stopRtkStatus) this.notify(this.feedback("commandSentWaiting", label));
    try {
      const domain = this.resolveServiceDomain(service);
      await this._hass.callService(domain, service, {
        ...data,
        entity_id: this._activeEntityId || this.config.entity,
      });
      stopRtkStatus?.();
      if (this.isMowingStartService(service)) this.notify(this.t("mowingStarting"));
      this.scheduleRefresh(200);
      void this.waitForCommandConfirmation(service);
    } catch (error) {
      stopRtkStatus?.();
      this.notify(this.feedback("commandFailed", label));
      throw error;
    }
  }

  isMowingStartService(service) {
    return ["start_full_mow", "start_outer_edge_mow", "start_dock_edge_mow", "start_zone_mow", "start_auto_zone_mow", "resume_mow"].includes(service);
  }

  sharedRtkPowerIsEnabled() {
    const entityId = this.getSwitchEntity("batterySaver");
    const state = entityId ? this._hass.states[entityId] : null;
    return state?.state === "on" && state?.attributes?.shared_rtk_power === true;
  }

  beginRtkInitializationStatus(service) {
    if (!this.isMowingStartService(service) || !this.sharedRtkPowerIsEnabled()) return null;
    let count = 1;
    const render = () => {
      showAnthbotCommandToast(`${this.t("rtkInitializing")}${".".repeat(count)}`);
      count = count % 3 + 1;
    };
    render();
    const timer = window.setInterval(render, 450);
    return () => window.clearInterval(timer);
  }

  resolveServiceDomain(service) {
    const domains = ["anthbot_map", "anthbot_genie_plus", "anthbot_ha"];
    return domains.find((domain) => this._hass?.services?.[domain]?.[service]) || "anthbot_map";
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
      pause_mow: this.t("pauseTask"),
      resume_mow: this.t("resumeTask"),
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
    ].map((value) => String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ""));
  }

  commandIsConfirmed(service) {
    const expected = ({
      start_full_mow: ["mowing", "globalmowing", "working", "cutting", "nyiras", "funyiras"],
      start_zone_mow: ["mowing", "zonemowing", "regionmowing", "working", "cutting", "nyiras", "zonanyiras"],
      start_outer_edge_mow: ["mowing", "bordermowing", "edgemowing", "edgecutting", "working", "nyiras", "szegelynyiras"],
      start_dock_edge_mow: ["mowing", "nestmowing", "working", "nyiras", "tolto", "kornyekeneknyirasa"],
      stop_mow: ["paused", "pause", "standby", "idle", "charging", "charge", "docked", "szunetel", "keszenlet", "toltes", "dokkolva"],
      pause_mow: ["paused", "pause", "szunetel", "szuneteltetve"],
      resume_mow: ["mowing", "globalmowing", "zonemowing", "regionmowing", "working", "cutting", "nyiras", "funyiras"],
      return_to_dock: ["returning", "backtodock", "returntodock", "docking", "charging", "charge", "docked", "visszaatoltore", "toltes", "dokkolva"],
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
      mowCount: "×",
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
    const confirmationService = ({ start: "start_full_mow", stop: "stop_mow", dock: "return_to_dock", "outer-edge": "start_outer_edge_mow", "dock-edge": "start_dock_edge_mow", pause: "pause_mow", resume: "resume_mow" })[command];
    const label = this.commandLabel(confirmationService || command);
    this.notify(this.feedback("commandSentWaiting", label));
    try {
      await this._hass.callService(domain, service, data, target);
      this.scheduleRefresh(200);
      if (confirmationService) void this.waitForCommandConfirmation(confirmationService);
    } catch (error) {
      this.notify(this.feedback("commandFailed", label));
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
        entity_id: this._activeEntityId || this.config.entity,
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
      this.mowingPathCalibration = resetCalibration();
      this.robotHeadingOffset = 0;
      this.renderer.setCalibration(this.calibration);
      this.renderer.setRobotCalibration(this.robotCalibration);
      this.renderer.setMowingPathCalibration(this.mowingPathCalibration);
      this.renderer.setOptions({ robotHeadingOffset: this.robotHeadingOffset });
      this.renderer.resetView();
      this.updateYaml();
    } else if (action === "reset-mowing-path") {
      this.mowingPathCalibration = resetCalibration();
      this.renderer.setMowingPathCalibration(this.mowingPathCalibration);
      this.updateYaml();
    } else if (action === "reset-robot") {
      this.robotCalibration = resetCalibration();
      this.renderer.setRobotCalibration(this.robotCalibration);
      this.updateYaml();
    } else if (action === "reset-robot-heading") {
      this.robotHeadingOffset = 0;
      this.renderer.setOptions({ robotHeadingOffset: this.robotHeadingOffset });
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

  handleMowingPathCalibration(action) {
    this.mowingPathCalibration = adjustCalibration(this.mowingPathCalibration, action, 1);
    this.renderer.setMowingPathCalibration(this.mowingPathCalibration);
    this.updateYaml();
  }

  handleRobotCalibration(action) {
    this.robotCalibration = adjustCalibration(this.robotCalibration, action, 1);
    this.renderer.setRobotCalibration(this.robotCalibration);
    this.updateYaml();
  }

  handleRobotHeading(action) {
    if (action === "left") this.robotHeadingOffset -= 15;
    if (action === "right") this.robotHeadingOffset += 15;
    if (action === "around") this.robotHeadingOffset += 180;
    this.robotHeadingOffset = ((this.robotHeadingOffset + 180) % 360 + 360) % 360 - 180;
    this.renderer.setOptions({ robotHeadingOffset: this.robotHeadingOffset });
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
        this.mowingPathCalibration,
      );
    }
  }

  async copyYaml() {
    const yaml = cardToYaml(
      this.configForYaml(),
      this.calibration,
      this.robotCalibration,
      this.decodedBoundaryCalibration,
      this.mowingPathCalibration,
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
      button_actions: this.customButtonActionsEnabled ? this.customButtonActions : {},
      map_only: this.mapOnly,
      theme_background: this.themeBackground,
      glass_background: this.glassBackground,
      transparent_background: this.transparentBackground,
      language: this.selectedLanguage,
      robot_heading_offset: this.robotHeadingOffset,
      show_decoded_boundary: this.showDecodedBoundary,
      show_zones: this.showZones,
      show_no_go_zones: this.showNoGoZones,
      show_no_go_labels: this.showNoGoLabels,
    };
  }

  getControlEntity(command) {
    const configured = this.config.controls?.[command];
    if (this.isEntityAvailable(configured)) {
      return configured;
    }

    const suffixByCommand = {
      start: ["start_full_mow"],
      stop: ["stop_mow"],
      dock: ["return_to_dock"],
      pause: ["pause_mow"],
      resume: ["resume_mow"],
      "reset-blade": ["reset_blade_maintenance"],
      "reset-camera": ["reset_camera_maintenance"],
      "reset-contact": ["reset_dock_contact_maintenance"],
    };
    return this.findEntity("button", suffixByCommand[command] || []);
  }

  getZoneButtonEntity(zone) {
    if (this.isEntityAvailable(zone.entity_id)) {
      return zone.entity_id;
    }

    const configured = this.config.zoneButtons?.[zone.id] || this.config.zoneButtons?.[zone.name];
    if (this.isEntityAvailable(configured)) {
      return configured;
    }

    const zoneId = zone.id === undefined || zone.id === null ? null : String(zone.id);
    const zoneName = String(zone.name || "").trim();
    const normalizedName = slugify(zoneName);

    for (const [entityId, state] of Object.entries(this._hass.states || {})) {
      if (!entityId.startsWith("button.")) {
        continue;
      }
      if (state.state === "unavailable") {
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
        if (this.isEntityAvailable(candidate)) {
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
    if (this.isEntityAvailable(configured)) {
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
    if (this.isEntityAvailable(configured)) {
      return configured;
    }
    return this.findEntity("number", NUMBER_MAP[kind] || []);
  }

  getSwitchEntity(kind) {
    const configured = this.config.switches?.[kind];
    if (this.isEntityAvailable(configured)) {
      return configured;
    }

    return this.findEntity("switch", SWITCH_MAP[kind] || []);
  }

  isEntityAvailable(entityId) {
    const state = entityId ? this._hass?.states?.[entityId] : null;
    return Boolean(state && state.state !== "unavailable");
  }

  findEntity(domain, suffixes) {
    const base = this.entityBase();
    for (const suffix of suffixes) {
      const escapedBase = base.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const escapedSuffix = suffix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const pattern = new RegExp(`^${domain}\\.${escapedBase}_${escapedSuffix}(?:_(\\d+))?$`);
      const matches = Object.entries(this._hass.states || {})
        .map(([entityId, state]) => ({ entityId, state, match: entityId.match(pattern) }))
        // Button entities normally have an `unknown` state in Home Assistant,
        // but they are still pressable. Only discard truly unavailable ones.
        .filter(({ state, match }) => match && state.state !== "unavailable")
        .sort((left, right) => Number(right.match?.[1] || 1) - Number(left.match?.[1] || 1));
      if (matches.length) {
        return matches[0].entityId;
      }
    }

    for (const suffix of suffixes) {
      const wanted = slugify(`${base}_${suffix}`);
      for (const [entityId, state] of Object.entries(this._hass.states || {})) {
        if (!entityId.startsWith(`${domain}.`)) {
          continue;
        }
        if (state.state === "unavailable") {
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
    return String(this._activeEntityId || this.config.entity || "")
      .replace(/^sensor\./, "")
      .replace(/_map(?:_\d+)?$/, "");
  }

  resolveMapEntityId() {
    const configured = String(this.config?.entity || "");
    const configuredState = this._hass?.states?.[configured];
    if (configuredState && configuredState.state !== "unavailable") {
      return configured;
    }

    const root = configured.replace(/_map(?:_\d+)?$/, "_map");
    const escapedRoot = root.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`^${escapedRoot}(?:_(\\d+))?$`);
    const active = Object.entries(this._hass?.states || {})
      .map(([entityId, state]) => ({ entityId, state, match: entityId.match(pattern) }))
      .filter(({ state, match }) => match && state.state !== "unavailable")
      .sort((left, right) => Number(right.match?.[1] || 1) - Number(left.match?.[1] || 1));
    return active[0]?.entityId || configured;
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
    const text = String(message || "");
    showAnthbotCommandToast(text);
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message: text }, bubbles: true, composed: true,
    }));
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

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[char]);
}

// --- Calculated mowing-history target geometry -----------------------------
// Mirrors the backend v3 progress test: polygon areas are kept in raw map
// units, then calibrated to m² with map_area / sum(all mowing-zone polygons).
// No-Go subtraction uses an exact vertical sweep over union(zone) ∩ union(no-go)
// so overlapping No-Go polygons are not subtracted twice.
function historyZonePoints(zone) {
  const points = getZonePoints(zone || {});
  return points
    .map((point) => ({ x: Number(point?.x), y: Number(point?.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
}

function historyPolygonAreaRaw(points) {
  if (!Array.isArray(points) || points.length < 3) return 0;
  let area2 = 0;
  for (let index = 0; index < points.length; index += 1) {
    const first = points[index];
    const second = points[(index + 1) % points.length];
    area2 += first.x * second.y - second.x * first.y;
  }
  return Math.abs(area2) / 2;
}

function historyPolygonSegments(points) {
  if (!Array.isArray(points) || points.length < 2) return [];
  const result = [];
  for (let index = 0; index < points.length; index += 1) {
    const first = points[index];
    const second = points[(index + 1) % points.length];
    if (first.x !== second.x || first.y !== second.y) result.push([first, second]);
  }
  return result;
}

function historySegmentIntersectionX(first, second) {
  const [a, b] = first;
  const [c, d] = second;
  const rx = b.x - a.x, ry = b.y - a.y;
  const sx = d.x - c.x, sy = d.y - c.y;
  const denominator = rx * sy - ry * sx;
  if (Math.abs(denominator) < 1e-12) return null;
  const qx = c.x - a.x, qy = c.y - a.y;
  const t = (qx * sy - qy * sx) / denominator;
  const u = (qx * ry - qy * rx) / denominator;
  const tolerance = 1e-9;
  if (t < -tolerance || t > 1 + tolerance || u < -tolerance || u > 1 + tolerance) return null;
  return a.x + t * rx;
}

function historyUnionIntervalsAtX(polygons, xValue) {
  const intervals = [];
  for (const points of polygons) {
    const yValues = [];
    for (const [first, second] of historyPolygonSegments(points)) {
      if (Math.abs(second.x - first.x) < 1e-12) continue;
      const lowX = Math.min(first.x, second.x);
      const highX = Math.max(first.x, second.x);
      if (!(lowX < xValue && xValue < highX)) continue;
      const ratio = (xValue - first.x) / (second.x - first.x);
      yValues.push(first.y + ratio * (second.y - first.y));
    }
    yValues.sort((a, b) => a - b);
    for (let index = 0; index + 1 < yValues.length; index += 2) {
      const lowY = yValues[index], highY = yValues[index + 1];
      if (highY > lowY) intervals.push([lowY, highY]);
    }
  }
  intervals.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged = [];
  for (const [lowY, highY] of intervals) {
    const last = merged[merged.length - 1];
    if (!last || lowY > last[1] + 1e-9) merged.push([lowY, highY]);
    else if (highY > last[1]) last[1] = highY;
  }
  return merged;
}

function historyIntervalIntersectionLength(first, second) {
  let firstIndex = 0, secondIndex = 0, total = 0;
  while (firstIndex < first.length && secondIndex < second.length) {
    const lowY = Math.max(first[firstIndex][0], second[secondIndex][0]);
    const highY = Math.min(first[firstIndex][1], second[secondIndex][1]);
    if (highY > lowY) total += highY - lowY;
    if (first[firstIndex][1] < second[secondIndex][1]) firstIndex += 1;
    else secondIndex += 1;
  }
  return total;
}

function historyPolygonUnionIntersectionAreaRaw(firstPolygons, secondPolygons) {
  const first = (firstPolygons || []).filter((points) => Array.isArray(points) && points.length >= 3);
  const second = (secondPolygons || []).filter((points) => Array.isArray(points) && points.length >= 3);
  if (!first.length || !second.length) return 0;

  const firstPoints = first.flat();
  const secondPoints = second.flat();
  const firstX = firstPoints.map((p) => p.x), firstY = firstPoints.map((p) => p.y);
  const secondX = secondPoints.map((p) => p.x), secondY = secondPoints.map((p) => p.y);
  if (
    Math.max(...firstX) <= Math.min(...secondX)
    || Math.max(...secondX) <= Math.min(...firstX)
    || Math.max(...firstY) <= Math.min(...secondY)
    || Math.max(...secondY) <= Math.min(...firstY)
  ) return 0;

  const events = [];
  const taggedSegments = [];
  [first, second].forEach((polygons, setIndex) => {
    polygons.forEach((points, polygonIndex) => {
      points.forEach((point) => events.push(point.x));
      historyPolygonSegments(points).forEach((segment) => taggedSegments.push({ setIndex, polygonIndex, segment }));
    });
  });
  for (let firstIndex = 0; firstIndex < taggedSegments.length; firstIndex += 1) {
    const a = taggedSegments[firstIndex];
    for (let secondIndex = firstIndex + 1; secondIndex < taggedSegments.length; secondIndex += 1) {
      const b = taggedSegments[secondIndex];
      if (a.setIndex === b.setIndex && a.polygonIndex === b.polygonIndex) continue;
      const x = historySegmentIntersectionX(a.segment, b.segment);
      if (x !== null) events.push(x);
    }
  }
  events.sort((a, b) => a - b);
  const unique = [];
  for (const value of events) {
    if (!unique.length || Math.abs(value - unique[unique.length - 1]) > 1e-7) unique.push(value);
  }

  let totalArea = 0;
  for (let index = 0; index + 1 < unique.length; index += 1) {
    const lowX = unique[index], highX = unique[index + 1];
    const width = highX - lowX;
    if (width <= 1e-9) continue;
    const midX = (lowX + highX) / 2;
    const overlapHeight = historyIntervalIntersectionLength(
      historyUnionIntervalsAtX(first, midX),
      historyUnionIntervalsAtX(second, midX),
    );
    totalArea += overlapHeight * width;
  }
  return Math.max(0, totalArea);
}

function historyPointInPolygon(point, polygon) {
  if (!point || !Array.isArray(polygon) || polygon.length < 3) return false;
  const x = Number(point.x), y = Number(point.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
    const xi = polygon[i].x, yi = polygon[i].y;
    const xj = polygon[j].x, yj = polygon[j].y;
    const crosses = ((yi > y) !== (yj > y))
      && x < ((xj - xi) * (y - yi)) / ((yj - yi) || Number.EPSILON) + xi;
    if (crosses) inside = !inside;
  }
  return inside;
}

function historyZoneMatchKey(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  const normalized = raw.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const zoneNumber = normalized.match(/(?:zone|zona)\s*[-_#:]?\s*(\d+)/);
  if (zoneNumber) return `zone:${zoneNumber[1]}`;
  return normalized.replace(/[^a-z0-9]+/g, "");
}

function historyRecordZoneIdCandidates(record) {
  const result = [];
  const keys = [
    "zone_id", "zoneId", "zone_ids", "zoneIds", "mow_zone", "mowZone",
    "region_id", "regionId", "region_ids", "regionIds", "area_id", "areaId",
  ];
  for (const key of keys) {
    const value = record?.[key];
    if (Array.isArray(value)) result.push(...value);
    else if (value !== undefined && value !== null && value !== "") result.push(value);
  }
  return result;
}

function historyRecordCacheKey(record) {
  const id = pickRecordValue(record, MOWING_RECORD_ID_KEYS);
  if (id !== undefined) return `id:${id}`;
  return [
    pickRecordValue(record, MOWING_RECORD_START_KEYS),
    pickRecordValue(record, MOWING_RECORD_END_KEYS),
    pickRecordValue(record, MOWING_RECORD_AREA_URL_KEYS),
    pickRecordValue(record, MOWING_RECORD_PATH_URL_KEYS),
  ].map((value) => String(value ?? "")).join("|");
}

function formatCalculatedRecordPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "–";
  return `${Math.round(number * 10) / 10}%`;
}

// --- Mowing history (previous mowing-task records) -------------------------
//
// The cloud "record list" endpoint field names have not been confirmed from a
// populated response yet (the account used to build this only had an empty
// history at the time), so every field is read defensively through a list of
// plausible camelCase/snake_case aliases, mirroring the alias-list approach
// already used for path/history URL keys elsewhere in this integration. Any
// record field that isn't recognized by one of these aliases is still shown,
// verbatim, in a collapsible "other fields" block so nothing is silently
// dropped. Once real records are available the alias lists below can be
// trimmed to the confirmed key names.

const MOWING_RECORD_ID_KEYS = ["id", "record_id", "recordId", "task_id", "taskId", "_id"];
const MOWING_RECORD_START_KEYS = [
  "start_time", "startTime", "begin_time", "beginTime", "begin",
  "task_start_time", "taskStartTime", "create_time", "createTime",
  "started_at", "startedAt",
];
const MOWING_RECORD_END_KEYS = [
  "end_time", "endTime", "finish_time", "finishTime", "stop_time", "stopTime",
  "complete_time", "completeTime", "finished_at", "finishedAt",
];
const MOWING_RECORD_AREA_KEYS = [
  "area", "mow_area", "mowArea", "actual_area", "actualArea", "clean_area",
  "cleanArea", "cleaned_area", "cleanedArea", "real_area", "realArea",
  "task_area", "taskArea", "mowing_area", "mowingArea",
];
const MOWING_RECORD_PERCENT_KEYS = [
  "percent", "percentage", "progress", "complete_rate", "completeRate",
  "finish_rate", "finishRate", "mow_percent", "mowPercent",
  "task_percent", "taskPercent", "rate", "mowing_progress", "mowingProgress",
];
const MOWING_RECORD_DURATION_KEYS = [
  "duration_ms", "durationMs", "elapsed_ms", "elapsedMs",
  "mowing_time_ms", "mowingTimeMs", "task_time_ms", "taskTimeMs",
  "duration", "cost_time", "costTime", "time_len", "timeLen", "elapsed",
  "elapsed_time", "elapsedTime", "mowing_time", "mowingTime",
  "task_time", "taskTime", "work_time", "workTime", "mow_time", "mowTime",
];
const MOWING_RECORD_MODE_KEYS = [
  "mode", "mow_mode", "mowMode", "task_type", "taskType", "type",
  "task_mode", "taskMode",
];
const MOWING_RECORD_SOURCE_KEYS = [
  "source", "start_source", "startSource", "trigger", "task_source",
  "taskSource", "from", "start_type", "startType", "start_reason", "startReason",
  "start_cause", "startCause",
];
const MOWING_RECORD_AREA_URL_KEYS = ["area_url", "areaUrl"];
const MOWING_RECORD_MAP_URL_KEYS = ["map_url", "mapUrl"];
const MOWING_RECORD_PATH_URL_KEYS = ["path_url", "pathUrl"];
// The record row's own start position (confirmed present alongside
// mow_mode/finish_time in the /api/v1/device/area response) -- used as the
// anchor for the mgs-v1-history path format, whose points turned out to be
// per-sample deltas rather than absolute coordinates (see
// extractDetailPathPoints).
const MOWING_RECORD_START_X_KEYS = ["x", "X", "start_x", "startX"];
const MOWING_RECORD_START_Y_KEYS = ["y", "Y", "start_y", "startY"];
const MOWING_RECORD_ZONE_LIST_KEYS = [
  "zone_list", "zoneList", "zones", "region_list", "regionList",
  "area_list", "areaList", "task_zones", "taskZones", "zone_info", "zoneInfo",
];
const MOWING_RECORD_ZONE_NAME_KEYS = [
  "name", "zone_name", "zoneName", "region_name", "regionName",
  "area_name", "areaName", "title",
];
const MOWING_RECORD_ZONE_WIDTH_KEYS = ["width", "w", "zone_width", "zoneWidth"];
const MOWING_RECORD_ZONE_HEIGHT_KEYS = [
  "height", "h", "zone_height", "zoneHeight", "length", "zone_length", "zoneLength",
];
const MOWING_RECORD_ZONE_AREA_KEYS = ["area", "zone_area", "zoneArea", "actual_area", "actualArea", "size"];

const MOWING_RECORD_MAPPED_KEYS = [
  ...MOWING_RECORD_ID_KEYS, ...MOWING_RECORD_START_KEYS, ...MOWING_RECORD_END_KEYS,
  ...MOWING_RECORD_AREA_KEYS, ...MOWING_RECORD_PERCENT_KEYS, ...MOWING_RECORD_DURATION_KEYS,
  ...MOWING_RECORD_MODE_KEYS, ...MOWING_RECORD_SOURCE_KEYS, ...MOWING_RECORD_ZONE_LIST_KEYS,
];

// Builds a lookup (normalized zone name -> {name, dims}) from the mowing
// record's own `zone_list` field -- this is the app's own account of which
// zones were actually part of *this* session (matching the reference
// screenshot Attila shared, which highlights only the mowed zone(s) among
// the full property layout). Matched against the full zone polygons from
// the `area` file by name in renderMowingRecordZonesSvg.
function mowedZoneInfoFromRecord(record) {
  const zoneListRaw = pickRecordValue(record, MOWING_RECORD_ZONE_LIST_KEYS);
  const zoneList = Array.isArray(zoneListRaw) ? zoneListRaw : [];
  const info = new Map();
  for (const zone of zoneList) {
    const zoneName = pickRecordValue(zone, MOWING_RECORD_ZONE_NAME_KEYS);
    if (!zoneName) continue;
    const width = pickRecordValue(zone, MOWING_RECORD_ZONE_WIDTH_KEYS);
    const height = pickRecordValue(zone, MOWING_RECORD_ZONE_HEIGHT_KEYS);
    const zoneArea = pickRecordValue(zone, MOWING_RECORD_ZONE_AREA_KEYS);
    let dims = "";
    if (width !== undefined && height !== undefined) {
      dims = `${formatRecordNumber(width)}m × ${formatRecordNumber(height)}m`;
    } else if (zoneArea !== undefined) {
      dims = formatRecordArea(zoneArea);
    }
    info.set(String(zoneName).trim().toLowerCase(), { name: String(zoneName), dims });
  }
  return info;
}

function pickRecordValue(record, keys) {
  if (!record || typeof record !== "object") return undefined;
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return undefined;
}

function pickRecordEntry(record, keys) {
  if (!record || typeof record !== "object") return null;
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && value !== "") return { key, value };
  }
  return null;
}

function collectUnmappedRecordKeys(record, mappedKeys) {
  if (!record || typeof record !== "object") return [];
  const mapped = new Set(mappedKeys);
  return Object.keys(record).filter((key) => !mapped.has(key));
}

function parseRecordTimestamp(value) {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value === "number") {
    const ms = value > 10_000_000_000 ? value : value * 1000;
    const date = new Date(ms);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (/^\d{14}$/.test(trimmed)) {
      const year = trimmed.slice(0, 4), month = trimmed.slice(4, 6), day = trimmed.slice(6, 8);
      const hour = trimmed.slice(8, 10), minute = trimmed.slice(10, 12), second = trimmed.slice(12, 14);
      const date = new Date(Date.UTC(+year, +month - 1, +day, +hour, +minute, +second));
      return Number.isNaN(date.getTime()) ? null : date;
    }
    if (/^\d+$/.test(trimmed)) return parseRecordTimestamp(Number(trimmed));
    let isoCandidate = trimmed.replace(" ", "T");
    // The Anthbot cloud API returns timestamps such as finish_time in UTC but
    // without a "Z"/offset suffix (e.g. "2026-08-19T15:09:59"). Per the JS Date
    // spec, a date-time string with no timezone designator is parsed as LOCAL
    // time, which silently shifted every mowing-history time by the viewer's
    // UTC offset (confirmed against the mobile app: cloud said 15:09, app
    // showed 17:09 in UTC+2). Mark it UTC explicitly before parsing.
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(isoCandidate)) {
      isoCandidate += "Z";
    }
    const date = new Date(isoCandidate);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
}

// Paints a run-length-encoded coverage raster (the same format the live map
// uses for `_map_raster`, see renderer.js's getRasterCanvas) into a small
// standalone <canvas>, without needing the live renderer's calibrated
// world-to-screen geometry -- the history popup just needs the raw picture.
function rasterColorForRecordDetail(value) {
  if (value === 255) return [248, 250, 252, 255];
  if (value === 160) return [158, 166, 174, 255];
  if (value === 128) return [117, 125, 133, 255];
  if (value === 0) return [25, 32, 42, 255];
  const shade = Math.max(0, Math.min(255, Number(value) || 0));
  return [shade, shade, shade, 255];
}

// Resolves once the image has loaded (with its natural pixel size readable)
// or once it fails -- never rejects, so callers can `await` it plainly and
// treat a null result as "no background image available".
function loadImageElement(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

function boundingBoxOf(points) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const point of points) {
    if (point.x < minX) minX = point.x;
    if (point.x > maxX) maxX = point.x;
    if (point.y < minY) minY = point.y;
    if (point.y > maxY) maxY = point.y;
  }
  return { minX, minY, maxX, maxY };
}

// The Genie/MGS path format tags every sample with a `type`; these codes
// (mirrored from renderer.js's live-map trail filter) mark "blade engaged /
// actually cutting" points, as opposed to plain travel (blade off, e.g.
// driving to the start point or back to the dock).
const DETAIL_PATH_MOWED_TYPES = new Set([1, 2, 5, 8]);
// Consecutive mowed samples farther apart than this (in the same mm world
// units as the map raster bounds) are treated as a break -- e.g. the mower
// was carried, or the log jumps between two disjoint passes -- rather than
// drawn as a single straight line cutting across the whole map.
const DETAIL_PATH_JUMP_LIMIT_MM = 2500;

function isDetailPathMowedPoint(point, hasKnownMowedTypes) {
  // Historical files may omit type information. When at least one known
  // blade-engaged type is present, use the same filtering as the live map so
  // travel to/from the dock is not painted as mowed coverage. If no known type
  // occurs, preserve the complete path rather than rendering a blank detail.
  return !hasKnownMowedTypes || DETAIL_PATH_MOWED_TYPES.has(Number(point?.type));
}

// Pulls the decoded path points out of a `path` file definition (see
// api.py's `_decode_path_definition`) and drops anything without finite
// coordinates.
//
// 2026-08-21 history: a live hex dump of an "mgs-v1-history" path file
// showed the very first points sitting almost still (x~-98, y~5, barely
// moving for several samples) -- exactly what you'd expect right at the
// start of a session near the dock, NOT a per-sample delta pattern. The
// real bug turned out to be the coordinate scale: this format was using x1
// instead of the x10 every other format uses (now fixed in api.py). No
// cumulative summing/anchor needed -- the decoded x/y are already absolute
// positions in the same mm world frame as the map raster bounds. (The
// `anchor` parameter is kept, unused, in case a future format genuinely
// turns out to be delta-encoded.)
function extractDetailPathPoints(pathDefinition, _anchor = null) {
  const raw = pathDefinition?._path_points;
  if (!Array.isArray(raw)) return [];
  const points = [];
  for (const point of raw) {
    const x = Number(point?.x);
    const y = Number(point?.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    points.push({ x, y, type: point?.type, clean_time: point?.clean_time });
  }
  return points;
}

// Splits the raw point stream into disjoint polylines: drops travel-only
// (blade-off) points and starts a new segment whenever consecutive mowed
// points are implausibly far apart.
function buildDetailPathSegments(points, jumpLimit) {
  const segments = [];
  let segment = [];
  let previous = null;
  const hasKnownMowedTypes = points.some((point) =>
    DETAIL_PATH_MOWED_TYPES.has(Number(point?.type))
  );
  for (const point of points) {
    if (!isDetailPathMowedPoint(point, hasKnownMowedTypes)) {
      if (segment.length) segments.push(segment);
      segment = [];
      previous = null;
      continue;
    }
    const jumped = previous && Math.hypot(point.x - previous.x, point.y - previous.y) > jumpLimit;
    if (jumped && segment.length) {
      segments.push(segment);
      segment = [];
    }
    segment.push(point);
    previous = point;
  }
  if (segment.length) segments.push(segment);
  return segments.filter((entry) => entry.length >= 2);
}

// Converts a path point's world coordinates (mm, same frame the map
// raster's `bounds` are expressed in) into the raster canvas's raw pixel
// space, matching the same row flip `renderMowingRecordRasterCanvas` uses.
function projectWorldPointToRasterPixel(point, raster) {
  const bounds = raster?.bounds;
  const resolution = Number(raster?.resolution);
  const height = Number(raster?.height);
  if (!bounds || !Number.isFinite(resolution) || resolution <= 0 || !Number.isFinite(height)) {
    return null;
  }
  const minX = Number(bounds.min_x ?? bounds.minX);
  const minY = Number(bounds.min_y ?? bounds.minY);
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null;
  const resolutionMm = resolution * 1000;
  if (!Number.isFinite(resolutionMm) || resolutionMm <= 0) return null;
  const x = (point.x - minX) / resolutionMm;
  const y = height - 1 - (point.y - minY) / resolutionMm;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

// Draws the session's actual mowed coverage on top of the static boundary
// raster. Returns true if anything was drawn.
function drawDetailPathOnRasterCanvas(canvas, raster, pathPoints) {
  if (!canvas || !pathPoints.length) return false;
  const ctx = canvas.getContext("2d");
  if (!ctx) return false;

  const segments = buildDetailPathSegments(pathPoints, DETAIL_PATH_JUMP_LIMIT_MM)
    .map((segment) => segment.map((point) => projectWorldPointToRasterPixel(point, raster)).filter(Boolean))
    .filter((segment) => segment.length >= 2);
  if (!segments.length) return false;

  const strokeWidth = Math.max(2, canvas.width * 0.012);
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const [color, width] of [
    ["rgba(82, 94, 245, 0.55)", strokeWidth],
    ["rgba(220, 226, 255, 0.7)", Math.max(1, strokeWidth * 0.35)],
  ]) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    for (const segment of segments) {
      ctx.beginPath();
      ctx.moveTo(segment[0].x, segment[0].y);
      for (const point of segment.slice(1)) ctx.lineTo(point.x, point.y);
      ctx.stroke();
    }
  }
  ctx.restore();
  return true;
}

// Appends the mowed-path polylines to an existing zone/path-only SVG, using
// raw world coordinates directly (the same unflipped convention the zone
// polygons already use, see renderMowingRecordZonesSvg).
function appendDetailPathPolylines(svg, pathPoints, strokeWidth) {
  const segments = buildDetailPathSegments(pathPoints, DETAIL_PATH_JUMP_LIMIT_MM);
  if (!segments.length) return false;
  const svgNs = "http://www.w3.org/2000/svg";
  for (const segment of segments) {
    const line = document.createElementNS(svgNs, "polyline");
    line.setAttribute("points", segment.map((p) => `${p.x},${p.y}`).join(" "));
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", "rgba(94, 224, 131, 0.85)");
    line.setAttribute("stroke-width", String(strokeWidth));
    line.setAttribute("stroke-linecap", "round");
    line.setAttribute("stroke-linejoin", "round");
    svg.appendChild(line);
  }
  return true;
}

// Standalone rendering for when only the path file decoded (no map raster,
// no area/zone data): plots the mowed-point bounding box on its own.
function renderMowingRecordPathOnlySvg(pathPoints) {
  const segments = buildDetailPathSegments(pathPoints, DETAIL_PATH_JUMP_LIMIT_MM);
  if (!segments.length) return null;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const segment of segments) {
    for (const point of segment) {
      if (point.x < minX) minX = point.x;
      if (point.x > maxX) maxX = point.x;
      if (point.y < minY) minY = point.y;
      if (point.y > maxY) maxY = point.y;
    }
  }
  if (![minX, minY, maxX, maxY].every(Number.isFinite)) return null;

  const spanX = Math.max(maxX - minX, 0.01);
  const spanY = Math.max(maxY - minY, 0.01);
  const padding = Math.max(spanX, spanY) * 0.08;
  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute(
    "viewBox",
    `${minX - padding} ${minY - padding} ${spanX + padding * 2} ${spanY + padding * 2}`
  );
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  appendDetailPathPolylines(svg, pathPoints, Math.max(spanX, spanY) * 0.01);
  return svg;
}

function renderMowingRecordRasterCanvas(raster) {
  const width = Number(raster.width);
  const height = Number(raster.height);
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    return null;
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const imageData = ctx.createImageData(width, height);
  let pixel = 0;
  const runs = raster.runs || [];
  for (let index = 0; index < runs.length - 1 && pixel < width * height; index += 2) {
    const value = Number(runs[index]);
    const count = Number(runs[index + 1]);
    if (!Number.isFinite(value) || !Number.isFinite(count) || count <= 0) continue;
    const color = rasterColorForRecordDetail(value);
    for (let step = 0; step < count && pixel < width * height; step += 1, pixel += 1) {
      const sourceX = pixel % width;
      const sourceY = Math.floor(pixel / width);
      const target = ((height - 1 - sourceY) * width + sourceX) * 4;
      imageData.data[target] = color[0];
      imageData.data[target + 1] = color[1];
      imageData.data[target + 2] = color[2];
      imageData.data[target + 3] = color[3];
    }
  }
  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

// Port of renderer.js's decodeRasterRuns(): expands the raster's
// run-length-encoded `runs` (value, count, value, count, ...) into a flat
// per-pixel array, row-major, NO row flip (that flip in
// renderMowingRecordRasterCanvas above is purely a canvas-image-orientation
// concern; the raw pixel order here matches world Y directly, same as
// renderer.js's own boundary tracer expects).
function decodeRasterSolidMask(raster, width, height) {
  if (!Array.isArray(raster?.runs)) return null;
  const pixels = new Uint8Array(width * height);
  let offset = 0;
  for (let index = 0; index < raster.runs.length - 1; index += 2) {
    const value = Math.max(0, Math.min(255, Number(raster.runs[index]) || 0));
    const count = Number(raster.runs[index + 1]);
    if (!Number.isFinite(count) || count <= 0) continue;
    pixels.fill(value, offset, Math.min(width * height, offset + count));
    offset += count;
    if (offset >= width * height) break;
  }
  return pixels;
}

// Port of renderer.js's drawRasterBoundary(): traces the edges between
// solid (mowed-lawn) and empty raster cells -- the real mapped-lawn
// silhouette, pixel-accurate, as opposed to the raw wire-perimeter/travel
// route in map_binary_paths (which can cut across non-grass areas like a
// driveway when the mower's route connects two mowing zones). Returns an
// SVG path `d` string built from many disconnected M/L segments -- one per
// boundary edge, exactly mirroring the ctx.moveTo/lineTo pairs the canvas
// version draws -- which is not a single closed loop, but reads as one
// when stroked with round joins/caps because adjacent edges share endpoints.
function buildRasterBoundaryPathD(raster, rasterBounds, worldToScreen) {
  const width = Number(raster?.width);
  const height = Number(raster?.height);
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    return null;
  }
  const pixels = decodeRasterSolidMask(raster, width, height);
  if (!pixels) return null;

  const minX = Number(rasterBounds?.min_x ?? rasterBounds?.minX);
  const maxX = Number(rasterBounds?.max_x ?? rasterBounds?.maxX);
  const minY = Number(rasterBounds?.min_y ?? rasterBounds?.minY);
  const maxY = Number(rasterBounds?.max_y ?? rasterBounds?.maxY);
  if (![minX, maxX, minY, maxY].every(Number.isFinite)) return null;

  const stepX = (maxX - minX) / width;
  const stepY = (maxY - minY) / height;
  if (!Number.isFinite(stepX) || !Number.isFinite(stepY) || stepX === 0 || stepY === 0) {
    return null;
  }

  const isSolid = (x, y) => x >= 0 && x < width && y >= 0 && y < height && pixels[y * width + x] !== 0;
  const toScreen = (x, y) => worldToScreen({ x: minX + x * stepX, y: minY + y * stepY });

  const segments = [];
  const addEdge = (x1, y1, x2, y2) => {
    const start = toScreen(x1, y1);
    const end = toScreen(x2, y2);
    segments.push(`M${start.x},${start.y} L${end.x},${end.y}`);
  };

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (!isSolid(x, y)) continue;
      if (!isSolid(x - 1, y)) addEdge(x, y, x, y + 1);
      if (!isSolid(x + 1, y)) addEdge(x + 1, y, x + 1, y + 1);
      if (!isSolid(x, y - 1)) addEdge(x, y, x + 1, y);
      if (!isSolid(x, y + 1)) addEdge(x, y + 1, x + 1, y + 1);
    }
  }

  return segments.length ? segments.join(" ") : null;
}

// Compose the live map's separate decoded-boundary adjustment with the
// geometry's normal world-to-screen projection.
function worldToScreenWithExtraCalibration(geometry, calibration, point) {
  const mapPoint = geometry.worldToMap(point);
  return geometry.mapToScreenWithLayerCalibration(mapPoint, calibration);
}

// Draws a simple schematic (not necessarily oriented like the live map) of
// the zone polygons an "area" file describes, reusing the same zone/vertex
// parsing the live map overlay uses (getZones/getZonePoints from geometry.js)
// so it recognizes the same field-name variants.
function renderMowingRecordZonesSvg(
  areaDefinition,
  pathPoints = [],
  mowedZoneInfo = null,
  {
    backgroundImage = null,
    calibration = null,
    decodedBoundaryCalibration = null,
    bounds: resolvedBounds = null,
    boundaryRaster = null,
    boundaryPaths = null,
    canvasSize = null,
    fit = "cover",
    rotation = 0,
  } = {}
) {
  const zones = getZones(areaDefinition, ["custom_areas", "zones", "customAreas", "ridable_areas"]);
  const zonePolygons = zones
    .map((zone) => ({ zone, points: getZonePoints(zone) }))
    .filter((entry) => entry.points.length >= 3);
  if (!zonePolygons.length) return null;

  // Mirrors renderer.js's draw() precisely, not just "the same calibration
  // values": the live map (1) computes its world bounds from the property's
  // CURRENT live boundary/zone/raster data (falling back to an explicit
  // config.bounds override when the caller set one) -- NOT from whatever
  // this particular historical record's own `area_url` snapshot happens to
  // contain, which can differ just enough to visibly mis-scale things; the
  // caller (openMowingRecordDetail) already resolves that and passes the
  // final `bounds` in, (2) fits BOTH its image geometry and its zone/path
  // geometry to the *photo's own* aspect ratio (not the raw world aspect
  // ratio), and (3) draws the background photo with an UNCALIBRATED
  // geometry (calibration: {}) while drawing zones/path with the
  // CALIBRATED one -- the photo is the fixed reference frame; calibration
  // is how the robot's own (possibly offset/rotated/scaled) coordinate
  // system gets nudged to line up with it.
  const bounds = resolvedBounds || getWorldBounds(areaDefinition, null);
  const sourceWidth = Number(backgroundImage?.naturalWidth || backgroundImage?.width) || 0;
  const sourceHeight = Number(backgroundImage?.naturalHeight || backgroundImage?.height) || 0;
  const hasImage = Boolean(backgroundImage && sourceWidth > 0 && sourceHeight > 0);
  const photoRatio = hasImage ? sourceWidth / sourceHeight : undefined;

  // Attila: the zones/coverage still read "too tall" vertically vs. the
  // live map even with matching bounds/calibration. Root cause: the live
  // map's "map" rect is fit against the live CANVAS's own actual pixel
  // width/height (whatever the card's on-screen box happens to be) using
  // its configured `fit` ("cover" by default -- crops/zooms rather than
  // showing the world uncropped when the container's aspect ratio doesn't
  // match the photo's). The popup was instead sizing its own SVG canvas to
  // exactly match the photo's aspect ratio with zero letterboxing by
  // construction -- a DIFFERENT fit, so even identical bounds/calibration
  // produced a differently zoomed/cropped picture. When the caller can
  // supply the live renderer's actual current canvas size, reuse it (and
  // its `fit` mode) directly so the popup reproduces the exact same "map"
  // rect the live view uses; only fall back to a synthetic, letterbox-free
  // size (photo's own aspect ratio, "contain") when that isn't available.
  let size;
  let fitMode;
  if (canvasSize && canvasSize.width > 0 && canvasSize.height > 0) {
    size = { width: canvasSize.width, height: canvasSize.height };
    fitMode = fit || "cover";
  } else {
    const rawWorldRatio = (bounds.maxX - bounds.minX) / (bounds.maxY - bounds.minY);
    const worldRatio = Number.isFinite(rawWorldRatio) && rawWorldRatio > 0 ? rawWorldRatio : 1;
    const fitRatio = Number.isFinite(photoRatio) && photoRatio > 0 ? photoRatio : worldRatio;
    size = { width: 1000, height: Math.max(1, 1000 / fitRatio) };
    fitMode = "contain";
  }
  const view = { rotation: Number(rotation) || 0 };
  const geometryOptions = { bounds, width: size.width, height: size.height, view, aspectRatio: photoRatio, fit: fitMode };
  const baseGeometry = createGeometry({ ...geometryOptions, calibration: {} });
  const geometry = createGeometry({ ...geometryOptions, calibration });
  const project = (point) => geometry.worldToScreen(point);

  // Styling mirrors the real app's own history-detail screen (reference
  // screenshot, 2026-08-21): every zone rectangle gets the same plain pale
  // frame, and the actual mowed *coverage* (the clipped path swath drawn
  // per zone below) is what visually shows what got mowed -- not a flat
  // solid fill on the whole rectangle.
  const MOWED_STROKE = "#4d4ed6";
  const NEUTRAL_FILL = "#8b8fdb";
  const NEUTRAL_STROKE = "#9598e0";
  // Attila: the dimension text ("15.3m x 11.7m") was reading as too
  // dominant over the photo -- shrunk noticeably smaller than the zone
  // name label, instead of the previous 0.8x-of-name ratio.
  const fontSize = Math.max(size.width, size.height) * 0.026;
  const dimsFontSize = Math.max(size.width, size.height) * 0.013;
  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

  // Same garden photo the live map card underlays behind the boundary/zones
  // (config.image), placed with the exact same affine fit the live map
  // renderer uses (renderer.js's drawImageOnMap/drawImageToScreenRect): the
  // image's unit-square corners (0,0)-(1,0)-(0,1) run through the
  // UNCALIBRATED baseGeometry.mapToScreen (see comment above), and the
  // resulting 2x3 affine is reproduced here as an SVG matrix transform
  // instead of a canvas setTransform.
  if (hasImage) {
    const topLeft = baseGeometry.mapToScreen({ x: 0, y: 0 });
    const topRight = baseGeometry.mapToScreen({ x: 1, y: 0 });
    const bottomLeft = baseGeometry.mapToScreen({ x: 0, y: 1 });
    const a = (topRight.x - topLeft.x) / sourceWidth;
    const b = (topRight.y - topLeft.y) / sourceWidth;
    const c = (bottomLeft.x - topLeft.x) / sourceHeight;
    const d = (bottomLeft.y - topLeft.y) / sourceHeight;

    const bgImage = document.createElementNS(svgNs, "image");
    bgImage.setAttributeNS("http://www.w3.org/1999/xlink", "href", backgroundImage.src);
    bgImage.setAttribute("href", backgroundImage.src);
    bgImage.setAttribute("x", "0");
    bgImage.setAttribute("y", "0");
    bgImage.setAttribute("width", String(sourceWidth));
    bgImage.setAttribute("height", String(sourceHeight));
    bgImage.setAttribute("preserveAspectRatio", "none");
    bgImage.setAttribute("opacity", "0.6");
    bgImage.setAttribute("transform", `matrix(${a} ${b} ${c} ${d} ${topLeft.x} ${topLeft.y})`);
    svg.appendChild(bgImage);
  }

  // Reference screenshot (the real app's own history-detail screen,
  // 2026-08-21) doesn't fill the whole zone RECTANGLE solid when it was
  // mowed -- it draws the real, irregular coverage silhouette (following
  // actual lawn edges/obstacles) inside the rectangle, and leaves the
  // rectangle itself as a plain pale reference frame for every zone,
  // mowed or not. We don't have a true coverage polygon, but the mowed
  // *path* (already decoded) traces that same irregular shape -- drawing
  // it as thick, near-solid, round-capped strokes (instead of the earlier
  // thin translucent lines that read as generic clutter) approximates it
  // closely, and clipping those strokes to each zone's own polygon (via an
  // SVG <clipPath>) keeps a session's coverage from bleeding into a
  // neighboring zone the same way the real app's per-zone silhouette does.
  const defs = document.createElementNS(svgNs, "defs");
  svg.appendChild(defs);
  const coverageSegments = pathPoints.length ? buildDetailPathSegments(pathPoints, DETAIL_PATH_JUMP_LIMIT_MM) : [];
  // Approximate cutting width of the mower, in world mm -- unconfirmed
  // against real device specs, chosen to visually read as a filled
  // coverage swath (like the reference screenshot) rather than thin
  // stripes when consecutive passes overlap.
  const MOWER_WIDTH_MM = 300;
  const pxPerMm = geometry.map.width / Math.max(1, bounds.maxX - bounds.minX);
  const coverageStrokeWidth = Math.max(2, MOWER_WIDTH_MM * pxPerMm);

  zonePolygons.forEach(({ zone, points }, zoneIndex) => {
    const name = zone?.name || zone?.label;
    const normalizedName = name ? String(name).trim().toLowerCase() : "";
    const matched = mowedZoneInfo?.get(normalizedName) || null;
    const screenPoints = points.map(project);

    const poly = document.createElementNS(svgNs, "polygon");
    poly.setAttribute("points", screenPoints.map((p) => `${p.x},${p.y}`).join(" "));
    poly.setAttribute("fill", NEUTRAL_FILL);
    poly.setAttribute("fill-opacity", "0.14");
    poly.setAttribute("stroke", NEUTRAL_STROKE);
    poly.setAttribute("stroke-width", String(Math.max(size.width, size.height) * 0.004));
    svg.appendChild(poly);

    if (coverageSegments.length) {
      const clipId = `mowing-zone-clip-${zoneIndex}`;
      const clipPath = document.createElementNS(svgNs, "clipPath");
      clipPath.setAttribute("id", clipId);
      const clipPoly = document.createElementNS(svgNs, "polygon");
      clipPoly.setAttribute("points", screenPoints.map((p) => `${p.x},${p.y}`).join(" "));
      clipPath.appendChild(clipPoly);
      defs.appendChild(clipPath);

      const coverageGroup = document.createElementNS(svgNs, "g");
      coverageGroup.setAttribute("clip-path", `url(#${clipId})`);
      for (const segment of coverageSegments) {
        const line = document.createElementNS(svgNs, "polyline");
        line.setAttribute(
          "points",
          segment
            .map((p) => {
              const s = project(p);
              return `${s.x},${s.y}`;
            })
            .join(" ")
        );
        line.setAttribute("fill", "none");
        line.setAttribute("stroke", MOWED_STROKE);
        line.setAttribute("stroke-opacity", "0.92");
        line.setAttribute("stroke-width", String(coverageStrokeWidth));
        line.setAttribute("stroke-linecap", "round");
        line.setAttribute("stroke-linejoin", "round");
        coverageGroup.appendChild(line);
      }
      svg.appendChild(coverageGroup);
    }

    if (name) {
      let cx = 0, cy = 0;
      for (const p of screenPoints) { cx += p.x; cy += p.y; }
      cx /= screenPoints.length;
      cy /= screenPoints.length;

      // Dimensions: prefer the record's own reported width x height for a
      // zone it actually mowed (confirmed correct against the app in an
      // earlier round); otherwise fall back to this zone polygon's own
      // world-mm bounding box (unconfirmed for zones outside a record's
      // zone_list).
      let dims = matched?.dims || "";
      if (!dims && points.length >= 3) {
        let zMinX = Infinity, zMinY = Infinity, zMaxX = -Infinity, zMaxY = -Infinity;
        for (const p of points) {
          if (p.x < zMinX) zMinX = p.x;
          if (p.x > zMaxX) zMaxX = p.x;
          if (p.y < zMinY) zMinY = p.y;
          if (p.y > zMaxY) zMaxY = p.y;
        }
        if ([zMinX, zMinY, zMaxX, zMaxY].every(Number.isFinite)) {
          dims = `${((zMaxX - zMinX) / 1000).toFixed(1)}m × ${((zMaxY - zMinY) / 1000).toFixed(1)}m`;
        }
      }

      // A dark outline keeps the label legible over the (optional) photo
      // background, whose brightness varies -- plain white fill alone can
      // wash out over light patches of the image.
      const textOutline = String(Math.max(size.width, size.height) * 0.0025);

      const nameText = document.createElementNS(svgNs, "text");
      nameText.setAttribute("x", String(cx));
      nameText.setAttribute("y", String(cy - fontSize * 0.35));
      nameText.setAttribute("text-anchor", "middle");
      nameText.setAttribute("font-size", String(fontSize));
      nameText.setAttribute("font-weight", "600");
      nameText.setAttribute("fill", "#ffffff");
      nameText.setAttribute("stroke", "rgba(0,0,0,0.65)");
      nameText.setAttribute("stroke-width", textOutline);
      nameText.setAttribute("paint-order", "stroke");
      nameText.textContent = String(name);
      svg.appendChild(nameText);

      if (dims) {
        const dimsText = document.createElementNS(svgNs, "text");
        dimsText.setAttribute("x", String(cx));
        dimsText.setAttribute("y", String(cy + fontSize * 0.7));
        dimsText.setAttribute("text-anchor", "middle");
        dimsText.setAttribute("font-size", String(dimsFontSize));
        dimsText.setAttribute("fill", "rgba(255,255,255,0.85)");
        dimsText.setAttribute("stroke", "rgba(0,0,0,0.65)");
        dimsText.setAttribute("stroke-width", textOutline);
        dimsText.setAttribute("paint-order", "stroke");
        dimsText.textContent = dims;
        svg.appendChild(dimsText);
      }
    }
  });

  // Attila: "a no-go zone nincs rajta" -- the popup was only ever reading
  // the mowable-zone keys (custom_areas/zones/customAreas/ridable_areas);
  // it never looked at the forbidden/no-go-area keys at all, so those
  // zones were silently missing here even though the live map always
  // draws them (renderer.js's draw(): drawZones(..., "zone") immediately
  // followed by drawZones(..., "no-go"), same geometry, right before the
  // boundary/mowed-path layers -- mirrored here in the same order/style:
  // solid red fill+stroke, label falls back to "No-go" for an unnamed or
  // generically-named ("Zone 1") zone, same as zoneLabel() in renderer.js).
  const noGoZones = getZones(areaDefinition, [
    "forbid_areas",
    "forbidAreas",
    "remote_forbid_areas",
    "remoteForbidAreas",
    "no_go_areas",
    "noGoAreas",
  ]);
  const noGoPolygons = noGoZones
    .map((zone) => ({ zone, points: getZonePoints(zone) }))
    .filter((entry) => entry.points.length >= 3);
  const NO_GO_FILL = "rgba(244, 67, 54, 0.38)";
  const NO_GO_STROKE = "rgba(255, 82, 82, 1)";
  noGoPolygons.forEach(({ zone, points }) => {
    const screenPoints = points.map(project);
    const poly = document.createElementNS(svgNs, "polygon");
    poly.setAttribute("points", screenPoints.map((p) => `${p.x},${p.y}`).join(" "));
    poly.setAttribute("fill", NO_GO_FILL);
    poly.setAttribute("stroke", NO_GO_STROKE);
    poly.setAttribute("stroke-width", String(Math.max(size.width, size.height) * 0.004));
    svg.appendChild(poly);

    const rawName = zone?.name || zone?.label;
    const label = rawName && !/^zone\s*\d+$/i.test(String(rawName)) ? String(rawName) : "No-go";
    let cx = 0, cy = 0;
    for (const p of screenPoints) { cx += p.x; cy += p.y; }
    cx /= screenPoints.length;
    cy /= screenPoints.length;
    const textOutline = String(Math.max(size.width, size.height) * 0.0025);
    const labelText = document.createElementNS(svgNs, "text");
    labelText.setAttribute("x", String(cx));
    labelText.setAttribute("y", String(cy));
    labelText.setAttribute("text-anchor", "middle");
    labelText.setAttribute("font-size", String(fontSize * 0.8));
    labelText.setAttribute("font-weight", "600");
    labelText.setAttribute("fill", "#ffffff");
    labelText.setAttribute("stroke", "rgba(0,0,0,0.65)");
    labelText.setAttribute("stroke-width", textOutline);
    labelText.setAttribute("paint-order", "stroke");
    labelText.textContent = label;
    svg.appendChild(labelText);
  });

  // Attila asked for the lawn's own boundary outline to be visible too
  // (previously only the zone rectangles were drawn), then pointed out the
  // first attempt (getBoundaryPaths()'s map_binary_paths -- the raw
  // wire-perimeter/travel route) cut straight across the driveway, since
  // that's the "legacy boundary" the live map itself only shows when
  // explicitly turned on. What the live map shows BY DEFAULT is a
  // pixel-traced outline of the map_raster mask -- the real mapped-lawn
  // silhouette -- so that's preferred here too, with the vector paths kept
  // only as a fallback when no usable raster is available. Either way,
  // drawn twice -- a thicker, translucent "glow" underneath, then a solid
  // line on top -- and drawn last (on top of the zone fills) to match the
  // live map's own draw order (zones, then boundary, then mowed path).
  const boundaryWidth = Math.max(size.width, size.height) * 0.006;
  const boundaryGlowWidth = boundaryWidth * 2.2;
  const strokeBoundaryPathD = (pathD) => {
    const glow = document.createElementNS(svgNs, "path");
    glow.setAttribute("d", pathD);
    glow.setAttribute("fill", "none");
    glow.setAttribute("stroke", "rgba(168, 179, 255, 0.38)");
    glow.setAttribute("stroke-width", String(boundaryGlowWidth));
    glow.setAttribute("stroke-linecap", "round");
    glow.setAttribute("stroke-linejoin", "round");
    svg.appendChild(glow);

    const solid = document.createElementNS(svgNs, "path");
    solid.setAttribute("d", pathD);
    solid.setAttribute("fill", "none");
    solid.setAttribute("stroke", "rgba(74, 101, 255, 0.9)");
    solid.setAttribute("stroke-width", String(boundaryWidth));
    solid.setAttribute("stroke-linecap", "round");
    solid.setAttribute("stroke-linejoin", "round");
    svg.appendChild(solid);
  };

  const rasterBoundaryD =
    boundaryRaster && boundaryRaster.bounds
      ? buildRasterBoundaryPathD(boundaryRaster, boundaryRaster.bounds, (point) =>
          worldToScreenWithExtraCalibration(geometry, decodedBoundaryCalibration, point)
        )
      : null;

  if (rasterBoundaryD) {
    strokeBoundaryPathD(rasterBoundaryD);
  } else if (Array.isArray(boundaryPaths) && boundaryPaths.length) {
    for (const path of boundaryPaths) {
      if (!Array.isArray(path) || path.length < 2) continue;
      const screenPoints = path.map(project);
      const closedD = `M${screenPoints.map((p) => `${p.x},${p.y}`).join(" L")} Z`;
      strokeBoundaryPathD(closedD);
    }
  }

  return svg;
}

function formatRecordArea(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return `${Math.round(num * 10) / 10} m²`;
}

function formatRecordNumber(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return String(Math.round(num * 10) / 10);
}

function formatRecordPercent(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return null;
  const pct = num > 0 && num <= 1 ? num * 100 : num;
  return `${Math.round(pct * 10) / 10}%`;
}

function formatRecordDurationSeconds(totalSeconds) {
  const total = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes} min`;
}

// The confirmed Anthbot mow_time field is expressed in seconds. Explicit
// millisecond aliases are converted by field name; magnitude is deliberately
// not used because a valid large-property mowing session can exceed 20,000 s.
function normalizeRecordDurationSeconds(rawDuration, sourceKey = "") {
  if (rawDuration === undefined || rawDuration === null || rawDuration === "") return null;
  const rawNum = Number(rawDuration);
  if (Number.isNaN(rawNum)) return null;
  return /(?:_ms|Ms)$/.test(String(sourceKey)) ? rawNum / 1000 : rawNum;
}

// Attila: the real app shows a "start - end" range for every history entry
// (e.g. "2026-08-09 13:53 - 2026-08-19 14:37"), but the cloud record itself
// only ever carries an end timestamp (`finish_time`) -- there is no
// start_time/begin_time field in the confirmed real response (see the
// MOWING_RECORD_START_KEYS alias list, which was written defensively before
// a populated history existed and has simply never matched anything real).
// What the record DOES carry is the session's duration (`mow_time`, in
// seconds), so the start can be reconstructed as end minus duration -- the
// same arithmetic the app itself must be doing to show that range. Falls
// back to whatever an actual start-time alias resolves to, if the cloud
// ever does start sending one, so this doesn't fight a real field later.
function resolveMowingRecordTimeRange(record) {
  const end = parseRecordTimestamp(pickRecordValue(record, MOWING_RECORD_END_KEYS));
  let start = parseRecordTimestamp(pickRecordValue(record, MOWING_RECORD_START_KEYS));
  if (!start && end) {
    const durationEntry = pickRecordEntry(record, MOWING_RECORD_DURATION_KEYS);
    const durationSeconds = normalizeRecordDurationSeconds(durationEntry?.value, durationEntry?.key);
    if (durationSeconds !== null && durationSeconds > 0) {
      start = new Date(end.getTime() - durationSeconds * 1000);
    }
  }
  return { start, end };
}

if (!customElements.get("anthbot-map-card")) {
  customElements.define("anthbot-map-card", AnthbotMapCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "anthbot-map-card")) {
  window.customCards.push({
    type: "anthbot-map-card",
    name: "Anthbot Map Card",
    description: "Canvas map display and controls for Anthbot map sensors",
  });
}










function showAnthbotCommandToast(message) {
  const id = "anthbot-command-feedback-global";
  document.getElementById(id)?.remove();
  const toast = document.createElement("div");
  toast.id = id;
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "assertive");
  toast.textContent = String(message || "");
  Object.assign(toast.style, {
    position: "fixed",
    zIndex: "2147483647",
    top: "70px",
    left: "50%",
    transform: "translateX(-50%)",
    width: "max-content",
    maxWidth: "calc(100vw - 24px)",
    boxSizing: "border-box",
    padding: "9px 14px",
    border: "1px solid rgba(255,255,255,.45)",
    borderRadius: "10px",
    background: "rgba(2, 119, 189, .92)",
    color: "#fff",
    boxShadow: "0 5px 18px rgba(0,0,0,.32)",
    font: "700 14px sans-serif",
    textAlign: "center",
    pointerEvents: "none",
  });
  document.body.appendChild(toast);
  window.setTimeout(() => {
    if (document.getElementById(id) === toast) toast.remove();
  }, 8000);
}

function anthbotFeedbackLanguage(card, hass) {
  return card?.language
    || resolveLanguage(card?.selectedLanguage || card?.config?.language || "auto", hass);
}

function anthbotFeedback(card, hass, key, command) {
  return translate(anthbotFeedbackLanguage(card, hass), key)
    .replaceAll("{command}", String(command || ""));
}

function anthbotCommandLabel(card, hass, command, control) {
  const language = anthbotFeedbackLanguage(card, hass);
  if (command === "zone") {
    const visibleLabel = String(control?.textContent || "").trim();
    return visibleLabel || translate(language, "zoneStart");
  }
  const key = ({
    start: "startLabel",
    stop: "stopLabel",
    dock: "homeLabel",
    "outer-edge": "commandOuterEdge",
    "dock-edge": "commandDockEdge",
    pause: "pauseTask",
    resume: "resumeTask",
  })[command];
  return key ? translate(language, key) : String(command || translate(language, "control"));
}

function anthbotStandaloneCommandIsConfirmed(hass, service) {
  const currentHass = hass
    || document.querySelector("home-assistant")?.hass
    || document.querySelector("home-assistant")?._hass;
  const normalize = (value) => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
  const values = [];
  for (const [entityId, entity] of Object.entries(currentHass?.states || {})) {
    if (
      entity?.state === "unavailable"
      || !(
        entityId.startsWith("lawn_mower.")
        || entityId.includes("mower_status")
        || entityId.includes("robot_status")
        || entityId.includes("anthbot") && entityId.endsWith("_map")
      )
    ) continue;
    values.push(
      entity.state,
      entity.attributes?.mower_status,
      entity.attributes?.robot_status_raw,
      entity.attributes?.robot_sta?.value,
    );
  }
  const collectVisibleStatuses = (root, output = []) => {
    if (!root?.querySelectorAll) return output;
    root.querySelectorAll(
      '[data-role="mower-status"], [data-role="state"], .status-copy strong'
    ).forEach((element) => output.push(element.textContent));
    root.querySelectorAll("*").forEach((element) => {
      if (element.shadowRoot) collectVisibleStatuses(element.shadowRoot, output);
    });
    return output;
  };
  values.push(...collectVisibleStatuses(document));
  const statuses = values.map(normalize).filter(Boolean);
  const expected = ({
    start_full_mow: ["mowing", "globalmowing", "working", "cutting", "nyiras", "funyiras"],
    start_zone_mow: ["mowing", "zonemowing", "regionmowing", "working", "cutting", "nyiras", "funyiras", "zonanyiras"],
    start_outer_edge_mow: ["mowing", "bordermowing", "edgemowing", "edgecutting", "working", "szegelynyiras"],
    start_dock_edge_mow: ["mowing", "nestmowing", "working", "tolto", "kornyekeneknyirasa"],
    stop_mow: ["paused", "pause", "standby", "idle", "charging", "charge", "docked", "szunetel", "keszenlet", "toltes", "dokkolva"],
    pause_mow: ["paused", "pause", "szunetel", "szuneteltetve"],
    resume_mow: ["mowing", "globalmowing", "zonemowing", "regionmowing", "working", "cutting", "nyiras", "funyiras"],
    return_to_dock: ["returning", "backtodock", "returntodock", "docking", "charging", "charge", "docked", "visszaatoltore", "toltes", "dokkolva"],
  })[service] || [];
  return statuses.some((status) => expected.some((value) => status.includes(value)));
}

async function waitForAnthbotVisibleConfirmation(card, hass, service, label) {
  const token = (window.__anthbotVisibleConfirmationToken || 0) + 1;
  window.__anthbotVisibleConfirmationToken = token;
  const deadline = Date.now() + 20000;
  while (window.__anthbotVisibleConfirmationToken === token && Date.now() < deadline) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    try {
      const cardConfirmed = typeof card?.commandIsConfirmed === "function"
        && card.commandIsConfirmed(service);
      if (cardConfirmed || anthbotStandaloneCommandIsConfirmed(hass, service)) {
        showAnthbotCommandToast(anthbotFeedback(card, hass, "commandConfirmed", label));
        return;
      }
    } catch {
      // A transient entity update must not interrupt the confirmation retry loop.
    }
  }
  if (window.__anthbotVisibleConfirmationToken === token) {
    showAnthbotCommandToast(anthbotFeedback(card, hass, "commandNotConfirmed", label));
  }
}

function installAnthbotCloudFeedback(hass) {
  if (!hass?.callService || hass.__anthbotCloudFeedbackInstalled) return;
  const originalCallService = hass.callService.bind(hass);
  hass.__anthbotCloudFeedbackInstalled = true;
  hass.callService = async (domain, service, data, target) => {
    const pending = window.__anthbotPendingCommand;
    const isRecent = pending && Date.now() - pending.createdAt < 8000;
    const isAnthbotCall = (
      ["anthbot_map", "anthbot_genie_plus", "anthbot_ha"].includes(domain)
      || (
        domain === "button"
        && service === "press"
        && String(data?.entity_id || target?.entity_id || "").includes("anthbot")
      )
    );
    try {
      const result = await originalCallService(domain, service, data, target);
      if (isRecent && isAnthbotCall && window.__anthbotPendingCommand?.token === pending.token) {
        showAnthbotCommandToast(anthbotFeedback(pending.card, hass, "commandCloudAccepted", pending.label));
        window.__anthbotPendingCommand = null;
        void waitForAnthbotVisibleConfirmation(
          pending.card,
          hass,
          pending.expectedService,
          pending.label,
        );
      }
      return result;
    } catch (error) {
      if (isRecent && isAnthbotCall && window.__anthbotPendingCommand?.token === pending.token) {
        showAnthbotCommandToast(anthbotFeedback(pending.card, hass, "commandCloudRejected", pending.label));
        window.__anthbotPendingCommand = null;
      }
      throw error;
    }
  };
}

function findAnthbotCommandTarget(hass, command, control, config = {}) {
  const configured = config?.controls?.[command];
  if (configured && hass?.states?.[configured]?.state !== "unavailable") return configured;
  const suffixes = ({
    start: ["start_full_mow"],
    stop: ["stop_mow"],
    dock: ["return_to_dock"],
    "outer-edge": ["start_outer_edge_mow"],
    "dock-edge": ["mow_around_charging_dock", "start_dock_edge_mow"],
    pause: ["pause_mow"],
    resume: ["resume_mow"],
    "reset-blade": ["reset_blade_maintenance"],
    "reset-camera": ["reset_camera_maintenance"],
    "reset-contact": ["reset_dock_contact_maintenance"],
  })[command] || [];
  const zoneNumber = String(control?.textContent || "").match(/\d+/)?.[0];
  const candidates = Object.entries(hass?.states || {})
    .filter(([entityId, state]) => {
      if (!entityId.startsWith("button.") || state?.state === "unavailable") return false;
      if (command === "zone") {
        const text = `${entityId} ${state?.attributes?.friendly_name || ""}`.toLowerCase();
        return Boolean(zoneNumber) && text.includes("zone") && new RegExp(`(?:_|\\s)${zoneNumber}(?:_|\\s|$)`).test(text);
      }
      return suffixes.some((suffix) =>
        entityId.includes(`_${suffix}`)
        || String(state?.attributes?.friendly_name || "").toLowerCase().includes(suffix.replaceAll("_", " "))
      );
    })
    .sort(([left], [right]) => {
      const leftNumber = Number(left.match(/_(\d+)$/)?.[1] || 0);
      const rightNumber = Number(right.match(/_(\d+)$/)?.[1] || 0);
      return rightNumber - leftNumber;
    });
  return candidates[0]?.[0] || null;
}

async function executeAnthbotCommand(hass, card, command, details, control, config) {
  const mapEntity = card?._activeEntityId || card?.config?.entity || config?.entity || "default";
  let entityId = findAnthbotCommandTarget(hass, command, control, config);
  if (command === "resume") {
    const savedTask = hass?.states?.[mapEntity]?.attributes?.last_mowing_task;
    if (!savedTask?.type) {
      showAnthbotCommandToast(
        translate(anthbotFeedbackLanguage(card, hass), "noTaskToResume")
      );
      return;
    }
  }
  try {
    if (entityId) {
      await hass.callService("button", "press", { entity_id: entityId });
    } else {
      const domain = ["anthbot_map", "anthbot_genie_plus", "anthbot_ha"]
        .find((name) => hass?.services?.[name]?.[details[1]]);
      const mapEntity = Object.entries(hass?.states || {})
        .find(([id, state]) =>
          id.startsWith("sensor.")
          && id.includes("anthbot")
          && /_map(?:_\d+)?$/.test(id)
          && state?.state !== "unavailable"
        )?.[0];
      if (!domain || !details[1]) throw new Error("No active Anthbot command target");
      await hass.callService(domain, details[1], mapEntity ? { entity_id: mapEntity } : {});
    }
    showAnthbotCommandToast(anthbotFeedback(card, hass, "commandCloudAccepted", details[0]));
    void waitForAnthbotVisibleConfirmation(card, hass, details[1], details[0]);
  } catch (error) {
    console.error("Anthbot command failed", error);
    showAnthbotCommandToast(anthbotFeedback(card, hass, "commandCloudRejected", details[0]));
  }
}

if (window.__anthbotFeedbackClickHandler) {
  document.removeEventListener("click", window.__anthbotFeedbackClickHandler, true);
}
window.__anthbotFeedbackClickHandler = (event) => {
    const path = typeof event.composedPath === "function" ? event.composedPath() : [];
    const card = path.find((item) => item?.tagName === "ANTHBOT-MAP-CARD");
    if (!card) return;
    const control = path.find((item) =>
      item instanceof HTMLElement
      && (
        item.matches?.("button[data-command]")
        || item.matches?.(".command-tile")
        || item.matches?.(".zone-tile")
        || (item.matches?.("button") && path.some((parent) => parent?.dataset?.role === "zone-controls"))
        || item.matches?.("[data-zone-id]")
      )
    );
    if (!control) return;
    // This command depends on the selected mowing target (full, edge or zones).
    // Let the tile's handlePrimaryMowingAction() listener dispatch it.
    if (control.matches?.("[data-primary-mowing-action]")) return;
    const hassHost = path.find((item) => item?._hass?.states || item?.hass?.states);
    const hass = hassHost?._hass
      || hassHost?.hass
      || card?._hass
      || document.querySelector("home-assistant")?.hass
      || document.querySelector("home-assistant")?._hass;
    const classCommand = [
      "start", "stop", "dock", "outer-edge", "dock-edge", "pause", "resume", "reset-blade", "reset-camera", "reset-contact",
    ].find((name) => control.classList?.contains(name));
    const command = control.dataset?.command || classCommand || "zone";
    const configHost = path.find((item) => item?.config?.button_actions || item?._config?.button_actions);
    const config = configHost?.config || configHost?._config || card?.config || {};
    const customAction = typeof card?.effectiveCustomButtonAction === "function"
      ? card.effectiveCustomButtonAction(command)
      : (config.button_actions?.[command] || config.buttonActions?.[command]);
    if (customAction) {
      // Let the card's own click listener run callCustomButtonAction(). The
      // document-level feedback handler must not replace configured actions.
      return;
    }
    const details = [anthbotCommandLabel(card, hass, command, control), ({
      start: "start_full_mow",
      stop: "stop_mow",
      dock: "return_to_dock",
      "outer-edge": "start_outer_edge_mow",
      "dock-edge": "start_dock_edge_mow",
      pause: "pause_mow",
      resume: "resume_mow",
      "reset-blade": "reset_blade_maintenance",
      "reset-camera": "reset_camera_maintenance",
      "reset-contact": "reset_dock_contact_maintenance",
      zone: "start_zone_mow",
    })[command] || null];
    if (!hass?.callService) {
      showAnthbotCommandToast(anthbotFeedback(card, hass, "commandFailed", details[0]));
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    showAnthbotCommandToast(anthbotFeedback(card, hass, "commandSentWaiting", details[0]));
    void executeAnthbotCommand(hass, card, command, details, control, config);
};
document.addEventListener("click", window.__anthbotFeedbackClickHandler, true);
