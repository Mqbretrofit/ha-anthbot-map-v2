"""Regression coverage for additive v2.4.7.2 live-map hardening."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.anthbot_map"
PACKAGE_DIR = ROOT / "custom_components" / "anthbot_map"


def _load_module(name: str, filename: str):
    custom_components = sys.modules.setdefault(
        "custom_components", types.ModuleType("custom_components")
    )
    custom_components.__path__ = [str(ROOT / "custom_components")]
    package = sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
    package.__path__ = [str(PACKAGE_DIR)]

    mower_name = f"{PACKAGE}.mower_status"
    if mower_name not in sys.modules:
        mower_spec = importlib.util.spec_from_file_location(
            mower_name, PACKAGE_DIR / "mower_status.py"
        )
        assert mower_spec and mower_spec.loader
        mower_module = importlib.util.module_from_spec(mower_spec)
        sys.modules[mower_name] = mower_module
        mower_spec.loader.exec_module(mower_module)

    spec = importlib.util.spec_from_file_location(name, PACKAGE_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hardening = _load_module(f"{PACKAGE}.live_map_hardening", "live_map_hardening.py")


def state(*, zone_x: int = 0, pose_x: float = 5.0, status: str = "globalmowing") -> dict:
    return {
        "robot_sta": status,
        "pose": {"x": pose_x, "y": 5.0, "heading": 90.0},
        "_map_definition": {
            "map_id": "map-1",
            "_map_raster": {
                "encoding": "rle",
                "width": 100,
                "height": 100,
                "bounds": {"min_x": 0, "min_y": 0, "max_x": 10, "max_y": 10},
            },
        },
        "_area_definition": {
            "custom_areas": [
                {
                    "id": 7,
                    "name": "North",
                    "mow_count": 1,
                    "points": [[zone_x, 0], [10, 0], [10, 10], [zone_x, 10]],
                }
            ]
        },
        "_ridable_area_definition": {
            "ridable_areas": [
                {"id": 1, "points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
            ]
        },
        "_path_definition": {
            "path_id": "live-1",
            "_m_series_first_index": 0,
            "_m_series_last_index": 2,
            "_path_points": [
                {"x": 1, "y": 1},
                {"x": 2, "y": 2},
                {"x": 3, "y": 3},
            ],
        },
    }


class TestLiveMapHardening(unittest.TestCase):
    def test_geometry_fingerprint_changes_when_same_size_zone_moves(self) -> None:
        first = state(zone_x=0)
        moved = state(zone_x=1)
        self.assertNotEqual(
            hardening.map_geometry_fingerprint(first),
            hardening.map_geometry_fingerprint(moved),
        )

    def test_non_geometry_setting_does_not_rotate_fingerprint(self) -> None:
        first = state()
        changed = state()
        changed["_area_definition"]["custom_areas"][0]["mow_count"] = 3
        changed["_area_definition"]["custom_areas"][0]["name"] = "Renamed"
        self.assertEqual(
            hardening.map_geometry_fingerprint(first),
            hardening.map_geometry_fingerprint(changed),
        )

    def test_nan_and_clear_out_of_bounds_pose_are_rejected(self) -> None:
        nan_state = state()
        nan_state["pose"] = {"x": float("nan"), "y": 5}
        self.assertIsNone(hardening.validated_pose(nan_state))

        outside = state(pose_x=1000)
        self.assertIsNone(hardening.validated_pose(outside))

    def test_edge_pose_keeps_tolerant_bounds_margin(self) -> None:
        near_edge = state(pose_x=12)
        pose = hardening.validated_pose(near_edge)
        self.assertIsNotNone(pose)
        self.assertEqual(pose["x"], 12.0)

    def test_pose_revision_ignores_unrelated_shadow_churn(self) -> None:
        first = state()
        changed = state()
        changed["battery"] = 73
        changed["map_time"] = 999
        self.assertEqual(
            hardening.pose_revision_token(first),
            hardening.pose_revision_token(changed),
        )

    def test_capabilities_are_sparse_and_never_guess_unsupported(self) -> None:
        capabilities = hardening.feature_capabilities(state())
        self.assertEqual(capabilities["live_map_stream"]["state"], "supported")
        self.assertEqual(capabilities["absolute_path_delta"]["state"], "supported")
        self.assertEqual(capabilities["map_raster"]["state"], "supported")
        self.assertEqual(capabilities["editable_boundary"]["state"], "supported")
        self.assertEqual(capabilities["known_dock_position"]["state"], "unknown")
        self.assertNotIn("unsupported", {item["state"] for item in capabilities.values()})

    def test_missing_evidence_stays_unknown(self) -> None:
        empty = {"pose": {"x": 1, "y": 1}}
        capabilities = hardening.feature_capabilities(empty)
        self.assertEqual(capabilities["absolute_path_delta"]["state"], "unknown")
        self.assertEqual(capabilities["map_raster"]["state"], "unknown")
        self.assertEqual(capabilities["editable_boundary"]["state"], "unknown")

    def test_source_keeps_dock_learning_pose_gated(self) -> None:
        source = (PACKAGE_DIR / "live_map_hardening.py").read_text(encoding="utf-8")
        self.assertIn('if mower_activity_name(state) == "docked":', source)
        self.assertIn("if token != hub._anthbot_pose_token:", source)
        self.assertIn("Never infer dock coordinates", source)

    def test_source_has_stale_and_map_mismatch_suppression(self) -> None:
        source = (PACKAGE_DIR / "live_map_hardening.py").read_text(encoding="utf-8")
        self.assertIn('status = "map_mismatch"', source)
        self.assertIn('status = "stale"', source)
        self.assertIn('"pose": None', source)
        self.assertIn("POSITION_MAX_AGE_SECONDS = 90.0", source)

    def test_snapshot_work_is_coalesced_and_shielded(self) -> None:
        source = (PACKAGE_DIR / "live_map_hardening.py").read_text(encoding="utf-8")
        self.assertIn("_anthbot_snapshot_inflight", source)
        self.assertIn("_anthbot_snapshot_cache", source)
        self.assertIn("await asyncio.shield(task)", source)
        self.assertIn("SNAPSHOT_CACHE_SECONDS = 1.0", source)
        self.assertIn("async_add_executor_job", source)

    def test_heartbeat_is_background_and_model_decoders_are_untouched(self) -> None:
        hardening_source = (PACKAGE_DIR / "live_map_hardening.py").read_text(
            encoding="utf-8"
        )
        models_init = (PACKAGE_DIR / "models" / "__init__.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("hass.async_create_background_task(", hardening_source)
        self.assertNotIn("hass.async_create_task(", hardening_source)
        self.assertIn("install_live_map_hardening()", models_init)

    def test_transport_hardening_does_not_call_cloud_or_refresh(self) -> None:
        source = (PACKAGE_DIR / "live_map_hardening.py").read_text(encoding="utf-8")
        self.assertNotIn("account_client", source)
        self.assertNotIn("shadow_client", source)
        self.assertNotIn("async_refresh", source)
        self.assertNotIn("download", source)


if __name__ == "__main__":
    unittest.main()
