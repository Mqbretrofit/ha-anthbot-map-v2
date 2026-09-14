"""Regression tests for ANTHBOT cloud/API resilience and reporting wiring."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.anthbot_map"


def _load_modules():
    """Load api.py and the resilience helper without importing Home Assistant."""
    homeassistant = types.ModuleType("homeassistant")
    homeassistant_exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    homeassistant_exceptions.HomeAssistantError = HomeAssistantError
    homeassistant.exceptions = homeassistant_exceptions
    sys.modules.setdefault("homeassistant", homeassistant)
    sys.modules.setdefault("homeassistant.exceptions", homeassistant_exceptions)

    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class ClientSession:
        pass

    aiohttp.ClientError = ClientError
    aiohttp.ClientSession = ClientSession
    sys.modules.setdefault("aiohttp", aiohttp)

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", custom_components)

    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components/anthbot_map")]
    sys.modules.setdefault(PACKAGE, package)

    models_name = f"{PACKAGE}.models"
    models = types.ModuleType(models_name)
    models.__path__ = [str(ROOT / "custom_components/anthbot_map/models")]
    sys.modules.setdefault(models_name, models)

    const_name = f"{PACKAGE}.const"
    if const_name not in sys.modules:
        const_spec = importlib.util.spec_from_file_location(
            const_name,
            ROOT / "custom_components/anthbot_map/const.py",
        )
        const_module = importlib.util.module_from_spec(const_spec)
        sys.modules[const_name] = const_module
        assert const_spec.loader is not None
        const_spec.loader.exec_module(const_module)

    api_name = f"{PACKAGE}.api"
    api_spec = importlib.util.spec_from_file_location(
        api_name,
        ROOT / "custom_components/anthbot_map/api.py",
    )
    api_module = importlib.util.module_from_spec(api_spec)
    sys.modules[api_name] = api_module
    assert api_spec.loader is not None
    api_spec.loader.exec_module(api_module)

    resilience_name = f"{models_name}.cloud_api_resilience"
    resilience_spec = importlib.util.spec_from_file_location(
        resilience_name,
        ROOT / "custom_components/anthbot_map/models/cloud_api_resilience.py",
    )
    resilience_module = importlib.util.module_from_spec(resilience_spec)
    sys.modules[resilience_name] = resilience_module
    assert resilience_spec.loader is not None
    resilience_spec.loader.exec_module(resilience_module)
    return api_module, resilience_module


api, resilience = _load_modules()


class TestCloudApiResilience(unittest.TestCase):
    def setUp(self) -> None:
        resilience._LISTENERS.clear()
        resilience._RECENT_ERRORS.clear()

    def test_json_code_500_is_temporary_and_report_safe(self) -> None:
        error = api.AnthbotGenieApiError("IoT STS returned code=500")

        classified = resilience._classify_cloud_error(error)

        self.assertTrue(classified.is_temporary)
        self.assertEqual(classified.api_code, 500)
        self.assertEqual(
            resilience._safe_message(classified),
            "ANTHBOT API returned code=500",
        )

    def test_json_code_400_remains_non_temporary(self) -> None:
        error = api.AnthbotGenieApiError("IoT STS returned code=400")

        classified = resilience._classify_cloud_error(error)

        self.assertFalse(classified.is_temporary)
        self.assertEqual(classified.api_code, 400)

    def test_timeout_and_retryable_http_status_are_temporary(self) -> None:
        timeout = resilience._classify_cloud_error(
            api.AnthbotGenieApiError("Request timed out")
        )
        throttled = resilience._classify_cloud_error(
            api.AnthbotGenieApiError("Task events failed (429): vendor body")
        )

        self.assertTrue(timeout.is_temporary)
        self.assertTrue(throttled.is_temporary)
        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(
            resilience._safe_message(throttled),
            "ANTHBOT HTTP request failed with status=429",
        )
        self.assertNotIn("vendor body", resilience._safe_message(throttled))

    def test_recent_cloud_error_is_replayed_to_late_reporter(self) -> None:
        event = resilience.CloudApiErrorEvent(
            serial_number="TEST123",
            operation="task_events",
            api_code=500,
            status_code=None,
            temporary=True,
            attempts=3,
            message="ANTHBOT API returned code=500",
            occurred_monotonic=time.monotonic(),
        )
        resilience._emit_cloud_error(event)
        received = []

        remove = resilience.register_cloud_error_listener("TEST123", received.append)

        self.assertEqual(received, [event])
        remove()
        self.assertNotIn("TEST123", resilience._LISTENERS)

    def test_warning_filter_rate_limits_only_known_cloud_warnings(self) -> None:
        cloud_filter = resilience._CloudWarningRateLimitFilter()
        record = logging.LogRecord(
            "custom_components.anthbot_map.api",
            logging.WARNING,
            __file__,
            1,
            "Unable to obtain Anthbot IoT credentials for %s after retries: %s",
            ("TEST123", "IoT STS returned code=500"),
            None,
        )
        unrelated = logging.LogRecord(
            "custom_components.anthbot_map.api",
            logging.WARNING,
            __file__,
            1,
            "Different warning",
            (),
            None,
        )

        with patch.object(resilience.time, "monotonic", side_effect=[10.0, 11.0]):
            self.assertTrue(cloud_filter.filter(record))
            self.assertFalse(cloud_filter.filter(record))
        self.assertTrue(cloud_filter.filter(unrelated))

    def test_installation_is_wired_without_touching_control_routing(self) -> None:
        common = (ROOT / "custom_components/anthbot_map/models/m_series_common.py").read_text(
            encoding="utf-8"
        )
        tracker = (ROOT / "custom_components/anthbot_map/device_tracker.py").read_text(
            encoding="utf-8"
        )
        reporter = (ROOT / "custom_components/anthbot_map/cloud_error_reporting.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("install_cloud_api_resilience()", common)
        self.assertIn("async_register_cloud_error_reporting", tracker)
        self.assertIn('trigger="cloud_api_error"', reporter)
        self.assertIn("include_identifiers=False", reporter)
        self.assertNotIn("async_start_mowing", reporter)
        self.assertNotIn("async_publish_service_command", reporter)

    def test_reporting_tasks_cannot_block_home_assistant_startup(self) -> None:
        tracker = (ROOT / "custom_components/anthbot_map/device_tracker.py").read_text(
            encoding="utf-8"
        )
        agent = (ROOT / "custom_components/anthbot_map/developer_agent.py").read_text(
            encoding="utf-8"
        )
        reporter = (ROOT / "custom_components/anthbot_map/cloud_error_reporting.py").read_text(
            encoding="utf-8"
        )
        optin = (ROOT / "custom_components/anthbot_map/developer_agent_optin.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("entry.async_create_background_task(", agent)
        self.assertNotIn("task = hass.async_create_task(", agent)
        self.assertIn("entry.async_create_background_task(", tracker)
        self.assertNotIn("hass.async_create_task(", tracker)
        self.assertIn("self.entry.async_create_background_task(", reporter)
        self.assertNotIn("self.hass.async_create_task(", reporter)
        self.assertNotIn("Path(__file__)", optin)
        self.assertNotIn("read_text(", optin)


if __name__ == "__main__":
    unittest.main()
