"""Regression checks for app-native schedules, overrides and mower events."""

from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


class ScheduleOverrideSourceTests(unittest.TestCase):
    def test_schedule_platforms_load_with_the_config_entry(self) -> None:
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        mower_source = (INTEGRATION / "lawn_mower.py").read_text(encoding="utf-8")
        self.assertIn('"calendar",', source)
        self.assertIn('"event",', source)
        self.assertIn("await async_setup_schedule(hass, entry)", source)
        self.assertNotIn("async_setup_schedule", mower_source)

    def test_override_expiry_and_duplicate_start_are_safe(self) -> None:
        source = (INTEGRATION / "schedule_engine.py").read_text(encoding="utf-8")
        self.assertIn('if action == "mow":', source)
        self.assertIn("SERVICE_RETURN_TO_DOCK", source)
        self.assertIn('rule["last_fired"] = stamp', source)
        self.assertIn("Persist before sending a mower command", source)
        self.assertNotIn('reported_state.get("_ha_schedule_last_fire")', source)

    def test_zone_height_next_mow_and_native_events_are_exposed(self) -> None:
        schedule = (INTEGRATION / "schedule_engine.py").read_text(encoding="utf-8")
        sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        events = (INTEGRATION / "event.py").read_text(encoding="utf-8")
        services = (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
        calendar = (INTEGRATION / "calendar.py").read_text(encoding="utf-8")
        self.assertIn("SERVICE_START_ZONE_MOW", schedule)
        self.assertIn("SERVICE_SET_MOW_HEIGHT", schedule)
        self.assertIn("class AnthbotNextMowSensor", sensor)
        for event_type in (
            "mowing_completed",
            "stuck",
            "error",
            "rain_hold",
            "docked",
        ):
            self.assertIn(f'"{event_type}"', events)
        for service in (
            "override_schedule:",
            "add_ha_schedule:",
            "delete_ha_schedule:",
        ):
            self.assertIn(service, services)
        self.assertIn('"zones": "zones"', calendar)
        self.assertIn('"height": "mow_height"', calendar)

    def test_next_mow_periodic_refresh_is_event_loop_safe(self) -> None:
        sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("from homeassistant.core import HomeAssistant, callback", sensor)
        self.assertIn("@callback\n    def _handle_time_update", sensor)
        self.assertIn("self._handle_time_update,", sensor)
        self.assertNotIn("lambda _now: self.async_write_ha_state()", sensor)

    def test_weather_guard_delays_and_retries_safely(self) -> None:
        schedule = (INTEGRATION / "schedule_engine.py").read_text(encoding="utf-8")
        services = (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
        self.assertIn("_async_weather_block_reason", schedule)
        self.assertIn('"pending_catch_up"', schedule)
        self.assertIn('"catch_up_expired"', schedule)
        self.assertIn('"get_forecasts"', schedule)
        for field in (
            "weather_entity:",
            "forecast_guard_hours:",
            "rain_probability:",
            "catch_up_hours:",
        ):
            self.assertIn(field, services)

    def test_schedule_is_managed_from_the_map_card(self) -> None:
        card = (INTEGRATION / "frontend" / "anthbot-map-card.js").read_text(
            encoding="utf-8"
        )
        panel = (INTEGRATION / "frontend" / "schedule-panel.js").read_text(
            encoding="utf-8"
        )
        sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
        self.assertIn('item("schedule", anthbotScheduleText(this, "schedule"), "mdi:calendar-clock")', card)
        self.assertIn("renderAnthbotSchedulePanel(this, body)", card)
        self.assertIn('nextMow: ["sensor", ["next_mow"]]', card)
        self.assertIn('data-role="next-mow-line" hidden', card)
        self.assertIn("updateNextMowDisplay", card)
        for service in (
            'call(card, "override_schedule"',
            'call(card, "add_ha_schedule"',
            'call(card, "delete_ha_schedule"',
        ):
            self.assertIn(service, panel)
        for field in (
            'name="weekday"',
            'name="mow_height"',
            'name="weather_entity"',
            'name="forecast_guard_hours"',
            'name="catch_up_hours"',
        ):
            self.assertIn(field, panel)
        self.assertIn('"schedules": self._public_schedules()', sensor)
        self.assertIn('"active_override": override_for(self.coordinator)', sensor)
        setup = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        manifest = json.loads(
            (INTEGRATION / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn(f'?v={manifest["version"]}', setup)

    def test_schedule_frontend_is_mirrored(self) -> None:
        for name in ("anthbot-map-card.js", "schedule-panel.js"):
            self.assertEqual(
                (INTEGRATION / "frontend" / name).read_bytes(),
                (ROOT / "www" / "anthbot-map" / name).read_bytes(),
            )

    def test_release_version_matches_manifest(self) -> None:
        manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        const = (INTEGRATION / "const.py").read_text(encoding="utf-8")
        version = manifest["version"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
        self.assertIn(f'INTEGRATION_VERSION = "{version}"', const)


if __name__ == "__main__":
    unittest.main()
