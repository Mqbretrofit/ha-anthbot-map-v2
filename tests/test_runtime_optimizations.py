from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeOptimizationSourceTests(unittest.TestCase):
    def test_optimizations_are_installed_before_counters(self) -> None:
        source = (ROOT / "custom_components/anthbot_map/models/m_series_common.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("install_runtime_optimizations()", source)
        self.assertIn("install_runtime_optimization_diagnostics()", source)
        self.assertLess(
            source.index("install_runtime_optimizations()"),
            source.index("install_performance_diagnostics()"),
        )
        self.assertLess(
            source.index("install_performance_diagnostics()"),
            source.index("install_runtime_optimization_diagnostics()"),
        )

    def test_duplicate_mqtt_filter_only_drops_equal_fields(self) -> None:
        source = (ROOT / "custom_components/anthbot_map/models/runtime_optimizations.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("existing != value", source)
        self.assertIn("duplicate_mqtt_messages_suppressed", source)
        self.assertIn("await previous_live(self, shadow_name, changed)", source)

    def test_task_event_refresh_is_phase_based_and_retry_is_conditional(self) -> None:
        source = (ROOT / "custom_components/anthbot_map/models/runtime_optimizations.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('return "active"', source)
        self.assertIn('return "returning"', source)
        self.assertIn("_event_signal_matches_phase", source)
        self.assertIn("task_event_retries", source)
        self.assertIn("latest_task_cycle_signal(self._task_events)", source)
        self.assertIn("if previous_phase == current_phase", source)

    def test_expensive_path_and_progress_work_is_cached(self) -> None:
        source = (ROOT / "custom_components/anthbot_map/models/runtime_optimizations.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "_runtime_path_merge_cache_signature",
            "path_merge_cache_hits",
            "_runtime_progress_geometry_cache",
            "_runtime_progress_learning_cache",
            "_runtime_ui_path_cache",
        ):
            self.assertIn(marker, source)
        self.assertIn("view = points", source)

    def test_custom_integration_runtime_translations_exist_for_all_23_languages(self) -> None:
        translations = ROOT / "custom_components/anthbot_map/translations"
        languages = (
            "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs",
            "sk", "ro", "da", "sv", "nb", "fi", "zh-Hans", "zh-Hant", "tr",
            "th", "vi", "ko", "km",
        )
        self.assertEqual(23, len(languages))
        for language in languages:
            path = translations / f"{language}.json"
            self.assertTrue(path.is_file(), language)
            payload = json.loads(path.read_text(encoding="utf-8"))
            menu = payload["options"]["step"]["init"]["menu_options"]
            self.assertTrue(menu["battery_saver"], language)
            self.assertTrue(menu["developer_reporting"], language)
            reporting = payload["options"]["step"]["developer_reporting"]["data"]
            self.assertTrue(reporting["share_anonymous_usage"], language)
            self.assertTrue(reporting["send_automatic_diagnostics"], language)

    def test_current_test_manifest_version(self) -> None:
        manifest = json.loads(
            (ROOT / "custom_components/anthbot_map/manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual("2.4.6-beta.11", manifest["version"])


if __name__ == "__main__":
    unittest.main()
