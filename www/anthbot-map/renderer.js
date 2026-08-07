import { createGeometry, getBoundaryPaths, getWorldBounds, getZonePoints, getZones } from "./geometry.js?v=138";

const COLORS = Object.freeze({
  background: "#18202a",
  grid: "rgba(255, 255, 255, 0.09)",
  zoneFill: "rgba(67, 160, 71, 0.28)",
  zoneStroke: "rgba(129, 199, 132, 0.95)",
  noGoFill: "rgba(244, 67, 54, 0.38)",
  noGoStroke: "rgba(255, 82, 82, 1)",
  boundaryStroke: "rgba(74, 101, 255, 0.9)",
  boundaryGlow: "rgba(168, 179, 255, 0.38)",
  mowedPath: "rgba(82, 94, 245, 0.62)",
  mowedPathStroke: "rgba(220, 226, 255, 0.72)",
  mowedCoverage: "rgba(255, 235, 59, 0.28)",
  robot: "#ffcc33",
  robotStroke: "#1b1b1b",
});

export class AnthbotMapRenderer {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.options = { ...options };
    this.state = {};
    this.image = null;
    this.imageUrl = null;
    this.rasterCanvas = null;
    this.rasterBoundaryCanvas = null;
    this.rasterKey = null;
    this.rasterBoundaryKey = null;
    this.robotImage = null;
    this.robotImageUrl = null;
    this.robotHeading = null;
    this.cloudHeading = null;
    this.liveMowedPath = [];
    this.persistedMowedPath = [];
    this.lastTrailPoint = null;
    this.mowedPathStorageKey = options.mowedPathStorageKey || null;
    this.lastSavedMowedPathSignature = "";
    this.currentMowedPathSessionId = null;
    this.lastMowingState = false;
    this.dpr = 1;
    this.view = {
      panX: 0,
      panY: 0,
      zoom: 1,
      rotation: Number(options.rotation) || 0,
    };
    this.drag = null;
    this.pointers = new Map();
    this.pinch = null;
    this.decodedBoundaryCalibration = options.decodedBoundaryCalibration || {};
    if (!this.isCloudOnlyMowedPath()) {
      this.restoreLiveMowedPath();
    }

