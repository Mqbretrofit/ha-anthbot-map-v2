"""Experimental M-series map-manager support layered on v2.4.3-beta.3.

This module deliberately leaves Genie code paths untouched.  It is installed
*after* m_series_compat and only activates for M5/M9-family model names.

Live field evidence (M9 Pro, app 2.15.16):
- current map object: sub_category=map, filename=map_manager_<SN>.tar.gz
- archive contains iot_map.bin
- iot_map.bin v1 carries the direct outer-boundary int32 X/Y vertices in mm
- path_<SN>.txt and curpath use the already-supported MGS path decoder
"""

from __future__ import annotations

import io
import json
import logging
import math
import struct
import tarfile
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_RETRY_SECONDS = 60.0


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _model_robot_asset(model: object) -> str | None:
    """Return an optional bundled test image name without affecting Genie."""
    value = str(model or "").upper().replace("_", " ").replace("-", " ")
    if "M9" in value and "PRO" in value:
        return "m9-pro.png"
    if "M9" in value:
        return "m9.png"
    # No verified M5 product image has been supplied yet.
    return None


def _rle_encode(data: bytes | bytearray) -> list[int]:
    if not data:
        return []
    out: list[int] = []
    current = int(data[0])
    count = 1
    for raw in data[1:]:
        value = int(raw)
        if value == current and count < 65535:
            count += 1
            continue
        out.extend((current, count))
        current = value
        count = 1
    out.extend((current, count))
    return out


def _polygon_area_m2(points: list[dict[str, int]]) -> float:
    if len(points) < 3:
        return 0.0
    area2 = 0.0
    for first, second in zip(points, points[1:] + points[:1]):
        area2 += float(first["x"]) * float(second["y"]) - float(second["x"]) * float(first["y"])
    return abs(area2) / 2_000_000.0


def _decode_iot_map_vector(raw: bytes, model: object = None) -> dict[str, Any] | None:
    """Decode the direct vector-boundary map found in current M-series map_manager archives."""
    if len(raw) < 47:
        return None
    try:
        header_len = int(raw[0])
        protocol_version = int(raw[1])
        map_type = int(raw[2])
        declared_count = struct.unpack_from("<H", raw, 3)[0]
        declared_file_size = struct.unpack_from("<H", raw, 5)[0]
        width = struct.unpack_from("<I", raw, 7)[0]
        height = struct.unpack_from("<I", raw, 11)[0]
        resolution_m = struct.unpack_from("<f", raw, 15)[0]
        x_min_m = struct.unpack_from("<f", raw, 19)[0]
        y_min_m = struct.unpack_from("<f", raw, 23)[0]
        map_id = struct.unpack_from("<Q", raw, 27)[0]
        payload_count = struct.unpack_from("<I", raw, header_len)[0]
    except (IndexError, struct.error):
        return None

    if (
        protocol_version != 1
        or header_len < 35
        or header_len + 4 > len(raw)
        or declared_count <= 2
        or payload_count != declared_count
        or payload_count > 10000
        or width <= 0
        or height <= 0
        or width * height > 8_000_000
        or not math.isfinite(resolution_m)
        or not (0.001 <= resolution_m <= 2.0)
        or not math.isfinite(x_min_m)
        or not math.isfinite(y_min_m)
    ):
        return None

    points_offset = header_len + 4
    expected_size = points_offset + payload_count * 8
    if expected_size > len(raw):
        return None
    # The live M9 Pro sample has an exact u16 file-size field.  Do not reject a
    # future M-series variant solely because the field is zero or extended.
    if declared_file_size not in (0, len(raw)) and declared_file_size < expected_size:
        return None

    points: list[dict[str, int]] = []
    try:
        for index in range(payload_count):
            x, y = struct.unpack_from("<ii", raw, points_offset + index * 8)
            points.append({"x": int(x), "y": int(y)})
    except struct.error:
        return None
    if len(points) < 3:
        return None

    # Reject clearly nonsensical geometry while remaining permissive for M5/M9
    # models not yet field-tested with this decoder.
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    if max(xs) - min(xs) < 500 or max(ys) - min(ys) < 500:
        return None

    resolution_mm = float(resolution_m) * 1000.0
    min_x = float(x_min_m) * 1000.0
    min_y = float(y_min_m) * 1000.0
    max_x = min_x + width * resolution_mm
    max_y = min_y + height * resolution_mm

    raster = _polygon_to_raster(points, width, height, min_x, min_y, resolution_mm)
    if raster is None:
        return None

    return {
        "format": "m-series-iot-map-vector-v1",
        "header_len": header_len,
        "protocol_version": protocol_version,
        "map_type": map_type,
        "map_id": str(map_id),
        "point_count": len(points),
        "declared_file_size": declared_file_size,
        "actual_file_size": len(raw),
        "polygon_area_m2": round(_polygon_area_m2(points), 3),
        "_map_raster": {
            "encoding": "m_series_vector_polygon_rasterized",
            "width": width,
            "height": height,
            "resolution": round(float(resolution_m), 6),
            "bounds": {
                "min_x": round(min_x, 3),
                "max_x": round(max_x, 3),
                "min_y": round(min_y, 3),
                "max_y": round(max_y, 3),
            },
            "values": {"0": int(raster.count(0)), "255": int(raster.count(255))},
            "runs": _rle_encode(raster),
            # Preserve the exact vertices too; the beta.3 renderer ignores this
            # extra key, but it is useful for diagnostics/future direct drawing.
            "vector_boundary": points,
            "map_id": str(map_id),
            "vector_point_count": len(points),
            "vector_polygon_area_m2": round(_polygon_area_m2(points), 3),
            "robot_image_asset": _model_robot_asset(model),
        },
        "_m_series_vector_boundary": points,
    }


