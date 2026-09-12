"""Regression guards for v2.4.6.5 Recorder throttling."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
RECORDER_FIX = INTEGRATION / "models" / "recorder_v2465.py"
COMMON = INTEGRATION / "models" / "m_series_common.py"
RELIABILITY = INTEGRATION / "models" / "reliability_v2465.py"


class V2465RecorderTests(unittest.TestCase):
    def test_fix_modules_compile(self) -> None:
        for path in (RECORDER_FIX, RELIABILITY):
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")

    def test_map_entity_is_throttled_without_throttling_coordinator(self) -> None:
        source = RECORDER_FIX.read_text(encoding="utf-8")
        self.assertIn("_MAP_STATE_MIN_SECONDS = 5.0", source)
        self.assertIn("AnthbotMapSensorEntity._handle_coordinator_update", source)
        self.assertIn("_anthbot_last_map_state_write", source)
        self.assertNotIn("async_set_updated_data", source)
        self.assertNotIn("_async_handle_live_shadow", source)

    def test_no_go_recorder_payload_keeps_only_episode_values(self) -> None:
        source = RECORDER_FIX.read_text(encoding="utf-8")
        self.assertIn('"no_go_path_crossing"', source)
        for key in (
            "path_id",
            "crossing_detected",
            "boundary_crossings",
            "points_inside",
            "traversals",
            "zone_ids",
        ):
            self.assertIn(f'"{key}"', source)
        self.assertNotIn('"checked_point_count"', source)
        self.assertNotIn('"checked_segment_count"', source)
        self.assertNotIn('"last_crossing"', source)

    def test_recorder_fix_is_last_patch_layer(self) -> None:
        source = COMMON.read_text(encoding="utf-8")
        reliability = source.index("install_v2465_reliability_fixes()")
        recorder = source.index("install_recorder_v2465()", reliability)
        self.assertLess(reliability, recorder)


if __name__ == "__main__":
    unittest.main()