    this.onPointerDown = this.onPointerDown.bind(this);
    this.onPointerMove = this.onPointerMove.bind(this);
    this.onPointerUp = this.onPointerUp.bind(this);
    this.onWheel = this.onWheel.bind(this);

    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointermove", this.onPointerMove);
    canvas.addEventListener("pointerup", this.onPointerUp);
    canvas.addEventListener("pointercancel", this.onPointerUp);
    canvas.addEventListener("wheel", this.onWheel, { passive: false });
  }

  destroy() {
    this.canvas.removeEventListener("pointerdown", this.onPointerDown);
    this.canvas.removeEventListener("pointermove", this.onPointerMove);
    this.canvas.removeEventListener("pointerup", this.onPointerUp);
    this.canvas.removeEventListener("pointercancel", this.onPointerUp);
    this.canvas.removeEventListener("wheel", this.onWheel);
  }

  setOptions(options = {}) {
    const previousMowedPathStorageKey = this.mowedPathStorageKey;
    this.options = { ...this.options, ...options };
    this.mowedPathStorageKey = this.options.mowedPathStorageKey || null;
    if (this.isCloudOnlyMowedPath()) {
      this.liveMowedPath = [];
      this.persistedMowedPath = [];
      this.lastTrailPoint = null;
    } else if (this.mowedPathStorageKey !== previousMowedPathStorageKey) {
      this.restoreLiveMowedPath();
    }
    if (options.decodedBoundaryCalibration) {
      this.decodedBoundaryCalibration = options.decodedBoundaryCalibration;
    }
    if (Number.isFinite(Number(options.rotation))) {
      this.view.rotation = Number(options.rotation);
    }
    this.loadImage(this.options.image);
    this.loadRobotImage(this.options.robotImage);
    this.draw();
  }

  setState(state = {}) {
    this.state = state;
    if (!this.isCloudOnlyMowedPath()) {
      this.updateMowedPathSession(state);
      this.updateLiveMowedPath(state);
    }
    this.loadImage(this.options.image);
    this.loadRobotImage(this.options.robotImage);
    this.draw();
  }

  isCloudOnlyMowedPath() {
    return String(this.options.mowedPathSource || "auto").toLowerCase() === "cloud";
  }

  setCalibration(calibration) {
    this.options.calibration = calibration;
    this.draw();
  }

  setRobotCalibration(robotCalibration) {
    this.options.robotCalibration = robotCalibration;
    this.draw();
  }

  setDecodedBoundaryCalibration(decodedBoundaryCalibration) {
    this.decodedBoundaryCalibration = decodedBoundaryCalibration || {};
    this.options.decodedBoundaryCalibration = this.decodedBoundaryCalibration;
    this.draw();
  }

  resetView() {
    this.view.panX = 0;
    this.view.panY = 0;
    this.view.zoom = 1;
    this.view.rotation = Number(this.options.rotation) || 0;
    this.draw();
  }

  rotate(delta) {
    this.view.rotation += delta;
    this.draw();
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    this.dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.round(rect.width * this.dpr));
    this.canvas.height = Math.max(1, Math.round(rect.height * this.dpr));
    this.draw();
  }

  draw() {
    if (!this.ctx || !this.canvas.width || !this.canvas.height) {
      return;
    }

    const ctx = this.ctx;
    const width = this.canvas.width / this.dpr;
    const height = this.canvas.height / this.dpr;
    const areaDefinition = this.state.area_definition || {};
    const mapSource = {
      ...areaDefinition,
      map_raster: this.state.map_raster,
      map_definition: this.state.map_definition,
      path_definition: this.state.path_definition,
      map_binary_paths: this.state.map_binary_paths,
      path_binary_paths: this.state.path_binary_paths,
    };
    const pose = this.state.pose || {};
    const bounds = this.options.bounds || getWorldBounds(mapSource, pose);
    const baseGeometry = createGeometry({
      width,
      height,
      bounds,
      view: this.view,
      calibration: {},
      aspectRatio: this.image ? this.image.width / this.image.height : undefined,
      fit: this.options.fit,
    });
    const geometry = createGeometry({
      width,
      height,
      bounds,
      view: this.view,
      calibration: this.options.calibration,
      aspectRatio: this.image ? this.image.width / this.image.height : undefined,
      fit: this.options.fit,
    });

    ctx.save();
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    this.drawBackground(ctx, this.image ? baseGeometry : geometry, width, height);
    if (this.options.showZones !== false) {
      this.drawZones(ctx, geometry, getZones(areaDefinition, ["custom_areas", "zones", "customAreas"]), "zone");
    }
    if (this.options.showNoGoZones !== false) {
      this.drawZones(
        ctx,
        geometry,
        getZones(areaDefinition, [
          "forbid_areas",
          "forbidAreas",
          "remote_forbid_areas",
          "remoteForbidAreas",
          "no_go_areas",
          "noGoAreas",
        ]),
        "no-go",
      );
    }
    if (this.options.showLegacyBoundary === true) {
      this.drawBoundary(ctx, geometry, getBoundaryPaths(mapSource));
    }
    this.drawDecodedBoundary(ctx, geometry);
    this.drawMowedPath(ctx, geometry);
    this.drawCharger(ctx, geometry);
    this.drawRobot(ctx, geometry, pose);

    ctx.restore();
  }

  drawMowedPath(ctx, geometry) {
    if (this.options.showMowedPath === false) {
      return;
    }
    // Match the official app: a completed route must not remain painted while
    // the mower is returning to, docked at, or charging on the station.  The
    // cloud can keep the previous path payload after the task has ended, so
    // checking only whether path points exist would display stale coverage.
    if (isDockingOrChargingState(this.state)) {
      return;
    }

    const pathSource = String(this.options.mowedPathSource || "auto").toLowerCase();
    const cloudOnly = pathSource === "cloud";
    const cloudTrail = pathSource === "live" ? [] : extractCloudMowedPathPoints(this.state);
    const baseTrail = cloudOnly
      ? cloudTrail
      : (cloudTrail.length >= 2 ? cloudTrail : this.persistedMowedPath);
    const liveTrail = cloudOnly ? [] : this.liveMowedPath;
    const hasCloudTrail = pathSource !== "live" && baseTrail?.length >= 1;
    const hasLiveTrail = liveTrail?.length >= 1;
    if (!hasCloudTrail && !hasLiveTrail) {
      return;
    }

    const rect = this.canvas.getBoundingClientRect();
    const canvasDiagonal = Math.hypot(rect.width || 0, rect.height || 0);
    const zoomWidthFactor = Math.sqrt(Math.max(0.25, Number(this.view.zoom) || 1));
    const width = clamp(
      (Number(this.options.mowedPathWidth) || 7) * zoomWidthFactor,
      3,
      22,
    );

    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.globalCompositeOperation = "source-over";

    if (hasCloudTrail) {
      this.drawMowedTrailLayer(ctx, geometry, this.mowedPathDisplayTrail(baseTrail, true), {
        width,
        canvasDiagonal,
        showCoverage: this.options.showMowedCoverage !== false,
      });
    }

    if (hasLiveTrail) {
      this.drawMowedTrailLayer(ctx, geometry, liveTrail, {
        width,
        canvasDiagonal,
        showCoverage: false,
      });
    }
    ctx.restore();
  }

  drawMowedTrailLayer(ctx, geometry, trail, options = {}) {
    const width = Number(options.width) || 7;
    const segments = buildMowedPathSegments(
      trail,
      (point) => this.robotPositionToScreen(geometry, point),
      Number(options.canvasDiagonal) || 800,
    );
    if (!segments.length) {
      return;
    }

    if (options.showCoverage) {
      const coverageWidth = this.mowedCoverageScreenWidth(geometry, trail);
      if (coverageWidth > width) {
        ctx.strokeStyle = this.options.mowedCoverageColor || COLORS.mowedCoverage;
        ctx.lineWidth = coverageWidth;
        for (const segment of segments) {
          if (segment.length < 2) continue;
          drawScreenSegment(ctx, segment);
          ctx.stroke();
        }
      }
    }

    ctx.strokeStyle = this.options.mowedPathColor || COLORS.mowedPath;
    ctx.lineWidth = width;
    if (segments.length === 1 && segments[0].length === 1) {
      ctx.fillStyle = this.options.mowedPathColor || COLORS.mowedPath;
      ctx.beginPath();
      ctx.arc(segments[0][0].x, segments[0][0].y, width / 2, 0, Math.PI * 2);
      ctx.fill();
      return;
    }
    for (const segment of segments) {
      if (segment.length < 2) continue;
      drawScreenSegment(ctx, segment);
      ctx.stroke();
    }

    ctx.strokeStyle = COLORS.mowedPathStroke;
    ctx.lineWidth = Math.max(1.5, width * 0.08);
    for (const segment of segments) {
      if (segment.length < 2) continue;
      drawScreenSegment(ctx, segment);
      ctx.stroke();
    }
  }

  mowedCoverageScreenWidth(geometry, trail) {
    const coverageMm = Number(
      this.options.mowedCoverageWidth ??
      this.options.mowed_coverage_width ??
      this.options.mowerCutWidth ??
      this.options.mower_cut_width ??
      360,
    );
    if (!Number.isFinite(coverageMm) || coverageMm <= 0) {
      return 0;
    }

    const anchor = (trail || []).find((point) =>
      Number.isFinite(Number(point?.x)) && Number.isFinite(Number(point?.y)),
    ) || this.state.pose;
    if (!anchor || !Number.isFinite(Number(anchor.x)) || !Number.isFinite(Number(anchor.y))) {
      return clamp(coverageMm / 35, 10, 48);
    }

    const a = this.robotPositionToScreen(geometry, anchor);
    const b = this.robotPositionToScreen(geometry, {
      x: Number(anchor.x) + coverageMm,
      y: Number(anchor.y),
    });
    return clamp(Math.hypot(b.x - a.x, b.y - a.y), 10, 64);
  }

  mowedPathDisplayTrail(trail, useCloudScale = false) {
    const scale = Number(
      this.options.mowedPathDisplayScale ??
      this.options.mowed_path_display_scale ??
      (useCloudScale && Number(this.state?.path_coordinate_scale) === 1 ? 10 : 1),
    );
    if (!Number.isFinite(scale) || scale === 1) {
      return trail;
    }
    return (trail || []).map((point) => ({
      ...point,
      x: Number(point.x) * scale,
      y: Number(point.y) * scale,
    }));
  }

  drawBoundary(ctx, geometry, paths) {
    if (this.options.showBoundary === false || !Array.isArray(paths) || !paths.length) {
      return;
    }

    const color = this.options.boundaryColor || COLORS.boundaryStroke;
    const width = clamp(
      Number(this.options.boundaryWidth) || 3,
      1,
      12,
    );

    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    for (const path of paths) {
      if (!Array.isArray(path) || path.length < 2) {
        continue;
      }

      const screenPoints = path.map((point) => geometry.worldToScreen(point));
      ctx.strokeStyle = COLORS.boundaryGlow;
      ctx.lineWidth = width + 4;
      drawPolyline(ctx, screenPoints, true);
      ctx.stroke();

      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      drawPolyline(ctx, screenPoints, true);
      ctx.stroke();
    }

    ctx.restore();
  }

  drawBackground(ctx, geometry, width, height) {
    if (this.options.transparentBackground === true) {
      return;
    }

    ctx.fillStyle = COLORS.background;
    ctx.fillRect(0, 0, width, height);

    if (this.image) {
      drawImageOnMap(ctx, geometry, this.image, {
        topLeft: { x: 0, y: 0 },
        topRight: { x: 1, y: 0 },
        bottomLeft: { x: 0, y: 1 },
        dpr: this.dpr,
        smoothing: true,
        stroke: "rgba(255, 255, 255, 0.12)",
      });
      return;
    }

    if (this.drawMapRaster(ctx, geometry)) {
      return;
    }

    this.drawGrid(ctx, geometry);
  }

  drawDecodedBoundary(ctx, geometry) {
    if (this.options.showBoundary === false || this.options.showDecodedBoundary === false) {
      return false;
    }

    const raster = this.state.map_raster;
    const bounds = raster?.bounds;
    if (!raster || !bounds || !Array.isArray(raster.runs)) {
      return false;
    }

    const minX = Number(bounds.min_x ?? bounds.minX);
    const maxX = Number(bounds.max_x ?? bounds.maxX);
    const minY = Number(bounds.min_y ?? bounds.minY);
    const maxY = Number(bounds.max_y ?? bounds.maxY);
    if (![minX, maxX, minY, maxY].every(Number.isFinite)) {
      return false;
    }

    const boundaryGeometry = applyMapCalibration(geometry, this.decodedBoundaryCalibration);
    return this.drawRasterBoundary(ctx, boundaryGeometry, raster, {
      minX,
      maxX,
      minY,
      maxY,
    });
  }

  drawRasterBoundary(ctx, geometry, raster, bounds) {
    const width = Number(raster?.width);
    const height = Number(raster?.height);
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
      return false;
    }

    const pixels = decodeRasterRuns(raster, width, height);
    if (!pixels) {
      return false;
    }

    const stepX = (bounds.maxX - bounds.minX) / width;
    const stepY = (bounds.maxY - bounds.minY) / height;
    if (!Number.isFinite(stepX) || !Number.isFinite(stepY) || stepX === 0 || stepY === 0) {
      return false;
    }

    const isSolid = (x, y) =>
      x >= 0 &&
      x < width &&
      y >= 0 &&
      y < height &&
      pixels[y * width + x] !== 0;
    const toScreen = (x, y) =>
      geometry.worldToScreen({
        x: bounds.minX + x * stepX,
        y: bounds.minY + y * stepY,
      });
    let edgeCount = 0;
    const addEdge = (x1, y1, x2, y2) => {
      const start = toScreen(x1, y1);
      const end = toScreen(x2, y2);
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      edgeCount += 1;
    };

    ctx.save();
    ctx.strokeStyle = this.options.boundaryColor || COLORS.boundaryStroke;
    ctx.lineWidth = clamp(Number(this.options.boundaryWidth) || 3, 1, 12);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();

    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        if (!isSolid(x, y)) {
          continue;
        }
        if (!isSolid(x - 1, y)) addEdge(x, y, x, y + 1);
        if (!isSolid(x + 1, y)) addEdge(x + 1, y, x + 1, y + 1);
        if (!isSolid(x, y - 1)) addEdge(x, y, x + 1, y);
        if (!isSolid(x, y + 1)) addEdge(x, y + 1, x + 1, y + 1);
      }
    }

    if (edgeCount) {
      ctx.stroke();
    }
    ctx.restore();
    return edgeCount > 0;
  }

  drawMapRaster(ctx, geometry) {
    const raster = this.state.map_raster;
    const bounds = raster?.bounds;
    if (!raster || !bounds || !Array.isArray(raster.runs)) {
      return false;
    }

    const rasterCanvas = this.getRasterCanvas(raster);
    if (!rasterCanvas) {
      return false;
    }

    const minX = Number(bounds.min_x ?? bounds.minX);
    const maxX = Number(bounds.max_x ?? bounds.maxX);
    const minY = Number(bounds.min_y ?? bounds.minY);
    const maxY = Number(bounds.max_y ?? bounds.maxY);
    if (![minX, maxX, minY, maxY].every(Number.isFinite)) {
      return false;
    }

    drawImageFromWorldRect(ctx, geometry, rasterCanvas, {
      minX,
      maxX,
      minY,
      maxY,
      dpr: this.dpr,
      smoothing: false,
    });
    return true;
  }

  getRasterCanvas(raster) {
    const width = Number(raster.width);
    const height = Number(raster.height);
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
      return null;
    }

    const key = `${width}x${height}:${raster.runs.length}:${raster.runs[0]}:${raster.runs[raster.runs.length - 1]}`;
    if (this.rasterCanvas && this.rasterKey === key) {
      return this.rasterCanvas;
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return null;
    }

    const imageData = ctx.createImageData(width, height);
    let pixel = 0;
    for (let index = 0; index < raster.runs.length - 1; index += 2) {
      const value = Number(raster.runs[index]);
      const count = Number(raster.runs[index + 1]);
      if (!Number.isFinite(value) || !Number.isFinite(count) || count <= 0) {
        continue;
      }
      const color = rasterColor(value);
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

    this.rasterCanvas = canvas;
    this.rasterKey = key;
    return canvas;
  }

  getRasterBoundaryCanvas(raster) {
    const width = Number(raster.width);
    const height = Number(raster.height);
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
      return null;
    }

    const boundaryColor = this.options.boundaryColor || COLORS.boundaryStroke;
    const boundaryWidth = clamp(Number(this.options.boundaryWidth) || 3, 1, 12);
    const key = `boundary:${width}x${height}:${raster.runs.length}:${raster.runs[0]}:${raster.runs[raster.runs.length - 1]}:${boundaryColor}:${boundaryWidth}`;
    if (this.rasterBoundaryCanvas && this.rasterBoundaryKey === key) {
      return this.rasterBoundaryCanvas;
    }

    const pixels = decodeRasterRuns(raster, width, height);
    if (!pixels) {
      return null;
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return null;
    }

    const imageData = ctx.createImageData(width, height);
    const radius = Math.max(0, Math.ceil((boundaryWidth - 1) / 2));
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const index = y * width + x;
        const value = pixels[index];
        const solid = value !== 0;
        const edge =
          solid &&
          (value !== 255 ||
            x === 0 ||
            y === 0 ||
            x === width - 1 ||
            y === height - 1 ||
            pixels[index - 1] === 0 ||
            pixels[index + 1] === 0 ||
            pixels[index - width] === 0 ||
            pixels[index + width] === 0);

        if (!edge) {
          continue;
        }

        const alpha = value === 255 ? 210 : 245;
        for (let offsetY = -radius; offsetY <= radius; offsetY += 1) {
          for (let offsetX = -radius; offsetX <= radius; offsetX += 1) {
            if (offsetX * offsetX + offsetY * offsetY > radius * radius + 0.5) {
              continue;
            }
            const targetX = x + offsetX;
            const targetY = height - 1 - y + offsetY;
            if (targetX < 0 || targetX >= width || targetY < 0 || targetY >= height) {
              continue;
            }
            const target = (targetY * width + targetX) * 4;
            imageData.data[target] = 255;
            imageData.data[target + 1] = 255;
            imageData.data[target + 2] = 255;
            imageData.data[target + 3] = Math.max(imageData.data[target + 3], alpha);
          }
        }
      }
    }
    ctx.putImageData(imageData, 0, 0);
    ctx.save();
    ctx.globalCompositeOperation = "source-in";
    ctx.fillStyle = boundaryColor;
    ctx.fillRect(0, 0, width, height);
    ctx.restore();

    this.rasterBoundaryCanvas = canvas;
    this.rasterBoundaryKey = key;
    return canvas;
  }

  drawGrid(ctx, geometry) {
    ctx.save();
    ctx.translate(geometry.map.centerX, geometry.map.centerY);
    ctx.rotate(geometry.map.rotation);
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;

    for (let step = -0.5; step <= 0.5; step += 0.1) {
      ctx.beginPath();
      ctx.moveTo(step * geometry.map.width, -geometry.map.height / 2);
      ctx.lineTo(step * geometry.map.width, geometry.map.height / 2);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(-geometry.map.width / 2, step * geometry.map.height);
      ctx.lineTo(geometry.map.width / 2, step * geometry.map.height);
      ctx.stroke();
    }

    ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
    ctx.strokeRect(-geometry.map.width / 2, -geometry.map.height / 2, geometry.map.width, geometry.map.height);
    ctx.restore();
  }

  drawZones(ctx, geometry, zones, type) {
    const isNoGo = type === "no-go";
    ctx.fillStyle = isNoGo ? COLORS.noGoFill : COLORS.zoneFill;
    ctx.strokeStyle = isNoGo ? COLORS.noGoStroke : COLORS.zoneStroke;
    ctx.lineWidth = 2;

    for (const zone of zones) {
      const points = getZonePoints(zone);
      if (points.length < 2) {
        continue;
      }

      const screenPoints = points.map((point) => geometry.worldToScreen(point));
      ctx.beginPath();
      ctx.moveTo(screenPoints[0].x, screenPoints[0].y);
      for (const point of screenPoints.slice(1)) {
        ctx.lineTo(point.x, point.y);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      if (!isNoGo || this.options.showNoGoLabels !== false) {
        this.drawZoneLabel(ctx, screenPoints, zoneLabel(zone, isNoGo, this.options.noGoLabel));
      }
    }
  }

  drawZoneLabel(ctx, points, label) {
    if (!label || !points.length) {
      return;
    }

    const center = points.reduce(
      (acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }),
      { x: 0, y: 0 },
    );
    center.x /= points.length;
    center.y /= points.length;

    ctx.save();
    ctx.font = "600 12px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const width = ctx.measureText(label).width + 14;
    const canvasWidth = ctx.canvas.width / (this.dpr || 1);
    const canvasHeight = ctx.canvas.height / (this.dpr || 1);
    if (
      center.x < 0 ||
      center.x > canvasWidth ||
      center.y < 0 ||
      center.y > canvasHeight ||
      !polygonIntersectsViewport(points, canvasWidth, canvasHeight)
    ) {
      ctx.restore();
      return;
    }
    ctx.fillStyle = "rgba(12, 18, 24, 0.72)";
    roundRect(ctx, center.x - width / 2, center.y - 13, width, 26, 13);
    ctx.fill();
    ctx.fillStyle = "rgba(232, 255, 237, 0.96)";
    ctx.fillText(label, center.x, center.y);
    ctx.restore();
  }

  drawCharger(ctx, geometry) {
    const charger = this.options.charger;
    if (!charger || !Number.isFinite(Number(charger.x)) || !Number.isFinite(Number(charger.y))) {
      return;
    }

    const point = geometry.mapToScreen({ x: Number(charger.x), y: Number(charger.y) });

    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.fillStyle = "rgba(13, 148, 136, 0.92)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.95)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, 0, 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = "700 14px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("H", 0, 0);
    ctx.restore();
  }

  drawRobot(ctx, geometry, pose) {
    if (!pose || !Number.isFinite(Number(pose.x)) || !Number.isFinite(Number(pose.y))) {
      return;
    }

    const robotCalibration = this.options.robotCalibration || {};
    const point = this.robotPositionToScreen(geometry, pose);
    const mowingHeadingOffset = this.isMowingState()
      ? Number(this.options.robotMowingHeadingOffset ?? this.options.robot_mowing_heading_offset ?? 0) || 0
      : 0;
    const cloudYaw =
      degreesToRadians(this.cloudHeadingDegrees(pose)) +
      geometry.map.rotation +
      degreesToRadians(Number(this.options.robotHeadingOffset ?? this.options.robot_heading_offset) || 0) +
      degreesToRadians(mowingHeadingOffset) +
      (Number(robotCalibration.rotation) || 0);
    const headingSource = String(this.options.robotHeadingSource || "cloud").toLowerCase();
    const movementYaw =
      headingSource === "movement" || headingSource === "auto"
        ? this.movementHeading(geometry)
        : null;
    this.cloudHeading =
      this.cloudHeading === null ? cloudYaw : smoothAngle(this.cloudHeading, cloudYaw, 0.45);
    const yaw = headingSource === "movement"
      ? movementYaw ?? this.cloudHeading
      : headingSource === "cloud"
        ? this.cloudHeading
        : movementYaw ?? this.cloudHeading;

    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(yaw);
    if (this.robotImage) {
      const size = clamp(
        (Number(this.options.robotSize) || 42) *
          (Number(robotCalibration.scaleX) || 1) *
          (Number(this.view.zoom) || 1),
        8,
        260,
      );
      const aspect = this.robotImage.width / this.robotImage.height || 1;
      const imageRotation =
        this.options.robotImageRotation === undefined
          ? Math.PI / 2
          : degreesToRadians(Number(this.options.robotImageRotation) || 0);

      ctx.rotate(imageRotation);
      ctx.shadowColor = "rgba(0, 0, 0, 0.45)";
      ctx.shadowBlur = 8;
      ctx.shadowOffsetY = 2;
      ctx.drawImage(this.robotImage, (-size * aspect) / 2, -size / 2, size * aspect, size);
      ctx.restore();
      return;
    }

    const radius = clamp(9 * (Number(this.view.zoom) || 1), 4, 64);
    ctx.fillStyle = COLORS.robot;
    ctx.strokeStyle = COLORS.robotStroke;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(radius + 5, 0);
    ctx.lineTo(-radius, -radius * 0.75);
    ctx.lineTo(-radius * 0.55, 0);
    ctx.lineTo(-radius, radius * 0.75);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  loadImage(url) {
    if (!url || url === this.imageUrl) {
      return;
    }

    this.imageUrl = url;
    this.image = null;
    const image = new Image();
    image.onload = () => {
      this.image = image;
      this.draw();
    };
    image.src = url;
  }

  loadRobotImage(url) {
    if (!url) {
      this.robotImageUrl = null;
      this.robotImage = null;
      return;
    }
    if (url === this.robotImageUrl) {
      return;
    }

    this.robotImageUrl = url;
    this.robotImage = null;
    const image = new Image();
    image.onload = () => {
      this.robotImage = image;
      this.draw();
    };
    image.src = url;
  }

  updateLiveMowedPath(state = {}) {
    const pose = state.pose || {};
    if (!Number.isFinite(Number(pose.x)) || !Number.isFinite(Number(pose.y))) {
      return;
    }

    const point = { x: Number(pose.x), y: Number(pose.y) };
    if (!isLiveMowingState(state) && !this.shouldTrackLiveMovementFallback(state, point)) {
      return;
    }

    if (!this.lastTrailPoint) {
      this.liveMowedPath.push(point);
      this.lastTrailPoint = point;
      this.saveLiveMowedPath();
      return;
    }

    if (this.lastTrailPoint) {
      const distance = Math.hypot(point.x - this.lastTrailPoint.x, point.y - this.lastTrailPoint.y);
      if (distance < 1) {
        return;
      }
    }

    this.liveMowedPath.push(point);
    this.lastTrailPoint = point;
    if (this.liveMowedPath.length > 3000) {
      this.liveMowedPath.splice(0, this.liveMowedPath.length - 3000);
    }
    this.saveLiveMowedPath();
  }

  shouldTrackLiveMovementFallback(state = {}, point) {
    if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
      return false;
    }
    if (
      isDockingOrChargingStateValue(state?.mower_status) ||
      isDockingOrChargingStateValue(state?.robot_status_raw) ||
      isDockingOrChargingStateValue(state?.robot_sta)
    ) {
      return false;
    }
    if (state?.history_path_live_refresh === true) {
      return true;
    }
    if (state?.path_time || state?.path_id || Number(state?.path_point_count) > 0) {
      return true;
    }
    if (!this.lastTrailPoint) {
      return false;
    }
    return Math.hypot(point.x - this.lastTrailPoint.x, point.y - this.lastTrailPoint.y) >= 1;
  }

  restoreLiveMowedPath() {
    this.persistedMowedPath = [];
    this.lastTrailPoint = null;
    const storageKey = this.effectiveMowedPathStorageKey();
    if (!storageKey) {
      return;
    }

    try {
      const stored = JSON.parse(window.localStorage.getItem(storageKey) || "null");
      const points = normalizePathPoints(Array.isArray(stored) ? stored : stored?.points);
      if (!points.length) {
        return;
      }
      this.persistedMowedPath = points.slice(-5000);
      this.lastTrailPoint = this.persistedMowedPath[this.persistedMowedPath.length - 1] || null;
    } catch (error) {
      console.warn("Anthbot mowed path restore failed", error);
    }
  }

  saveLiveMowedPath() {
    this.rememberMowedPath(
      mergeCloudAndLivePaths(this.persistedMowedPath, this.liveMowedPath),
    );
  }

  rememberMowedPath(points) {
    const storageKey = this.effectiveMowedPathStorageKey();
    if (!storageKey) {
      return;
    }
    const normalized = normalizePathPoints(points).slice(-5000);
    if (!normalized.length) {
      return;
    }
    const last = normalized[normalized.length - 1];
    const signature = `${normalized.length}:${Math.round(Number(last.x) * 10)}:${Math.round(Number(last.y) * 10)}`;
    if (signature === this.lastSavedMowedPathSignature) {
      return;
    }
    this.persistedMowedPath = normalized;
    this.lastSavedMowedPathSignature = signature;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({
        savedAt: Date.now(),
        sessionId: this.currentMowedPathSessionId,
        points: normalized,
      }));
    } catch (error) {
      console.warn("Anthbot mowed path save failed", error);
    }
  }

  effectiveMowedPathStorageKey() {
    if (!this.mowedPathStorageKey) {
      return null;
    }
    return this.currentMowedPathSessionId
      ? `${this.mowedPathStorageKey}:${this.currentMowedPathSessionId}`
      : this.mowedPathStorageKey;
  }

  mowedPathSessionMetaKey() {
    return this.mowedPathStorageKey ? `${this.mowedPathStorageKey}:session` : null;
  }

  readMowedPathSessionMeta() {
    const storageKey = this.mowedPathSessionMetaKey();
    if (!storageKey || typeof window === "undefined" || !window.localStorage) {
      return {};
    }
    try {
      const value = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
      return value && typeof value === "object" ? value : {};
    } catch (error) {
      console.warn("Anthbot mowed path session restore failed", error);
      return {};
    }
  }

  writeMowedPathSessionMeta(mowing) {
    const storageKey = this.mowedPathSessionMetaKey();
    if (!storageKey || typeof window === "undefined" || !window.localStorage) {
      return;
    }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({
        savedAt: Date.now(),
        mowing: Boolean(mowing),
        sessionId: this.currentMowedPathSessionId,
      }));
    } catch (error) {
      console.warn("Anthbot mowed path session save failed", error);
    }
  }

  findLatestStoredLiveSession() {
    if (!this.mowedPathStorageKey || typeof window === "undefined" || !window.localStorage) {
      return null;
    }
    const prefix = `${this.mowedPathStorageKey}:live:`;
    let latest = null;
    try {
      for (let index = 0; index < window.localStorage.length; index += 1) {
        const key = window.localStorage.key(index);
        if (!key?.startsWith(prefix)) {
          continue;
        }
        const stored = JSON.parse(window.localStorage.getItem(key) || "{}");
        const savedAt = Number(stored?.savedAt);
        const points = Array.isArray(stored?.points) ? stored.points.length : 0;
        if (!Number.isFinite(savedAt) || points < 2) {
          continue;
        }
        if (!latest || savedAt > latest.savedAt) {
          latest = { savedAt, sessionId: key.slice(this.mowedPathStorageKey.length + 1) };
        }
      }
    } catch (error) {
      console.warn("Anthbot latest mowed path lookup failed", error);
    }
    if (!latest || Date.now() - latest.savedAt > 24 * 60 * 60 * 1000) {
      return null;
    }
    return latest.sessionId;
  }

  updateMowedPathSession(state = {}) {
    const mowing = isLiveMowingState(state);
    const cloudSession = mowedPathSessionId(state);
    const storedSession = this.readMowedPathSessionMeta();
    let nextSession = cloudSession;

    if (!nextSession && mowing) {
      const storedLiveSession =
        storedSession.mowing === true &&
        typeof storedSession.sessionId === "string" &&
        storedSession.sessionId.startsWith("live:")
          ? storedSession.sessionId
          : null;
      const latestLiveSession = storedSession.sessionId ? null : this.findLatestStoredLiveSession();
      nextSession =
        this.currentMowedPathSessionId?.startsWith("live:")
          ? this.currentMowedPathSessionId
          : storedLiveSession || latestLiveSession || `live:${Date.now()}`;
    }

    if (!nextSession && !mowing) {
      nextSession =
        this.currentMowedPathSessionId ||
        (typeof storedSession.sessionId === "string" ? storedSession.sessionId : null);
    }

    if (nextSession && nextSession !== this.currentMowedPathSessionId) {
      this.currentMowedPathSessionId = nextSession;
      this.liveMowedPath = [];
      this.persistedMowedPath = [];
      this.lastTrailPoint = null;
      this.lastSavedMowedPathSignature = "";
      this.restoreLiveMowedPath();
    }
    this.lastMowingState = mowing;
    this.writeMowedPathSessionMeta(mowing);
  }

  movementHeading(geometry) {
    const trail = this.liveMowedPath;
    if (!trail || trail.length < 2) {
      return null;
    }

    const last = this.robotPositionToScreen(geometry, trail[trail.length - 1]);
    const previous = this.robotPositionToScreen(geometry, trail[trail.length - 2]);
    const dx = last.x - previous.x;
    const dy = last.y - previous.y;
    if (Math.hypot(dx, dy) < 6) {
      return this.robotHeading;
    }

    const nextHeading =
      Math.atan2(dy, dx) + (Number(this.options.robotCalibration?.rotation) || 0);
    this.robotHeading =
      this.robotHeading === null ? nextHeading : smoothAngle(this.robotHeading, nextHeading, 0.35);
    return this.robotHeading;
  }

  cloudHeadingDegrees(pose) {
    const headingCandidates = [
      this.state.cur_pose?.heading,
      this.state.curPose?.heading,
      this.state.map_scan_pose?.heading,
      this.state.mapScanPose?.heading,
      this.state.raw_pose?.heading,
      pose?.heading,
    ];
    for (const value of headingCandidates) {
      const heading = Number(value);
      if (Number.isFinite(heading)) {
        return normalizeHeadingDegrees(heading);
      }
    }

    const yawCandidates = [
      this.state.cur_pose?.yaw,
      this.state.curPose?.yaw,
      this.state.map_scan_pose?.yaw,
      this.state.mapScanPose?.yaw,
      this.state.raw_pose?.yaw,
      pose?.yaw,
    ];
    for (const value of yawCandidates) {
      const yaw = Number(value);
      if (Number.isFinite(yaw)) {
        return milliRadiansToDegrees(yaw);
      }
    }
    return 0;
  }

  robotPositionToScreen(geometry, point) {
    const robotCalibration = this.options.robotCalibration || {};
    const mapPoint = geometry.worldToMap({ x: Number(point.x), y: Number(point.y) });
    return geometry.mapToScreen({
      x: mapPoint.x + (Number(robotCalibration.offsetX) || 0),
      y: mapPoint.y + (Number(robotCalibration.offsetY) || 0),
    });
  }

  isMowingState() {
    return isLiveMowingState(this.state);
  }

  onPointerDown(event) {
    this.canvas.setPointerCapture(event.pointerId);
    this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (this.pointers.size >= 2) {
      this.startPinch();
      this.drag = null;
      return;
    }
    this.drag = {
      x: event.clientX,
      y: event.clientY,
      panX: this.view.panX,
      panY: this.view.panY,
    };
  }

  onPointerMove(event) {
    if (this.pointers.has(event.pointerId)) {
      this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    }
    if (this.pinch && this.pointers.size >= 2) {
      const [first, second] = [...this.pointers.values()];
      const distance = Math.max(1, Math.hypot(second.x - first.x, second.y - first.y));
      const midpoint = { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
      const factor = distance / this.pinch.distance;
      const zoom = clamp(this.pinch.zoom * factor, 0.2, 8);
      const appliedFactor = zoom / this.pinch.zoom;
      const rect = this.canvas.getBoundingClientRect();
      const startLocal = {
        x: this.pinch.midpoint.x - rect.left,
        y: this.pinch.midpoint.y - rect.top,
      };
      const currentLocal = { x: midpoint.x - rect.left, y: midpoint.y - rect.top };
      const startCenter = {
        x: rect.width / 2 + this.pinch.panX,
        y: rect.height / 2 + this.pinch.panY,
      };
      this.view.zoom = zoom;
      this.view.panX = currentLocal.x + (startCenter.x - startLocal.x) * appliedFactor - rect.width / 2;
      this.view.panY = currentLocal.y + (startCenter.y - startLocal.y) * appliedFactor - rect.height / 2;
      this.draw();
      return;
    }
    if (!this.drag) {
      return;
    }

    this.view.panX = this.drag.panX + event.clientX - this.drag.x;
    this.view.panY = this.drag.panY + event.clientY - this.drag.y;
    this.draw();
  }

  onPointerUp(event) {
    if (this.canvas.hasPointerCapture(event.pointerId)) {
      this.canvas.releasePointerCapture(event.pointerId);
    }
    this.pointers.delete(event.pointerId);
    this.pinch = null;
    if (this.pointers.size === 1) {
      const [remaining] = this.pointers.values();
      this.drag = {
        x: remaining.x,
        y: remaining.y,
        panX: this.view.panX,
        panY: this.view.panY,
      };
    } else {
      this.drag = null;
    }
  }

  startPinch() {
    const [first, second] = [...this.pointers.values()];
    this.pinch = {
      distance: Math.max(1, Math.hypot(second.x - first.x, second.y - first.y)),
      midpoint: { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 },
      zoom: this.view.zoom,
      panX: this.view.panX,
      panY: this.view.panY,
    };
  }

  onWheel(event) {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    this.view.zoom = clamp(this.view.zoom * factor, 0.2, 8);
    this.draw();
  }
}

