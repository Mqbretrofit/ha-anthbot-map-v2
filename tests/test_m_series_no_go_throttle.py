from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/anthbot_map/models/m_series_path.py"


class MSeriesNoGoThrottleSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_live_no_go_scan_is_bounded_to_five_seconds(self) -> None:
        self.assertIn("_NO_GO_LIVE_MIN_SECONDS = 5.0", self.source)
        self.assertIn("time.monotonic()", self.source)
        self.assertIn("now - last_run < _NO_GO_LIVE_MIN_SECONDS", self.source)
        self.assertIn("live=True", self.source)

    def test_cache_key_uses_path_revision_not_transient_list_identity(self) -> None:
        self.assertIn('definition["_m_series_revision"]', self.source)
        self.assertIn('definition.get("_m_series_revision")', self.source)
        self.assertIn("_m_series_test4_revision", self.source)
        self.assertNotIn("id(points)", self.source)

    def test_heavy_geometry_is_offloaded_from_home_assistant_event_loop(self) -> None:
        self.assertIn("async_add_executor_job", self.source)
        self.assertIn("_evaluate_no_go_worker", self.source)
        self.assertIn("asyncio.Lock()", self.source)
        self.assertIn("await _update_no_go_check", self.source)

    def test_area_or_new_path_bypasses_live_throttle(self) -> None:
        self.assertIn("area_unchanged", self.source)
        self.assertIn("path_unchanged", self.source)
        self.assertIn("_m_series_no_go_area_token", self.source)
        self.assertIn("_m_series_no_go_path_id", self.source)

    def test_live_path_and_pose_forwarding_remains_enabled(self) -> None:
        for marker in (
            'forwarded["path"] = points',
            'forwarded["mowed_path"] = points',
            'forwarded["cloud_path"] = points',
            'forwarded["pose"] = pose',
            'forwarded["cur_pose"] = pose',
        ):
            self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
