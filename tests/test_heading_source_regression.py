"""Regression coverage for cloud/live robot heading source semantics."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "custom_components" / "anthbot_map" / "frontend"


class HeadingSourceRegressionTests(unittest.TestCase):
    def _renderer_data(self) -> str:
        geometry_source = base64.b64encode((FRONTEND / "geometry.js").read_bytes()).decode("ascii")
        renderer_source = (FRONTEND / "renderer.js").read_text(encoding="utf-8")
        renderer_source, replacements = re.subn(
            r'from "\./geometry\.js(?:\?v=[^"]+)?"',
            lambda _: f'from "data:text/javascript;base64,{geometry_source}"',
            renderer_source,
            count=1,
        )
        self.assertEqual(replacements, 1)
        return base64.b64encode(renderer_source.encode("utf-8")).decode("ascii")

    def _cloud_heading(self, state: str, pose: str = "{}") -> float:
        script = (
            f'const renderer = await import("data:text/javascript;base64,{self._renderer_data()}");\n'
            f'const fake = {{ state: {state} }};\n'
            f'const value = renderer.AnthbotMapRenderer.prototype.cloudHeadingDegrees.call(fake, {pose});\n'
            'process.stdout.write(JSON.stringify(value));\n'
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(json.loads(result.stdout))

    def test_verified_yaw_wins_over_conflicting_heading(self) -> None:
        value = self._cloud_heading(
            '{ raw_pose: { yaw: Math.PI * 500, heading: -90 }, cur_pose: { heading: -90 } }',
            '{ yaw: Math.PI * 500, heading: -90 }',
        )
        self.assertAlmostEqual(value, 90.0, places=7)

    def test_heading_remains_a_fallback_when_yaw_is_absent(self) -> None:
        value = self._cloud_heading('{ raw_pose: { heading: 90 } }', '{ heading: 90 }')
        self.assertAlmostEqual(value, 90.0, places=7)

    def test_live_pose_does_not_relabel_heading_as_yaw(self) -> None:
        card = (FRONTEND / "anthbot-map-card.js").read_text(encoding="utf-8")
        start = card.index("  computeLivePose(")
        end = card.index("\n  updateRenderer(", start)
        method = card[start:end]
        yaw_block = method.split("const fallbackYaw = [", 1)[1].split("const fallbackHeading = [", 1)[0]
        self.assertNotIn("heading", yaw_block)
        self.assertIn("const fallbackHeading = [", method)
        self.assertIn("merged.heading = fallbackHeading", method)

    def test_frontend_and_bundled_files_stay_identical(self) -> None:
        for name in ("renderer.js", "anthbot-map-card.js"):
            self.assertEqual(
                (FRONTEND / name).read_bytes(),
                (ROOT / "www" / "anthbot-map" / name).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