function fitAspect(sourceWidth, sourceHeight, maxWidth, maxHeight) {
  const scale = Math.min(maxWidth / sourceWidth, maxHeight / sourceHeight);
  return {
    width: sourceWidth * scale,
    height: sourceHeight * scale,
  };
}

function rotateAround(point, center, angle) {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const dx = point.x - center.x;
  const dy = point.y - center.y;

  return {
    x: center.x + dx * cos - dy * sin,
    y: center.y + dx * sin + dy * cos,
  };
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

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function normalizeAngle(angle) {
  while (angle > Math.PI) {
    angle -= Math.PI * 2;
  }
  while (angle < -Math.PI) {
    angle += Math.PI * 2;
  }
  return angle;
}

function smoothAngle(current, next, amount) {
  return current + normalizeAngle(next - current) * amount;
}

function isMowingStateValue(value) {
  const status = String(value || "").toLowerCase().replace(/[\s-]+/g, "_");
  return [
    "globalmowing",
    "global_mowing",
    "zonemowing",
    "zone_mowing",
    "pointmowing",
    "point_mowing",
    "bordermowing",
    "border_mowing",
    "regionmowing",
    "region_mowing",
    "nestmowing",
    "nest_mowing",
    "mowing",
    "working",
    "cutting",
    "edge_cutting",
    "gototarget",
    "goto_target",
    "remotectrl",
    "remote_ctrl",
    "nyiras",
    "nyir",
    "munka",
    "vagas",
  ].some((item) => status.includes(item));
}

function isDockingOrChargingStateValue(value) {
  const status = String(value || "").toLowerCase().replace(/[\s-]+/g, "_");
  return [
    "charge",
    "charging",
    "dock",
    "docking",
    "go_home",
    "gohome",
    "return",
    "returning",
    "back_to_dock",
    "backtodock",
    "toltes",
    "dokkol",
  ].some((item) => status.includes(item));
}

function isDockingOrChargingState(state = {}) {
  return (
    state?.charging === true ||
    String(state?.charging || "").toLowerCase() === "on" ||
    isDockingOrChargingStateValue(state?.mower_status) ||
    isDockingOrChargingStateValue(state?.robot_status_raw) ||
    isDockingOrChargingStateValue(state?.robot_sta)
  );
}

function isLiveMowingState(state = {}) {
  return (
    state?.history_path_live_refresh === true ||
    isMowingStateValue(state?.mower_status) ||
    isMowingStateValue(state?.robot_status_raw) ||
    isMowingStateValue(state?.robot_sta)
  );
}

function mowedPathSessionId(state = {}) {
  const definition = state.path_definition || state.pathDefinition || {};
  const pathId = firstStableToken(state.path_id, state.pathId, definition.path_id, definition.pathId);
  if (pathId) {
    return `path:${pathId}`;
  }

  const pathTime = firstStableToken(
    state.path_time,
    state.pathTime,
    definition.path_time,
    definition.pathTime,
  );
  if (pathTime) {
    return `time:${pathTime}`;
  }

  const start = firstStableToken(state.path_start, state.pathStart, definition.start);
  const pointCount = firstStableToken(
    state.path_point_count,
    state.pathPointCount,
    definition.point_count,
    definition.pointCount,
  );
  if (start && pointCount) {
    return `start:${start}:${pointCount}`;
  }

  return null;
}

function firstStableToken(...values) {
  for (const value of values) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    const token = String(value).trim();
    if (token) {
      return token.replace(/[^a-zA-Z0-9_.:-]/g, "_").slice(0, 120);
    }
  }
  return null;
}

