from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/anthbot_map/models/n8_path.py"


class N8NoGoThrottleSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_n8_live_path_uses_shared_live_throttle(self) -> None:
        self.assertIn("_path._update_no_go_check", self.source)
        self.assertIn("live=True", self.source)

    def test_n8_initializes_shared_no_go_cache_state(self) -> None:
        for marker in (
            "_m_series_test4_revision = 0",
            "_m_series_no_go_geometry_signature = None",
            "_m_series_no_go_path_id = None",
            "_m_series_no_go_last_monotonic = 0.0",
        ):
            self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
