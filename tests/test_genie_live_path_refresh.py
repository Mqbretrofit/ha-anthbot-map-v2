from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"
MODELS = COMPONENT / "models"
PACKAGE = "anthbot_genie_live_path_test"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_path_refresh_module():
    root_package = types.ModuleType(PACKAGE)
    root_package.__path__ = [str(COMPONENT)]
    sys.modules[PACKAGE] = root_package

    models_package = types.ModuleType(f"{PACKAGE}.models")
    models_package.__path__ = [str(MODELS)]
    sys.modules[f"{PACKAGE}.models"] = models_package

    _load_module(f"{PACKAGE}.models.base", MODELS / "base.py")
    return _load_module(
        f"{PACKAGE}.models.genie_live_path_refresh",
        MODELS / "genie_live_path_refresh.py",
    )


class _Coordinator:
    def __init__(self) -> None:
        self.client = types.SimpleNamespace(serial_number="GENIE123")
        self.reported_state = {
            "path_time": "old-time",
            "path": [
                {"x": 0, "y": 0},
                {"x": 100, "y": 100},
            ],
            "_path_definition": {
                "path_id": "old-path",
                "_path_points": [
                    {"x": 0, "y": 0},
                    {"x": 100, "y": 100},
                ],
            },
            "_history_path_info": {"path_id": "old-path"},
            "_history_path_source": "presigned",
        }
        self._path_definition = self.reported_state["_path_definition"]
        self._history_path_info = self.reported_state["_history_path_info"]
        self._history_path_source = "presigned"
        self._path_definition_error = "old-error"
        self._last_path_time = "old-time"
        self._last_path_download_monotonic = 123.0
        self._last_history_path_request = "old-time"
        self._last_history_path_request_monotonic = 456.0
        self._genie_path_session_generation = 0
        self._genie_path_render_session = 0
        self.published: dict | None = None

    def async_set_updated_data(self, state: dict) -> None:
        self.reported_state = state
        self.published = state


class GenieLivePathRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_path_refresh_module()
        cls.stream = _load_module(
            f"{PACKAGE}.live_map_stream_core",
            COMPONENT / "live_map_stream_core.py",
        )

    def test_new_task_keeps_old_path_visible_until_fresh_snapshot(self) -> None:
        coordinator = _Coordinator()
        old_definition = coordinator._path_definition

        self.module._begin_new_task_path_session(coordinator)

        self.assertIs(coordinator._path_definition, old_definition)
        self.assertEqual(
            coordinator._genie_path_visible_definition["path_id"],
            "old-path",
        )
        self.assertTrue(coordinator._genie_path_waiting_for_new_time)
        self.assertEqual(
            coordinator._genie_path_session_baseline_time,
            "old-time",
        )
        self.assertEqual(coordinator._genie_path_session_generation, 1)
        self.assertEqual(coordinator._genie_path_render_session, 1)
        self.assertIsNone(coordinator._last_history_path_request)
        self.assertEqual(coordinator._last_history_path_request_monotonic, 0.0)
        self.assertIsNone(coordinator.published)

    def test_stale_refresh_keeps_visible_old_path_then_swaps_atomically(self) -> None:
        coordinator = _Coordinator()
        self.module._begin_new_task_path_session(coordinator)

        stale = {
            **coordinator.reported_state,
            "path_time": "old-time",
            "_path_definition": {
                "path_id": "stale-cloud-copy",
                "_path_points": [{"x": 1, "y": 1}],
            },
            "_history_path_info": {"path_id": "stale-cloud-copy"},
        }
        masked = self.module._accept_waiting_state_if_fresh(coordinator, stale)

        self.assertEqual(masked["_path_definition"]["path_id"], "old-path")
        self.assertEqual(len(masked["_path_definition"]["_path_points"]), 2)
        self.assertEqual(masked["path_time"], "old-time")
        self.assertTrue(coordinator._genie_path_waiting_for_new_time)

        fresh = {
            **masked,
            "path_time": "new-time",
            "_path_definition": {
                "path_id": "new-path",
                "_path_points": [
                    {"x": 5, "y": 6},
                    {"x": 7, "y": 8},
                ],
            },
            "_history_path_info": {"path_id": "new-path"},
            "_history_path_source": "presigned",
        }
        accepted = self.module._accept_waiting_state_if_fresh(coordinator, fresh)

        self.assertEqual(accepted["_path_definition"]["path_id"], "new-path")
        self.assertEqual(accepted["path"], accepted["_path_definition"]["_path_points"])
        self.assertFalse(coordinator._genie_path_waiting_for_new_time)
        self.assertEqual(coordinator._genie_path_session_baseline_time, "new-time")

    def test_path_id_change_resets_without_empty_intermediate_frame(self) -> None:
        old_state = {
            "path_time": "old-time",
            "_history_path_info": {"path_id": "old-path"},
            "_path_definition": {
                "path_id": "old-path",
                "_path_points": [
                    {"x": 0, "y": 0},
                    {"x": 100, "y": 100},
                ],
            },
        }
        _, cursor = self.stream.build_snapshot("GENIE", 0, old_state)

        new_state = {
            "path_time": "new-time",
            "_history_path_info": {"path_id": "new-path"},
            "_path_definition": {
                "path_id": "new-path",
                "_path_points": [
                    {"x": 5, "y": 6},
                    {"x": 7, "y": 8},
                ],
            },
        }
        delta, _ = self.stream.build_delta("GENIE", 1, cursor, new_state)

        self.assertIsNotNone(delta)
        self.assertEqual(delta["path"]["op"], "reset")
        self.assertEqual(delta["path"]["path_id"], "new-path")
        self.assertEqual(delta["path"]["points"], new_state["_path_definition"]["_path_points"])

    def test_same_genie_snapshot_growth_uses_append(self) -> None:
        old_state = {
            "path_time": "t1",
            "_path_definition": {
                "path_id": "same-path",
                "_path_points": [
                    {"x": 0, "y": 0},
                    {"x": 1, "y": 1},
                ],
            },
        }
        _, cursor = self.stream.build_snapshot("GENIE", 0, old_state)
        grown_state = {
            "path_time": "t2",
            "_path_definition": {
                "path_id": "same-path",
                "_path_points": [
                    {"x": 0, "y": 0},
                    {"x": 1, "y": 1},
                    {"x": 2, "y": 2},
                ],
            },
        }

        delta, _ = self.stream.build_delta("GENIE", 1, cursor, grown_state)

        self.assertIsNotNone(delta)
        self.assertEqual(delta["path"]["op"], "append")
        self.assertEqual(delta["path"]["points"], [{"x": 2, "y": 2}])

    def test_refresh_layer_and_return_motion_are_ordered_genie_only(self) -> None:
        source = (MODELS / "genie_live_path_refresh.py").read_text(encoding="utf-8")
        motion = (MODELS / "genie_live_motion.py").read_text(encoding="utf-8")
        common = (MODELS / "m_series_common.py").read_text(encoding="utf-8")

        self.assertIn('== "genie"', source)
        self.assertIn('"backtodock"', motion)
        self.assertIn('"returningtodock"', motion)
        self.assertIn('"curPose"', motion)
        self.assertIn("install_genie_live_path_refresh()", common)
        self.assertIn("install_genie_live_motion_support()", common)
        self.assertGreater(
            common.index("install_genie_live_path_refresh()"),
            common.index("install_genie_path_diagnostics()"),
        )
        self.assertGreater(
            common.index("install_genie_live_motion_support()"),
            common.index("install_genie_live_path_refresh()"),
        )
        self.assertLess(
            common.index("install_genie_live_motion_support()"),
            common.index("install_live_task_event_refresh()"),
        )


if __name__ == "__main__":
    unittest.main()