function drawPolyline(ctx, points, close = false) {
  if (!points.length) {
    return;
  }

  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (const point of points.slice(1)) {
    ctx.lineTo(point.x, point.y);
  }
  if (close) {
    ctx.closePath();
  }
}

function drawScreenSegment(ctx, segment) {
  if (!segment?.length) {
    return;
  }
  ctx.beginPath();
  ctx.moveTo(segment[0].x, segment[0].y);
  for (const point of segment.slice(1)) {
    ctx.lineTo(point.x, point.y);
  }
}

function drawImageOnMap(ctx, geometry, source, options = {}) {
  const topLeft = geometry.mapToScreen(options.topLeft);
  const topRight = geometry.mapToScreen(options.topRight);
  const bottomLeft = geometry.mapToScreen(options.bottomLeft);
  drawImageToScreenRect(ctx, source, topLeft, topRight, bottomLeft, options);
}

function drawImageFromWorldRect(ctx, geometry, source, options = {}) {
  const topLeft = geometry.worldToScreen({ x: options.minX, y: options.maxY });
  const topRight = geometry.worldToScreen({ x: options.maxX, y: options.maxY });
  const bottomLeft = geometry.worldToScreen({ x: options.minX, y: options.minY });
  drawImageToScreenRect(ctx, source, topLeft, topRight, bottomLeft, options);
}

