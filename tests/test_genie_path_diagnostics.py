from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"
MODELS = COMPONENT / "models"
PACKAGE = "anthbot_genie_path_test"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_genie_module():
    root_package = types.ModuleType(PACKAGE)
    root_package.__path__ = [str(COMPONENT)]
    sys.modules[PACKAGE] = root_package

    models_package = types.ModuleType(f"{PACKAGE}.models")
    models_package.__path__ = [str(MODELS)]
    sys.modules[f"{PACKAGE}.models"] = models_package

    _load_module(f"{PACKAGE}.path_zone_check", COMPONENT / "path_zone_check.py")
    _load_module(f"{PACKAGE}.models.base", MODELS / "base.py")
    return _load_module(
        f"{PACKAGE}.models.genie_path_diagnostics",
        MODELS / "genie_path_diagnostics.py",
    )


class _Coordinator:
    _genie_no_go_check_signature = None
    _genie_no_go_check = None


class GeniePathDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_genie_module()

    def test_decoded_genie_path_gets_same_crossing_metrics(self) -> None:
        state = {
            "_path_definition": {
                "path_id": "genie-live-1",
                "_path_points": [
                    {"x": 0, "y": 0},
                    {"x": 100, "y": 0},
                    {"x": 200, "y": 0},
                    {"x": 300, "y": 0},
                    {"x": 400, "y": 0},
                    {"x": 500, "y": 0},
                ],
            },
            "_area_definition": {
                "forbid_areas": [
                    {
                        "id": 4,
                        "points": [
                            [250, -50],
                            [350, -50],
                            [350, 50],
                            [250, 50],
                        ],
                    }
                ]
            },
        }

        check = self.module._update_no_go_check(_Coordinator(), state)

        self.assertEqual(check["source"], "genie_decoded_path")
        self.assertEqual(check["path_id"], "genie-live-1")
        self.assertTrue(check["crossing_detected"])
        self.assertEqual(check["points_inside"], 1)
        self.assertEqual(check["boundary_crossings"], 2)
        self.assertEqual(check["traversals"], 1)
        self.assertEqual(check["zone_ids"], [4])

    def test_genie_falls_back_to_shared_path_attribute(self) -> None:
        state = {
            "path_id": "genie-path-fallback",
            "path": [{"x": 0, "y": 0}, {"x": 500, "y": 0}],
            "area_definition": {
                "noGoAreas": [
                    {
                        "id": 8,
                        "vertices": [
                            [250, -50],
                            [350, -50],
                            [350, 50],
                            [250, 50],
                        ],
                    }
                ]
            },
        }

        check = self.module._update_no_go_check(_Coordinator(), state)

        self.assertEqual(check["checked_point_count"], 2)
        self.assertEqual(check["points_inside"], 0)
        self.assertEqual(check["boundary_crossings"], 2)
        self.assertEqual(check["traversals"], 1)

    def test_genie_layer_is_installed_after_live_status_normalization(self) -> None:
        common = (MODELS / "m_series_common.py").read_text(encoding="utf-8")
        self.assertIn("install_genie_path_diagnostics()", common)
        self.assertGreater(
            common.index("install_genie_path_diagnostics()"),
            common.index("install_genie_live_status_support()"),
        )

    def test_genie_diagnostic_is_read_only(self) -> None:
        source = (MODELS / "genie_path_diagnostics.py").read_text(encoding="utf-8")
        self.assertNotIn('state["path"] =', source)
        self.assertNotIn('state["mowed_path"] =', source)
        self.assertNotIn('state["cloud_path"] =', source)
        self.assertIn('pending["_no_go_path_check"] = check', source)


if __name__ == "__main__":
    unittest.main()
