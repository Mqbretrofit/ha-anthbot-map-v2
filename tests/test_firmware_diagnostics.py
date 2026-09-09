from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import tempfile
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
    _live_shadow_error = "websocket reconnect failed"
    _map_definition_source = "m_series_map_manager:iot_map.bin"
    _last_map_time = "20260909175200"
    _last_map_key = "map-key-7"
    _last_path_time = "20260909180000"
    _history_path_info = {
        "recordPathUrl": "https://cdn.example.test/history/path.bin?page=2&format=bin",
        "path_id": "live-7",
    }
    reported_state = {
        "fw_version": {"system_version": "9.9.9"},
        "robot_sta": {"value": "mowing"},
        "elec": {"value": 77},
        "rtk_state": 3,
        "pose": {"x": 500, "y": 0},
        "map_time": "20260909175200",
        "map_tar_time": "20260909175159",
        "path_time": "20260909180000",
        "_history_path_source": "m_series_curpath",
        "_map_definition_error": (
            "HTTP 403 while fetching https://cdn.example.test/maps/current.tar?page=2"
        ),
        "_path_definition_error": "Unable to decode path chunk 17",
        "_ridable_area_definition_error": None,
        "_map_archive_selection": {
            "selected": {
                "filename": "current.tar",
                "download_url": "https://cdn.example.test/maps/current.tar?page=2&format=tar",
                "md5": "0123456789abcdef",
            }
        },
        "_map_definition": {
            "map_id": "map-7",
            "_download_source": {
                "filename": "iot_map.bin",
                "url": "https://cdn.example.test/maps/iot_map.bin?page=3",
                "md5": "fedcba9876543210",
            },
        },
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
        "runtime_performance": {"path_merge_cache_hits": 4},
        "_task_events": {
            "data": [
                {"code": 1000, "create_time": 10},
                {"code": 1001, "create_time": 20},
            ]
        },
        "nested": {"ok": 1},
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

        definitions = report["definitions"]
        self.assertEqual(
            definitions["map"]["error"],
            "HTTP 403 while fetching <url-redacted>",
        )
        self.assertEqual(
            definitions["path"]["error"], "Unable to decode path chunk 17"
        )
        self.assertEqual(
            definitions["map"]["source"], "m_series_map_manager:iot_map.bin"
        )
        archive_url = definitions["map"]["archive_selection"]["selected"][
            "download_url"
        ]
        self.assertEqual(archive_url["host"], "cdn.example.test")
        self.assertEqual(archive_url["filename"], "current.tar")
        self.assertEqual(archive_url["query_keys"], ["format", "page"])
        history_url = definitions["path"]["history_info"]["recordPathUrl"]
        self.assertEqual(history_url["filename"], "path.bin")
        self.assertEqual(history_url["query_keys"], ["format", "page"])
        self.assertEqual(
            definitions["map"]["cached_definition"]["download_source"]["url"][
                "filename"
            ],
            "iot_map.bin",
        )
        self.assertNotIn("raw_state", report)

    def test_manufacturer_view_excludes_integration_failures(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(_Coordinator())
        vendor = MODULE.manufacturer_report_view(report)

        self.assertEqual(vendor["report_kind"], "manufacturer")
        self.assertEqual(vendor["schema"], "anthbot-firmware-diagnostics-v1")
        self.assertNotIn("definitions", vendor)
        self.assertNotIn("runtime_performance", vendor)
        self.assertNotIn("raw_state", vendor)
        self.assertNotIn("live_shadow_error", vendor["connection"])
        self.assertEqual(vendor["telemetry"]["path_time"], "20260909180000")
        self.assertEqual(vendor["path"]["path_id"], "live-7")

    def test_integration_view_keeps_parser_and_transport_errors(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(_Coordinator())
        internal = MODULE.integration_report_view(report)

        self.assertEqual(internal["report_kind"], "integration")
        self.assertEqual(
            internal["schema"], "anthbot-map-integration-diagnostics-v1"
        )
        self.assertEqual(
            internal["definitions"]["path"]["error"],
            "Unable to decode path chunk 17",
        )
        self.assertEqual(
            internal["connection"]["live_shadow_error"],
            "websocket reconnect failed",
        )
        self.assertEqual(internal["runtime_performance"]["path_merge_cache_hits"], 4)

    def test_raw_state_is_opt_in(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(
            _Coordinator(), include_raw_state=True
        )

        self.assertEqual(report["raw_state"]["nested"]["ok"], 1)
        self.assertNotIn("raw_state", MODULE.manufacturer_report_view(report))

    def test_identifiers_can_be_removed_without_losing_trace_hash(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(
            _Coordinator(), include_identifiers=False
        )

        self.assertIsNone(report["device"]["serial_number"])
        self.assertIsNone(report["device"]["alias"])
        self.assertEqual(len(report["device"]["serial_sha256"]), 64)

    def test_filename_and_email_summary_are_manufacturer_safe(self) -> None:
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
        self.assertNotIn("Map definition error", summary)
        self.assertNotIn("Path definition error", summary)
        self.assertNotIn("websocket reconnect failed", summary)

    def test_written_firmware_report_is_manufacturer_profile(self) -> None:
        report = MODULE.build_firmware_diagnostics_report(_Coordinator())
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "diag.json"
            MODULE.write_firmware_diagnostics_report(path, report)
            stored = __import__("json").loads(path.read_text("utf-8"))

        self.assertEqual(stored["report_kind"], "manufacturer")
        self.assertNotIn("definitions", stored)
        self.assertNotIn("runtime_performance", stored)

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