function drawImageToScreenRect(ctx, source, topLeft, topRight, bottomLeft, options = {}) {
  const sourceWidth = Number(source.width) || 1;
  const sourceHeight = Number(source.height) || 1;
  const dpr = Number(options.dpr) || 1;
  const a = (topRight.x - topLeft.x) / sourceWidth;
  const b = (topRight.y - topLeft.y) / sourceWidth;
  const c = (bottomLeft.x - topLeft.x) / sourceHeight;
  const d = (bottomLeft.y - topLeft.y) / sourceHeight;

  ctx.save();
  ctx.imageSmoothingEnabled = options.smoothing !== false;
  ctx.setTransform(a * dpr, b * dpr, c * dpr, d * dpr, topLeft.x * dpr, topLeft.y * dpr);
  ctx.drawImage(source, 0, 0);
  if (options.stroke) {
    ctx.strokeStyle = options.stroke;
    ctx.lineWidth = 1;
    ctx.strokeRect(0, 0, sourceWidth, sourceHeight);
  }
  ctx.restore();
}

function extractPathPoints(value) {
  const direct = normalizePathPoints(value);
  if (direct.length) {
    return direct;
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => extractPathPoints(item));
  }

  if (value && typeof value === "object") {
    if (Number.isFinite(Number(value.x)) && Number.isFinite(Number(value.y))) {
      return [normalizePathPoint(value)];
    }

    for (const key of ["points", "path", "track", "tracks", "trajectory", "mowed_path", "mowedPath"]) {
      const points = extractPathPoints(value[key]);
      if (points.length) {
        return points;
      }
    }
  }

  return [];
}

