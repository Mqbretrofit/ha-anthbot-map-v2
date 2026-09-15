from __future__ import annotations

from pathlib import Path
import textwrap


def replace_once(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 match in {path}, got {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


renderer_old = '''  cloudHeadingDegrees(pose) {
    const headingCandidates = [
      this.state.raw_pose?.heading,
      pose?.heading,
      this.state.cur_pose?.heading,
      this.state.curPose?.heading,
      this.state.map_scan_pose?.heading,
      this.state.mapScanPose?.heading,
    ];
    for (const value of headingCandidates) {
      const heading = Number(value);
      if (Number.isFinite(heading)) {
        return normalizeHeadingDegrees(heading);
      }
    }

    const yawCandidates = [
      this.state.raw_pose?.yaw,
      pose?.yaw,
      this.state.cur_pose?.yaw,
      this.state.curPose?.yaw,
      this.state.map_scan_pose?.yaw,
      this.state.mapScanPose?.yaw,
    ];
    for (const value of yawCandidates) {
      const yaw = Number(value);
      if (Number.isFinite(yaw)) {
        return milliRadiansToDegrees(yaw);
      }
    }
    return 0;
  }
'''
renderer_new = '''  cloudHeadingDegrees(pose) {
    // The cloud/app pose.yaw orientation is the source already verified on
    // real hardware. Live-map aliases can also expose `heading`, but that
    // field may use a different horizontal-axis convention. A real yaw
    // must therefore win whenever both representations are present.
    const yawCandidates = [
      this.state.raw_pose?.yaw,
      pose?.yaw,
      this.state.cur_pose?.yaw,
      this.state.curPose?.yaw,
      this.state.map_scan_pose?.yaw,
      this.state.mapScanPose?.yaw,
    ];
    for (const value of yawCandidates) {
      const yaw = Number(value);
      if (Number.isFinite(yaw)) {
        return milliRadiansToDegrees(yaw);
      }
    }

    const headingCandidates = [
      this.state.raw_pose?.heading,
      pose?.heading,
      this.state.cur_pose?.heading,
      this.state.curPose?.heading,
      this.state.map_scan_pose?.heading,
      this.state.mapScanPose?.heading,
    ];
    for (const value of headingCandidates) {
      const heading = Number(value);
      if (Number.isFinite(heading)) {
        return normalizeHeadingDegrees(heading);
      }
    }
    return 0;
  }
'''

card_old = '''  computeLivePose(attributes = this.entity?.attributes || {}) {
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
'''
card_new = '''  computeLivePose(attributes = this.entity?.attributes || {}) {
    const rawPose = attributes.pose && typeof attributes.pose === "object" ? attributes.pose : {};
    const coordinatePose = [rawPose, attributes.cur_pose, attributes.map_scan_pose].find((candidate) =>
      Number.isFinite(Number(candidate?.x)) && Number.isFinite(Number(candidate?.y)),
    );
    const poseYawEntity = this.getRelatedEntity("poseYaw");
    // Keep yaw and heading separate. They are different telemetry
    // representations and, on Genie live aliases, can use different axis
    // conventions. Copying heading into yaw makes the renderer interpret
    // degrees as milliradians and can mirror the horizontal direction.
    const fallbackYaw = [
      coordinatePose?.yaw,
      rawPose.yaw,
      poseYawEntity?.state,
    ].find((value) => Number.isFinite(Number(value)));
    const fallbackHeading = [
      coordinatePose?.heading,
      rawPose.heading,
    ].find((value) => Number.isFinite(Number(value)));
    const merged = coordinatePose ? { ...rawPose, ...coordinatePose } : { ...rawPose };
    if (fallbackYaw !== undefined) merged.yaw = fallbackYaw;
    if (fallbackHeading !== undefined) merged.heading = fallbackHeading;
    return merged;
  }
'''

for path in (
    "custom_components/anthbot_map/frontend/renderer.js",
    "www/anthbot-map/renderer.js",
):
    replace_once(path, renderer_old, renderer_new, "renderer heading-source priority")

for path in (
    "custom_components/anthbot_map/frontend/anthbot-map-card.js",
    "www/anthbot-map/anthbot-map-card.js",
):
    replace_once(path, card_old, card_new, "card yaw/heading separation")
    replace_once(
        path,
        'import { AnthbotMapRenderer } from "./renderer.js?v=243-heading-fix1";',
        'import { AnthbotMapRenderer } from "./renderer.js?v=2473-heading-source-fix1";',
        "renderer cache key",
    )

replace_once(
    "custom_components/anthbot_map/__init__.py",
    'FRONTEND_RESOURCE_URL = f"{FRONTEND_RESOURCE_PATH}?v=2.4.7.3"',
    'FRONTEND_RESOURCE_URL = f"{FRONTEND_RESOURCE_PATH}?v=2.4.7.3-heading-source-fix1"',
    "frontend resource cache key",
)

test_source = textwrap.dedent(
    """\
    \"\"\"Regression coverage for cloud/live robot heading source semantics.\"\"\"

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
                r'from "\\./geometry\\.js(?:\\?v=[^\"]+)?"',
                lambda _: f'from "data:text/javascript;base64,{geometry_source}"',
                renderer_source,
                count=1,
            )
            self.assertEqual(replacements, 1)
            return base64.b64encode(renderer_source.encode("utf-8")).decode("ascii")

        def _cloud_heading(self, state: str, pose: str = "{}") -> float:
            script = (
                f'const renderer = await import("data:text/javascript;base64,{self._renderer_data()}");\\n'
                f'const fake = {{ state: {state} }};\\n'
                f'const value = renderer.AnthbotMapRenderer.prototype.cloudHeadingDegrees.call(fake, {pose});\\n'
                'process.stdout.write(JSON.stringify(value));\\n'
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
            end = card.index("\\n  updateRenderer(", start)
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
    """
)
Path("tests/test_heading_source_regression.py").write_text(test_source, encoding="utf-8")
