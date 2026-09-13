"""Regression coverage for the v2.4.6.7 Recorder cache repair."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"
COMMON = COMPONENT / "models" / "m_series_common.py"
RECORDER_2467 = COMPONENT / "models" / "recorder_v2467.py"
RECORDER_2465 = COMPONENT / "models" / "recorder_v2465.py"


class RecorderV2467Tests(unittest.TestCase):
    def test_runtime_performance_is_added_to_home_assistant_cached_set(self) -> None:
        source = RECORDER_2467.read_text(encoding="utf-8")

        self.assertIn('{"runtime_performance"}', source)
        self.assertIn("_Entity__combined_unrecorded_attributes", source)
        self.assertIn("_entity_component_unrecorded_attributes", source)

    def test_cache_repair_runs_after_performance_diagnostics(self) -> None:
        common = COMMON.read_text(encoding="utf-8")

        self.assertIn("from .recorder_v2467 import install_recorder_v2467", common)
        self.assertLess(
            common.index("install_performance_diagnostics()"),
            common.index("install_recorder_v2467()"),
        )
        self.assertLess(
            common.index("install_recorder_v2467()"),
            common.index("install_runtime_optimization_diagnostics()"),
        )

    def test_live_map_throttle_is_not_relaxed_by_this_fix(self) -> None:
        source = RECORDER_2465.read_text(encoding="utf-8")
        repair = RECORDER_2467.read_text(encoding="utf-8")

        self.assertIn("_MAP_STATE_MIN_SECONDS = 5.0", source)
        self.assertNotIn("_MAP_STATE_MIN_SECONDS", repair)
        self.assertNotIn("_handle_coordinator_update", repair)


if __name__ == "__main__":
    unittest.main()