function normalizePathPoints(value) {
  if (!Array.isArray(value)) return [];
  return value.map(normalizePathPoint).filter(Boolean);
}

function normalizePathPoint(value) {
  if (Array.isArray(value) && value.length >= 2) {
    return { x: Number(value[0]), y: Number(value[1]) };
  }
  if (!value || typeof value !== "object") return null;
  const point = {
    x: Number(value.x ?? value.lng ?? value.lon),
    y: Number(value.y ?? value.lat),
  };
  if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return null;
  if (value.type !== undefined) point.type = Number(value.type);
  if (value.clean_time !== undefined) point.clean_time = Number(value.clean_time);
  if (value.break_before === true) point.break_before = true;
  return point;
}

function buildMowedPathSegments(points, toScreen, canvasDiagonal) {
  const segments = [];
  let segment = [];
  let previous = null;
  const jumpLimit = Math.max(45, Math.min(180, (Number(canvasDiagonal) || 800) * 0.12));

  for (const point of points || []) {
    const pointType = Number(point?.type);
    const cleanTime = Number(point?.clean_time ?? point?.cleanTime ?? point?.cleanedCode);
    const isAppMowedPoint =
      point?.type === undefined ||
      [1, 2, 5, 8].includes(pointType) ||
      (Number.isFinite(cleanTime) && cleanTime > 0);
    if (!isAppMowedPoint) {
      if (segment.length) segments.push(segment);
      segment = [];
      previous = null;
      continue;
    }
    const screen = toScreen(point);
    if (!screen || !Number.isFinite(screen.x) || !Number.isFinite(screen.y)) continue;
    const jumped = previous && Math.hypot(screen.x - previous.x, screen.y - previous.y) > jumpLimit;
    if (point.break_before || jumped) {
      if (segment.length) segments.push(segment);
      segment = [];
    }
    segment.push(screen);
    previous = screen;
  }
  if (segment.length) segments.push(segment);
  return segments;
}

