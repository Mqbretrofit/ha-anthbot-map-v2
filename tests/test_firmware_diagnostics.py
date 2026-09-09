from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "anthbot_map"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PACKAGE_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


custom_components = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
custom_components.__path__ = [str(ROOT / "custom_components")]
anthbot_package = sys.modules.setdefault(
    "custom_components.anthbot_map", types.ModuleType("custom_components.anthbot_map")
)
anthbot_package.__path__ = [str(PACKAGE_DIR)]
_load_module("custom_components.anthbot_map.path_zone_check", "path_zone_check.py")
MODULE = _load_module(
    "custom_components.anthbot_map.firmware_diagnostics", "firmware_diagnostics.py"
)


class _Device:
    model = "M9 Pro"
    alias = "Garden mower"
    is_owner = True


class _Client:
    serial_number = "26230LGW00000110"


class _Coordinator:
    device = _Device()
    client = _Client()
    last_update_success = True
    _live_shadow_connected = True
    _live_shadow_error = None
    reported_state = {
        "fw_version": {"system_version": "9.9.9"},
        "robot_sta": {"value": "mowing"},
        "elec": {"value": 77},
        "rtk_state": 3,
        "pose": {"x": 500, "y": 0},
        "_history_path_source": "m_series_curpath",
        "_path_definition": {
            "path_id": "live-7",
            "_m_series_first_index": 0,
            "_m_series_last_index": 5,
            "_path_points": [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 200, "y": 0},
                {"x": 300, "y": 0},
                {"x": 400, "y": 0},
                {"x": 500, "y": 0},
            ],
        },
        "_area_definition": {
            "forbid_areas": [
                {
                    "id": 3,
                    "name": "test no-go",
                    "points": [(250, -50), (350, -50), (350, 50), (250, 50)],
                }
            ]
        },
        "_no_go_path_check": {
            "crossing_detected": True,
            "boundary_crossings": 2,
            "points_inside": 1,
            "traversals": 1,
            "zone_ids": [3],
        },
        "_task_events": {
            "data": [
                {"code": 1000, "create_time": 10},
                {"code": 1001, "create_time": 20},
            ]
        },
        "access_token": "must-not-leak",
        "nested": {"session_token": "must-not-leak-either", "ok": 1},
    }


class _N8Device:
    model = "N8"
    alias = "N8 test mower"
    is_owner = True


class _N8Coordinator:
    device = _N8Device()
    client = _Client()
    last_update_success = True
    _live_shadow_connected = True
    _live_shadow_error = None
    reported_state = {
        "fw_version": {"system_version": "1.2.3"},
        "mode": {"value": "dumpgrass"},
        "grass_state": {
            "grass_bag_in_position": 1,
            "grass_shield_in_position": 0,
        },
        "anti_loss_switch": 1,
        "anti_loss_radius": 8,
        "rain_switch": 1,
        "rain_continue_time": 10800,
        "param_set": {
            "work_mode": 1,
            "cutter_height": 45,
            "mow_count": 2,
            "rid_switch": 1,
            "nest_switch": 0,
        },
        "pobctl": {"switch": 1, "level": 2},
        "device_config": {
            "child_lock": 1,
            "pin_code": "1234",
            "anti_loss_radius": 8,
        },
        "_n8_dumping": True,
        "_n8_grass_bag_in_position": 1,
        "_n8_grass_shield_in_position": 0,
        "_area_definition": {
            "dump_grass_areas": [
                {"id": 7, "points": [[1, 2], [3, 4], [5, 6]]},
                {"id": 8, "points": [[11, 12], [13, 14], [15, 16]]},
            ]
        },
    }


