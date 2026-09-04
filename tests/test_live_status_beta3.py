"""Regression guard for the beta3 live mowing status UI."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components" / "anthbot_map" / "frontend" / "anthbot-map-card.js"


class LiveStatusBeta3Tests(unittest.TestCase):
    def test_live_status_keeps_target_and_progress(self) -> None:
        source = CARD.read_text(encoding="utf-8")
        self.assertIn('data-role="mowing-live-line"', source)
        self.assertIn('data-role="mowing-live-target"', source)
        self.assertIn('data-role="mowing-live-progress"', source)
        self.assertIn('const progressEntity = this.getRelatedEntity("mowingProgress")', source)
        self.assertIn('const progress = Number(progressEntity?.state)', source)
        self.assertIn('updateMowingProgressStatus()', source)


if __name__ == "__main__":
    unittest.main()
