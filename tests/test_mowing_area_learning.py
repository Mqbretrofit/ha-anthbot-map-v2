"""Behavior tests for learned mowing-area progress without importing Home Assistant."""

import ast
from pathlib import Path
from typing import Any
import unittest


ROOT = Path(__file__).parents[1]
COORDINATOR = ROOT / "custom_components/anthbot_map/models/genie.py"
SENSOR = ROOT / "custom_components/anthbot_map/sensor.py"


def _coordinator_helper_class():
    tree = ast.parse(COORDINATOR.read_text(encoding="utf-8-sig"))
    original = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "AnthbotGenieDataUpdateCoordinator"
    )
    names = {"_mowing_area_reference", "_manual_mowing_area_key"}
    methods = [
        node
        for node in original.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    module = ast.Module(
        body=[ast.ClassDef(name="Helpers", bases=[], keywords=[], body=methods, decorator_list=[])],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {"Any": Any}
    exec(compile(module, str(COORDINATOR), "exec"), namespace)
    return namespace["Helpers"]


def _sensor_helpers():
    tree = ast.parse(SENSOR.read_text(encoding="utf-8-sig"))
    names = {
        "_safe_get",
        "_progress_float",
        "_progress_learning_key",
        "_progress_learning_debug",
        "_progress_target_area",
        "_mowing_progress",
        "_active_zone_area",
    }
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    module = ast.Module(body=functions, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Any": Any,
        "active_manual_zone_ids": lambda data: data.get("active_ids", []),
        "_progress_active_zone_debug": lambda data: {
            "calibrated_area_total_m2": data.get("geometric_area"),
            "area_source": "active_zone_polygon_calibrated_to_map_area",
        },
    }
    exec(compile(module, str(SENSOR), "exec"), namespace)
    return namespace


class TestMowingAreaLearning(unittest.TestCase):
    def test_three_sample_reference_is_the_median(self) -> None:
        helpers = _coordinator_helper_class()
        self.assertEqual(helpers._mowing_area_reference([92.0, 94.0, 93.0]), 93.0)
        self.assertEqual(helpers._mowing_area_reference([93.0, 95.0]), 94.0)

    def test_zone_selection_key_is_order_independent(self) -> None:
        helpers = _coordinator_helper_class()
        self.assertEqual(
            helpers._manual_mowing_area_key([101, 100, 101]),
            "manual:100,101",
        )

    def test_93_m2_completed_zone_becomes_100_percent(self) -> None:
        helpers = _sensor_helpers()
        data = {
            "active_ids": [100],
            "geometric_area": 114.466,
            "mowing_area_new": {"value": 93},
            "_mowing_area_learning": {
                "sample_limit": 3,
                "current_key": "manual:100",
                "profiles": {
                    "manual:100": {
                        "samples_m2": [93.0],
                        "sample_count": 1,
                        "reference_m2": 93.0,
                    }
                },
            },
        }
        self.assertEqual(
            helpers["_progress_target_area"](data),
            (93.0, "learned_zone_mowing_area"),
        )
        self.assertEqual(helpers["_mowing_progress"](data), 100.0)
        self.assertEqual(helpers["_active_zone_area"](data), 114.466)

    def test_geometric_area_remains_fallback_before_learning(self) -> None:
        helpers = _sensor_helpers()
        data = {
            "active_ids": [100],
            "geometric_area": 114.466,
            "mowing_area_new": {"value": 93},
        }
        target, source = helpers["_progress_target_area"](data)
        self.assertEqual(target, 114.466)
        self.assertEqual(source, "active_zone_polygon_calibrated_to_map_area")
        self.assertEqual(helpers["_mowing_progress"](data), 81.2)


if __name__ == "__main__":
    unittest.main()
