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
        self.reported_state = {
            "path_time": "old-time",
            "path": [{"x": 999, "y": 999}],
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

    def test_new_task_immediately_publishes_explicit_empty_path(self) -> None:
        coordinator = _Coordinator()

        self.module._publish_empty_new_task_path(coordinator)

        self.assertEqual(coordinator._path_definition, {"_path_points": []})
        self.assertEqual(
            coordinator.published["_path_definition"],
            {"_path_points": []},
        )
        self.assertIsNone(coordinator._history_path_info)
        self.assertIsNone(coordinator._history_path_source)
        self.assertIsNone(coordinator._path_definition_error)
        self.assertTrue(coordinator._genie_path_waiting_for_new_time)
        self.assertEqual(
            coordinator._genie_path_session_baseline_time,
            "old-time",
        )
        self.assertEqual(coordinator._genie_path_session_generation, 1)
        self.assertIsNone(coordinator._last_history_path_request)
        self.assertEqual(coordinator._last_history_path_request_monotonic, 0.0)

    def test_stale_old_path_is_masked_until_new_path_time_arrives(self) -> None:
        coordinator = _Coordinator()
        self.module._publish_empty_new_task_path(coordinator)

        stale = {
            **coordinator.reported_state,
            "path_time": "old-time",
            "_path_definition": {
                "path_id": "old-path",
                "_path_points": [{"x": 1, "y": 1}],
            },
            "_history_path_info": {"path_id": "old-path"},
        }
        masked = self.module._mask_stale_path_while_waiting(coordinator, stale)

        self.assertEqual(masked["_path_definition"], {"_path_points": []})
        self.assertIsNone(masked["_history_path_info"])
        self.assertTrue(coordinator._genie_path_waiting_for_new_time)

        fresh = {
            **masked,
            "path_time": "new-time",
            "_path_definition": {
                "path_id": "new-path",
                "_path_points": [{"x": 5, "y": 6}],
            },
        }
        accepted = self.module._mask_stale_path_while_waiting(coordinator, fresh)

        self.assertIs(accepted, fresh)
        self.assertEqual(accepted["_path_definition"]["path_id"], "new-path")
        self.assertFalse(coordinator._genie_path_waiting_for_new_time)
        self.assertEqual(coordinator._genie_path_session_baseline_time, "new-time")

    def test_websocket_stream_resets_even_if_stale_top_level_path_exists(self) -> None:
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

        reset_state = {
            "path_time": "old-time",
            # Simulate a stale legacy top-level path. The explicit empty
            # _path_points list must win and prevent fallback to this value.
            "path": [{"x": 999, "y": 999}],
            "_history_path_info": None,
            "_path_definition": {"_path_points": []},
        }
        delta, _ = self.stream.build_delta("GENIE", 1, cursor, reset_state)

        self.assertIsNotNone(delta)
        self.assertEqual(delta["path"]["op"], "reset")
        self.assertEqual(delta["path"]["points"], [])

    def test_refresh_layer_is_genie_only_and_installed_after_status_diagnostics(self) -> None:
        source = (MODELS / "genie_live_path_refresh.py").read_text(encoding="utf-8")
        common = (MODELS / "m_series_common.py").read_text(encoding="utf-8")

        self.assertIn('== "genie"', source)
        self.assertIn("install_genie_live_path_refresh()", common)
        self.assertGreater(
            common.index("install_genie_live_path_refresh()"),
            common.index("install_genie_path_diagnostics()"),
        )
        self.assertLess(
            common.index("install_genie_live_path_refresh()"),
            common.index("install_live_task_event_refresh()"),
        )


if __name__ == "__main__":
    unittest.main()
