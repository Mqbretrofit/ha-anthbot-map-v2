"""Regression coverage for the v2.3.0 mowing-history fixes."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import unittest

from test_map_archive import api


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
CARD = INTEGRATION / "frontend" / "anthbot-map-card.js"


class MowingHistoryV230Tests(unittest.TestCase):
    """Protect multi-mower targeting, history geometry, and privacy fixes."""

    def test_history_path_uses_confirmed_scale_without_raw_debug_bytes(self) -> None:
        header = bytearray(22)
        header[0] = 22
        header[1] = 1
        header[2] = 3
        header[3] = 5
        struct.pack_into("<i", header, 4, 1)
        struct.pack_into("<i", header, 8, 123456)
        struct.pack_into("<h", header, 12, 90)
        struct.pack_into("<Q", header, 14, 987654321)
        payload = bytes(header) + struct.pack("<hhB", 123, -45, 1)

        decoded = api._decode_path_definition(payload)

        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded["format"], "mgs-v1-history")
        self.assertEqual(decoded["coordinate_scale"], 10)
        self.assertEqual(decoded["_path_points"][0]["x"], 1230)
        self.assertEqual(decoded["_path_points"][0]["y"], -450)
        self.assertNotIn("_first_bytes", decoded)
        self.assertNotIn("_size", decoded)

    def test_map_sensor_exposes_serial_and_unresolved_target_is_safe(self) -> None:
        sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        init_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")

        self.assertIn('"serial_number": self.coordinator.client.serial_number', sensor_source)
        self.assertIn("return [] if target_requested else coordinators", init_source)

    def test_captured_identifiers_and_temporary_debug_payloads_are_absent(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (INTEGRATION / "m_series_compat.py", INTEGRATION / "api.py")
        )
        self.assertNotIn("26130LGR", sources)
        self.assertNotIn("ANTHBOT MODEL TEST", sources)
        self.assertNotIn("CURPATH COORDS", sources)
        self.assertNotIn("_shadow_diagnostic_payload", sources)
        self.assertNotIn("_first_bytes", sources)

    def test_long_duration_and_blade_off_filtering(self) -> None:
        source = CARD.read_text(encoding="utf-8")
        start = source.index("const ENTITY_MAP")
        guarded_registration = 'if (!customElements.get("anthbot-map-card"))'
        legacy_registration = 'customElements.define("anthbot-map-card"'
        end_marker = guarded_registration if guarded_registration in source else legacy_registration
        source = source[start : source.index(end_marker)]
        assertions = r"""
const longSeconds = normalizeRecordDurationSeconds(21600, "mow_time");
const explicitMilliseconds = normalizeRecordDurationSeconds(21600000, "duration_ms");
const filtered = buildDetailPathSegments([
  {x: 0, y: 0, type: 0},
  {x: 10, y: 0, type: 1},
  {x: 20, y: 0, type: 1},
  {x: 30, y: 0, type: 0},
], 2500);
const fallback = buildDetailPathSegments([
  {x: 0, y: 0, type: 0},
  {x: 10, y: 0, type: 0},
], 2500);
process.stdout.write(JSON.stringify({longSeconds, explicitMilliseconds, filtered, fallback}));
"""
        script = "global.HTMLElement = class {};\n" + source + assertions
        result = subprocess.run(
            ["node", "-"],
            check=True,
            capture_output=True,
            input=script,
            text=True,
        )
        values = json.loads(result.stdout)

        self.assertEqual(values["longSeconds"], 21600)
        self.assertEqual(values["explicitMilliseconds"], 21600)
        self.assertEqual([point["x"] for point in values["filtered"][0]], [10, 20])
        self.assertEqual([point["x"] for point in values["fallback"][0]], [0, 10])

    def test_release_version_and_frontend_mirrors_are_consistent(self) -> None:
        manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        init_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

        self.assertEqual(manifest["version"], "2.4.3-beta.2")
        self.assertIn('?v=2.4.3-beta.2', init_source)
        self.assertIn("Release tag $tag does not match manifest version", workflow)
        for filename in ("anthbot-map-card.js", "i18n.js", "styles.css"):
            self.assertEqual(
                (INTEGRATION / "frontend" / filename).read_bytes(),
                (ROOT / "www" / "anthbot-map" / filename).read_bytes(),
                filename,
            )


if __name__ == "__main__":
    unittest.main()
