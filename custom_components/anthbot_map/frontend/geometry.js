export const DEFAULT_VIEW = Object.freeze({
  panX: 0,
  panY: 0,
  zoom: 1,
  rotation: 0,
});

export function createGeometry(options = {}) {
  const bounds = normalizeBounds(options.bounds);
  const calibration = normalizeCalibration(options.calibration);
  const size = {
    width: Math.max(1, Number(options.width) || 1),
    height: Math.max(1, Number(options.height) || 1),
  };
  const view = { ...DEFAULT_VIEW, ...options.view };
  const map = computeMapFit(size, bounds, view, options.aspectRatio, options.fit);

  return {
    bounds,
    calibration,
    size,
    view,
    map,
    worldToMap(point) {
      return worldToMap(point, bounds);
    },
    mapToWorld(point) {
      return mapToWorld(point, bounds);
    },
    mapToScreen(point) {
      return mapToScreen(point, map, calibration);
    },
    screenToMap(point) {
      return screenToMap(point, map, calibration);
    },
    worldToScreen(point) {
      return mapToScreen(worldToMap(point, bounds), map, calibration);
    },
    screenToWorld(point) {
      return mapToWorld(screenToMap(point, map, calibration), bounds);
    },
  };
}

export function normalizeBounds(bounds) {
  const fallback = { minX: -500, minY: -500, maxX: 500, maxY: 500 };
  const next = { ...fallback, ...(bounds || {}) };

  for (const key of Object.keys(next)) {
    next[key] = Number(next[key]);
  }

  if (!Number.isFinite(next.minX) || !Number.isFinite(next.maxX) || next.minX === next.maxX) {
    next.minX = fallback.minX;
    next.maxX = fallback.maxX;
  }

  if (!Number.isFinite(next.minY) || !Number.isFinite(next.maxY) || next.minY === next.maxY) {
    next.minY = fallback.minY;
    next.maxY = fallback.maxY;
  }

  if (next.minX > next.maxX) {
    [next.minX, next.maxX] = [next.maxX, next.minX];
  }

  if (next.minY > next.maxY) {
    [next.minY, next.maxY] = [next.maxY, next.minY];
  }

  return next;
}

export function getWorldBounds(areaDefinition, pose) {
  const points = [];

  const rasterBounds = areaDefinition?.map_raster?.bounds;
  if (rasterBounds && typeof rasterBounds === "object") {
    const minX = Number(rasterBounds.min_x ?? rasterBounds.minX);
    const maxX = Number(rasterBounds.max_x ?? rasterBounds.maxX);
    const minY = Number(rasterBounds.min_y ?? rasterBounds.minY);
    const maxY = Number(rasterBounds.max_y ?? rasterBounds.maxY);
    if ([minX, maxX, minY, maxY].every(Number.isFinite)) {
      points.push(
        { x: minX, y: minY },
        { x: maxX, y: minY },
        { x: maxX, y: maxY },
        { x: minX, y: maxY },
      );
    }
  }

  for (const path of getBoundaryPaths(areaDefinition)) {
    points.push(...path);
  }

  for (const zone of [
    ...getZones(areaDefinition, ["custom_areas", "zones", "customAreas"]),
    ...getZones(areaDefinition, [
      "forbid_areas",
      "forbidAreas",
      "remote_forbid_areas",
      "remoteForbidAreas",
      "no_go_areas",
      "noGoAreas",
    ]),
  ]) {
    points.push(...getZonePoints(zone));
  }

  if (isFinitePoint(pose)) {
    points.push({ x: Number(pose.x), y: Number(pose.y) });
  }

  if (!points.length) {
    return normalizeBounds();
  }

  const xs = points.map((point) => Number(point.x)).filter(Number.isFinite);
  const ys = points.map((point) => Number(point.y)).filter(Number.isFinite);
  const padding = Math.max(100, Math.max(max(xs) - min(xs), max(ys) - min(ys)) * 0.08);

  return normalizeBounds({
    minX: min(xs) - padding,
    maxX: max(xs) + padding,
    minY: min(ys) - padding,
    maxY: max(ys) + padding,
  });
}

export function getZones(areaDefinition, keys) {
  if (!areaDefinition || typeof areaDefinition !== "object") {
    return [];
  }

  const zones = [];
  for (const key of keys) {
    if (Array.isArray(areaDefinition[key])) {
      zones.push(...areaDefinition[key].filter((zone) => zone && typeof zone === "object"));
    }
  }

  return zones;
}

