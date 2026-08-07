"""Tests for native Anthbot mower activity mapping."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "anthbot_map"
    / "mower_status.py"
)
SPEC = importlib.util.spec_from_file_location("anthbot_mower_status", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

mower_activity_name = MODULE.mower_activity_name
raw_robot_status = MODULE.raw_robot_status


class MowerActivityTests(unittest.TestCase):
    """Cover Anthbot shadow formats used by the native mower entity."""

    def test_string_statuses(self) -> None:
        self.assertEqual(
            mower_activity_name({"robot_sta": {"value": "globalmowing"}}),
            "mowing",
        )
        self.assertEqual(
            mower_activity_name({"robot_sta": {"value": "back_to_dock"}}),
            "returning",
        )
        self.assertEqual(
            mower_activity_name({"robot_sta": {"value": "charge"}}),
            "docked",
        )
        self.assertEqual(
            mower_activity_name({"robot_sta": {"value": "pause"}}),
            "paused",
        )

    def test_numeric_status_codes(self) -> None:
        self.assertEqual(mower_activity_name({"robot_sta": {"value": 6}}), "mowing")
        self.assertEqual(mower_activity_name({"robot_sta": {"value": 10}}), "returning")
        self.assertEqual(mower_activity_name({"robot_sta": {"value": 2}}), "docked")

    def test_nested_m_series_value_envelopes(self) -> None:
        payload = {
            "robot_sta": {
                "value": {
                    "time": 1786014185003,
                    "value": "regionmowing",
                }
            }
        }
        self.assertEqual(mower_activity_name(payload), "mowing")

    def test_error_takes_precedence(self) -> None:
        payload = {
            "robot_sta": {"value": "globalmowing"},
            "err_code": {"value": {"time": 1786014185003, "value": 230}},
        }
        self.assertEqual(mower_activity_name(payload), "error")

    def test_zero_error_does_not_override_activity(self) -> None:
        payload = {
            "robot_sta": {"value": "charge"},
            "err_code": {"value": 0},
        }
        self.assertEqual(mower_activity_name(payload), "docked")

    def test_mower_status_fallback_and_unknown(self) -> None:
        self.assertEqual(
            raw_robot_status({"mower_status": "Returning To Dock"}),
            "returningtodock",
        )
        self.assertEqual(
            mower_activity_name({"mower_status": "Returning To Dock"}),
            "returning",
        )
        self.assertIsNone(mower_activity_name({"robot_sta": {"value": "mapping"}}))


if __name__ == "__main__":
    unittest.main()
