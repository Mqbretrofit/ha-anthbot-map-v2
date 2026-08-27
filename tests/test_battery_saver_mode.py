"""Regression tests for cloud task events and optional battery saver mode."""

from __future__ import annotations

from datetime import timezone
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"


def _load_task_events_module():
    spec = importlib.util.spec_from_file_location(
        "anthbot_task_events", COMPONENT / "task_events.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


events = _load_task_events_module()


class TaskEventTests(unittest.TestCase):
    def test_low_battery_return_is_detected(self) -> None:
        payload = {
            "data": [
                {"code": 1019, "event_message": "Starting to recharge"},
                {"code": 1021, "event_message": "Low battery level"},
                {"code": 1017, "event_message": "Task resumes"},
            ]
        }
        self.assertEqual(events.latest_task_cycle_signal(payload), "low_battery_return")

    def test_manual_return_does_not_look_like_low_battery(self) -> None:
        payload = {
            "data": [
                {"code": 1022, "event_message": "Charging begins"},
                {"code": 1019, "event_message": "Starting to recharge"},
                {"code": 1018, "event_message": "Zone mowing starts"},
            ]
        }
        self.assertEqual(events.latest_task_cycle_signal(payload), "active")

    def test_completed_task_wins_before_docking_events(self) -> None:
        payload = {
            "data": [
                {"code": 1022},
                {"code": 1019},
                {"code": 1014, "event_message": "Task finished"},
                {"code": 1015},
            ]
        }
        self.assertEqual(events.latest_task_cycle_signal(payload), "completed")

    def test_new_resume_clears_old_low_battery_signal(self) -> None:
        payload = {
            "data": [
                {"code": 1017, "event_message": "Task resumes"},
                {"code": 1022},
                {"code": 1019},
                {"code": 1021},
            ]
        }
        self.assertEqual(events.latest_task_cycle_signal(payload), "active")

    def test_latest_event_fields_and_timestamp(self) -> None:
        payload = {
            "data": {
                "data": [
                    {
                        "code": "1021",
                        "event_message": "Low battery level",
                        "create_time": "2026-08-23T19:28:32",
                    }
                ]
            }
        }
        self.assertEqual(events.task_event_code(payload), 1021)
        timestamp = events.task_event_datetime(payload)
        self.assertIsNotNone(timestamp)
        assert timestamp is not None
        self.assertEqual(timestamp.tzinfo, timezone.utc)


class BatterySaverSourceTests(unittest.TestCase):
    def test_mode_is_local_persistent_and_event_driven(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        config_flow = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        switch = (COMPONENT / "switch.py").read_text(encoding="utf-8")
        api = (COMPONENT / "api.py").read_text(encoding="utf-8")
        self.assertIn("battery_saver_store", coordinator)
        self.assertIn('"initial_charge"', coordinator)
        self.assertIn('"recovery_charge"', coordinator)
        self.assertIn('"manual_charge"', coordinator)
        self.assertIn("latest_task_cycle_signal", coordinator)
        self.assertIn("SERVICE_RESUME_MOW", coordinator)
        self.assertNotIn("mowing_progress(self.reported_state)", coordinator)
        self.assertIn("/api/v1/device/v2/code/list", api)
        self.assertIn("CONF_CHARGER_SWITCH", config_flow)
        self.assertIn("CONF_CHARGE_LIMIT", config_flow)
        self.assertIn("CONF_MAINTENANCE_LEVEL", config_flow)
        self.assertIn("CONF_RESUME_LEVEL", config_flow)
        self.assertIn("CONF_SHARED_RTK_POWER", config_flow)
        self.assertIn("async_update_battery_saver_config(user_input)", config_flow)
        self.assertIn("async def async_update_battery_saver_config", coordinator)
        self.assertIn("self.async_schedule_battery_saver_evaluation()", coordinator)
        self.assertIn("return AnthbotGenieOptionsFlow()", config_flow)
        self.assertNotIn("self._config_entry", config_flow)
        self.assertIn("AnthbotBatterySaverSwitchEntity", switch)

    def test_idle_charge_has_hysteresis_and_temporary_mute(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn("_async_maintain_idle_charge", coordinator)
        self.assertIn("CONF_MAINTENANCE_LEVEL", coordinator)
        self.assertIn("_async_mute_charging_announcement", coordinator)
        self.assertIn("_async_delayed_voice_volume_restore", coordinator)
        self.assertIn('cmd="volume_ctl", data={"volume": 0}', coordinator)

    def test_shared_station_rtk_supply_stays_on_for_mowing(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        commands = (COMPONENT / "commands.py").read_text(encoding="utf-8")
        mowing_block = coordinator.split("if is_mowing:", 1)[1].split(
            "if self._battery_saver_phase == \"initial_charge\"", 1
        )[0]
        self.assertIn("config[CONF_SHARED_RTK_POWER]", mowing_block)
        self.assertIn("async def async_prepare_mowing_power", coordinator)
        prepare_power = coordinator.split(
            "async def async_prepare_mowing_power", 1
        )[1].split("async def _async_maintain_idle_charge", 1)[0]
        self.assertIn("CONF_SHARED_RTK_POWER", prepare_power)
        self.assertIn("await coordinator.async_prepare_mowing_power()", commands)
        self.assertEqual(commands.count("mowing_start=True"), 2)

    def test_card_battery_saver_settings_have_a_persistent_backend(self) -> None:
        init_source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        const_source = (COMPONENT / "const.py").read_text(encoding="utf-8")
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        card = (COMPONENT / "frontend" / "anthbot-map-card.js").read_text(
            encoding="utf-8"
        )
        services = (COMPONENT / "services.yaml").read_text(encoding="utf-8")

        self.assertIn(
            'SERVICE_SET_BATTERY_SAVER_CONFIG = "set_battery_saver_config"',
            const_source,
        )
        self.assertIn("battery_saver_config_schema", init_source)
        self.assertIn("_handle_set_battery_saver_config", init_source)
        self.assertIn(
            "hass.config_entries.async_update_entry(entry, options=options)",
            init_source,
        )
        self.assertIn(
            "SERVICE_SET_BATTERY_SAVER_CONFIG,\n            _handle_set_battery_saver_config",
            init_source,
        )
        self.assertIn("SERVICE_SET_BATTERY_SAVER_CONFIG,", init_source)
        self.assertIn("CONF_SHARED_RTK_POWER", coordinator)
        self.assertIn('"set_battery_saver_config"', card)
        self.assertIn("shared_rtk_power", card)
        self.assertIn("set_battery_saver_config:", services)

    def test_mowed_path_stays_visible_during_recovery_charging(self) -> None:
        renderer = (
            ROOT / "custom_components" / "anthbot_map" / "frontend" / "renderer.js"
        ).read_text(encoding="utf-8")
        draw_path = renderer.split("drawMowedPath(ctx, geometry) {", 1)[1].split(
            "mowedCoverageScreenWidth", 1
        )[0]

        self.assertNotIn("isDockingOrChargingState(this.state)", draw_path)
        self.assertIn("mowedPathSessionId(state)", renderer)
        self.assertIn("nextSession !== this.currentMowedPathSessionId", renderer)

    def test_card_exposes_battery_saver_without_fake_progress(self) -> None:
        card = (COMPONENT / "frontend" / "anthbot-map-card.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('batterySaver: ["battery_saver_mode"', card)
        self.assertIn('this.t("batterySaverMode")', card)
        self.assertNotIn('mowingProgress: ["sensor"', card)

    def test_card_label_exists_for_every_supported_language(self) -> None:
        source = (COMPONENT / "frontend" / "i18n.js").read_text(encoding="utf-8")
        block = source.split("const batterySaverTranslations = {", 1)[1].split(
            "};", 1
        )[0]
        for language in (
            "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs",
            "sk", "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr",
            "th", "vi", "ko", "km",
        ):
            self.assertIn(f'{language}:', block.replace('"', ""))


if __name__ == "__main__":
    unittest.main()
