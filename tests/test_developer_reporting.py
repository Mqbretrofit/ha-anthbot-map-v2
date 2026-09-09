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
_load_module("custom_components.anthbot_map.path_zone_check", "path_zone_check.py")
_load_module(
    "custom_components.anthbot_map.firmware_diagnostics", "firmware_diagnostics.py"
)
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

    def test_manufacturer_trigger_gets_clean_vendor_report(self) -> None:
        report = {
            "schema": "anthbot-firmware-diagnostics-v1",
            "safe": True,
            "connection": {"live_shadow_connected": True, "live_shadow_error": "internal"},
            "definitions": {"path": {"error": "decode failed"}},
            "runtime_performance": {"cache_hits": 5},
        }
        payload = MODULE.build_diagnostics_upload_payload(
            installation_id="random-install-id",
            report=report,
            trigger="mower_error_code",
        )
        vendor = payload["report"]
        self.assertEqual(vendor["report_kind"], "manufacturer")
        self.assertNotIn("definitions", vendor)
        self.assertNotIn("runtime_performance", vendor)
        self.assertNotIn("live_shadow_error", vendor["connection"])
        self.assertEqual(payload["trigger"], "mower_error_code")

    def test_integration_trigger_keeps_internal_failure_details(self) -> None:
        report = {
            "schema": "anthbot-firmware-diagnostics-v1",
            "connection": {"live_shadow_error": "internal"},
            "definitions": {"path": {"error": "decode failed"}},
            "runtime_performance": {"cache_hits": 5},
        }
        payload = MODULE.build_diagnostics_upload_payload(
            installation_id="random-install-id",
            report=report,
            trigger="path_definition_error",
        )
        internal = payload["report"]
        self.assertEqual(internal["report_kind"], "integration")
        self.assertEqual(
            internal["schema"], "anthbot-map-integration-diagnostics-v1"
        )
        self.assertEqual(internal["definitions"]["path"]["error"], "decode failed")
        self.assertEqual(internal["runtime_performance"]["cache_hits"], 5)
        self.assertEqual(internal["connection"]["live_shadow_error"], "internal")

    def test_reporting_is_not_mixed_into_account_setup(self) -> None:
        source = (PACKAGE_DIR / "config_flow.py").read_text(encoding="utf-8")
        user_step = source.split("class AnthbotGenieOptionsFlow", 1)[0]
        self.assertNotIn("selector.BooleanSelector", user_step)
        self.assertIn("Consent can be changed later from integration options", user_step)

    def test_reporting_is_available_in_integration_options(self) -> None:
        source = (PACKAGE_DIR / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn('menu_options=["battery_saver", "developer_reporting"]', source)
        self.assertIn("async_step_developer_reporting", source)
        self.assertIn("CONF_SHARE_ANONYMOUS_USAGE", source)
        self.assertIn("CONF_SEND_AUTOMATIC_DIAGNOSTICS", source)
        self.assertIn("SERVICE_UPDATE_DEVELOPER_REPORTING", source)
        self.assertIn("selector.BooleanSelector()", source)
        self.assertIn("return_response=True", source)

    def test_battery_saver_preserves_unrelated_options(self) -> None:
        source = (PACKAGE_DIR / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("options = dict(self.config_entry.options)", source)
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
        self.assertIn(
            'CONF_DEVELOPER_REPORTING_ACKNOWLEDGED = "developer_reporting_opt_in_acknowledged"',
            source,
        )
        self.assertIn('"should_show": not acknowledged and prompt_version != version', source)
        self.assertIn("options[CONF_DEVELOPER_REPORTING_ACKNOWLEDGED] = True", source)
        self.assertIn('event="opt_in"', source)

    def test_popup_is_registered_from_independent_tracker_platform(self) -> None:
        source = (PACKAGE_DIR / "device_tracker.py").read_text(encoding="utf-8")
        self.assertIn("from .developer_optin import async_register_developer_optin", source)
        self.assertIn("await async_register_developer_optin(hass)", source)

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
