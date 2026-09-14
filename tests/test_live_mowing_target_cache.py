"""Regression guards for the restored v2.4.6.4 mowing-target flow."""

from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "custom_components" / "anthbot_map" / "frontend" / "live-map-stream.js"
BUNDLED = ROOT / "www" / "anthbot-map" / "live-map-stream.js"
CALIBRATION = ROOT / "www" / "anthbot-map" / "calibration.js"
GENIE_PRESENTATION = (
    ROOT
    / "custom_components"
    / "anthbot_map"
    / "models"
    / "genie_progress_presentation.py"
)


class TestLiveMowingTargetCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frontend = FRONTEND.read_text(encoding="utf-8")
        cls.bundled = BUNDLED.read_text(encoding="utf-8")
        cls.calibration = CALIBRATION.read_text(encoding="utf-8")
        cls.genie = GENIE_PRESENTATION.read_text(encoding="utf-8")

    def test_mirrors_are_identical(self) -> None:
        self.assertEqual(self.frontend, self.bundled)

    def test_live_transport_does_not_own_mowing_target_or_local_cache(self) -> None:
        for forbidden in (
            "lastMowingProgressStorageKey",
            "readLastMowingProgress",
            "writeLastMowingProgress",
            "specificMowingTarget",
            "selectedMowingTarget",
            "armSelectedMowingTarget",
            "preserveStoppedMowingProgress",
            "patchedUpdateMowingProgressStatus",
        ):
            self.assertNotIn(forbidden, self.frontend)
        self.assertIn("this.updateMowingProgressStatus?.();", self.frontend)

    def test_v2464_calibration_resolves_exact_target_from_ha_state(self) -> None:
        self.assertIn("const resolveProgressTarget", self.calibration)
        self.assertIn("last_mowing_task", self.calibration)
        self.assertIn("active_zone_ids", self.calibration)
        self.assertIn("learned_zone_mowing_key", self.calibration)
        self.assertIn('source.startsWith("full_map_area")', self.calibration)
        self.assertIn('return card.t("fullArea")', self.calibration)
        self.assertIn("zoneTarget(card, learnedIds)", self.calibration)
        self.assertIn("line.hidden = false;", self.calibration)

    def test_genie_backend_restores_v2464_target_evidence_after_trim(self) -> None:
        self.assertIn('attributes["active_zone_ids"]', self.genie)
        self.assertIn('attributes["learned_zone_mowing_key"]', self.genie)
        self.assertIn('attributes["progress_source"]', self.genie)
        self.assertIn('attributes["last_mowing_task"]', self.genie)
        self.assertIn("_progress_learning_debug", self.genie)
        self.assertIn("_progress_target_area", self.genie)

    def test_genie_backend_keeps_last_percentage_after_stop(self) -> None:
        self.assertIn('cache["progress"]', self.genie)
        self.assertIn("numeric >= previous", self.genie)
        self.assertIn("return latched", self.genie)


if __name__ == "__main__":
    unittest.main()
