"""Regression test for model-specific robot heading orientation."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "custom_components" / "anthbot_map" / "frontend"


class ModelSpecificHeadingTests(unittest.TestCase):
    def test_m9_direct_and_genie_horizontal_mirror(self) -> None:
        geometry_source = base64.b64encode((FRONTEND / "geometry.js").read_bytes()).decode("ascii")
        renderer_source = (FRONTEND / "renderer.js").read_text(encoding="utf-8")
        renderer_source, replacements = re.subn(
            r'from "\./geometry\.js(?:\?v=[^"]+)?"',
            lambda _: f'from "data:text/javascript;base64,{geometry_source}"',
            renderer_source,
            count=1,
        )
        self.assertEqual(replacements, 1)
        renderer_data = base64.b64encode(renderer_source.encode("utf-8")).decode("ascii")
        script = f"""
const renderer = await import("data:text/javascript;base64,{renderer_data}");
const degrees = (radians) => radians * 180 / Math.PI;
const headings = [0, 90, 180, -90];
const m9 = headings.map((heading) => degrees(renderer.cloudHeadingToCanvasRadians(heading, "M9 Pro")));
const genie = headings.map((heading) => degrees(renderer.cloudHeadingToCanvasRadians(heading, "Genie 1000")));
process.stdout.write(JSON.stringify({{ m9, genie }}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        values = json.loads(result.stdout)
        expected_m9 = [0, 90, 180, -90]
        expected_genie = [0, -90, -180, 90]
        for actual, expected in zip(values["m9"], expected_m9, strict=True):
            self.assertAlmostEqual(actual, expected, places=7)
        for actual, expected in zip(values["genie"], expected_genie, strict=True):
            self.assertAlmostEqual(actual, expected, places=7)

    def test_card_passes_model_to_renderer(self) -> None:
        card = (FRONTEND / "anthbot-map-card.js").read_text(encoding="utf-8")
        renderer = (FRONTEND / "renderer.js").read_text(encoding="utf-8")
        self.assertIn("robotModel: this.entity?.attributes?.model", card)
        self.assertIn(
            "cloudHeadingToCanvasRadians(this.cloudHeadingDegrees(pose), this.options.robotModel)",
            renderer,
        )


if __name__ == "__main__":
    unittest.main()
