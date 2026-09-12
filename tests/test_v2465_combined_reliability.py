"""Regression guards for the v2.4.6.5 combined reliability release."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
FIX = INTEGRATION / "models" / "reliability_v2465.py"
COMMON = INTEGRATION / "models" / "m_series_common.py"


class V2465CombinedReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = FIX.read_text(encoding="utf-8")

    def test_fix_is_installed_after_v2464_and_report_identity(self) -> None:
        common = COMMON.read_text(encoding="utf-8")
        reliability = common.index("install_runtime_reliability_fixes()")
        identity = common.index("install_report_identity_suffix()", reliability)
        v2465 = common.index("install_v2465_reliability_fixes()", identity)
        self.assertLess(reliability, identity)
        self.assertLess(identity, v2465)

    def test_cloud_error_signatures_ignore_request_specific_ids(self) -> None:
        self.assertIn("_REQUEST_ID_RE", self.source)
        self.assertIn("_HOST_ID_RE", self.source)
        self.assertIn("_stable_error_signature", self.source)
        self.assertIn('"map_definition_error": "_map_definition_error"', self.source)
        self.assertIn('"path_definition_error": "_path_definition_error"', self.source)
        self.assertIn('"live_shadow_error": "_live_shadow_error"', self.source)

    def test_automatic_reporting_is_singleton_episode_aware(self) -> None:
        self.assertIn("_anthbot_auto_diag_listener_remove", self.source)
        self.assertIn("_anthbot_auto_diag_active_signature", self.source)
        self.assertIn("_anthbot_auto_diag_clear_since", self.source)
        self.assertIn("_anthbot_auto_diag_last_sent", self.source)
        self.assertIn("_DIAGNOSTIC_CLEAR_GRACE_SECONDS", self.source)
        self.assertIn("_DIAGNOSTIC_HARD_REPEAT_SECONDS", self.source)
        self.assertIn('trigger == "mower_error_code"', self.source)

    def test_recorder_fanout_attributes_are_filtered(self) -> None:
        for attribute in (
            "mowing_time",
            "mowing_area",
            "mower_status",
            "robot_status_raw",
            "voice_status",
            "rain_continue_time",
        ):
            self.assertIn(f'"{attribute}"', self.source)
        self.assertIn("_COMMON_SENSOR_ATTRIBUTES", self.source)
        self.assertIn("attributes.pop(\"cloud_last_success\", None)", self.source)
        self.assertIn("_POSITION_STATE_MIN_SECONDS", self.source)
        self.assertIn("_POSITION_SENSOR_KEYS", self.source)
        self.assertIn('if key in {"serial_number", "pose_type"}', self.source)

    def test_no_go_details_do_not_churn_while_sensor_is_off(self) -> None:
        self.assertIn('entity_key == "no_go_path_crossing"', self.source)
        self.assertIn("if self.is_on:", self.source)
        self.assertIn('if key in {"serial_number", "model"}', self.source)

    def test_m_series_map_manager_supports_raster_fallback(self) -> None:
        self.assertIn("previous_decoder(raw, model=model)", self.source)
        self.assertIn("api_module._decode_map_raster(iot_map)", self.source)
        self.assertIn('"m-series-iot-map-raster-v1"', self.source)
        self.assertIn('"map_manager_probe"', self.source)
        self.assertIn('"decode_status"] = "unrecognized"', self.source)
        # Preserve the serial-based archive naming proven by field captures.
        self.assertIn('f"map_manager_{serial}.tar.gz"', self.source)

    def test_model_control_paths_are_not_modified_here(self) -> None:
        self.assertNotIn("async_publish_service_command", self.source)
        self.assertNotIn("mow_start", self.source)
        self.assertNotIn("mow_pause", self.source)
        self.assertNotIn("mow_continue", self.source)
        self.assertNotIn("start_dump", self.source)


if __name__ == "__main__":
    unittest.main()
