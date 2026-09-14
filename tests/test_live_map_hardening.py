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

    def test_position_status_current_stale_and_map_mismatch(self) -> None:
        current_state = state()
        fingerprint = hardening.map_geometry_fingerprint(current_state)
        hub = types.SimpleNamespace(
            _anthbot_geometry_fingerprint=fingerprint,
            _anthbot_pose_observed_at=1000.0,
            _anthbot_pose_geometry=fingerprint,
            _anthbot_last_known_pose=None,
            _anthbot_known_dock_pose=None,
        )

        current = hardening._position_attributes(hub, current_state, now=1001.0)
        self.assertEqual(current["position_status"], "current")
        self.assertNotIn("pose", current)

        stale = hardening._position_attributes(
            hub,
            current_state,
            now=1000.0 + hardening.POSITION_MAX_AGE_SECONDS + 1.0,
        )
        self.assertEqual(stale["position_status"], "stale")
        self.assertIsNone(stale["pose"])

        hub._anthbot_pose_geometry = "0" * 64
        mismatch = hardening._position_attributes(hub, current_state, now=1001.0)
        self.assertEqual(mismatch["position_status"], "map_mismatch")
        self.assertIsNone(mismatch["pose"])

    def test_dock_location_requires_new_pose_while_docked(self) -> None:
        docked = state(status="charge")
        fingerprint = hardening.map_geometry_fingerprint(docked)
        hub = types.SimpleNamespace(
            _anthbot_geometry_object_token=hardening.geometry_object_token(docked),
            _anthbot_geometry_fingerprint=fingerprint,
            _anthbot_pose_token=hardening.pose_revision_token(docked),
            _anthbot_pose_observed_at=1000.0,
            _anthbot_pose_geometry=fingerprint,
            _anthbot_last_known_pose=None,
            _anthbot_known_dock_pose=None,
        )

        # A charging state by itself must never manufacture dock coordinates.
        hardening._refresh_hub_observation(hub, docked)
        self.assertIsNone(hub._anthbot_known_dock_pose)

        # A later, genuinely changed pose while already docked is valid evidence.
        docked["pose"] = {"x": 6.0, "y": 5.0, "heading": 90.0}
        hardening._refresh_hub_observation(hub, docked)
        self.assertIsNotNone(hub._anthbot_known_dock_pose)
        self.assertEqual(
            hub._anthbot_known_dock_pose["position_status"], "known_dock"
        )
        capabilities = hardening.feature_capabilities(
            docked, known_dock_pose=hub._anthbot_known_dock_pose
        )
        self.assertEqual(capabilities["known_dock_position"]["state"], "supported")

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
