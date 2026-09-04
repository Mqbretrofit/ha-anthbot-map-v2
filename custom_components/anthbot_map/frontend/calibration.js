export const DEFAULT_CALIBRATION = Object.freeze({
  offsetX: 0,
  offsetY: 0,
  scaleX: 1,
  scaleY: 1,
  rotation: 0,
});

export function readCalibration(config = {}) {
  return {
    ...DEFAULT_CALIBRATION,
    ...(config.calibration || {}),
  };
}

export function readRobotCalibration(config = {}) {
  return {
    ...DEFAULT_CALIBRATION,
    ...(config.robotCalibration || {}),
  };
}

export function readMowingPathCalibration(config = {}) {
  const configured = config.mowingPathCalibration || config.mowing_path_calibration;
  if (configured && typeof configured === "object") {
    return {
      ...DEFAULT_CALIBRATION,
      ...configured,
    };
  }

  // Legacy robotCalibration offsets moved the path, while scale and rotation
  // adjusted the icon. Preserve those meanings for existing card YAML.
  const legacy = config.robotCalibration || {};
  return {
    ...DEFAULT_CALIBRATION,
    offsetX: Number(legacy.offsetX) || 0,
    offsetY: Number(legacy.offsetY) || 0,
  };
}

export function readDecodedBoundaryCalibration(config = {}) {
  return {
    ...DEFAULT_CALIBRATION,
    ...(config.decodedBoundaryCalibration || config.decoded_boundary_calibration || {}),
  };
}

export function resetCalibration() {
  return { ...DEFAULT_CALIBRATION };
}

export function adjustCalibration(calibration, action, amount = 1) {
  const next = { ...DEFAULT_CALIBRATION, ...(calibration || {}) };
  const move = 0.01 * amount;
  const scale = 0.02 * amount;
  const rotate = (Math.PI / 180) * amount;
  const rotateLarge = (Math.PI / 12) * amount;

  switch (action) {
    case "left":
      next.offsetX -= move;
      break;
    case "right":
      next.offsetX += move;
      break;
    case "up":
      next.offsetY -= move;
      break;
    case "down":
      next.offsetY += move;
      break;
    case "wider":
      next.scaleX += scale;
      break;
    case "narrower":
      next.scaleX = Math.max(0.1, next.scaleX - scale);
      break;
    case "taller":
      next.scaleY += scale;
      break;
    case "shorter":
      next.scaleY = Math.max(0.1, next.scaleY - scale);
      break;
    case "rotate-left":
      next.rotation -= rotate;
      break;
    case "rotate-right":
      next.rotation += rotate;
      break;
    case "rotate-left-large":
      next.rotation -= rotateLarge;
      break;
    case "rotate-right-large":
      next.rotation += rotateLarge;
      break;
    case "rotate-around":
      next.rotation += Math.PI;
      break;
    default:
      break;
  }

  return next;
}

export function calibrationToYaml(calibration) {
  const next = { ...DEFAULT_CALIBRATION, ...(calibration || {}) };

  return [
    "calibration:",
    `  offsetX: ${formatNumber(next.offsetX)}`,
    `  offsetY: ${formatNumber(next.offsetY)}`,
    `  scaleX: ${formatNumber(next.scaleX)}`,
    `  scaleY: ${formatNumber(next.scaleY)}`,
    `  rotation: ${formatNumber(next.rotation)}`,
  ].join("\n");
}

export function robotCalibrationToYaml(robotCalibration) {
  const next = { ...DEFAULT_CALIBRATION, ...(robotCalibration || {}) };

  return [
    "robotCalibration:",
    `  offsetX: ${formatNumber(next.offsetX)}`,
    `  offsetY: ${formatNumber(next.offsetY)}`,
    `  scaleX: ${formatNumber(next.scaleX)}`,
    `  scaleY: ${formatNumber(next.scaleY)}`,
    `  rotation: ${formatNumber(next.rotation)}`,
  ].join("\n");
}

export function mowingPathCalibrationToYaml(mowingPathCalibration) {
  const next = { ...DEFAULT_CALIBRATION, ...(mowingPathCalibration || {}) };

  return [
    "mowingPathCalibration:",
    `  offsetX: ${formatNumber(next.offsetX)}`,
    `  offsetY: ${formatNumber(next.offsetY)}`,
    `  scaleX: ${formatNumber(next.scaleX)}`,
    `  scaleY: ${formatNumber(next.scaleY)}`,
    `  rotation: ${formatNumber(next.rotation)}`,
  ].join("\n");
}

export function decodedBoundaryCalibrationToYaml(decodedBoundaryCalibration) {
  const next = { ...DEFAULT_CALIBRATION, ...(decodedBoundaryCalibration || {}) };

  return [
    "decodedBoundaryCalibration:",
    `  offsetX: ${formatNumber(next.offsetX)}`,
    `  offsetY: ${formatNumber(next.offsetY)}`,
    `  scaleX: ${formatNumber(next.scaleX)}`,
    `  scaleY: ${formatNumber(next.scaleY)}`,
    `  rotation: ${formatNumber(next.rotation)}`,
  ].join("\n");
}

