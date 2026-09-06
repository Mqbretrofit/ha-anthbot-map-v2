"""Regression coverage for low-overhead runtime activity diagnostics."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"
PERF = COMPONENT / "models" / "performance_diagnostics.py"
COMMON = COMPONENT / "models" / "m_series_common.py"


class RuntimePerformanceDiagnosticsTests(unittest.TestCase):
    def test_counters_are_installed_last_and_exposed_on_map(self) -> None:
        source = PERF.read_text(encoding="utf-8")
        common = COMMON.read_text(encoding="utf-8")

        self.assertIn("install_performance_diagnostics()", common)
        self.assertLess(
            common.index("install_shutdown_guard_state_settle()"),
            common.index("install_performance_diagnostics()"),
        )
        self.assertIn('attributes["runtime_performance"] = _snapshot', source)
        self.assertIn('| {"runtime_performance"}', source)
        self.assertNotIn("async_create_background_task", source)

    def test_support_hot_paths_are_counted_without_per_point_instrumentation(self) -> None:
        source = PERF.read_text(encoding="utf-8")

        for key in (
            "mqtt_shadow_updates",
            "coordinator_updates",
            "coordinator_refreshes",
            "task_event_refresh_attempts",
            "task_event_downloads",
            "path_merges",
            "progress_sensor_evaluations",
            "progress_attribute_evaluations",
        ):
            self.assertIn(f'"{key}"', source)

        self.assertIn("previous_merged = m_series_path._merged", source)
        self.assertIn("previous_native_value", source)
        self.assertIn("previous_extra_attributes", source)
        self.assertNotIn("_progress_float =", source)
        self.assertNotIn("_progress_zone_points =", source)

    def test_runtime_diagnostics_do_not_claim_cpu_percentage(self) -> None:
        source = PERF.read_text(encoding="utf-8")

        self.assertIn("measure *activity*, not CPU percentage", source)
        self.assertIn('"estimated_entity_writes_per_min"', source)
        self.assertIn('"current_rates_per_min"', source)
        self.assertIn('"last_window_rates_per_min"', source)
        self.assertIn('"totals"', source)

    def test_only_suspicious_activity_is_warning_level(self) -> None:
        source = PERF.read_text(encoding="utf-8")

        self.assertIn('_LOGGER.warning(message + " [HIGH ACTIVITY]"', source)
        self.assertIn("_LOGGER.debug(message, *args)", source)
        self.assertIn('"coordinator_updates": 1800.0', source)
        self.assertIn('"task_event_downloads": 30.0', source)


if __name__ == "__main__":
    unittest.main()