export function getZonePoints(zone) {
  const candidates = [zone.vertexs, zone.vertices, zone.points, zone.path, zone.polygon];

  for (const candidate of candidates) {
    const points = normalizePoints(candidate);
    if (points.length) {
      return points;
    }
  }

  if (Number.isFinite(Number(zone.x)) && Number.isFinite(Number(zone.y))) {
    const width = Number(zone.width ?? zone.w ?? zone.radius ?? 100);
    const height = Number(zone.height ?? zone.h ?? zone.radius ?? width);
    const x = Number(zone.x);
    const y = Number(zone.y);

    return [
      { x: x - width / 2, y: y - height / 2 },
      { x: x + width / 2, y: y - height / 2 },
      { x: x + width / 2, y: y + height / 2 },
      { x: x - width / 2, y: y + height / 2 },
    ];
  }

  return [];
}

export function getBoundaryPaths(areaDefinition) {
  if (!areaDefinition || typeof areaDefinition !== "object") {
    return [];
  }

  const paths = [];
  collectBinaryPaths(areaDefinition, paths);
  collectBoundaryPaths(areaDefinition, paths);
  if (paths.length) {
    return paths;
  }

  const fallback = zoneHullBoundary(areaDefinition);
  return fallback.length ? [fallback] : [];
}

function collectBinaryPaths(value, paths, seen = new Set()) {
  if (!value || typeof value !== "object" || seen.has(value)) {
    return;
  }
  seen.add(value);

  if (Array.isArray(value)) {
    for (const item of value) {
      collectBinaryPaths(item, paths, seen);
    }
    return;
  }

  for (const key of ["map_binary_paths"]) {
    const candidates = value[key];
    if (!Array.isArray(candidates)) {
      continue;
    }
    for (const candidate of candidates) {
      const points = normalizePoints(candidate?.points ?? candidate);
      if (isUsableBoundaryCandidate(points)) {
        paths.push(points);
      }
    }
  }

  for (const child of Object.values(value)) {
    collectBinaryPaths(child, paths, seen);
  }
}

function isUsableBoundaryCandidate(points) {
  if (!Array.isArray(points) || points.length < 12) {
    return false;
  }

  const xs = points.map((point) => Number(point.x)).filter(Number.isFinite);
  const ys = points.map((point) => Number(point.y)).filter(Number.isFinite);
  if (!xs.length || !ys.length) {
    return false;
  }

  const width = max(xs) - min(xs);
  const height = max(ys) - min(ys);
  if (width < 800 || height < 800) {
    return false;
  }

  let longJumpCount = 0;
  for (let index = 1; index < points.length; index += 1) {
    const dx = Number(points[index].x) - Number(points[index - 1].x);
    const dy = Number(points[index].y) - Number(points[index - 1].y);
    if (Math.hypot(dx, dy) > 14000) {
      longJumpCount += 1;
    }
  }

  return longJumpCount <= Math.max(2, points.length * 0.04);
}

function collectBoundaryPaths(value, paths, parentKey = "", seen = new Set()) {
  if (!value || typeof value !== "object" || seen.has(value)) {
    return;
  }
  seen.add(value);

  if (isBoundaryKey(parentKey)) {
    collectPointPaths(value, paths);
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      collectBoundaryPaths(item, paths, parentKey, seen);
    }
    return;
  }

  for (const [key, child] of Object.entries(value)) {
    if (isBoundaryKey(key)) {
      collectPointPaths(child, paths);
    }
    collectBoundaryPaths(child, paths, key, seen);
  }
}

function isBoundaryKey(key) {
  return /boundary|boundaries|border|perimeter|outline|wire|route|work_?area|map_?(line|path|border)/i.test(String(key || ""));
}

function collectPointPaths(value, paths) {
  const points = normalizePoints(value);
  if (points.length >= 2) {
    paths.push(points);
    return;
  }

  if (!Array.isArray(value)) {
    return;
  }

  for (const item of value) {
    if (item && typeof item === "object") {
      collectPointPaths(item.vertexs ?? item.vertices ?? item.points ?? item.path ?? item.polygon ?? item, paths);
    }
  }
}

function zoneHullBoundary(areaDefinition) {
  const points = [];

  for (const zone of getZones(areaDefinition, ["custom_areas", "zones", "customAreas"])) {
    points.push(...getZonePoints(zone));
  }

  return convexHull(points);
}

