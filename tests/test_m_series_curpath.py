"""Regression tests for M5/M9 live curpath pose anchoring."""

from __future__ import annotations

import ast
import math
from pathlib import Path
import unittest
from typing import Any


ROOT = Path(__file__).parents[1]
COMPAT_PATH = ROOT / "custom_components/anthbot_map/m_series_compat.py"


def _load_curpath_helpers():
    source = COMPAT_PATH.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(COMPAT_PATH))
    names = {
        "_m_series_display_path_points",
        "_m_series_valid_pose",
        "_m_series_pose_for_update",
        "_m_series_anchor_path_to_pose",
    }
    selected = [
        node
        for node in parsed.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "Any": Any,
        "math": math,
        "_M_SERIES_PATH_SCALE": 1000.0,
    }
    exec(compile(module, str(COMPAT_PATH), "exec"), namespace)
    return namespace


HELPERS = _load_curpath_helpers()
select_pose = HELPERS["_m_series_pose_for_update"]
anchor_path = HELPERS["_m_series_anchor_path_to_pose"]


class MSeriesCurpathTests(unittest.TestCase):
    """Keep delta-only curpath packets in the last known M-series frame."""

    def test_cached_pose_is_used_when_delta_omits_pose(self) -> None:
        pose, source = select_pose(None, {"x": -5.786, "y": 2.391, "yaw": 12})

        self.assertEqual(source, "cached")
        self.assertEqual(pose, {"x": -5.786, "y": 2.391, "yaw": 12})

    def test_reported_pose_replaces_cached_pose(self) -> None:
        pose, source = select_pose(
            {"x": -5.7, "y": 2.4},
            {"x": -5.786, "y": 2.391},
        )

        self.assertEqual(source, "reported")
        self.assertEqual(pose, {"x": -5.7, "y": 2.4})

    def test_missing_pose_does_not_anchor_path_to_zero(self) -> None:
        self.assertEqual(
            anchor_path([{"x": 1000, "y": 2000}, {"x": 1100, "y": 2200}], None),
            [],
        )

    def test_curpath_last_point_is_anchored_to_selected_pose(self) -> None:
        points = anchor_path(
            [{"x": 1000, "y": 2000}, {"x": 1100, "y": 2200}],
            {"x": -5.786, "y": 2.391},
        )

        self.assertAlmostEqual(points[0]["x"], -5.886)
        self.assertAlmostEqual(points[0]["y"], 2.191)
        self.assertEqual(points[-1], {"x": -5.786, "y": 2.391})


if __name__ == "__main__":
    unittest.main()
