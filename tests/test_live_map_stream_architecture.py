"""Architecture guards for the dedicated ANTHBOT live-map transport."""

from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]


class TestLiveMapStreamArchitecture(unittest.TestCase):
    def test_websocket_protocol_and_compatibility_gate_exist(self):
        backend = (ROOT / "custom_components" / "anthbot_map" / "live_map_stream.py").read_text(encoding="utf-8")
        frontend = (ROOT / "www" / "anthbot-map" / "live-map-stream.js").read_text(encoding="utf-8")
        self.assertIn('"anthbot_map/subscribe_live"', backend)
        self.assertIn('"anthbot_map/subscribe_live"', frontend)
        self.assertIn("live_stream_available", backend)
        self.assertIn("live_stream_available", frontend)

    def test_compact_entity_does_not_embed_live_geometry(self):
        source = (ROOT / "custom_components" / "anthbot_map" / "live_map_stream.py").read_text(encoding="utf-8")
        start = source.index("def _compact_extra_state_attributes")
        end = source.index("def _compact_write_signature", start)
        compact = source[start:end]
        for forbidden in (
            '"path":',
            '"cloud_path":',
            '"mowed_path":',
            '"trajectory":',
            '"pose":',
            '"cur_pose":',
            '"area_definition":',
            '"map_raster":',
        ):
            self.assertNotIn(forbidden, compact)

    def test_lawn_mower_platform_starts_live_map_transport(self):
        source = (ROOT / "custom_components" / "anthbot_map" / "lawn_mower.py").read_text(encoding="utf-8")
        self.assertIn("async_setup_live_map_stream", source)

    def test_frontend_patch_is_bundled_identically(self):
        source = (ROOT / "custom_components" / "anthbot_map" / "frontend" / "live-map-stream.js").read_text(encoding="utf-8")
        bundled = (ROOT / "www" / "anthbot-map" / "live-map-stream.js").read_text(encoding="utf-8")
        self.assertEqual(source, bundled)

    def test_websocket_cleanup_is_registered_before_success_is_visible(self):
        source = (ROOT / "custom_components" / "anthbot_map" / "live_map_stream.py").read_text(encoding="utf-8")
        registered = source.index('connection.subscriptions[msg["id"]] = unsubscribe')
        result = source.index('connection.send_result(msg["id"])')
        self.assertLess(registered, result)

    def test_existing_bound_map_listener_is_rebound_to_compact_handler(self):
        source = (ROOT / "custom_components" / "anthbot_map" / "live_map_stream.py").read_text(encoding="utf-8")
        self.assertIn("_async_rebind_existing_map_entities", source)
        self.assertIn("entity.async_write_ha_state", source)

    def test_existing_map_listener_gets_quiet_signature_after_stream_activation(self):
        source = (ROOT / "custom_components" / "anthbot_map" / "live_map_stream.py").read_text(encoding="utf-8")
        self.assertIn("_anthbot_live_compact_signature", source)
        self.assertIn("_compact_write_signature", source)

    def test_live_map_write_signature_ignores_stream_and_diagnostic_churn(self):
        source = (ROOT / "custom_components" / "anthbot_map" / "live_map_stream.py").read_text(encoding="utf-8")
        start = source.index("def _compact_write_signature")
        end = source.index("def _compact_map_entity_write", start)
        signature = source[start:end]
        self.assertNotIn("runtime_performance", signature)
        self.assertNotIn("path_time", signature)
        self.assertNotIn("map_time", signature)

    def test_live_frontend_keeps_lightweight_status_refresh_without_polling_map(self):
        source = ROOT / "www" / "anthbot-map" / "live-map-stream.js"
        text = source.read_text(encoding="utf-8")
        self.assertIn("originalStartRefreshTimer", text)
        self.assertIn("originalRefreshEntities", text)
        self.assertIn("originalRefreshEntityIds", text)
        self.assertIn("entityId !== mapEntityId", text)
        self.assertIn("syncLiveCardFromHass(this);", text)
        self.assertIn("return originalStartRefreshTimer.apply(this, args);", text)
        self.assertIn("this.updateMowingProgressStatus?.();", text)

        refresh_start = text.index("proto.refreshEntities = function patchedRefreshEntities")
        refresh_end = text.index("const hassDescriptor", refresh_start)
        live_refresh = text[refresh_start:refresh_end]
        self.assertIn("if (liveStreamAvailable(this))", live_refresh)
        self.assertIn("return Promise.resolve();", live_refresh)
        self.assertNotIn('callService("homeassistant"', live_refresh)

    def test_stopped_mowing_progress_remains_visible_until_next_task(self):
        source = ROOT / "www" / "anthbot-map" / "live-map-stream.js"
        text = source.read_text(encoding="utf-8")
        self.assertIn("function preserveStoppedMowingProgress", text)
        self.assertIn("anthbot-map-last-mowing-progress", text)
        self.assertIn("function canonicalMowingIsActive", text)
        # A freshly armed exact command target may render from 0% immediately;
        # an unrelated active task with no known target must not resurrect the
        # previous stopped task's percentage or label.
        self.assertIn("if (activeMowing && !commandTarget) return;", text)
        self.assertIn("line.hidden = false;", text)
        self.assertIn("patchedUpdateMowingProgressStatus", text)
        self.assertIn("preserveStoppedMowingProgress(this);", text)

    def test_stopped_mowing_progress_preserves_exact_task_target(self):
        source = ROOT / "www" / "anthbot-map" / "live-map-stream.js"
        text = source.read_text(encoding="utf-8")
        self.assertIn("function rememberedMowingTarget", text)
        self.assertIn("last_mowing_task", text)
        self.assertIn("active_zone_ids", text)
        self.assertIn("learned_zone_mowing_key", text)
        self.assertIn('source.startsWith("full_map_area")', text)
        self.assertIn('card.t?.("fullArea")', text)
        self.assertIn("mowingZoneTarget", text)
        self.assertIn("armSelectedMowingTarget(this);", text)

    def test_live_frontend_retries_failed_subscription_without_page_reload(self):
        source = ROOT / "www" / "anthbot-map" / "live-map-stream.js"
        text = source.read_text(encoding="utf-8")
        backend = (ROOT / "custom_components" / "anthbot_map" / "live_map_stream.py").read_text(encoding="utf-8")
        self.assertIn("function scheduleSubscriptionRetry", text)
        self.assertIn('scheduleSubscriptionRetry(card, "subscription failed")', text)
        self.assertIn("ANTHBOT_LIVE_RETRY_MAX_MS", text)
        self.assertRegex(backend, r'LIVE_RESOURCE_URL = f"\{LIVE_RESOURCE_PATH\}\?v=247-live2-[0-9]+"')


if __name__ == "__main__":
    unittest.main()