function convexHull(points) {
  const unique = [];
  const seen = new Set();

  for (const point of points.filter(isFinitePoint)) {
    const x = Number(point.x);
    const y = Number(point.y);
    const key = `${x}:${y}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push({ x, y });
    }
  }

  if (unique.length < 3) {
    return [];
  }

  unique.sort((a, b) => (a.x === b.x ? a.y - b.y : a.x - b.x));

  const lower = [];
  for (const point of unique) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) {
      lower.pop();
    }
    lower.push(point);
  }

  const upper = [];
  for (let index = unique.length - 1; index >= 0; index -= 1) {
    const point = unique[index];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) {
      upper.pop();
    }
    upper.push(point);
  }

  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}

function cross(origin, a, b) {
  return (a.x - origin.x) * (b.y - origin.y) - (a.y - origin.y) * (b.x - origin.x);
}

export function normalizePoints(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  if (value.every((item) => typeof item === "number")) {
    const points = [];
    for (let index = 0; index + 1 < value.length; index += 2) {
      points.push({ x: Number(value[index]), y: Number(value[index + 1]) });
    }
    return points.filter(isFinitePoint);
  }

  return value
    .map((item) => {
      if (Array.isArray(item) && item.length >= 2) {
        return { x: Number(item[0]), y: Number(item[1]) };
      }

      if (item && typeof item === "object") {
        return { x: Number(item.x ?? item.lng ?? item.lon), y: Number(item.y ?? item.lat) };
      }

      return null;
    })
    .filter(isFinitePoint);
}

function worldToMap(point, bounds) {
  const width = bounds.maxX - bounds.minX;
  const height = bounds.maxY - bounds.minY;

  return {
    x: (Number(point.x) - bounds.minX) / width,
    y: 1 - (Number(point.y) - bounds.minY) / height,
  };
}

function mapToWorld(point, bounds) {
  return {
    x: bounds.minX + Number(point.x) * (bounds.maxX - bounds.minX),
    y: bounds.minY + (1 - Number(point.y)) * (bounds.maxY - bounds.minY),
  };
}

function mapToScreen(point, map, calibration) {
  const transformed = applyCalibration(point, calibration);
  const centered = {
    x: (transformed.x - 0.5) * map.width,
    y: (transformed.y - 0.5) * map.height,
  };
  const rotated = rotatePoint(centered, map.rotation);

  return {
    x: map.centerX + rotated.x,
    y: map.centerY + rotated.y,
  };
}

function screenToMap(point, map, calibration) {
  const centered = {
    x: Number(point.x) - map.centerX,
    y: Number(point.y) - map.centerY,
  };
  const rotated = rotatePoint(centered, -map.rotation);
  const normalized = {
    x: rotated.x / map.width + 0.5,
    y: rotated.y / map.height + 0.5,
  };

  return removeCalibration(normalized, calibration);
}

function computeMapFit(size, bounds, view, aspectRatio, fit = "contain") {
  const worldRatio = (bounds.maxX - bounds.minX) / (bounds.maxY - bounds.minY);
  const targetRatio = Number.isFinite(Number(aspectRatio)) && Number(aspectRatio) > 0
    ? Number(aspectRatio)
    : worldRatio;
  const canvasRatio = size.width / size.height;
  let width = size.width;
  let height = size.height;

  if (fit === "cover") {
    if (targetRatio > canvasRatio) {
      width = height * targetRatio;
    } else {
      height = width / targetRatio;
    }
  } else if (targetRatio > canvasRatio) {
    height = width / targetRatio;
  } else {
    width = height * targetRatio;
  }

  return {
    width: Math.max(1, width * view.zoom),
    height: Math.max(1, height * view.zoom),
    centerX: size.width / 2 + view.panX,
    centerY: size.height / 2 + view.panY,
    rotation: Number(view.rotation) || 0,
  };
}

export function normalizeCalibration(calibration) {
  return {
    offsetX: Number(calibration?.offsetX) || 0,
    offsetY: Number(calibration?.offsetY) || 0,
    scaleX: Number(calibration?.scaleX) || 1,
    scaleY: Number(calibration?.scaleY) || 1,
    rotation: Number(calibration?.rotation) || 0,
  };
}

function applyCalibration(point, calibration) {
  const centered = {
    x: (Number(point.x) - 0.5) * calibration.scaleX,
    y: (Number(point.y) - 0.5) * calibration.scaleY,
  };
  const rotated = rotatePoint(centered, calibration.rotation);

  return {
    x: rotated.x + 0.5 + calibration.offsetX,
    y: rotated.y + 0.5 + calibration.offsetY,
  };
}

function removeCalibration(point, calibration) {
  const centered = {
    x: Number(point.x) - 0.5 - calibration.offsetX,
    y: Number(point.y) - 0.5 - calibration.offsetY,
  };
  const rotated = rotatePoint(centered, -calibration.rotation);

  return {
    x: rotated.x / calibration.scaleX + 0.5,
    y: rotated.y / calibration.scaleY + 0.5,
  };
}

function rotatePoint(point, angle) {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);

  return {
    x: point.x * cos - point.y * sin,
    y: point.x * sin + point.y * cos,
  };
}

function isFinitePoint(point) {
  return Boolean(point && Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y)));
}

function min(values) {
  return Math.min(...values);
}

function max(values) {
  return Math.max(...values);
}
