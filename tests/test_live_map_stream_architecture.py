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

    def test_existing_map_listener_gets_compact_signature_after_stream_activation(self):
        source = (INTEGRATION / "lawn_mower.py").read_text(encoding="utf-8")
        setup_start = source.index("async def async_setup_entry")
        setup_end = source.index("class AnthbotLawnMowerEntity", setup_start)
        setup = source[setup_start:setup_end]
        self.assertIn('live_data.get("frontend_ready")', setup)
        self.assertIn(
            "_recorder_v2467._map_live_signature = _compact_write_signature", setup
        )

    def test_websocket_protocol_and_compatibility_gate_exist(self):
        source = (INTEGRATION / "live_map_stream.py").read_text(encoding="utf-8")
        self.assertIn('"anthbot_map/subscribe_live"', source)
        self.assertIn("async_add_executor_job", source)
        self.assertIn("live_stream_available", source)
        self.assertIn("_install_compact_map_entity", source)
        self.assertIn("frontend_ready", source)

    def test_websocket_cleanup_is_registered_before_success_is_visible(self):
        source = (INTEGRATION / "live_map_stream.py").read_text(encoding="utf-8")
        handler_start = source.index("async def _websocket_subscribe_live")
        handler_end = source.index("async def _async_ensure_frontend_resource", handler_start)
        handler = source[handler_start:handler_end]
        register_pos = handler.index('connection.subscriptions[msg["id"]] = unsubscribe')
        result_pos = handler.index('connection.send_result(msg["id"])')
        activate_pos = handler.index("hub.activate_subscriber")
        self.assertLess(register_pos, result_pos)
        self.assertLess(result_pos, activate_pos)
        self.assertIn("subscribe_pending", handler)
        self.assertIn("async_prepare_snapshot", handler)

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
        self.assertIn("window_start_index", text)
        self.assertIn("append_from_index", text)
        self.assertIn("live_stream_available !== true", text)


if __name__ == "__main__":
    unittest.main()