export function cardToYaml(
  config = {},
  calibration,
  robotCalibration,
  decodedBoundaryCalibration,
  mowingPathCalibration,
) {
  const lines = [
    "type: custom:anthbot-map-card",
    `entity: ${config.entity || ""}`,
  ];

  if (config.name) {
    lines.push(`name: ${quoteYaml(config.name)}`);
  }

  if (config.language) {
    lines.push(`language: ${quoteYaml(config.language)}`);
  }

  if (config.image) {
    lines.push(`image: ${quoteYaml(config.image)}`);
  }

  if (config.map_only === true || config.mapOnly === true) {
    lines.push("map_only: true");
  }

  if (config.transparent_background === true || config.transparentBackground === true) {
    lines.push("transparent_background: true");
  }

  if (config.robot_image || config.robotImage) {
    lines.push(`robot_image: ${quoteYaml(config.robot_image || config.robotImage)}`);
  }

  if (Number.isFinite(Number(config.robot_size || config.robotSize))) {
    lines.push(`robot_size: ${formatNumber(config.robot_size || config.robotSize)}`);
  }

  if (Number.isFinite(Number(config.robot_image_rotation ?? config.robotImageRotation))) {
    lines.push(`robot_image_rotation: ${formatNumber(config.robot_image_rotation ?? config.robotImageRotation)}`);
  }

  if (config.robot_heading_source || config.robotHeadingSource) {
    lines.push(`robot_heading_source: ${quoteYaml(config.robot_heading_source || config.robotHeadingSource)}`);
  }

  if (Number.isFinite(Number(config.robot_heading_offset ?? config.robotHeadingOffset))) {
    lines.push(`robot_heading_offset: ${formatNumber(config.robot_heading_offset ?? config.robotHeadingOffset)}`);
  }

  if (Number.isFinite(Number(config.robot_mowing_heading_offset ?? config.robotMowingHeadingOffset))) {
    lines.push(
      `robot_mowing_heading_offset: ${formatNumber(
        config.robot_mowing_heading_offset ?? config.robotMowingHeadingOffset,
      )}`,
    );
  }

  if (config.show_mowed_path === false) {
    lines.push("show_mowed_path: false");
  }

  if (config.show_decoded_boundary === false || config.showDecodedBoundary === false) {
    lines.push("show_decoded_boundary: false");
  }

  if (config.show_zones === false || config.showZones === false) {
    lines.push("show_zones: false");
  }

  if (config.show_no_go_zones === false || config.showNoGoZones === false) {
    lines.push("show_no_go_zones: false");
  }

  if (config.show_no_go_labels === false || config.showNoGoLabels === false) {
    lines.push("show_no_go_labels: false");
  }

  if (config.show_legacy_boundary === true || config.showLegacyBoundary === true) {
    lines.push("show_legacy_boundary: true");
  }

  if (config.mowed_path_color || config.mowedPathColor) {
    lines.push(`mowed_path_color: ${quoteYaml(config.mowed_path_color || config.mowedPathColor)}`);
  }

  if (config.mowed_path_source || config.mowedPathSource) {
    lines.push(`mowed_path_source: ${quoteYaml(config.mowed_path_source || config.mowedPathSource)}`);
  }

  if (Number.isFinite(Number(config.mowed_path_width ?? config.mowedPathWidth))) {
    lines.push(`mowed_path_width: ${formatNumber(config.mowed_path_width ?? config.mowedPathWidth)}`);
  }

  if (config.fit) {
    lines.push(`fit: ${quoteYaml(config.fit)}`);
  }

  if (Number.isFinite(Number(config.rotation)) && Number(config.rotation) !== 0) {
    lines.push(`rotation: ${formatNumber(config.rotation)}`);
  }

  if (Number.isFinite(Number(config.height))) {
    lines.push(`height: ${formatNumber(config.height)}`);
  }

  if (Number.isFinite(Number(config.refresh_interval ?? config.refreshInterval))) {
    lines.push(`refresh_interval: ${formatNumber(config.refresh_interval ?? config.refreshInterval)}`);
  }

  if (
    config.charger &&
    Number.isFinite(Number(config.charger.x)) &&
    Number.isFinite(Number(config.charger.y))
  ) {
    lines.push("charger:");
    lines.push(`  x: ${formatNumber(config.charger.x)}`);
    lines.push(`  y: ${formatNumber(config.charger.y)}`);
  }

  if (config.entities && typeof config.entities === "object") {
    lines.push("entities:");
    for (const key of ["battery", "status", "charging"]) {
      if (config.entities[key]) {
        lines.push(`  ${key}: ${config.entities[key]}`);
      }
    }
  }

  if (config.controls && typeof config.controls === "object") {
    lines.push("controls:");
    for (const key of ["start", "stop", "dock"]) {
      if (config.controls[key]) {
        lines.push(`  ${key}: ${config.controls[key]}`);
      }
    }
  }

  if (config.button_actions && typeof config.button_actions === "object") {
    lines.push("button_actions:");
    for (const [command, action] of Object.entries(config.button_actions)) {
      if (typeof action === "string") {
        lines.push(`  ${command}: ${quoteYaml(action)}`);
        continue;
      }
      if (!action || typeof action !== "object" || !action.service) continue;
      lines.push(`  ${command}:`);
      lines.push(`    service: ${quoteYaml(action.service)}`);
      appendYamlObject(lines, "    target", action.target, 6);
      appendYamlObject(lines, "    data", action.data || action.service_data, 6);
    }
  }

  lines.push(calibrationToYaml(calibration));
  lines.push(robotCalibrationToYaml(robotCalibration));
  lines.push(mowingPathCalibrationToYaml(mowingPathCalibration));
  lines.push(decodedBoundaryCalibrationToYaml(decodedBoundaryCalibration));

  return lines.join("\n");
}

