from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "anthbot_map"
REPORTER = PACKAGE_DIR / "robot_error_reporting.py"
TRACKER = PACKAGE_DIR / "device_tracker.py"


class RobotErrorReportingSourceTests(unittest.TestCase):
    def test_reporter_source_compiles(self) -> None:
        source = REPORTER.read_text(encoding="utf-8")
        compile(source, str(REPORTER), "exec")

    def test_reporting_is_opt_in_and_privacy_filtered(self) -> None:
        source = REPORTER.read_text(encoding="utf-8")
        self.assertIn("CONF_SEND_AUTOMATIC_DIAGNOSTICS", source)
        self.assertIn("DEVELOPER_DIAGNOSTICS_ENDPOINT", source)
        self.assertIn("include_raw_state=False", source)
        self.assertIn("include_identifiers=False", source)
        self.assertIn('report.get("latest_task_event")', source)

    def test_new_mower_and_task_event_errors_are_supported(self) -> None:
        source = REPORTER.read_text(encoding="utf-8")
        self.assertIn('trigger = "mower_error_code" if code_is_new else "task_event_error"', source)
        self.assertIn('casefold() == "error"', source)
        self.assertIn('"diagnostic_event"', source)
        self.assertIn('"err_code"', source)
        self.assertIn('"event_code"', source)
        self.assertIn('"cloud_task_event_code"', source)
        self.assertIn('"mode"', source)
        self.assertIn('"robot_sta"', source)
        self.assertIn('"online"', source)

    def test_error_episode_is_deduplicated_but_can_rearm(self) -> None:
        source = REPORTER.read_text(encoding="utf-8")
        self.assertIn("active_error_code", source)
        self.assertIn("last_error_event_signature", source)
        self.assertIn("self.active_error_code = None", source)
        self.assertIn("_event_code(event) == code", source)
        self.assertIn("await asyncio.sleep(_REPORT_DEBOUNCE_SECONDS)", source)

    def test_tracker_registers_error_reporter(self) -> None:
        source = TRACKER.read_text(encoding="utf-8")
        self.assertIn(
            "from .robot_error_reporting import async_register_robot_error_reporting",
            source,
        )
        self.assertIn(
            "await async_register_robot_error_reporting(hass, entry, coordinators)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
