from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "anthbot_map"
FRONTEND_DIR = PACKAGE_DIR / "frontend"


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


class _NeverPostSession:
    def post(self, *args, **kwargs):
        raise AssertionError("blocked reporting endpoint must not be contacted")


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

    def test_reporting_is_not_mixed_into_account_or_battery_saver_forms(self) -> None:
        source = (PACKAGE_DIR / "config_flow.py").read_text(encoding="utf-8")
        strings = (PACKAGE_DIR / "strings.json").read_text(encoding="utf-8")
        self.assertNotIn("CONF_SHARE_ANONYMOUS_USAGE", source)
        self.assertNotIn("CONF_SEND_AUTOMATIC_DIAGNOSTICS", source)
        self.assertNotIn('"share_anonymous_usage"', strings)
        self.assertNotIn('"send_automatic_diagnostics"', strings)
        self.assertIn("CONF_CHARGER_SWITCH", source)
        self.assertIn("options[CONF_BATTERY_SAVER_CONFIGS] = configs", source)

    def test_popup_follows_home_assistant_language_with_english_fallback(self) -> None:
        source = (FRONTEND_DIR / "developer-optin.js").read_text(encoding="utf-8")
        self.assertIn('hass?.locale?.language || hass?.language || "en"', source)
        self.assertIn('return ANTHBOT_OPTIN_SUPPORTED.has(base) ? base : "en"', source)
        self.assertNotIn("<select", source.lower())
        for language in (
            "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs",
            "sk", "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr",
            "th", "vi", "ko", "km",
        ):
            self.assertIn(f'"{language}"', source)

    def test_popup_backend_is_version_gated_and_permanently_acknowledges_opt_in(self) -> None:
        source = (PACKAGE_DIR / "developer_optin.py").read_text(encoding="utf-8")
        self.assertIn('CONF_DEVELOPER_PROMPT_VERSION = "developer_prompt_version"', source)
        self.assertIn('CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED = "developer_opt_in_acknowledged"', source)
        self.assertIn('"should_show": not acknowledged and prompt_version != version', source)
        self.assertIn("options[CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED] = True", source)
        self.assertIn('event="opt_in"', source)

    def test_popup_is_not_auto_registered_from_tracker_platform(self) -> None:
        source = (PACKAGE_DIR / "device_tracker.py").read_text(encoding="utf-8")
        self.assertNotIn("from .developer_optin import async_register_developer_optin", source)
        self.assertNotIn("await async_register_developer_optin(hass)", source)
        self.assertNotIn("async_register_developer_agent_optin", source)

    def test_privacy_document_states_reporting_is_optional(self) -> None:
        privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")
        self.assertIn("optional and disabled by default", privacy)
        self.assertIn("works without enabling either reporting option", privacy)
        self.assertIn("does **not** contain", privacy)

    def test_reporting_endpoint_requires_https_and_blocks_vendor_host(self) -> None:
        self.assertTrue(
            MODULE.reporting_endpoint_allowed(
                "https://reports.example.org/api/anthbot/telemetry"
            )
        )
        self.assertFalse(
            MODULE.reporting_endpoint_allowed(
                "http://reports.example.org/api/anthbot/telemetry"
            )
        )
        self.assertFalse(
            MODULE.reporting_endpoint_allowed(
                "https://installer.tmt-automation.com/api/anthbot/telemetry"
            )
        )


class DeveloperReportingAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_vendor_endpoint_is_blocked_before_network_call(self) -> None:
        result = await MODULE.async_post_json(
            _NeverPostSession(),
            "https://installer.tmt-automation.com/api/anthbot/telemetry",
            {"test": True},
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
