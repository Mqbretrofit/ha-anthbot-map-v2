"""Tests for the multi_maps archive decoder (M5/M9 map raster)."""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import types
import unittest
import zlib


ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.anthbot_map"

WIDTH = 4
HEIGHT = 3
PIXELS = bytes([0, 255, 255, 0, 128, 160, 0, 0, 255, 64, 255, 160])


def _load_api_module():
    """Load api.py without importing the full Home Assistant integration."""
    homeassistant = types.ModuleType("homeassistant")
    homeassistant_exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        """Minimal Home Assistant error stub."""

    homeassistant_exceptions.HomeAssistantError = HomeAssistantError
    homeassistant.exceptions = homeassistant_exceptions
    sys.modules.setdefault("homeassistant", homeassistant)
    sys.modules.setdefault("homeassistant.exceptions", homeassistant_exceptions)

    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        """Minimal aiohttp client error stub."""

    class ClientSession:
        """Minimal aiohttp client session stub."""

    aiohttp.ClientError = ClientError
    aiohttp.ClientSession = ClientSession
    sys.modules.setdefault("aiohttp", aiohttp)

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", custom_components)

    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components/anthbot_map")]
    sys.modules.setdefault(PACKAGE, package)

    const_name = f"{PACKAGE}.const"
    if const_name not in sys.modules:
        const_spec = importlib.util.spec_from_file_location(
            const_name,
            ROOT / "custom_components/anthbot_map/const.py",
        )
        const_module = importlib.util.module_from_spec(const_spec)
        sys.modules[const_name] = const_module
        assert const_spec.loader is not None
        const_spec.loader.exec_module(const_module)

    api_name = f"{PACKAGE}.api"
    api_spec = importlib.util.spec_from_file_location(
        api_name,
        ROOT / "custom_components/anthbot_map/api.py",
    )
    api_module = importlib.util.module_from_spec(api_spec)
    sys.modules[api_name] = api_module
    assert api_spec.loader is not None
    api_spec.loader.exec_module(api_module)
    return api_module


api = _load_api_module()


def _add_tar_member(archive, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def _build_archive() -> bytes:
    """Build a raw tar archive mirroring the app's multi_maps payload."""
    metadata = json.dumps(
        {
            "navi_map": {
                "width": WIDTH,
                "height": HEIGHT,
                "resolution": 0.05,
                "x_min": -2.0,
                "y_min": 1.5,
            }
        }
    ).encode("utf-8")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        _add_tar_member(archive, "maps/remote_map_navi.map", PIXELS)
        _add_tar_member(archive, "maps/remote_map.json", metadata)
        _add_tar_member(archive, "maps/rtk_mask_map", b"\x00" * len(PIXELS))
    return buffer.getvalue()


class TestDecodeMapArchive(unittest.TestCase):
    """Verify raw, gzip and zlib-compressed multi_maps archives decode."""

    def _assert_decoded(self, payload: bytes) -> None:
        result = api._decode_map_archive(payload)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["encoding"], "multi_maps_tar_gz")
        self.assertEqual(result["width"], WIDTH)
        self.assertEqual(result["height"], HEIGHT)
        self.assertEqual(result["resolution"], 0.05)
        self.assertEqual(result["bounds"]["min_x"], -2000.0)
        self.assertEqual(result["bounds"]["min_y"], 1500.0)
        self.assertEqual(result["bounds"]["max_x"], -2000.0 + WIDTH * 50.0)
        self.assertEqual(result["bounds"]["max_y"], 1500.0 + HEIGHT * 50.0)
        self.assertEqual(result["runs"], api._rle_encode_bytes(PIXELS))
        self.assertEqual(result["values"], api._byte_counts(PIXELS))
        self.assertEqual(
            result["metadata"]["navi_map"]["resolution"], 0.05
        )

    def test_raw_tar(self) -> None:
        self._assert_decoded(_build_archive())

    def test_gzip_compressed_tar(self) -> None:
        self._assert_decoded(gzip.compress(_build_archive()))

    def test_zlib_compressed_tar(self) -> None:
        self._assert_decoded(zlib.compress(_build_archive()))

    def test_empty_input_returns_none(self) -> None:
        self.assertIsNone(api._decode_map_archive(b""))

    def test_garbage_input_returns_none(self) -> None:
        self.assertIsNone(api._decode_map_archive(b"not an archive"))

    def test_archive_without_raster_returns_none(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            _add_tar_member(archive, "maps/remote_map.json", b"{}")
        self.assertIsNone(api._decode_map_archive(buffer.getvalue()))

    def test_archive_without_metadata_returns_none(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            _add_tar_member(archive, "maps/remote_map_navi.map", PIXELS)
        self.assertIsNone(api._decode_map_archive(buffer.getvalue()))


if __name__ == "__main__":
    unittest.main()
