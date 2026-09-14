"""Regression guards for Genie mowing-progress presentation semantics."""

from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


class TestGenieProgressPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (MODELS / "genie_progress_presentation.py").read_text(
            encoding="utf-8"
        )
        cls.common = (MODELS / "m_series_common.py").read_text(encoding="utf-8")

    def test_layer_is_genie_only_and_progress_only(self) -> None:
        self.assertIn('getattr(description, "key", None) == "mowing_progress"', self.source)
        self.assertIn('== "genie"', self.source)
        self.assertIn("model_family", self.source)

    def test_last_nonzero_progress_survives_stop_reset(self) -> None:
        self.assertIn('cache["progress"]', self.source)
        self.assertIn("numeric >= previous", self.source)
        self.assertIn('cache["active"] = False', self.source)
        self.assertIn("return latched", self.source)

    def test_new_mowing_session_resets_old_progress(self) -> None:
        self.assertIn("if not was_active:", self.source)
        self.assertIn("cache.clear()", self.source)
        self.assertIn('cache["active"] = True', self.source)

    def test_exact_target_metadata_survives_reliability_trimming(self) -> None:
        self.assertIn('attributes["last_mowing_task"]', self.source)
        self.assertIn('attributes["active_zone_ids"]', self.source)
        self.assertIn('attributes["learned_zone_mowing_key"]', self.source)
        self.assertIn('attributes["progress_source"]', self.source)
        self.assertIn('raw == "globalmowing"', self.source)
        self.assertIn('"manual_zone"', self.source)

    def test_latch_installs_after_all_reliability_and_recorder_layers(self) -> None:
        latch_pos = self.common.index("install_genie_progress_presentation()")
        recorder_pos = self.common.index("install_recorder_idle_semantics_v2467()")
        reliability_pos = self.common.index("install_v2465_reliability_fixes()")
        self.assertGreater(latch_pos, recorder_pos)
        self.assertGreater(latch_pos, reliability_pos)


if __name__ == "__main__":
    unittest.main()
