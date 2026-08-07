"""Regression test for Home Assistant TrackerEntity import compatibility."""

from pathlib import Path
import unittest


SOURCE_PATH = Path(__file__).parents[1] / "custom_components/anthbot_map/device_tracker.py"


class TestDeviceTrackerCompatibility(unittest.TestCase):
    def test_tracker_entity_has_legacy_import_fallback(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("except ImportError", source)
        self.assertIn("device_tracker.config_entry import TrackerEntity", source)


if __name__ == "__main__":
    unittest.main()
