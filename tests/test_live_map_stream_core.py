"""Regression tests for the dedicated live-map delta protocol."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components" / "anthbot_map" / "live_map_stream_core.py"
spec = spec_from_file_location("anthbot_live_map_stream_core_test", MODULE_PATH)
module = module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def point(x):
    return {"x": x, "y": 0, "type": 1}


def state(points, *, path_id="p1", first=None, map_time=1, area_time=1, pose_x=0):
    definition = {
        "path_id": path_id,
        "point_count": len(points),
        "coordinate_scale": 10,
        "_path_points": points,
    }
    if first is not None:
        definition["_m_series_first_index"] = first
        definition["_m_series_last_index"] = first + len(points) - 1
    return {
        "_path_definition": definition,
        "path_time": len(points),
        "map_time": map_time,
        "area_time": area_time,
        "pose": {"x": pose_x, "y": 2, "yaw": 3},
        "_map_definition": {
            "map_id": "m1",
            "_map_raster": {
                "width": 2,
                "height": 2,
                "bounds": {"min_x": 0, "max_x": 1, "min_y": 0, "max_y": 1},
                "runs": [1],
            },
        },
        "_area_definition": {
            "custom_areas": [{"id": 1, "points": [[0, 0], [1, 0], [1, 1]]}]
        },
    }


class TestLiveMapStreamCore(unittest.TestCase):
    def test_snapshot_contains_full_path_and_static_geometry(self):
        payload, cursor = module.build_snapshot(
            "SERIAL", 0, state([point(1), point(2)], first=10)
        )
        self.assertEqual(payload["protocol"], 2)
        self.assertEqual(payload["kind"], "snapshot")
        self.assertEqual(payload["sequence"], 0)
        self.assertEqual(payload["path"]["op"], "reset")
        self.assertEqual(payload["path"]["start_index"], 10)
        self.assertEqual(payload["path"]["end_index"], 11)
        self.assertEqual([p["x"] for p in payload["path"]["points"]], [1, 2])
        self.assertIn("area_definition", payload["attributes"])
        self.assertIn("map_raster", payload["attributes"])
        self.assertEqual(cursor.path_last_index, 11)

    def test_absolute_append_sends_only_new_points(self):
        _, cursor = module.build_snapshot(
            "S", 0, state([point(1), point(2)], first=0)
        )
        payload, current = module.build_delta(
            "S",
            1,
            cursor,
            state([point(1), point(2), point(3), point(4)], first=0),
        )
        self.assertIsNotNone(payload)
        path = payload["path"]
        self.assertEqual(path["op"], "append")
        self.assertEqual(path["append_from_index"], 2)
        self.assertEqual([p["x"] for p in path["points"]], [3, 4])
        self.assertIsNone(path["trim_before_index"])
        self.assertEqual(current.path_last_index, 3)

    def test_rolling_window_trims_front_and_appends_tail(self):
        old = [point(i) for i in range(100, 105)]
        _, cursor = module.build_snapshot("S", 0, state(old, first=100))
        new = [point(i) for i in range(102, 107)]
        payload, current = module.build_delta("S", 1, cursor, state(new, first=102))
        path = payload["path"]
        self.assertEqual(path["op"], "append")
        self.assertEqual(path["trim_before_index"], 102)
        self.assertEqual(path["append_from_index"], 105)
        self.assertEqual([p["x"] for p in path["points"]], [105, 106])
        self.assertEqual(current.path_first_index, 102)
        self.assertEqual(current.path_last_index, 106)

    def test_path_replacement_resets(self):
        _, cursor = module.build_snapshot(
            "S", 0, state([point(1), point(2)], first=0, path_id="p1")
        )
        payload, _ = module.build_delta(
            "S", 1, cursor, state([point(9)], first=0, path_id="p2")
        )
        self.assertEqual(payload["path"]["op"], "reset")
        self.assertEqual(payload["path"]["path_id"], "p2")
        self.assertEqual([p["x"] for p in payload["path"]["points"]], [9])

    def test_pose_only_delta_does_not_reset_path(self):
        base = state([point(1), point(2)], first=0, pose_x=1)
        _, cursor = module.build_snapshot("S", 0, base)
        changed = state([point(1), point(2)], first=0, pose_x=5)
        changed["path_time"] = base["path_time"]
        payload, _ = module.build_delta("S", 1, cursor, changed)
        self.assertEqual(payload["attributes"]["pose"]["x"], 5)
        self.assertNotIn("path", payload)

    def test_rewritten_tail_resets_instead_of_corrupt_append(self):
        _, cursor = module.build_snapshot(
            "S", 0, state([point(1), point(2)], first=0)
        )
        payload, _ = module.build_delta(
            "S", 1, cursor, state([point(1), point(99), point(3)], first=0)
        )
        self.assertEqual(payload["path"]["op"], "reset")

    def test_rotating_map_time_does_not_resend_static_raster(self):
        base = state([point(1)], first=0, map_time=1)
        _, cursor = module.build_snapshot("S", 0, base)
        changed = state([point(1)], first=0, map_time=999)
        changed["path_time"] = base["path_time"]
        payload, _ = module.build_delta("S", 1, cursor, changed)
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
