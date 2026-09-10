from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "n8_validation_interpret.py"

spec = importlib.util.spec_from_file_location("n8_validation_interpret", TOOL)
assert spec is not None and spec.loader is not None
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class N8ValidationInterpretTests(unittest.TestCase):
    def test_child_lock_is_identified(self) -> None:
        result = MODULE.classify(
            ["n8_protocol.candidate_fields.device_config.child_lock_switch"]
        )
        self.assertEqual(result["likely_feature"], "child_lock")
        self.assertFalse(result["ambiguous"])

    def test_dumping_area_is_identified_from_map_diff(self) -> None:
        result = MODULE.classify(
            ["area_setting.dump_grass_areas.geometry_fingerprints"]
        )
        self.assertEqual(result["likely_feature"], "dumping_area")

    def test_equal_feature_scores_are_marked_ambiguous(self) -> None:
        result = MODULE.classify(
            [
                "n8_protocol.candidate_fields.device_config.child_lock_switch",
                "n8_protocol.direct.anti_loss_radius",
            ]
        )
        self.assertIsNone(result["likely_feature"])
        self.assertTrue(result["ambiguous"])

    def test_unknown_path_is_not_mislabeled(self) -> None:
        result = MODULE.classify(["n8_protocol.direct.some_new_field"])
        self.assertIsNone(result["likely_feature"])
        self.assertEqual(result["feature_scores"], {})


if __name__ == "__main__":
    unittest.main()
