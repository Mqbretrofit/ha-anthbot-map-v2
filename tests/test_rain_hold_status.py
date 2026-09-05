"""Regression coverage for rain hold state and card status."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"


def _load_task_events_module():
    spec = importlib.util.spec_from_file_location(
        "anthbot_task_events_rain", COMPONENT / "task_events.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


events = _load_task_events_module()


class RainTaskEventTests(unittest.TestCase):
    def test_rain_return_survives_docking_events(self) -> None:
        payload = {
            "data": [
                {"code": 1022, "event_message": "Charging begins"},
                {"code": 1019, "event_message": "Starting to recharge"},
                {"code": 1036, "event_message": "It's raining, please recharge"},
                {"code": 1018, "event_message": "Zone mowing starts"},
            ]
        }
        self.assertEqual(events.latest_task_cycle_signal(payload), "rain_return")

    def test_resume_clears_old_rain_return(self) -> None:
        payload = {
            "data": [
                {"code": 1017, "event_message": "Task resumes"},
                {"code": 1022},
                {"code": 1019},
                {"code": 1036},
            ]
        }
        self.assertEqual(events.latest_task_cycle_signal(payload), "active")

    def test_finished_task_clears_old_rain_return(self) -> None:
        payload = {
            "data": [
                {"code": 1022},
                {"code": 1014, "event_message": "Task finished"},
                {"code": 1036},
            ]
        }
        self.assertEqual(events.latest_task_cycle_signal(payload), "completed")


class RainStatusSourceTests(unittest.TestCase):
    def test_binary_sensor_is_model_independent_and_event_backed(self) -> None:
        source = (COMPONENT / "binary_sensor.py").read_text(encoding="utf-8")
        self.assertIn('key="rain_hold"', source)
        self.assertIn('latest_task_cycle_signal(payload) != "rain_return"', source)
        self.assertNotIn('if description.key != "rain_hold"', source)
        self.assertNotIn('_is_m_series_model(coordinator.device.model)', source)
        self.assertIn('"source": "task_event"', source)
        self.assertIn('"event_code": 1036', source)

    def test_card_overrides_visible_status_while_rain_hold_is_on(self) -> None:
        card = (COMPONENT / "frontend" / "anthbot-map-card.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('rainHold: ["binary_sensor", ["rain_hold"]]', card)
        self.assertIn('rainHoldEntity?.state === "on"', card)
        self.assertIn('this.translateStatus("rain_hold")', card)

    def test_hungarian_and_english_status_labels_exist(self) -> None:
        source = (COMPONENT / "frontend" / "i18n.js").read_text(encoding="utf-8")
        self.assertIn('status_rain_hold: "waiting after rain"', source)
        self.assertIn('status_rain_hold: "eső miatti várakozás"', source)


if __name__ == "__main__":
    unittest.main()
