"""Regression tests for map sensor Recorder exclusions."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


SENSOR_PATH = (
    Path(__file__).parents[1] / "custom_components/anthbot_map/sensor.py"
)


class TestMapSensorRecording(unittest.TestCase):
    """Ensure map attributes stay live but are excluded from Recorder."""

    def test_all_map_attributes_are_unrecorded(self) -> None:
        tree = ast.parse(SENSOR_PATH.read_text(encoding="utf-8"))
        map_entity = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "AnthbotMapSensorEntity"
        )

        exclusion_assignment = next(
            node
            for node in map_entity.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "_unrecorded_attributes"
                for target in node.targets
            )
        )
        excluded = set(ast.literal_eval(exclusion_assignment.value.args[0]))

        attributes_method = next(
            node
            for node in map_entity.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "extra_state_attributes"
        )
        returned_attributes = next(
            node.value
            for node in ast.walk(attributes_method)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        )
        live_attribute_names = {
            ast.literal_eval(key) for key in returned_attributes.keys if key is not None
        }

        self.assertEqual(live_attribute_names, excluded)


if __name__ == "__main__":
    unittest.main()