class FirmwareDiagnosticsTests(unittest.TestCase):
    def test_report_contains_reproducible_path_and_no_go_evidence(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(
            _Coordinator(),
            generated_at=datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(report["schema"], "anthbot-firmware-diagnostics-v1")
        self.assertEqual(report["device"]["model"], "M9 Pro")
        self.assertEqual(report["device"]["firmware_version"], "9.9.9")
        self.assertEqual(report["device"]["serial_number"], "26230LGW00000110")
        self.assertEqual(report["path"]["path_id"], "live-7")
        self.assertEqual(report["path"]["point_count"], 6)
        self.assertEqual(report["path"]["last_point"]["x"], 500)
        self.assertEqual(report["no_go"]["check"]["boundary_crossings"], 2)
        self.assertEqual(report["no_go"]["check"]["points_inside"], 1)
        self.assertEqual(report["no_go"]["zones"][0]["id"], 3)
        self.assertEqual(report["latest_task_event"]["code"], 1001)
        self.assertNotIn("raw_state", report)
        self.assertNotIn("n8_protocol", report)

    def test_raw_state_is_opt_in_and_secrets_are_redacted(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(
            _Coordinator(), include_raw_state=True
        )

        self.assertEqual(report["raw_state"]["access_token"], "<redacted>")
        self.assertEqual(
            report["raw_state"]["nested"]["session_token"], "<redacted>"
        )
        self.assertEqual(report["raw_state"]["nested"]["ok"], 1)

    def test_n8_report_contains_compact_protocol_discovery_evidence(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(_N8Coordinator())
        n8 = report["n8_protocol"]

        self.assertTrue(n8["direct"]["_n8_dumping"])
        self.assertEqual(n8["direct"]["anti_loss_radius"], 8)
        self.assertEqual(n8["param_set"]["work_mode"], 1)
        self.assertEqual(n8["perception_obstacle"], {"switch": 1, "level": 2})
        self.assertEqual(n8["dump_grass_areas"]["count"], 2)
        self.assertEqual(n8["dump_grass_areas"]["ids"], [7, 8])
        self.assertEqual(n8["candidate_fields"]["device_config.child_lock"], 1)
        self.assertEqual(n8["candidate_fields"]["device_config.anti_loss_radius"], 8)
        self.assertNotIn("device_config.pin_code", n8["candidate_fields"])

    def test_pin_codes_are_redacted_from_opt_in_raw_state(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(
            _N8Coordinator(), include_raw_state=True
        )
        self.assertEqual(
            report["raw_state"]["device_config"]["pin_code"], "<redacted>"
        )

    def test_identifiers_can_be_removed_without_losing_trace_hash(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(
            _Coordinator(), include_identifiers=False
        )

        self.assertIsNone(report["device"]["serial_number"])
        self.assertIsNone(report["device"]["alias"])
        self.assertEqual(len(report["device"]["serial_sha256"]), 64)

    def test_filename_and_email_summary_are_stable(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(
            _Coordinator(),
            note="Crossed zone 3 while mowing",
            generated_at=datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc),
        )
        filename = MODULE.report_filename(report)
        summary = MODULE.report_email_summary(report)

        self.assertTrue(filename.startswith("anthbot_firmware_diag_m9-pro_"))
        self.assertTrue(filename.endswith("_20260907150000.json"))
        self.assertIn("Boundary crossings: 2", summary)
        self.assertIn("Crossed zone 3 while mowing", summary)
        self.assertNotIn("must-not-leak", summary)

    def test_button_exports_to_local_media_and_fires_email_ready_event(self) -> None:
        source = (PACKAGE_DIR / "button.py").read_text("utf-8")
        self.assertIn('key="export_firmware_diagnostics"', source)
        self.assertIn('"anthbot_firmware_diagnostics_ready"', source)
        self.assertIn('media-source://media_source/local/', source)
        self.assertIn("include_raw_state=False", source)
        export_block = source[source.index('if key == "export_firmware_diagnostics"'):]
        self.assertLess(export_block.index("return"), export_block.index('if key == "connect_cloud"'))


if __name__ == "__main__":
    unittest.main()