def _polygon_to_raster(
    points: list[dict[str, int]],
    width: int,
    height: int,
    min_x: float,
    min_y: float,
    resolution_mm: float,
) -> bytes | None:
    """Rasterize polygon interior by scanline, preserving concavities (no convex hull)."""
    if width <= 0 or height <= 0 or resolution_mm <= 0:
        return None
    pixels = bytearray(width * height)
    vertices = [(float(p["x"]), float(p["y"])) for p in points]
    if vertices[0] != vertices[-1]:
        vertices.append(vertices[0])

    for row in range(height):
        y = min_y + (row + 0.5) * resolution_mm
        intersections: list[float] = []
        for (x1, y1), (x2, y2) in zip(vertices, vertices[1:]):
            if y1 == y2:
                continue
            # Half-open crossing rule prevents double hits at polygon vertices.
            if (y1 <= y < y2) or (y2 <= y < y1):
                ratio = (y - y1) / (y2 - y1)
                intersections.append(x1 + ratio * (x2 - x1))
        intersections.sort()
        for idx in range(0, len(intersections) - 1, 2):
            left = intersections[idx]
            right = intersections[idx + 1]
            if right <= left:
                continue
            first_col = max(0, int(math.ceil((left - min_x) / resolution_mm - 0.5)))
            last_col = min(width - 1, int(math.floor((right - min_x) / resolution_mm - 0.5)))
            if last_col >= first_col:
                start = row * width + first_col
                end = row * width + last_col + 1
                pixels[start:end] = b"\xff" * (end - start)
    return bytes(pixels)