function extractCloudMowedPathPoints(state = {}) {
  const candidates = [
    state.mowed_path,
    state.mowedPath,
    state.cloud_path,
    state.cloudPath,
    state.history_path_info,
    state.historyPathInfo,
    state.his_path,
    state.hisPath,
    state.HisPath,
    state.record_path,
    state.recordPath,
    state.RecordPath,
    state.path_definition,
    state.pathDefinition,
    state.path_binary_paths,
    state.pathBinaryPaths,
    state.mowing_path,
    state.mowingPath,
    state.track,
    state.tracks,
    state.trajectory,
    state.path,
  ];

  for (const candidate of candidates) {
    const points = extractPathPoints(candidate);
    if (points.length >= 2) {
      return points;
    }
  }

  return [];
}

function mergeCloudAndLivePaths(cloudPath, livePath) {
  if (!cloudPath?.length) {
    return livePath || [];
  }
  if (!livePath?.length) {
    return cloudPath;
  }

  const merged = [...cloudPath];
  let startIndex = 0;
  for (let index = livePath.length - 1; index >= 0; index -= 1) {
    if (pointDistance(merged[merged.length - 1], livePath[index]) < 1) {
      startIndex = index + 1;
      break;
    }
  }

  let firstLive = startIndex === 0;
  for (const point of livePath.slice(startIndex)) {
    if (pointDistance(merged[merged.length - 1], point) >= 1) {
      merged.push(firstLive ? { ...point, break_before: true } : point);
      firstLive = false;
    }
  }
  return merged;
}

