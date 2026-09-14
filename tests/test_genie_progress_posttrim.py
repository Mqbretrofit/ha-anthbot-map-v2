"""Regression guards for the deferred v2.4.6.5 progress-attribute trim."""

from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
MODELS = ROOT / "custom_components" / "anthbot_map" / "models"


class TestGenieProgressPostTrim(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.posttrim = (MODELS / "genie_progress_posttrim.py").read_text(encoding="utf-8")
        cls.common = (MODELS / "m_series_common.py").read_text(encoding="utf-8")
        cls.reliability = (MODELS / "reliability_v2465.py").read_text(encoding="utf-8")

    def test_reliability_platform_trim_is_deferred_to_coordinator_init(self) -> None:
        self.assertIn("def _install_deferred_platform_patch", self.reliability)
        self.assertIn("previous_init(self, *args, **kwargs)", self.reliability)
        self.assertIn("_patch_platform_modules()", self.reliability)

    def test_posttrim_wrapper_runs_after_previous_coordinator_init(self) -> None:
        start = self.posttrim.index("def coordinator_init")
        body = self.posttrim[start:]
        previous_pos = body.index("previous_init(self, *args, **kwargs)")
        patch_pos = body.index("_patch_sensor_attributes()")
        self.assertLess(previous_pos, patch_pos)

    def test_posttrim_restores_exact_v2464_target_evidence(self) -> None:
        for required in (
            'attributes["active_zone_ids"]',
            'attributes["learned_zone_mowing_key"]',
            'attributes["progress_source"]',
            'attributes["last_mowing_task"]',
            'attributes["progress_presentation_latched"]',
            "active_manual_zone_ids",
            "_progress_learning_debug",
            "_progress_target_area",
        ):
            self.assertIn(required, self.posttrim)

    def test_posttrim_is_genie_mowing_progress_only(self) -> None:
        self.assertIn('getattr(description, "key", None) == "mowing_progress"', self.posttrim)
        self.assertIn('== "genie"', self.posttrim)

    def test_posttrim_installer_is_registered_after_session_latch(self) -> None:
        presentation_pos = self.common.index("install_genie_progress_presentation()")
        posttrim_pos = self.common.index("install_genie_progress_posttrim()")
        self.assertGreater(posttrim_pos, presentation_pos)


if __name__ == "__main__":
    unittest.main()
