from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"

spec = importlib.util.spec_from_file_location(
    "anthbot_report_identity_test",
    INTEGRATION / "report_identity.py",
)
assert spec is not None and spec.loader is not None
report_identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_identity)


class _Client:
    serial_number = "26230LGW00000046"


class _Coordinator:
    client = _Client()


class ReportIdentitySuffixTests(unittest.TestCase):
    def test_serial_suffix_keeps_only_last_four_characters(self) -> None:
        self.assertEqual(report_identity.serial_suffix("26230LGW00000110"), "0110")
        self.assertEqual(report_identity.serial_suffix("26230LGW00000046"), "0046")
        self.assertIsNone(report_identity.serial_suffix(None))

    def test_report_enrichment_does_not_add_full_serial(self) -> None:
        report = {
            "device": {
                "model": "Anthbot M9 Pro",
                "serial_number": None,
                "serial_sha256": "5770fbd15a25abcdef",
            }
        }
        result = report_identity.add_serial_suffix(report, _Coordinator())
        self.assertEqual(result["device"]["serial_suffix"], "0046")
        self.assertIsNone(result["device"]["serial_number"])
        self.assertNotIn("26230LGW00000046", repr(result))

    def test_report_wrapper_is_installed_after_reliability_layer(self) -> None:
        source = (INTEGRATION / "models" / "m_series_common.py").read_text("utf-8")
        reliability_call = source.index("install_runtime_reliability_fixes()")
        identity_call = source.index("install_report_identity_suffix()", reliability_call)
        self.assertLess(reliability_call, identity_call)

        wrapper = (INTEGRATION / "models" / "report_identity_suffix.py").read_text("utf-8")
        self.assertIn("button_module.build_firmware_diagnostics_report", wrapper)
        self.assertIn("robot_error_reporting.build_firmware_diagnostics_report", wrapper)
        self.assertIn("firmware_diagnostics.build_firmware_diagnostics_report", wrapper)


if __name__ == "__main__":
    unittest.main()
