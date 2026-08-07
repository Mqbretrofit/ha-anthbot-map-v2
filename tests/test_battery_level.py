"""Regression tests for Anthbot battery payload formats."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SENSOR_PATH = ROOT / "custom_components/anthbot_map/sensor.py"


def _load_battery_helpers():
    """Load only the dependency-free battery helper functions from sensor.py."""
    source = SENSOR_PATH.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(SENSOR_PATH))
    selected = [
        node
        for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_as_int", "_battery_level"}
    ]
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(SENSOR_PATH), "exec"), namespace)
    return namespace["_battery_level"]


battery_level = _load_battery_helpers()


class TestBatteryLevel(unittest.TestCase):
    """Verify Genie, M5 and M9 battery payloads."""

    def test_direct_numeric_value(self) -> None:
        self.assertEqual(battery_level({"elec": 85}), 85)

    def test_single_value_wrapper(self) -> None:
        self.assertEqual(battery_level({"elec": {"value": 85}}), 85)

    def test_m9_timestamped_nested_value_wrapper(self) -> None:
        self.assertEqual(
            battery_level(
                {
                    "elec": {
                        "value": {
                            "time": 1786014185003,
                            "value": 100,
                        }
                    }
                }
            ),
            100,
        )

    def test_numeric_string_in_nested_wrapper(self) -> None:
        self.assertEqual(
            battery_level({"elec": {"value": {"value": "42"}}}),
            42,
        )

    def test_missing_or_invalid_values_return_none(self) -> None:
        for payload in (
            {},
            {"elec": None},
            {"elec": {}},
            {"elec": {"value": {"time": 1786014185003}}},
            {"elec": "invalid"},
            {"elec": -1},
            {"elec": 101},
        ):
            with self.subTest(payload=payload):
                self.assertIsNone(battery_level(payload))

    def test_cyclic_wrapper_returns_none(self) -> None:
        wrapper = {}
        wrapper["value"] = wrapper
        self.assertIsNone(battery_level({"elec": wrapper}))


if __name__ == "__main__":
    unittest.main()