function pointDistance(a, b) {
  if (!a || !b) {
    return Number.POSITIVE_INFINITY;
  }
  return Math.hypot(Number(a.x) - Number(b.x), Number(a.y) - Number(b.y));
}

function rasterColor(value) {
  if (value === 255) {
    return [248, 250, 252, 255];
  }
  if (value === 160) {
    return [158, 166, 174, 255];
  }
  if (value === 128) {
    return [117, 125, 133, 255];
  }
  if (value === 0) {
    return [25, 32, 42, 255];
  }

  const shade = clamp(Number(value) || 0, 0, 255);
  return [shade, shade, shade, 255];
}

function applyMapCalibration(geometry, calibration = {}) {
  const next = {
    offsetX: Number(calibration.offsetX) || 0,
    offsetY: Number(calibration.offsetY) || 0,
    scaleX: Number(calibration.scaleX) || 1,
    scaleY: Number(calibration.scaleY) || 1,
    rotation: Number(calibration.rotation) || 0,
  };

  return {
    worldToScreen(point) {
      const mapPoint = geometry.worldToMap(point);
      const centered = {
        x: (Number(mapPoint.x) - 0.5) * next.scaleX,
        y: (Number(mapPoint.y) - 0.5) * next.scaleY,
      };
      const cos = Math.cos(next.rotation);
      const sin = Math.sin(next.rotation);
      const calibrated = {
        x: centered.x * cos - centered.y * sin + 0.5 + next.offsetX,
        y: centered.x * sin + centered.y * cos + 0.5 + next.offsetY,
      };
      return geometry.mapToScreen(calibrated);
    },
  };
}

function decodeRasterRuns(raster, width, height) {
  if (!Array.isArray(raster?.runs)) {
    return null;
  }

  const pixels = new Uint8Array(width * height);
  let offset = 0;
  for (let index = 0; index < raster.runs.length - 1; index += 2) {
    const value = clamp(Number(raster.runs[index]) || 0, 0, 255);
    const count = Number(raster.runs[index + 1]);
    if (!Number.isFinite(count) || count <= 0) {
      continue;
    }
    pixels.fill(value, offset, Math.min(width * height, offset + count));
    offset += count;
    if (offset >= width * height) {
      break;
    }
  }
  return pixels;
}

function zoneLabel(zone, isNoGo, noGoLabel = "No-go") {
  if (isNoGo) {
    const name = String(zone?.name || zone?.label || "").trim();
    return name && !/^zone\s*\d+$/i.test(name) ? name : noGoLabel;
  }

  const name = String(zone?.name || zone?.label || "").trim();
  if (name) {
    return name;
  }

  return zone?.id === undefined || zone?.id === null ? "Zone" : `Zone ${zone.id}`;
}

function roundRect(ctx, x, y, width, height, radius) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function polygonIntersectsViewport(points, width, height) {
  if (!Array.isArray(points) || points.length < 2 || width <= 0 || height <= 0) {
    return false;
  }

  const insideViewport = (point) =>
    point.x >= 0 && point.x <= width && point.y >= 0 && point.y <= height;
  if (points.some(insideViewport)) {
    return true;
  }

  const corners = [
    { x: 0, y: 0 },
    { x: width, y: 0 },
    { x: width, y: height },
    { x: 0, y: height },
  ];
  if (corners.some((corner) => pointInPolygon(corner, points))) {
    return true;
  }

  const viewportEdges = corners.map((corner, index) => [
    corner,
    corners[(index + 1) % corners.length],
  ]);
  for (let index = 0; index < points.length; index += 1) {
    const start = points[index];
    const end = points[(index + 1) % points.length];
    if (viewportEdges.some(([edgeStart, edgeEnd]) => segmentsIntersect(start, end, edgeStart, edgeEnd))) {
      return true;
    }
  }

  return false;
}

function pointInPolygon(point, polygon) {
  let inside = false;
  for (let current = 0, previous = polygon.length - 1; current < polygon.length; previous = current++) {
    const a = polygon[current];
    const b = polygon[previous];
    const crosses =
      (a.y > point.y) !== (b.y > point.y) &&
      point.x < ((b.x - a.x) * (point.y - a.y)) / ((b.y - a.y) || Number.EPSILON) + a.x;
    if (crosses) {
      inside = !inside;
    }
  }
  return inside;
}

function segmentsIntersect(a, b, c, d) {
  const cross = (p, q, r) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
  const onSegment = (p, q, r) =>
    Math.min(p.x, r.x) <= q.x &&
    q.x <= Math.max(p.x, r.x) &&
    Math.min(p.y, r.y) <= q.y &&
    q.y <= Math.max(p.y, r.y);

  const abC = cross(a, b, c);
  const abD = cross(a, b, d);
  const cdA = cross(c, d, a);
  const cdB = cross(c, d, b);
  const epsilon = 1e-9;

  if (
    ((abC > epsilon && abD < -epsilon) || (abC < -epsilon && abD > epsilon)) &&
    ((cdA > epsilon && cdB < -epsilon) || (cdA < -epsilon && cdB > epsilon))
  ) {
    return true;
  }

  return (
    (Math.abs(abC) <= epsilon && onSegment(a, c, b)) ||
    (Math.abs(abD) <= epsilon && onSegment(a, d, b)) ||
    (Math.abs(cdA) <= epsilon && onSegment(c, a, d)) ||
    (Math.abs(cdB) <= epsilon && onSegment(c, b, d))
  );
}





