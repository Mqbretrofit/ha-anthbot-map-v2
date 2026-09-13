"""Regression coverage for the v2.4.6.7 Recorder repairs."""

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

    def test_v2467_runs_after_diagnostics_and_final_v2465_throttle(self) -> None:
        common = COMMON.read_text(encoding="utf-8")

        self.assertIn("from .recorder_v2467 import install_recorder_v2467", common)
        self.assertLess(
            common.index("install_performance_diagnostics()"),
            common.index("install_recorder_v2467()"),
        )
        self.assertLess(
            common.index("install_recorder_v2465()"),
            common.index("install_recorder_v2467()"),
        )

    def test_existing_five_second_live_limit_is_preserved(self) -> None:
        source = RECORDER_2465.read_text(encoding="utf-8")
        repair = RECORDER_2467.read_text(encoding="utf-8")

        self.assertIn("_MAP_STATE_MIN_SECONDS = 5.0", source)
        self.assertNotIn("_MAP_STATE_MIN_SECONDS =", repair)
        self.assertIn("previous_update = map_entity._handle_coordinator_update", repair)
        self.assertIn("previous_update(self)", repair)
        self.assertIn("_anthbot_last_map_state_write", repair)

    def test_unchanged_map_writes_are_suppressed_with_idle_heartbeat(self) -> None:
        source = RECORDER_2467.read_text(encoding="utf-8")

        self.assertIn("_MAP_UNCHANGED_HEARTBEAT_SECONDS = 60.0", source)
        self.assertIn("signature != previous_signature", source)
        self.assertIn("if not changed and not heartbeat_due", source)
        self.assertIn("_anthbot_v2467_map_signature", source)
        self.assertIn("if after_write != before_write", source)

    def test_map_signature_tracks_live_ui_sources_not_runtime_diagnostics(self) -> None:
        source = RECORDER_2467.read_text(encoding="utf-8")

        for key in (
            'state.get("pose")',
            'state.get("curPose")',
            'state.get("mapScanPose")',
            'state.get("_path_definition")',
            'state.get("_map_definition")',
            'state.get("_area_definition")',
            'state.get("_mowing_records")',
            'state.get("_task_events")',
        ):
            self.assertIn(key, source)

        signature_body = source.split("def _map_live_signature", 1)[1].split(
            "def _install_unchanged_map_write_filter", 1
        )[0]
        self.assertNotIn("runtime_performance", signature_body)
        self.assertNotIn("id(", signature_body)
        self.assertIn("_map_definition_signature", signature_body)
        self.assertIn("_area_definition_signature", signature_body)
        self.assertIn("_sequence_edge_signature", signature_body)

    def test_semantic_helpers_do_not_use_python_object_identity(self) -> None:
        source = RECORDER_2467.read_text(encoding="utf-8")
        helpers = source.split("def _stable_small", 1)[1].split(
            "def _install_unchanged_map_write_filter", 1
        )[0]

        self.assertNotIn("id(", helpers)
        self.assertIn("json.dumps", helpers)
        self.assertIn("len(points)", helpers)
        self.assertIn("len(runs)", helpers)


if __name__ == "__main__":
    unittest.main()
