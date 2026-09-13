from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map" / "models"
COMMON = COMPONENT / "m_series_common.py"
SOURCE = COMPONENT / "recorder_idle_semantics_v2467.py"


class RecorderIdleSemanticsV2467Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_layer_is_installed_after_v2467_filter(self) -> None:
        common = COMMON.read_text(encoding="utf-8")
        self.assertIn("install_recorder_idle_semantics_v2467", common)
        self.assertLess(
            common.index("install_recorder_v2467()"),
            common.index("install_recorder_idle_semantics_v2467()"),
        )

    def test_rotating_map_time_is_not_a_semantic_write_trigger(self) -> None:
        signature = self.source.split("def _stable_map_live_signature", 1)[1].split(
            "def install_recorder_idle_semantics_v2467", 1
        )[0]
        self.assertNotIn('state.get("map_time")', signature)
        self.assertIn("_map_definition_signature", signature)
        self.assertIn("_archive_identity", signature)

    def test_archive_identity_ignores_timestamp_fields(self) -> None:
        helper = self.source.split("def _archive_identity", 1)[1].split(
            "def _actual_error_history_signature", 1
        )[0]
        for key in ("map_time", "map_tar_time", "timestamp", "update_time"):
            self.assertNotIn(f'"{key}"', helper)
        for key in ("selected_file", "selected_md5", "selected_map_id", "map_id"):
            self.assertIn(f'"{key}"', helper)

    def test_event_only_error_history_does_not_trigger_map_write(self) -> None:
        helper = self.source.split("def _actual_error_history_signature", 1)[1].split(
            "def _stable_map_live_signature", 1
        )[0]
        for key in ("error", "err_code", "error_code"):
            self.assertIn(f'"{key}"', helper)
        self.assertNotIn('"event_code"', helper)
        self.assertNotIn('"event"', helper)
        self.assertNotIn('"time"', helper)


if __name__ == "__main__":
    unittest.main()
