"""Executable tests for the v2.4.6.5 M9 map-manager rescue fallback."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import types
import unittest


ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.anthbot_map.models"
MODULE_NAME = f"{PACKAGE}.m9_map_rescue_v2465"


def _load_module():
    custom_components = sys.modules.setdefault(
        "custom_components", types.ModuleType("custom_components")
    )
    custom_components.__path__ = [str(ROOT / "custom_components")]

    anthbot_map = sys.modules.setdefault(
        "custom_components.anthbot_map", types.ModuleType("custom_components.anthbot_map")
    )
    anthbot_map.__path__ = [str(ROOT / "custom_components/anthbot_map")]

    models = sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
    models.__path__ = [str(ROOT / "custom_components/anthbot_map/models")]

    stub = types.ModuleType(f"{PACKAGE}.m_series_map")

    def polygon_area(points):
        area2 = 0.0
        for first, second in zip(points, points[1:] + points[:1]):
            area2 += first["x"] * second["y"] - second["x"] * first["y"]
        return abs(area2) / 2_000_000.0

    def polygon_to_raster(points, width, height, min_x, min_y, resolution_mm):
        del points, min_x, min_y, resolution_mm
        return bytes([255]) * (width * height)

    def rle_encode(data):
        return [255, len(data)] if data else []

    stub._polygon_area_m2 = polygon_area
    stub._polygon_to_raster = polygon_to_raster
    stub._rle_encode = rle_encode
    stub._model_robot_asset = lambda model: "m9-pro.png" if "PRO" in str(model).upper() else "m9.png"
    stub._decode_map_manager_archive = lambda raw, model=None: None
    sys.modules[f"{PACKAGE}.m_series_map"] = stub
    models.m_series_map = stub

    sys.modules.pop(MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        ROOT / "custom_components/anthbot_map/models/m9_map_rescue_v2465.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _archive(area_setting: dict) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        payload = json.dumps(area_setting).encode("utf-8")
        info = tarfile.TarInfo("maps/area_setting.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

        unknown_iot = b"future-iot-map-format"
        info = tarfile.TarInfo("maps/iot_map.bin")
        info.size = len(unknown_iot)
        archive.addfile(info, io.BytesIO(unknown_iot))
    return buffer.getvalue()


class M9MapRescueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module()
        self.area = {
            "area_id": "20260909183622",
            "custom_areas": [
                {
                    "id": 100,
                    "vertexs": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
                },
                {
                    "id": 101,
                    "vertexs": [[4000, 0], [7000, 0], [7000, 2500], [4000, 2500]],
                },
            ],
        }

    def test_m9_unknown_iot_map_uses_area_zone_hull(self) -> None:
        decoded = self.module._decode_area_zone_hull(
            _archive(self.area), "Anthbot M9 Pro"
        )
        self.assertIsInstance(decoded, dict)
        self.assertEqual(decoded["format"], "m9-area-zone-hull-fallback-v1")
        self.assertEqual(decoded["map_manager_decode"], "area_zone_hull_fallback")
        self.assertGreaterEqual(decoded["point_count"], 4)
        raster = decoded["_map_raster"]
        self.assertGreater(raster["width"], 0)
        self.assertGreater(raster["height"], 0)
        self.assertEqual(raster["encoding"], "m9_area_zone_hull_rasterized")
        self.assertTrue(raster["runs"])

    def test_rescue_is_not_applied_to_m5_or_n8(self) -> None:
        raw = _archive(self.area)
        self.assertIsNone(self.module._decode_area_zone_hull(raw, "Anthbot M5"))
        self.assertIsNone(self.module._decode_area_zone_hull(raw, "Anthbot N8"))

    def test_archive_without_manual_zone_geometry_is_not_masked(self) -> None:
        raw = _archive({"area_id": "x", "custom_areas": []})
        self.assertIsNone(self.module._decode_area_zone_hull(raw, "Anthbot M9 Pro"))


if __name__ == "__main__":
    unittest.main()
