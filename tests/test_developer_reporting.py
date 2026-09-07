from __future__ import annotations

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
_load_module("custom_components.anthbot_map.const", "const.py")
MODULE = _load_module(
    "custom_components.anthbot_map.developer_reporting", "developer_reporting.py"
)


class _Device:
    def __init__(self, model: str, serial: str, alias: str) -> None:
        self.model = model
        self.serial_number = serial
        self.alias = alias


class DeveloperReportingTests(unittest.TestCase):
    def test_usage_payload_is_minimal_and_model_aware(self) -> None:
        payload = MODULE.build_anonymous_usage_payload(
            installation_id="random-install-id",
            area_code="36",
            devices=[
                _Device("M9 Pro", "SECRET-SERIAL-1", "Back garden"),
                _Device("M9 Pro", "SECRET-SERIAL-2", "Front garden"),
                _Device("Genie 1000", "SECRET-SERIAL-3", "Genie"),
            ],
            home_assistant_version="2026.9.0",
        )

        self.assertEqual(payload["country"], "Hungary")
        self.assertEqual(payload["device_count"], 3)
        self.assertEqual(payload["models"], ["Genie 1000", "M9 Pro"])
        self.assertEqual(payload["model_counts"], {"Genie 1000": 1, "M9 Pro": 2})
        text = repr(payload)
        self.assertNotIn("SECRET-SERIAL", text)
        self.assertNotIn("Back garden", text)
        self.assertNotIn("Front garden", text)

    def test_unknown_country_is_not_invented(self) -> None:
        self.assertIsNone(MODULE.country_name_from_area_code("9999"))

    def test_diagnostics_upload_wraps_existing_filtered_report(self) -> None:
        report = {"schema": "anthbot-firmware-diagnostics-v1", "safe": True}
        payload = MODULE.build_diagnostics_upload_payload(
            installation_id="random-install-id",
            report=report,
            trigger="no_go_crossing",
        )
        self.assertEqual(payload["report"], report)
        self.assertEqual(payload["trigger"], "no_go_crossing")

    def test_config_flow_requires_explicit_opt_in_before_usage_send(self) -> None:
        source = (PACKAGE_DIR / "config_flow.py").read_text(encoding="utf-8")
        const_source = (PACKAGE_DIR / "const.py").read_text(encoding="utf-8")
        strings = (PACKAGE_DIR / "strings.json").read_text(encoding="utf-8")

        self.assertIn("DEFAULT_SHARE_ANONYMOUS_USAGE = False", const_source)
        self.assertIn("DEFAULT_SEND_AUTOMATIC_DIAGNOSTICS = False", const_source)
        self.assertIn(
            "if bool(user_input.get(CONF_SHARE_ANONYMOUS_USAGE, False)):", source
        )
        self.assertIn("CONF_SEND_AUTOMATIC_DIAGNOSTICS", source)
        self.assertIn("developer_reporting", source)
        self.assertIn("Privacy information", strings)

    def test_privacy_document_states_reporting_is_optional(self) -> None:
        privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")
        self.assertIn("optional and disabled by default", privacy)
        self.assertIn("works without enabling either reporting option", privacy)
        self.assertIn("does **not** contain", privacy)


if __name__ == "__main__":
    unittest.main()
