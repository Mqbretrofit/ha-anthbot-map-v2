"""Regression coverage for independent mowing-path alignment."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "custom_components" / "anthbot_map" / "frontend"


class CalibrationAlignmentTests(unittest.TestCase):
    def test_path_rotation_is_aspect_aware_and_map_projection_is_invertible(self) -> None:
        source = base64.b64encode((FRONTEND / "geometry.js").read_bytes()).decode("ascii")
        script = f"""
const geometryModule = await import("data:text/javascript;base64,{source}");
const options = {{
  width: 1000,
  height: 500,
  bounds: {{ minX: 0, minY: 0, maxX: 1000, maxY: 500 }},
  aspectRatio: 2,
  fit: "contain",
}};
const base = geometryModule.createGeometry(options);
const calibrated = geometryModule.createGeometry({{
  ...options,
  calibration: {{ offsetX: 0.08, offsetY: 0.03, scaleX: 1.2, scaleY: 0.8, rotation: -0.05236 }},
}});
const a = {{ x: 0.25, y: 0.5 }};
const b = {{ x: 0.75, y: 0.5 }};
const distance = (geometry, first, second) => {{
  const p = geometry.mapToScreen(first);
  const q = geometry.mapToScreen(second);
  return Math.hypot(q.x - p.x, q.y - p.y);
}};
const sourcePoint = {{ x: 0.73, y: 0.21 }};
const projected = calibrated.mapToScreen(sourcePoint);
const roundTrip = calibrated.screenToMap(projected);
const legacyCalibration = {{ offsetX: 0.08, offsetY: 0.03, scaleX: 1.2, scaleY: 0.8, rotation: -0.05236 }};
const legacyCentered = {{
  x: (sourcePoint.x - 0.5) * legacyCalibration.scaleX,
  y: (sourcePoint.y - 0.5) * legacyCalibration.scaleY,
}};
const legacyExpected = {{
  x: (legacyCentered.x * Math.cos(legacyCalibration.rotation) - legacyCentered.y * Math.sin(legacyCalibration.rotation) + legacyCalibration.offsetX) * calibrated.map.width + calibrated.map.centerX,
  y: (legacyCentered.x * Math.sin(legacyCalibration.rotation) + legacyCentered.y * Math.cos(legacyCalibration.rotation) + legacyCalibration.offsetY) * calibrated.map.height + calibrated.map.centerY,
}};
const rotatedA = base.mapToScreen(base.calibrateMapPoint(a, {{ rotation: Math.PI / 2 }}));
const rotatedB = base.mapToScreen(base.calibrateMapPoint(b, {{ rotation: Math.PI / 2 }}));
process.stdout.write(JSON.stringify({{
  baseLength: distance(base, a, b),
  rotatedLength: Math.hypot(rotatedB.x - rotatedA.x, rotatedB.y - rotatedA.y),
  projected,
  legacyExpected,
  roundTrip,
}}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        values = json.loads(result.stdout)

        self.assertAlmostEqual(values["baseLength"], values["rotatedLength"], places=7)
        self.assertAlmostEqual(values["projected"]["x"], values["legacyExpected"]["x"], places=7)
        self.assertAlmostEqual(values["projected"]["y"], values["legacyExpected"]["y"], places=7)
        self.assertAlmostEqual(values["roundTrip"]["x"], 0.73, places=7)
        self.assertAlmostEqual(values["roundTrip"]["y"], 0.21, places=7)

    def test_mowing_layer_uses_full_independent_calibration(self) -> None:
        source = base64.b64encode((FRONTEND / "geometry.js").read_bytes()).decode("ascii")
        script = f"""
const geometryModule = await import("data:text/javascript;base64,{source}");
const geometry = geometryModule.createGeometry({{
  width: 1000,
  height: 500,
  bounds: {{ minX: 0, minY: 0, maxX: 1000, maxY: 500 }},
  aspectRatio: 2,
}});
const point = {{ x: 0.75, y: 0.5 }};
const transformed = geometry.calibrateMapPoint(point, {{
  offsetX: 0.08,
  offsetY: 0.03,
  scaleX: 1,
  scaleY: 1,
  rotation: Math.PI / 2,
}});
process.stdout.write(JSON.stringify({{ transformed, screen: geometry.mapToScreen(transformed) }}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        values = json.loads(result.stdout)

        self.assertAlmostEqual(values["transformed"]["x"], 0.58, places=7)
        self.assertAlmostEqual(values["transformed"]["y"], 1.03, places=7)
        self.assertAlmostEqual(values["screen"]["x"], 580, places=7)
        self.assertAlmostEqual(values["screen"]["y"], 515, places=7)

    def test_ui_separates_path_alignment_from_robot_direction(self) -> None:
        card = (FRONTEND / "anthbot-map-card.js").read_text(encoding="utf-8")
        renderer = (FRONTEND / "renderer.js").read_text(encoding="utf-8")
        calibration = (FRONTEND / "calibration.js").read_text(encoding="utf-8")
        translations = (FRONTEND / "i18n.js").read_text(encoding="utf-8")

        self.assertIn('robotFit: "Robot calibration"', translations)
        self.assertIn('mowingPathFit: "Mowing path calibration"', translations)
        self.assertIn('robotFit: "Robot kalibráció"', translations)
        self.assertIn('mowingPathFit: "Nyírási útvonal kalibráció"', translations)
        self.assertIn('data-robot-calibration="up"', card)
        self.assertIn('data-mowing-path-calibration="shorter"', card)
        self.assertIn('data-mowing-path-calibration="taller"', card)
        self.assertIn('data-robot-heading="left"', card)
        self.assertNotIn('data-robot-calibration="rotate-left-large"', card)
        self.assertIn("geometry.mapToScreenWithLayerCalibration(mapPoint, mowingPathCalibration)", renderer)
        self.assertIn("geometry.mapToScreenWithLayerCalibration(mapPoint, {", renderer)
        self.assertIn("offsetX: Number(robotCalibration.offsetX) || 0", renderer)
        self.assertIn('`  scaleY: ${formatNumber(next.scaleY)}`', calibration)

    def test_layer_controls_follow_displayed_map_axes_after_map_rotation(self) -> None:
        source = base64.b64encode((FRONTEND / "geometry.js").read_bytes()).decode("ascii")
        script = f"""
const geometryModule = await import("data:text/javascript;base64,{source}");
const geometry = geometryModule.createGeometry({{
  width: 1000,
  height: 500,
  bounds: {{ minX: 0, minY: 0, maxX: 1000, maxY: 500 }},
  aspectRatio: 2,
  calibration: {{ rotation: Math.PI / 2 }},
}});
const center = {{ x: 0.5, y: 0.5 }};
const base = geometry.mapToScreenWithLayerCalibration(center, {{}});
const left = geometry.mapToScreenWithLayerCalibration(center, {{ offsetX: -0.01 }});
const right = geometry.mapToScreenWithLayerCalibration(center, {{ offsetX: 0.01 }});
const up = geometry.mapToScreenWithLayerCalibration(center, {{ offsetY: -0.01 }});
const down = geometry.mapToScreenWithLayerCalibration(center, {{ offsetY: 0.01 }});

const horizontalA = {{ x: 0.5, y: 0.25 }};
const horizontalB = {{ x: 0.5, y: 0.75 }};
const verticalA = {{ x: 0.25, y: 0.5 }};
const verticalB = {{ x: 0.75, y: 0.5 }};
const distance = (first, second) => Math.hypot(second.x - first.x, second.y - first.y);
const project = (point, layer = {{}}) => geometry.mapToScreenWithLayerCalibration(point, layer);
const baseWidth = distance(project(horizontalA), project(horizontalB));
const narrowerWidth = distance(project(horizontalA, {{ scaleX: 0.8 }}), project(horizontalB, {{ scaleX: 0.8 }}));
const widerWidth = distance(project(horizontalA, {{ scaleX: 1.2 }}), project(horizontalB, {{ scaleX: 1.2 }}));
const baseHeight = distance(project(verticalA), project(verticalB));
const shorterHeight = distance(project(verticalA, {{ scaleY: 0.8 }}), project(verticalB, {{ scaleY: 0.8 }}));
const tallerHeight = distance(project(verticalA, {{ scaleY: 1.2 }}), project(verticalB, {{ scaleY: 1.2 }}));

process.stdout.write(JSON.stringify({{
  base,
  left,
  right,
  up,
  down,
  baseWidth,
  narrowerWidth,
  widerWidth,
  baseHeight,
  shorterHeight,
  tallerHeight,
}}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        values = json.loads(result.stdout)

        self.assertAlmostEqual(values["left"]["x"] - values["base"]["x"], -10, places=7)
        self.assertAlmostEqual(values["left"]["y"] - values["base"]["y"], 0, places=7)
        self.assertAlmostEqual(values["right"]["x"] - values["base"]["x"], 10, places=7)
        self.assertAlmostEqual(values["right"]["y"] - values["base"]["y"], 0, places=7)
        self.assertAlmostEqual(values["up"]["x"] - values["base"]["x"], 0, places=7)
        self.assertAlmostEqual(values["up"]["y"] - values["base"]["y"], -5, places=7)
        self.assertAlmostEqual(values["down"]["x"] - values["base"]["x"], 0, places=7)
        self.assertAlmostEqual(values["down"]["y"] - values["base"]["y"], 5, places=7)
        self.assertAlmostEqual(values["narrowerWidth"] / values["baseWidth"], 0.8, places=7)
        self.assertAlmostEqual(values["widerWidth"] / values["baseWidth"], 1.2, places=7)
        self.assertAlmostEqual(values["shorterHeight"] / values["baseHeight"], 0.8, places=7)
        self.assertAlmostEqual(values["tallerHeight"] / values["baseHeight"], 1.2, places=7)

    def test_legacy_robot_rotation_does_not_rotate_mowing_path(self) -> None:
        source = base64.b64encode((FRONTEND / "calibration.js").read_bytes()).decode("ascii")
        script = f"""
const calibration = await import("data:text/javascript;base64,{source}");
const legacy = calibration.readMowingPathCalibration({{
  robotCalibration: {{ offsetX: 0.08, offsetY: 0.03, scaleX: 2, rotation: Math.PI / 2 }},
}});
const explicit = calibration.readMowingPathCalibration({{
  robotCalibration: {{ rotation: Math.PI / 2 }},
  mowingPathCalibration: {{ offsetX: 0.02, rotation: -0.05236 }},
}});
process.stdout.write(JSON.stringify({{ legacy, explicit }}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        values = json.loads(result.stdout)

        self.assertEqual(values["legacy"]["offsetX"], 0.08)
        self.assertEqual(values["legacy"]["offsetY"], 0.03)
        self.assertEqual(values["legacy"]["scaleX"], 1)
        self.assertEqual(values["legacy"]["rotation"], 0)
        self.assertEqual(values["explicit"]["offsetX"], 0.02)
        self.assertEqual(values["explicit"]["rotation"], -0.05236)

    def test_cloud_heading_mirrors_only_the_horizontal_axis(self) -> None:
        geometry_source = base64.b64encode((FRONTEND / "geometry.js").read_bytes()).decode("ascii")
        renderer_source = (FRONTEND / "renderer.js").read_text(encoding="utf-8")
        renderer_source = renderer_source.replace(
            'from "./geometry.js?v=149"',
            f'from "data:text/javascript;base64,{geometry_source}"',
            1,
        )
        renderer_data = base64.b64encode(renderer_source.encode("utf-8")).decode("ascii")
        script = f"""
const renderer = await import("data:text/javascript;base64,{renderer_data}");
const degrees = (radians) => radians * 180 / Math.PI;
const cardinal = [0, 90, 180, -90].map((heading) =>
  degrees(renderer.cloudHeadingToCanvasRadians(heading))
);
process.stdout.write(JSON.stringify(cardinal));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        cardinal = json.loads(result.stdout)

        self.assertAlmostEqual(cardinal[0], 180, places=7)
        self.assertAlmostEqual(cardinal[1], 90, places=7)
        self.assertAlmostEqual(cardinal[2], 0, places=7)
        self.assertAlmostEqual(cardinal[3], -90, places=7)


if __name__ == "__main__":
    unittest.main()
