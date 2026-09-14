"""Regression guards for M9/M9 Pro mowing target presentation."""

from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
MODELS = ROOT / "custom_components" / "anthbot_map" / "models"


class TestM9ProgressPosttrim(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (MODELS / "m9_progress_posttrim.py").read_text(encoding="utf-8")
        cls.common = (MODELS / "m_series_common.py").read_text(encoding="utf-8")

    def test_only_m9_families_are_targeted(self) -> None:
        self.assertIn('_M9_FAMILIES = {"m9", "m9_pro"}', self.source)
        self.assertIn('getattr(description, "key", None) == "mowing_progress"', self.source)

    def test_v2464_target_evidence_is_restored(self) -> None:
        self.assertIn('attributes["active_zone_ids"]', self.source)
        self.assertIn('attributes["learned_zone_mowing_key"]', self.source)
        self.assertIn('attributes["progress_source"]', self.source)
        self.assertIn('attributes["last_mowing_task"]', self.source)
        self.assertIn("active_manual_zone_ids", self.source)
        self.assertIn("_progress_learning_debug", self.source)

    def test_stopped_task_uses_cached_target_metadata(self) -> None:
        self.assertIn('cache["active_zone_ids"] = current_ids', self.source)
        self.assertIn('cache["learned_zone_mowing_key"]', self.source)
        self.assertIn('_copy_task(cache.get("task")) or current_task', self.source)

    def test_native_progress_value_is_not_wrapped(self) -> None:
        self.assertNotIn("native_value", self.source)

    def test_installed_after_genie_posttrim_wrapper(self) -> None:
        genie_pos = self.common.index("install_genie_progress_posttrim()")
        m9_pos = self.common.index("install_m9_progress_posttrim()")
        self.assertGreater(m9_pos, genie_pos)


if __name__ == "__main__":
    unittest.main()
