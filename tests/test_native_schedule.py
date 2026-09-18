"""Unit tests for the app-native ANTHBOT schedule adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "anthbot_map" / "native_schedule.py"


def _load_module():
    dt_module = types.ModuleType("homeassistant.util.dt")
    dt_module.now = lambda: datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    dt_module.as_local = lambda value: value
    dt_module.utc_from_timestamp = lambda value: datetime.fromtimestamp(
        value, tz=timezone.utc
    )
    homeassistant = types.ModuleType("homeassistant")
    util = types.ModuleType("homeassistant.util")
    util.dt = dt_module
    sys.modules.setdefault("homeassistant", homeassistant)
    sys.modules.setdefault("homeassistant.util", util)
    sys.modules.setdefault("homeassistant.util.dt", dt_module)
    spec = importlib.util.spec_from_file_location("anthbot_native_schedule_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


native = _load_module()


class _Client:
    serial_number = "TEST123"

    def __init__(self) -> None:
        self.commands = []

    async def async_publish_service_command(self, **kwargs) -> None:
        self.commands.append(kwargs)


class _AccountClient:
    def __init__(self, appointment=None) -> None:
        self.appointment = appointment
        self.appointment_requests = []

    async def async_get_device_appointment_definition(self, serial_number):
        self.appointment_requests.append(serial_number)
        return self.appointment


class _Coordinator:
    def __init__(self, plan, model="M9 Pro") -> None:
        self.client = _Client()
        self.account_client = _AccountClient()
        self.device = types.SimpleNamespace(model=model)
        self.reported_state = {"appointment": plan}

    def async_set_updated_data(self, state) -> None:
        self.reported_state = state


class NativeScheduleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.plan = {
            "timezone": 2,
            "timezone_sec": 7200,
            "version": 17,
            "value": [
                {
                    "id": 9,
                    "start_time": 9 * 3600 + 30 * 60,
                    "active": 1,
                    "unlock": 1,
                    "week": [1, 3, 7],
                    "repeat": 1,
                    "workmode": 1,
                    "area_id": [2, 4],
                    "area_points": [],
                    "cutter_height": 45,
                    "firmware_extra": {"keep": True},
                },
                {"id": 10, "unlock": 0, "active": 1, "week": [1]},
            ],
        }
        self.coordinator = _Coordinator(self.plan)

    def test_normalizes_native_rule_and_hides_dnd(self) -> None:
        rules = native.native_rules_for(
            self.coordinator,
            [{"id": "9", "summary": "Front", "weather_entity": "weather.home"}],
        )
        self.assertEqual(1, len(rules))
        self.assertEqual("9", rules[0]["id"])
        self.assertEqual([0, 2, 6], rules[0]["weekdays"])
        self.assertEqual("09:30", rules[0]["start_time"])
        self.assertEqual("zone", rules[0]["mode"])
        self.assertEqual("2,4", rules[0]["zones"])
        self.assertEqual(45, rules[0]["mow_height"])
        self.assertEqual("Front", rules[0]["summary"])
        self.assertTrue(rules[0]["repeating"])

    def test_normalizes_one_time_app_appointment(self) -> None:
        coordinator = _Coordinator(
            {
                "value": [
                    {
                        "start_time": 1_789_718_400,
                        "active": 1,
                        "unlock": 1,
                        "repeat": 0,
                        "week": [],
                        "workmode": 0,
                    }
                ]
            },
            model="Genie 1000",
        )
        rule = native.native_rules_for(coordinator)[0]
        self.assertFalse(rule["repeating"])
        self.assertIsNotNone(rule["start_datetime"])

    async def test_m_series_edit_uses_appointment_payload(self) -> None:
        previous = self.plan["value"][0]
        entry = native.build_native_entry(
            self.coordinator,
            {
                "weekdays": [1, 4],
                "start_time": "08:15",
                "mode": "zone",
                "zones": "3",
                "mow_height": 40,
                "enabled": True,
            },
            previous,
        )
        await native.async_publish_native_plan_change(
            self.coordinator,
            operation="edit",
            schedule_id="9",
            entry=entry,
        )
        command = self.coordinator.client.commands[-1]
        self.assertEqual("mow_regular", command["cmd"])
        self.assertEqual([entry], command["data"]["appointment"])
        self.assertNotIn("value", command["data"])
        self.assertNotIn("version", command["data"])
        self.assertEqual({"keep": True}, entry["firmware_extra"])
        self.assertEqual([3], entry["area_id"])
        self.assertEqual("command_sent", self.coordinator.reported_state["_native_schedule_sync"]["status"])

    async def test_m_series_delete_uses_native_incremental_delete(self) -> None:
        await native.async_publish_native_plan_change(
            self.coordinator, operation="delete", schedule_id="9"
        )
        data = self.coordinator.client.commands[-1]["data"]
        self.assertNotIn("value", data)
        self.assertNotIn("appointment", data)
        self.assertEqual([9], data["delete_appointment"])
        self.assertEqual([10], [item["id"] for item in self.coordinator.reported_state["appointment"]["value"]])

    async def test_m_series_add_generates_id_and_uses_appointment_payload(self) -> None:
        entry = native.build_native_entry(
            self.coordinator,
            {
                "weekdays": [0, 2],
                "start_time": "07:30",
                "mode": "full",
                "enabled": True,
            },
        )
        await native.async_publish_native_plan_change(
            self.coordinator,
            operation="add",
            entry=entry,
        )
        data = self.coordinator.client.commands[-1]["data"]
        self.assertEqual(11, data["appointment"][0]["id"])
        self.assertNotIn("value", data)

    async def test_genie_versioned_plan_keeps_value_payload(self) -> None:
        coordinator = _Coordinator(self.plan, model="Genie 1000")
        previous = self.plan["value"][0]
        entry = native.build_native_entry(
            coordinator,
            {
                "weekdays": [1],
                "start_time": "08:15",
                "mode": "zone",
                "zones": "3",
                "enabled": True,
            },
            previous,
        )
        await native.async_publish_native_plan_change(
            coordinator,
            operation="edit",
            schedule_id="9",
            entry=entry,
        )
        data = coordinator.client.commands[-1]["data"]
        self.assertEqual(17, data["version"])
        self.assertEqual([entry], data["value"])
        self.assertNotIn("appointment", data)

    def test_extracts_nested_time_setting_archive(self) -> None:
        raw = io.BytesIO()
        payload = json.dumps({"data": {"appointment": self.plan["value"], "version": 4}}).encode()
        with tarfile.open(fileobj=raw, mode="w:gz") as archive:
            info = tarfile.TarInfo("map/time_setting.json")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        plan = native._plan_from_map_manager(raw.getvalue())
        self.assertEqual(4, plan["version"])
        self.assertEqual(2, len(plan["value"]))

    def test_unwraps_aws_shadow_envelope_and_bare_list(self) -> None:
        wrapped = {
            "value": {
                "timezone": 2,
                "timezone_sec": 7200,
                "value": [self.plan["value"][0]],
            },
            "timestamp": 1_789_718_400,
        }
        coordinator = _Coordinator(wrapped, model="Genie 1000")
        rules = native.native_rules_for(coordinator)
        self.assertEqual(1, len(rules))
        self.assertEqual("09:30", rules[0]["start_time"])

        listed = _Coordinator([self.plan["value"][0]], model="Genie 1000")
        self.assertEqual("09:30", native.native_rules_for(listed)[0]["start_time"])

        encoded = _Coordinator(json.dumps(wrapped), model="Genie 1000")
        self.assertEqual("09:30", native.native_rules_for(encoded)[0]["start_time"])

    def test_parses_genie_single_appointment_object(self) -> None:
        coordinator = _Coordinator(
            {
                "start_time": 9 * 3600,
                "active": 1,
                "unlock": 1,
                "week": [0, 1, 2, 3, 4, 5, 6],
                "repeat": 1,
                "workmode": 0,
            },
            model="Genie 1000",
        )
        rule = native.native_rules_for(coordinator)[0]
        self.assertEqual("09:00", rule["start_time"])
        self.assertEqual(list(range(7)), rule["weekdays"])

    def test_weekdays_accept_zero_based_and_bitmask(self) -> None:
        self.assertEqual([0, 2, 6], native._weekday_list([1, 3, 7]))
        self.assertEqual([0, 1, 6], native._weekday_list([0, 1, 6]))
        self.assertEqual(list(range(7)), native._weekday_list(127))

    async def test_appointment_time_downloads_real_genie_plan_file(self) -> None:
        coordinator = _Coordinator(None, model="Genie 1000")
        coordinator.account_client = _AccountClient(
            {
                "timezone": 2,
                "value": [
                    {
                        "start_time": 9 * 3600,
                        "active": 1,
                        "unlock": 1,
                        "week": [1, 2, 3, 4, 5, 6, 7],
                        "repeat": 1,
                        "workmode": 0,
                    }
                ],
            }
        )
        coordinator.reported_state = {
            "appointment": {"value": [], "timestamp": 1},
            # This is a file revision, not the scheduled mowing time.
            "appointment_time": 1_789_718_400,
        }
        self.assertTrue(await native.async_refresh_native_plan(coordinator))
        rules = native.native_rules_for(coordinator)
        self.assertEqual(1, len(rules))
        self.assertEqual("09:00", rules[0]["start_time"])
        self.assertEqual(list(range(7)), rules[0]["weekdays"])
        self.assertTrue(rules[0]["repeating"])
        self.assertEqual(["TEST123"], coordinator.account_client.appointment_requests)
        self.assertEqual(
            "loaded",
            coordinator.reported_state["_native_schedule_probe"]["status"],
        )
        self.assertEqual(
            1,
            coordinator.reported_state["_native_schedule_probe"]["entry_count"],
        )

    async def test_appointment_probe_exposes_parse_failure_shape(self) -> None:
        coordinator = _Coordinator(None, model="Genie 1000")
        coordinator.account_client = _AccountClient(
            {
                "_binary_probe": {
                    "label": "appointment",
                    "size": 12,
                    "first_bytes": "00 01",
                    "decode_errors": ["raw/json:test"],
                },
                "_download_source": {
                    "filename": "appointment_TEST123.json",
                    "category": "device",
                    "sub_category": "appointment",
                },
            }
        )
        coordinator.reported_state = {"appointment_time": 1_789_718_400}
        self.assertFalse(await native.async_refresh_native_plan(coordinator))
        probe = coordinator.reported_state["_native_schedule_probe"]
        self.assertEqual("parse_failed", probe["status"])
        self.assertEqual("appointment_TEST123.json", probe["download_source"]["filename"])
        self.assertEqual(12, probe["binary_probe"]["size"])

    def test_service_shadow_appointment_is_visible(self) -> None:
        coordinator = _Coordinator(None, model="Genie 1000")
        coordinator.reported_state = {
            "_service_reported": {
                "appointment": {
                    "value": [
                        {
                            "start_time": "09:00",
                            "active": 1,
                            "unlock": 1,
                            "week": [1, 2, 3, 4, 5, 6, 7],
                            "repeat": 1,
                            "workmode": 0,
                        }
                    ]
                }
            }
        }
        self.assertEqual("09:00", native.native_rules_for(coordinator)[0]["start_time"])

    def test_appointment_time_is_not_invented_as_a_schedule(self) -> None:
        coordinator = _Coordinator(None, model="Genie 1000")
        coordinator.reported_state = {"appointment_time": 1_789_718_400}
        self.assertEqual([], native.native_rules_for(coordinator))


if __name__ == "__main__":
    unittest.main()
