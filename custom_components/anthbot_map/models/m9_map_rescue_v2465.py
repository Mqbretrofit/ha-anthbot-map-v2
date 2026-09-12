"""M9/M9 Pro map-manager rescue fallback for v2.4.6.5.

When a current serial-named map_manager archive is available but its iot_map.bin
uses an as-yet unknown encoding, do not fall through to the known-missing
multi_maps/map_<serial>_0 object if area_setting.json already provides usable
manual-zone geometry.  The frontend has long used the convex hull of those
zones as its last-resort boundary; this backend fallback mirrors that behavior
and keeps the current map-manager archive as the authoritative source.

This module is deliberately M9-only.  M5 and N8 keep their existing map paths.
"""

from __future__ import annotations

import io
import json
import math
import tarfile
from typing import Any

from . import m_series_map

_INSTALLED = False
_RESOLUTION_MM = 50.0
_PADDING_MM = 250.0


def _is_m9(model: object) -> bool:
    return "M9" in str(model or "").upper()


def _read_area_setting(raw: bytes) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                if member.name.rsplit("/", 1)[-1] != "area_setting.json":
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    return None
                payload = json.loads(extracted.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else None
    except (tarfile.TarError, OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return None


def _manual_zone_points(area: dict[str, Any]) -> list[tuple[int, int]]:
    zones = area.get("custom_areas")
    if not isinstance(zones, list):
        return []
    points: list[tuple[int, int]] = []
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        vertices = zone.get("vertexs")
        if not isinstance(vertices, list):
            vertices = zone.get("vertices")
        if not isinstance(vertices, list):
            continue
        for vertex in vertices:
            if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
                continue
            try:
                x = int(round(float(vertex[0])))
                y = int(round(float(vertex[1])))
            except (TypeError, ValueError, OverflowError):
                continue
            points.append((x, y))
    return points


def _convex_hull(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    unique = sorted(set(points))
    if len(unique) <= 2:
        return unique

    def cross(
        origin: tuple[int, int],
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> int:
        return (
            (first[0] - origin[0]) * (second[1] - origin[1])
            - (first[1] - origin[1]) * (second[0] - origin[0])
        )

    lower: list[tuple[int, int]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: list[tuple[int, int]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


def _decode_area_zone_hull(raw: bytes, model: object) -> dict[str, Any] | None:
    if not _is_m9(model):
        return None
    area = _read_area_setting(raw)
    if not isinstance(area, dict):
        return None
    hull = _convex_hull(_manual_zone_points(area))
    if len(hull) < 3:
        return None

    xs = [point[0] for point in hull]
    ys = [point[1] for point in hull]
    min_x = float(min(xs)) - _PADDING_MM
    max_x = float(max(xs)) + _PADDING_MM
    min_y = float(min(ys)) - _PADDING_MM
    max_y = float(max(ys)) + _PADDING_MM
    width = int(math.ceil((max_x - min_x) / _RESOLUTION_MM))
    height = int(math.ceil((max_y - min_y) / _RESOLUTION_MM))
    if width <= 0 or height <= 0 or width * height > 8_000_000:
        return None

    vector = [{"x": x, "y": y} for x, y in hull]
    raster = m_series_map._polygon_to_raster(  # noqa: SLF001
        vector,
        width,
        height,
        min_x,
        min_y,
        _RESOLUTION_MM,
    )
    if raster is None:
        return None

    area_m2 = m_series_map._polygon_area_m2(vector)  # noqa: SLF001
    raster_definition = {
        "encoding": "m9_area_zone_hull_rasterized",
        "width": width,
        "height": height,
        "resolution": _RESOLUTION_MM / 1000.0,
        "bounds": {
            "min_x": round(min_x, 3),
            "max_x": round(max_x, 3),
            "min_y": round(min_y, 3),
            "max_y": round(max_y, 3),
        },
        "values": {
            "0": int(raster.count(0)),
            "255": int(raster.count(255)),
        },
        "runs": m_series_map._rle_encode(raster),  # noqa: SLF001
        "vector_boundary": vector,
        "vector_point_count": len(vector),
        "vector_polygon_area_m2": round(area_m2, 3),
        "robot_image_asset": m_series_map._model_robot_asset(model),  # noqa: SLF001
    }
    return {
        "format": "m9-area-zone-hull-fallback-v1",
        "map_manager_decode": "area_zone_hull_fallback",
        "point_count": len(vector),
        "polygon_area_m2": round(area_m2, 3),
        "_map_raster": raster_definition,
        "_m_series_vector_boundary": vector,
        "fallback_reason": "iot_map.bin not recognized; boundary derived from area_setting custom_areas",
    }


def install_m9_map_rescue_v2465() -> None:
    """Install an M9-only final decoder before legacy multi_maps fallback."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_decoder = m_series_map._decode_map_manager_archive  # noqa: SLF001

    def decode_map_manager_archive(
        raw: bytes,
        model: object = None,
    ) -> dict[str, Any] | None:
        decoded = previous_decoder(raw, model=model)
        if isinstance(decoded, dict):
            return decoded
        return _decode_area_zone_hull(raw, model)

    m_series_map._decode_map_manager_archive = decode_map_manager_archive  # noqa: SLF001


__all__ = [
    "install_m9_map_rescue_v2465",
]
