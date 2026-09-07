from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "anthbot_map" / "path_zone_check.py"
SPEC = importlib.util.spec_from_file_location("anthbot_path_zone_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _state_with_no_go(points, *, zone_id=3):
    return {
        "_area_definition": {
            "forbid_areas": [
                {
                    "id": zone_id,
                    "name": "test no-go",
                    "points": points,
                }
            ]
        }
    }


class PathZoneCheckTests(unittest.TestCase):
    def test_omnilink_replay_crossing_matches_reported_metrics(self):
        path = [
            {"x": 0, "y": 0},
            {"x": 100, "y": 0},
            {"x": 200, "y": 0},
            {"x": 300, "y": 0},
            {"x": 400, "y": 0},
            {"x": 500, "y": 0},
        ]
        state = _state_with_no_go(
            [(250, -50), (350, -50), (350, 50), (250, 50)]
        )

        result = MODULE.evaluate_path_no_go(path, state, path_id="live-7")

        self.assertIs(result["crossing_detected"], True)
        self.assertEqual(result["path_id"], "live-7")
        self.assertEqual(result["checked_point_count"], 6)
        self.assertEqual(result["points_inside"], 1)
        self.assertEqual(result["boundary_crossings"], 2)
        self.assertEqual(result["traversals"], 1)
        self.assertEqual(result["zone_ids"], [3])
        self.assertEqual(result["last_crossing"]["x"], 350.0)
        self.assertEqual(result["last_crossing"]["y"], 0.0)

    def test_segment_crossing_is_detected_even_without_sample_point_inside(self):
        path = [{"x": 0, "y": 0}, {"x": 500, "y": 0}]
        state = _state_with_no_go(
            [(250, -50), (350, -50), (350, 50), (250, 50)]
        )

        result = MODULE.evaluate_path_no_go(path, state)

        self.assertEqual(result["points_inside"], 0)
        self.assertEqual(result["boundary_crossings"], 2)
        self.assertEqual(result["traversals"], 1)
        self.assertIs(result["crossing_detected"], True)

    def test_break_before_does_not_create_false_crossing_across_missing_chunks(self):
        path = [
            {"x": 0, "y": 0},
            {"x": 100, "y": 0},
            {"x": 400, "y": 0, "break_before": True},
            {"x": 500, "y": 0},
        ]
        state = _state_with_no_go(
            [(250, -50), (350, -50), (350, 50), (250, 50)]
        )

        result = MODULE.evaluate_path_no_go(path, state)

        self.assertEqual(result["checked_segment_count"], 2)
        self.assertEqual(result["points_inside"], 0)
        self.assertEqual(result["boundary_crossings"], 0)
        self.assertEqual(result["traversals"], 0)
        self.assertIs(result["crossing_detected"], False)

    def test_known_no_go_payload_aliases_are_normalized_and_deduplicated(self):
        polygon = [[250, -50], [350, -50], [350, 50], [250, 50]]
        zone = {"id": 9, "vertices": polygon}
        state = {
            "area_definition": {
                "forbid_areas": [zone],
                "noGoAreas": [zone],
            }
        }

        zones = MODULE.no_go_zones(state)

        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]["id"], 9)
        self.assertEqual(zones[0]["points"][0], (250.0, -50.0))


if __name__ == "__main__":
    unittest.main()