function formatNumber(value) {
  return Number(value).toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
}

function appendYamlObject(lines, label, value, indent) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return;
  const entries = Object.entries(value);
  if (!entries.length) return;
  lines.push(`${label}:`);
  const prefix = " ".repeat(indent);
  for (const [key, item] of entries) {
    if (["string", "number", "boolean"].includes(typeof item)) {
      const rendered = typeof item === "string" ? quoteYaml(item) : String(item);
      lines.push(`${prefix}${key}: ${rendered}`);
    }
  }
}

function quoteYaml(value) {
  return JSON.stringify(String(value));
}

// Preserve the real mowing target next to progress even after the mower has
// already returned to charging/standby. The main card keeps its original beta3
// status logic; this is a narrow post-processing layer driven by the persisted
// last_mowing_task attribute.
if (typeof customElements !== "undefined") {
  customElements.whenDefined("anthbot-map-card").then(() => {
    const Card = customElements.get("anthbot-map-card");
    const proto = Card?.prototype;
    if (!proto || proto.__anthbotMowingTargetPatch === true) return;

    const original = proto.updateMowingProgressStatus;
    if (typeof original !== "function") return;

    const resolveTaskTarget = (card, task) => {
      if (!task || typeof task !== "object") return "";
      const type = String(task.type || "").trim().toLowerCase();
      const data = task.data && typeof task.data === "object" ? task.data : {};

      if (type === "full") return card.t("fullArea");
      if (type === "edge") return card.t("commandOuterEdge");
      if (type === "dock_edge") return card.t("dockEdgeLabel");
      if (type === "auto_zone") return card.t("autoZone");

      if (type === "manual_zone") {
        const rawIds = Array.isArray(data.id) ? data.id : [];
        const ids = rawIds.map(String);
        const names = new Map(
          (typeof card.currentZones === "function" ? card.currentZones() : [])
            .filter((zone) => zone && zone.id !== undefined && zone.id !== null)
            .map((zone) => [String(zone.id), String(zone.name || `${card.t("zone")} ${zone.id}`).trim()])
        );
        const labels = ids.map((id) => names.get(id) || `${card.t("zone")} ${id}`);
        return labels.join(" + ");
      }
      return "";
    };

    proto.updateMowingProgressStatus = function (...args) {
      original.apply(this, args);

      const lines = Array.from(this.shadowRoot?.querySelectorAll?.('[data-role="mowing-live-line"]') || []);
      if (!lines.length) return;

      const progressEntity = this.getRelatedEntity?.("mowingProgress");
      const progress = Number(progressEntity?.state);
      if (!Number.isFinite(progress)) return;

      const task = this.entity?.attributes?.last_mowing_task
        ?? progressEntity?.attributes?.last_mowing_task
        ?? null;
      const target = resolveTaskTarget(this, task);
      if (!target) return;

      const statusEntity = this.getRelatedEntity?.("status");
      const status = String(statusEntity?.state || "").trim().toLowerCase().replace(/[_\s-]+/g, "");
      const finished = [
        "returningtodock", "backtodock", "returntodock", "docking",
        "charging", "charge", "docked", "standby", "idle",
      ].some((value) => status.includes(value));
      const bounded = Math.max(0, Math.min(100, progress));
      const shownProgress = finished && bounded >= 95 ? 100 : bounded;

      lines.forEach((line) => {
        const targetNode = line.querySelector('[data-role="mowing-live-target"]');
        const progressNode = line.querySelector('[data-role="mowing-live-progress"]');
        if (!targetNode || !progressNode) return;
        targetNode.textContent = target;
        progressNode.textContent = `${shownProgress.toFixed(1)}%`;
        line.hidden = false;
      });
    };

    proto.__anthbotMowingTargetPatch = true;
  });
}
