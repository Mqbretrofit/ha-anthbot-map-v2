"""Tests for conservative stationary live-map position display."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.anthbot_map"
PACKAGE_DIR = ROOT / "custom_components" / "anthbot_map"


def _ensure_package() -> None:
    custom_components = sys.modules.setdefault(
        "custom_components", types.ModuleType("custom_components")
    )
    custom_components.__path__ = [str(ROOT / "custom_components")]
    package = sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
    package.__path__ = [str(PACKAGE_DIR)]


def _load(name: str, filename: str):
    _ensure_package()
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PACKAGE_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mower_status = _load(f"{PACKAGE}.mower_status", "mower_status.py")
hardening = _load(f"{PACKAGE}.live_map_hardening", "live_map_hardening.py")
stationary = _load(
    f"{PACKAGE}.live_map_stationary_position", "live_map_stationary_position.py"
)


def state(status: str) -> dict:
    return {
        "robot_sta": status,
        "pose": {"x": 5.0, "y": 5.0, "heading": 90.0},
        "_map_definition": {
            "map_id": "map-1",
            "_map_raster": {
                "encoding": "rle",
                "width": 100,
                "height": 100,
                "bounds": {"min_x": 0, "min_y": 0, "max_x": 10, "max_y": 10},
            },
        },
        "_area_definition": {},
    }


def stale_hub(data: dict, *, known_dock: bool = False):
    geometry = hardening.map_geometry_fingerprint(data)
    last = hardening._position_record(  # noqa: SLF001
        data["pose"], observed_at=1000.0, geometry=geometry, status="last_known"
    )
    dock = (
        hardening._position_record(  # noqa: SLF001
            data["pose"], observed_at=1000.0, geometry=geometry, status="known_dock"
        )
        if known_dock
        else None
    )
    return types.SimpleNamespace(
        _anthbot_geometry_fingerprint=geometry,
        _anthbot_pose_observed_at=1000.0,
        _anthbot_pose_geometry=geometry,
        _anthbot_last_known_pose=last,
        _anthbot_known_dock_pose=dock,
    )


class TestLiveMapStationaryPosition(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stationary.install_stationary_position_semantics()

    def test_docked_stationary_pose_is_labelled_last_known_not_current(self) -> None:
        data = state("charge")
        attributes = hardening._position_attributes(  # noqa: SLF001
            stale_hub(data), data, now=1200.0
        )
        self.assertEqual(attributes["position_status"], "last_known")
        self.assertEqual(attributes["pose"], {"x": 5.0, "y": 5.0})

    def test_observed_dock_position_is_preferred_and_keeps_heading(self) -> None:
        data = state("charge")
        attributes = hardening._position_attributes(  # noqa: SLF001
            stale_hub(data, known_dock=True), data, now=1200.0
        )
        self.assertEqual(attributes["position_status"], "known_dock")
        self.assertEqual(attributes["pose"]["x"], 5.0)
        self.assertEqual(attributes["pose"]["heading"], 90.0)

    def test_paused_stationary_pose_is_last_known_without_heading(self) -> None:
        data = state("pause")
        attributes = hardening._position_attributes(  # noqa: SLF001
            stale_hub(data), data, now=1200.0
        )
        self.assertEqual(attributes["position_status"], "last_known")
        self.assertEqual(attributes["pose"], {"x": 5.0, "y": 5.0})

    def test_active_mowing_pose_still_ages_to_stale_and_is_hidden(self) -> None:
        data = state("globalmowing")
        attributes = hardening._position_attributes(  # noqa: SLF001
            stale_hub(data), data, now=1200.0
        )
        self.assertEqual(attributes["position_status"], "stale")
        self.assertIsNone(attributes["pose"])

    def test_map_mismatch_is_never_resurrected_by_stationary_fallback(self) -> None:
        data = state("charge")
        hub = stale_hub(data, known_dock=True)
        hub._anthbot_pose_geometry = "0" * 64
        attributes = hardening._position_attributes(hub, data, now=1001.0)  # noqa: SLF001
        self.assertEqual(attributes["position_status"], "map_mismatch")
        self.assertIsNone(attributes["pose"])


if __name__ == "__main__":
    unittest.main()
