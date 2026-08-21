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
    def test_rotation_is_aspect_aware_and_projection_is_invertible(self) -> None:
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
const rotated = geometryModule.createGeometry({{
  ...options,
  calibration: {{ rotation: Math.PI / 2 }},
}});
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
const roundTrip = calibrated.screenToMap(calibrated.mapToScreen(sourcePoint));
process.stdout.write(JSON.stringify({{
  baseLength: distance(base, a, b),
  rotatedLength: distance(rotated, a, b),
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

        self.assertIn('robotFit: "Mowing path alignment"', translations)
        self.assertIn('robotFit: "Nyírási útvonal illesztése"', translations)
        self.assertIn('data-robot-calibration="shorter"', card)
        self.assertIn('data-robot-calibration="taller"', card)
        self.assertIn('data-robot-heading="left"', card)
        self.assertNotIn('data-robot-calibration="rotate-left-large"', card)
        self.assertIn("geometry.calibrateMapPoint(mapPoint, robotCalibration)", renderer)
        self.assertIn('`  scaleY: ${formatNumber(next.scaleY)}`', calibration)


if __name__ == "__main__":
    unittest.main()
