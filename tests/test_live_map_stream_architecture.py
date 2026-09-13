"""Source-level guards for the live-map/state separation."""

from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


class TestLiveMapStreamArchitecture(unittest.TestCase):
    def test_lawn_mower_platform_starts_live_map_transport(self):
        source = (INTEGRATION / "lawn_mower.py").read_text(encoding="utf-8")
        self.assertIn("async_setup_live_map_stream", source)
        self.assertIn(
            "await async_setup_live_map_stream(hass, entry, coordinators)", source
        )

    def test_websocket_protocol_and_compatibility_gate_exist(self):
        source = (INTEGRATION / "live_map_stream.py").read_text(encoding="utf-8")
        self.assertIn('"anthbot_map/subscribe_live"', source)
        self.assertIn("async_add_executor_job", source)
        self.assertIn("live_stream_available", source)
        self.assertIn("_install_compact_map_entity", source)
        self.assertIn("frontend_ready", source)

    def test_compact_entity_does_not_embed_live_geometry(self):
        source = (INTEGRATION / "live_map_stream.py").read_text(encoding="utf-8")
        start = source.index("def _compact_extra_state_attributes")
        end = source.index("def _compact_write_signature", start)
        compact = source[start:end]
        for forbidden in (
            '"path":',
            '"cloud_path":',
            '"mowed_path":',
            '"pose":',
            '"cur_pose":',
            '"map_raster":',
            '"area_definition":',
            '"map_binary_paths":',
            '"path_binary_paths":',
        ):
            self.assertNotIn(forbidden, compact)

    def test_frontend_patch_is_bundled_identically(self):
        source = ROOT / "www" / "anthbot-map" / "live-map-stream.js"
        bundled = INTEGRATION / "frontend" / "live-map-stream.js"
        self.assertEqual(source.read_bytes(), bundled.read_bytes())
        text = source.read_text(encoding="utf-8")
        self.assertIn("subscribeMessage", text)
        self.assertIn("sequence gap", text)
        self.assertIn("trim_before_index", text)
        self.assertIn("live_stream_available !== true", text)


if __name__ == "__main__":
    unittest.main()