def _decode_map_manager_archive(raw: bytes, model: object = None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            iot_map = None
            members: list[str] = []
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                members.append(member.name)
                if member.name.rsplit("/", 1)[-1] == "iot_map.bin":
                    extracted = archive.extractfile(member)
                    if extracted is not None:
                        iot_map = extracted.read()
            if not iot_map:
                return None
    except (tarfile.TarError, OSError, EOFError, ValueError):
        return None

    decoded = _decode_iot_map_vector(iot_map, model=model)
    if decoded is None:
        return None
    decoded["archive_members"] = members
    return decoded


async def _download_current_map_manager(account_client: Any, serial: str) -> tuple[bytes, dict[str, Any]]:
    """Read the current app map-manager object without changing any mower state."""
    require_token = getattr(account_client, "_require_token", None)
    if callable(require_token):
        require_token()
    session = getattr(account_client, "_session")
    host = getattr(account_client, "_host")
    headers = getattr(account_client, "_auth_headers")
    token_builder = getattr(account_client, "build_verification_token")
    filename = f"map_manager_{serial}.tar.gz"
    params = {
        "filename": filename,
        "sn": serial,
        "category": "device",
        "sub_category": "map",
        "verification_token": token_builder(serial),
    }
    url = f"https://{host}/api/v1/device/v2/presigned_url"
    async with session.get(url, headers=headers, params=params, timeout=15) as response:
        if response.status != 200:
            body = await response.text()
            raise RuntimeError(f"map-manager presigned URL failed ({response.status}): {body[:180]}")
        payload = await response.json(content_type=None)
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise RuntimeError(
            f"map-manager presigned URL rejected: code={payload.get('code') if isinstance(payload, dict) else 'n/a'}"
        )
    data = payload.get("data")
    presigned_url = data.get("presigned_url") if isinstance(data, dict) else None
    if not isinstance(presigned_url, str) or not presigned_url:
        raise RuntimeError("map-manager presigned URL payload missing presigned_url")
    async with session.get(presigned_url, timeout=20) as response:
        if response.status != 200:
            body = await response.text()
            raise RuntimeError(f"map-manager download failed ({response.status}): {body[:180]}")
        raw = await response.read()
    return raw, {"filename": filename, "category": "device", "sub_category": "map"}


def _map_id_from_state(state: dict[str, Any]) -> str | None:
    value = state.get("map")
    if isinstance(value, dict):
        map_id = value.get("map_id")
        if map_id not in (None, ""):
            return str(map_id)
    return None


def install_m_series_map_support() -> None:
    """Install the verified M-series-only map-manager decoder once."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_refresh_map = AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition

    async def refresh_map_definition(
        self: AnthbotGenieDataUpdateCoordinator,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        model = getattr(self.device, "model", None)
        if not _is_m_series(model):
            return await previous_refresh_map(self, property_state, now, allow_periodic=allow_periodic)

        map_id = _map_id_from_state(property_state)
        loaded_id = getattr(self, "_m_series_vector_map_id", None)
        source = str(getattr(self, "_map_definition_source", "") or "")
        if source.startswith("m_series_map_manager:") and (map_id is None or loaded_id == map_id):
            return {
                "preferred_source": "m_series_map_manager",
                "active_source": source,
                "map_id": loaded_id,
                "experimental": True,
            }, False

        last_probe = float(getattr(self, "_m_series_vector_map_probe_last", 0.0) or 0.0)
        should_probe = last_probe == 0.0 or now - last_probe >= _RETRY_SECONDS or loaded_id != map_id
        if should_probe:
            setattr(self, "_m_series_vector_map_probe_last", now)
            try:
                raw, source_info = await _download_current_map_manager(
                    self.account_client, self.client.serial_number
                )
                definition = _decode_map_manager_archive(raw, model=model)
                if definition is None:
                    raise RuntimeError("map_manager downloaded but iot_map.bin vector decode was not recognized")
                definition["_download_source"] = source_info
                self._map_definition = definition
                self._map_definition_source = f"m_series_map_manager:{source_info['filename']}"
                self._map_definition_error = None
                self._last_map_download_monotonic = now
                decoded_id = str(definition.get("map_id") or map_id or "") or None
                setattr(self, "_m_series_vector_map_id", decoded_id)
                _LOGGER.info(
                    "ANTHBOT M-SERIES TEST: loaded current map_manager for %s (%s), %s boundary points, %.3f m2",
                    self.client.serial_number,
                    model,
                    definition.get("point_count"),
                    float(definition.get("polygon_area_m2") or 0.0),
                )
                return {
                    "preferred_source": "m_series_map_manager",
                    "active_source": self._map_definition_source,
                    "map_id": decoded_id,
                    "boundary_points": definition.get("point_count"),
                    "boundary_area_m2": definition.get("polygon_area_m2"),
                    "experimental": True,
                }, True
            except Exception as err:  # noqa: BLE001 - safe legacy fallback below.
                _LOGGER.warning(
                    "ANTHBOT M-SERIES TEST: current map_manager probe failed for %s (%s): %s; falling back",
                    self.client.serial_number,
                    model,
                    err,
                )

        # Preserve every pre-existing beta.3 M-series fallback when the new
        # current-map format is absent or differs on an unverified model.
        return await previous_refresh_map(self, property_state, now, allow_periodic=allow_periodic)

    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition
