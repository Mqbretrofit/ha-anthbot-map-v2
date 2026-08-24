"""API client for Anthbot Genie cloud polling."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import hmac
import io
import json
import logging
import re
import struct
import tarfile
import time
from typing import Any
import uuid
from urllib.parse import parse_qs, quote, urlencode, urlparse
import zlib

from aiohttp import ClientError, ClientSession

from homeassistant.exceptions import HomeAssistantError

from .const import (
    DEFAULT_IOT_ENDPOINT,
    DEFAULT_IOT_REGION,
    IOT_ENDPOINT_TEMPLATE,
    MODEL_NAME_BY_CATEGORY,
)

# Refresh STS creds this many seconds before declared expiration.
_CREDENTIALS_REFRESH_BUFFER_SECONDS = 0
_CREDENTIALS_FALLBACK_TTL_SECONDS = 45 * 60
_IOT_CREDENTIAL_RETRY_DELAYS_SECONDS = (1, 3)
_RETRYABLE_HTTP_STATUS_CODES = frozenset({500, 502, 503, 504})
_AUTHENTICATION_HTTP_STATUS_CODES = frozenset({401, 403})

_LOGGER = logging.getLogger(__name__)

# The official Android app uses OkHttp 4.12.0 for both Axios/XHR requests and
# the AWS IoT WebSocket handshake.  The Anthbot API can use the native client
# identity while issuing the temporary IoT role, so keep this app-identical.
ANDROID_APP_USER_AGENT = "okhttp/4.12.0"

LiveCommandPublisher = Callable[[str, bytes], Awaitable[None]]


class AnthbotGenieApiError(HomeAssistantError):
    """Raised when the Anthbot API request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        temporary: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.temporary = temporary

    @property
    def is_authentication_error(self) -> bool:
        """Return whether the server rejected the current authentication."""
        return self.status_code in _AUTHENTICATION_HTTP_STATUS_CODES

    @property
    def is_temporary(self) -> bool:
        """Return whether repeating the request may recover automatically."""
        return (
            self.temporary
            or self.status_code in _RETRYABLE_HTTP_STATUS_CODES
        )


class AnthbotDefinitionIntegrityError(AnthbotGenieApiError):
    """Raised when a downloaded device file does not match its cloud MD5."""


def _validate_definition_md5(raw_bytes: bytes, expected_md5: str | None) -> str:
    """Return the payload MD5 and reject a valid-but-different expected MD5."""
    actual_md5 = hashlib.md5(raw_bytes).hexdigest()  # noqa: S324 - cache identity
    normalized_expected = (
        expected_md5.strip().lower() if isinstance(expected_md5, str) else ""
    )
    if re.fullmatch(r"[0-9a-f]{32}", normalized_expected) and not hmac.compare_digest(
        actual_md5, normalized_expected
    ):
        raise AnthbotDefinitionIntegrityError(
            "Downloaded map archive MD5 mismatch "
            f"(expected {normalized_expected}, received {actual_md5})"
        )
    return actual_md5


@dataclass(frozen=True, slots=True)
class AnthbotBoundDevice:
    """A mower/device bound to the Anthbot account."""

    serial_number: str
    alias: str
    model: str
    is_owner: bool | None = None
    device_id: int | None = None


@dataclass(frozen=True, slots=True)
class AnthbotTemporaryIotCredentials:
    """Temporary Anthbot-issued AWS IoT credentials."""

    access_key_id: str
    secret_access_key: str
    session_token: str
    region_name: str
    endpoint: str
    expiration: int | None = None


@dataclass(frozen=True, slots=True)
class AnthbotDeviceRegion:
    """Cloud region metadata for a bound mower."""

    serial_number: str
    region_name: str
    iot_endpoint: str


def decode_device_definition(raw_bytes: bytes, label: str) -> dict[str, Any] | list[Any]:
    """Decode Anthbot device file payloads from JSON or compact binary formats."""
    if "path" in label.lower():
        path_payloads: list[tuple[str, bytes]] = [("raw", raw_bytes)]
        if raw_bytes.startswith(b"\x1f\x8b"):
            try:
                path_payloads.append(("gzip", gzip.decompress(raw_bytes)))
            except (OSError, EOFError, zlib.error):
                pass
        try:
            inflated = zlib.decompress(raw_bytes)
            if all(inflated != payload for _, payload in path_payloads):
                path_payloads.append(("zlib", inflated))
        except zlib.error:
            pass

        for compression, payload in path_payloads:
            path_definition = _decode_path_definition(payload)
            if path_definition is not None:
                path_definition["compression"] = compression
                path_definition["compressed_size"] = len(raw_bytes)
                path_definition["decoded_size"] = len(payload)
                return path_definition
        return {
            "format": "unsupported",
            "size": len(raw_bytes),
            "first_bytes": raw_bytes[:32].hex(" "),
            "_path_points": [],
        }

    if "map" in label.lower():
        map_raster = _decode_map_raster(raw_bytes)
        if map_raster is None:
            map_raster = _decode_map_archive(raw_bytes)
        if map_raster is not None:
            return {
                "_map_raster": map_raster,
                "_binary_probe": _probe_binary_definition(raw_bytes, label, []),
            }

    attempts: list[tuple[str, bytes]] = [("raw", raw_bytes)]
    if raw_bytes.startswith(b"\x1f\x8b"):
        try:
            attempts.append(("gzip", gzip.decompress(raw_bytes)))
        except (OSError, EOFError, zlib.error):
            pass
    try:
        attempts.append(("zlib", zlib.decompress(raw_bytes)))
    except zlib.error:
        pass

    errors: list[str] = []
    for name, data in attempts:
        try:
            parsed = json.loads(data.decode("utf-8"))
            if isinstance(parsed, (dict, list)):
                return parsed
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            errors.append(f"{name}/json:{err}")

        try:
            parsed, offset = _read_msgpack_value(data, 0)
            if offset <= len(data) and isinstance(parsed, (dict, list)):
                return parsed
        except (ValueError, UnicodeDecodeError, struct.error) as err:
            errors.append(f"{name}/msgpack:{err}")

    preview = raw_bytes[:16].hex(" ")
    return {
        "_binary_probe": _probe_binary_definition(raw_bytes, label, errors),
    }


def _decode_path_definition(raw_bytes: bytes) -> dict[str, Any] | None:
    """Decode the Genie/MGS historical path format used by the Anthbot app."""
    if len(raw_bytes) < 2:
        return None

    header_len = int(raw_bytes[0])
    protocol_version = int(raw_bytes[1])
    if protocol_version == 0:
        return {
            "format": "mgs-v0",
            "header_len": header_len,
            "protocol_version": protocol_version,
            "point_count": 0,
            "_path_points": [],
        }
    if protocol_version not in (1, 2, 3):
        return None

    try:
        format_name = f"mgs-v{protocol_version}"
        if protocol_version == 1:
            if header_len < 21 or len(raw_bytes) < header_len:
                return None
            shifted_point_len = int(raw_bytes[3]) if len(raw_bytes) > 3 else 0
            shifted_declared_size = struct.unpack_from("<i", raw_bytes, 4)[0] if len(raw_bytes) >= 8 else -1
            shifted_available = (
                (len(raw_bytes) - header_len) // shifted_point_len
                if shifted_point_len > 0 and len(raw_bytes) >= header_len
                else -1
            )
            if (
                header_len >= 22
                and shifted_point_len >= 5
                and 0 <= shifted_declared_size <= shifted_available
                and len(raw_bytes) >= 22
            ):
                point_len = shifted_point_len
                task_type = int(raw_bytes[2])
                declared_size = shifted_declared_size
                start = struct.unpack_from("<i", raw_bytes, 8)[0]
                angle = struct.unpack_from("<h", raw_bytes, 12)[0]
                path_id = struct.unpack_from("<Q", raw_bytes, 14)[0]
                format_name = "mgs-v1-history"
            else:
                point_len = int(raw_bytes[2])
                task_type = -1
                angle = struct.unpack_from("<h", raw_bytes, 3)[0]
                declared_size = struct.unpack_from("<i", raw_bytes, 5)[0]
                start = struct.unpack_from("<i", raw_bytes, 9)[0]
                path_id = struct.unpack_from("<Q", raw_bytes, 13)[0]
        else:
            if header_len < 22 or len(raw_bytes) < header_len:
                return None
            point_len = int(raw_bytes[2])
            task_type = int(raw_bytes[3])
            angle = struct.unpack_from("<h", raw_bytes, 4)[0]
            declared_size = struct.unpack_from("<i", raw_bytes, 6)[0]
            start = struct.unpack_from("<i", raw_bytes, 10)[0]
            path_id = struct.unpack_from("<Q", raw_bytes, 14)[0]

        minimum_point_len = 6 if protocol_version == 3 else 5
        if point_len < minimum_point_len or declared_size < 0:
            return None

        point_count = min(declared_size, (len(raw_bytes) - header_len) // point_len)
        points: list[dict[str, int]] = []
        # Historical-record confirmation (2026-08-21, live hex dump): the
        # "mgs-v1-history" branch's points were previously assumed to already
        # be in mm (scale=1), which produced an absurdly tiny (~1m) bounding
        # box for an 11921-point/93 m² session. With the same x10 scale the
        # other formats use, the box works out to ~8.7m x 11.8m -- squarely
        # in the right ballpark for that mowed area and comfortably inside
        # the map raster's own world bounds. Scale is 10 for every format.
        coordinate_scale = 10
        for index in range(point_count):
            offset = header_len + (index * point_len)
            x, y = struct.unpack_from("<hh", raw_bytes, offset)
            point = {
                "x": x * coordinate_scale,
                "y": y * coordinate_scale,
                "angle": angle,
                "type": int(raw_bytes[offset + 4]),
            }
            if protocol_version == 3:
                point["clean_time"] = int(raw_bytes[offset + 5])
            points.append(point)

        return {
            "format": format_name,
            "header_len": header_len,
            "protocol_version": protocol_version,
            "task_type": task_type,
            "path_id": path_id,
            "declared_size": declared_size,
            "start": start,
            "angle": angle,
            "point_len": point_len,
            "coordinate_scale": coordinate_scale,
            "point_count": len(points),
            "_path_points": points,
        }
    except (IndexError, struct.error, ValueError):
        return None


def _probe_binary_definition(
    raw_bytes: bytes,
    label: str,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "label": label,
        "size": len(raw_bytes),
        "first_bytes": raw_bytes[:32].hex(" "),
        "int16le_runs": _find_coordinate_runs(raw_bytes, fmt="<hh", step=2),
        "int32le_runs": _find_coordinate_runs(raw_bytes, fmt="<ii", step=4),
        "coordinate_paths": _find_coordinate_paths(raw_bytes),
        "decode_errors": errors[-4:],
    }


def _decode_map_raster(raw_bytes: bytes) -> dict[str, Any] | None:
    """Decode Anthbot cloud map raster from the app-compatible LZ4 payload."""
    if len(raw_bytes) < 68:
        return None
    try:
        header_len = struct.unpack_from("<I", raw_bytes, 0)[0]
        decoded_len = struct.unpack_from("<I", raw_bytes, 12)[0]
        width = struct.unpack_from("<I", raw_bytes, 36)[0]
        height = struct.unpack_from("<I", raw_bytes, 40)[0]
        resolution = struct.unpack_from("<f", raw_bytes, 44)[0]
        min_x_m = struct.unpack_from("<f", raw_bytes, 48)[0]
        min_y_m = struct.unpack_from("<f", raw_bytes, 52)[0]
    except struct.error:
        return None

    if (
        header_len < 32
        or header_len >= len(raw_bytes)
        or width <= 0
        or height <= 0
        or decoded_len != width * height
        or decoded_len > 2_000_000
    ):
        return None

    try:
        pixels = _lz4_block_decompress(raw_bytes[header_len:], decoded_len)
    except ValueError:
        return None

    resolution_mm = float(resolution) * 1000.0
    min_x = float(min_x_m) * 1000.0
    min_y = float(min_y_m) * 1000.0
    max_x = min_x + width * resolution_mm
    max_y = min_y + height * resolution_mm

    return {
        "encoding": "rle_u8_lz4_map",
        "width": width,
        "height": height,
        "resolution": round(float(resolution), 6),
        "bounds": {
            "min_x": round(min_x, 3),
            "max_x": round(max_x, 3),
            "min_y": round(min_y, 3),
            "max_y": round(max_y, 3),
        },
        "values": _byte_counts(pixels),
        "runs": _rle_encode_bytes(pixels),
    }


def _decode_map_archive(raw_bytes: bytes) -> dict[str, Any] | None:
    """Decode the app-style multi_maps archive (tar/gzip) for M5/M9 mowers.

    The archive holds a raw navigation raster at ``maps/remote_map_navi.map``
    (one byte per pixel), JSON metadata at ``maps/remote_map.json`` with a
    ``navi_map`` object carrying ``width``/``height``/``resolution``/``x_min``/
    ``y_min``, and an optional already-mowed raster at ``maps/rtk_mask_map``.
    """
    if not raw_bytes:
        return None

    tar_bytes = raw_bytes
    if raw_bytes.startswith(b"\x1f\x8b"):
        try:
            tar_bytes = gzip.decompress(raw_bytes)
        except (OSError, EOFError, zlib.error):
            return None
    elif raw_bytes[257:262] != b"ustar":
        try:
            decompressed = zlib.decompress(raw_bytes)
            if decompressed[257:262] == b"ustar":
                tar_bytes = decompressed
        except zlib.error:
            pass

    members: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                base_name = member.name.rsplit("/", 1)[-1]
                if base_name == "remote_map_navi.map":
                    members["pixels"] = archive.extractfile(member).read()
                elif base_name == "remote_map.json":
                    members["metadata"] = archive.extractfile(member).read()
                elif base_name == "rtk_mask_map":
                    members["rtk_mask"] = archive.extractfile(member).read()
    except (tarfile.TarError, OSError, EOFError, zlib.error, ValueError):
        return None

    pixels = members.get("pixels")
    metadata_bytes = members.get("metadata")
    if not pixels or not metadata_bytes:
        return None
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    navi_map = metadata.get("navi_map")
    if not isinstance(navi_map, dict):
        return None
    try:
        width = int(navi_map["width"])
        height = int(navi_map["height"])
        resolution = float(navi_map["resolution"])
        x_min = float(navi_map["x_min"])
        y_min = float(navi_map["y_min"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        width <= 0
        or height <= 0
        or resolution <= 0
        or len(pixels) != width * height
        or width * height > 8_000_000
    ):
        return None

    # The HA card draws raster rows in the archive's own order, so the raw
    # pixels are used as-is.
    raster_bytes = bytes(pixels)

    min_x = x_min * 1000.0
    min_y = y_min * 1000.0
    max_x = min_x + width * resolution * 1000.0
    max_y = min_y + height * resolution * 1000.0

    return {
        "encoding": "multi_maps_tar_gz",
        "width": width,
        "height": height,
        "resolution": round(resolution, 6),
        "bounds": {
            "min_x": round(min_x, 3),
            "max_x": round(max_x, 3),
            "min_y": round(min_y, 3),
            "max_y": round(max_y, 3),
        },
        "values": _byte_counts(raster_bytes),
        "runs": _rle_encode_bytes(raster_bytes),
        "metadata": metadata,
    }


def _lz4_block_decompress(data: bytes, expected_len: int) -> bytes:
    """Decompress an LZ4 block without frame headers."""
    output = bytearray(expected_len)
    src = 0
    dst = 0

    while src < len(data):
        token = data[src]
        src += 1

        literal_len = token >> 4
        if literal_len == 15:
            while True:
                if src >= len(data):
                    raise ValueError("unterminated lz4 literal length")
                extra = data[src]
                src += 1
                literal_len += extra
                if extra != 255:
                    break

        if src + literal_len > len(data) or dst + literal_len > expected_len:
            raise ValueError("lz4 literal overrun")
        output[dst : dst + literal_len] = data[src : src + literal_len]
        src += literal_len
        dst += literal_len

        if src >= len(data):
            break
        if src + 2 > len(data):
            raise ValueError("truncated lz4 offset")

        offset = data[src] | (data[src + 1] << 8)
        src += 2
        if offset <= 0 or offset > dst:
            raise ValueError("invalid lz4 offset")

        match_len = token & 0x0F
        if match_len == 15:
            while True:
                if src >= len(data):
                    raise ValueError("unterminated lz4 match length")
                extra = data[src]
                src += 1
                match_len += extra
                if extra != 255:
                    break
        match_len += 4

        if dst + match_len > expected_len:
            raise ValueError("lz4 match overrun")
        for _ in range(match_len):
            output[dst] = output[dst - offset]
            dst += 1

    if dst != expected_len:
        raise ValueError("lz4 decoded length mismatch")
    return bytes(output)


def _rle_encode_bytes(data: bytes) -> list[int]:
    """Return flattened value/count RLE pairs for compact HA attributes."""
    if not data:
        return []
    runs: list[int] = []
    current = data[0]
    count = 1
    for value in data[1:]:
        if value == current and count < 65535:
            count += 1
            continue
        runs.extend((int(current), count))
        current = value
        count = 1
    runs.extend((int(current), count))
    return runs


def _byte_counts(data: bytes) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in data:
        key = str(int(value))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _find_coordinate_runs(
    raw_bytes: bytes,
    *,
    fmt: str,
    step: int,
) -> list[dict[str, Any]]:
    size = struct.calcsize(fmt)
    runs: list[dict[str, Any]] = []
    limit = len(raw_bytes) - size

    for start in range(0, min(len(raw_bytes), 512), step):
        points: list[tuple[int, int]] = []
        previous: tuple[int, int] | None = None
        offset = start

        while offset <= limit:
            x, y = struct.unpack_from(fmt, raw_bytes, offset)
            if not _looks_like_coordinate(x, y, previous):
                break
            if x != 0 or y != 0:
                points.append((int(x), int(y)))
                previous = (int(x), int(y))
            offset += size

        if len(points) >= 8:
            runs.append(
                {
                    "offset": start,
                    "count": len(points),
                    "first": [[x, y] for x, y in points[:8]],
                    "bounds": _point_bounds(points),
                }
            )
        if len(runs) >= 12:
            break

    return runs


def _find_coordinate_paths(raw_bytes: bytes) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for name, fmt, step in (
        ("int16le", "<hh", 2),
        ("int16be", ">hh", 2),
        ("int32le", "<ii", 4),
        ("int32be", ">ii", 4),
    ):
        candidates.extend(_scan_coordinate_paths(raw_bytes, name=name, fmt=fmt, step=step))

    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    return candidates[:6]


def _scan_coordinate_paths(
    raw_bytes: bytes,
    *,
    name: str,
    fmt: str,
    step: int,
) -> list[dict[str, Any]]:
    pair_size = struct.calcsize(fmt)
    limit = len(raw_bytes) - pair_size
    paths: list[dict[str, Any]] = []
    offset = 0

    while offset <= limit:
        points: list[tuple[int, int]] = []
        previous: tuple[int, int] | None = None
        cursor = offset

        while cursor <= limit:
            x, y = struct.unpack_from(fmt, raw_bytes, cursor)
            point = (int(x), int(y))
            if _is_coordinate_sentinel(point):
                cursor += pair_size
                continue
            if not _looks_like_path_coordinate(point, previous):
                break
            points.append(point)
            previous = point
            cursor += pair_size

        candidate = _coordinate_path_candidate(name, offset, points)
        if candidate is not None:
            paths.append(candidate)
            offset = max(cursor, offset + pair_size)
        else:
            offset += step

        if len(paths) >= 24:
            break

    return paths


def _coordinate_path_candidate(
    encoding: str,
    offset: int,
    points: list[tuple[int, int]],
) -> dict[str, Any] | None:
    if len(points) < 24:
        return None
    unique_count = len(set(points))
    if unique_count < 16:
        return None
    bounds = _point_bounds(points)
    width = bounds["max_x"] - bounds["min_x"]
    height = bounds["max_y"] - bounds["min_y"]
    if width < 800 or height < 800:
        return None

    score = unique_count + min(len(points), 800) + (width + height) / 100
    return {
        "encoding": encoding,
        "offset": offset,
        "count": len(points),
        "score": round(score, 2),
        "bounds": bounds,
        "first": [[x, y] for x, y in points[:10]],
        "points": [[x, y] for x, y in points[:1000]],
    }


def _is_coordinate_sentinel(point: tuple[int, int]) -> bool:
    return point in {
        (0, 0),
        (-1, -1),
        (1, -1),
        (-1, 1),
    }


def _looks_like_path_coordinate(
    point: tuple[int, int],
    previous: tuple[int, int] | None,
) -> bool:
    x, y = point
    if abs(x) > 35000 or abs(y) > 35000:
        return False
    if previous is None:
        return True
    return abs(x - previous[0]) <= 16000 and abs(y - previous[1]) <= 16000


def _looks_like_coordinate(
    x: int,
    y: int,
    previous: tuple[int, int] | None,
) -> bool:
    if abs(x) > 50000 or abs(y) > 50000:
        return False
    if previous is None:
        return True
    return abs(x - previous[0]) <= 12000 and abs(y - previous[1]) <= 12000


def _point_bounds(points: list[tuple[int, int]]) -> dict[str, int]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
    }


def _read_msgpack_value(data: bytes, offset: int) -> tuple[Any, int]:
    if offset >= len(data):
        raise ValueError("unexpected end of msgpack data")
    prefix = data[offset]
    offset += 1

    if prefix <= 0x7F:
        return prefix, offset
    if prefix >= 0xE0:
        return prefix - 0x100, offset
    if 0x80 <= prefix <= 0x8F:
        return _read_msgpack_map(data, offset, prefix & 0x0F)
    if 0x90 <= prefix <= 0x9F:
        return _read_msgpack_array(data, offset, prefix & 0x0F)
    if 0xA0 <= prefix <= 0xBF:
        return _read_msgpack_string(data, offset, prefix & 0x1F)

    if prefix == 0xC0:
        return None, offset
    if prefix == 0xC2:
        return False, offset
    if prefix == 0xC3:
        return True, offset
    if prefix == 0xCA:
        return _unpack(">f", data, offset)
    if prefix == 0xCB:
        return _unpack(">d", data, offset)
    if prefix == 0xCC:
        return _unpack(">B", data, offset)
    if prefix == 0xCD:
        return _unpack(">H", data, offset)
    if prefix == 0xCE:
        return _unpack(">I", data, offset)
    if prefix == 0xCF:
        return _unpack(">Q", data, offset)
    if prefix == 0xD0:
        return _unpack(">b", data, offset)
    if prefix == 0xD1:
        return _unpack(">h", data, offset)
    if prefix == 0xD2:
        return _unpack(">i", data, offset)
    if prefix == 0xD3:
        return _unpack(">q", data, offset)
    if prefix == 0xD9:
        length, offset = _unpack(">B", data, offset)
        return _read_msgpack_string(data, offset, length)
    if prefix == 0xDA:
        length, offset = _unpack(">H", data, offset)
        return _read_msgpack_string(data, offset, length)
    if prefix == 0xDB:
        length, offset = _unpack(">I", data, offset)
        return _read_msgpack_string(data, offset, length)
    if prefix == 0xDC:
        length, offset = _unpack(">H", data, offset)
        return _read_msgpack_array(data, offset, length)
    if prefix == 0xDD:
        length, offset = _unpack(">I", data, offset)
        return _read_msgpack_array(data, offset, length)
    if prefix == 0xDE:
        length, offset = _unpack(">H", data, offset)
        return _read_msgpack_map(data, offset, length)
    if prefix == 0xDF:
        length, offset = _unpack(">I", data, offset)
        return _read_msgpack_map(data, offset, length)
    if prefix in {0xC4, 0xC5, 0xC6}:
        size_formats = {0xC4: ">B", 0xC5: ">H", 0xC6: ">I"}
        length, offset = _unpack(size_formats[prefix], data, offset)
        return data[offset : offset + length], offset + length

    raise ValueError(f"unsupported msgpack prefix 0x{prefix:02x}")


def _read_msgpack_string(data: bytes, offset: int, length: int) -> tuple[str, int]:
    end = offset + length
    if end > len(data):
        raise ValueError("string extends past end of msgpack data")
    return data[offset:end].decode("utf-8"), end


def _read_msgpack_array(data: bytes, offset: int, length: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    for _ in range(length):
        item, offset = _read_msgpack_value(data, offset)
        items.append(item)
    return items, offset


def _read_msgpack_map(data: bytes, offset: int, length: int) -> tuple[dict[Any, Any], int]:
    result: dict[Any, Any] = {}
    for _ in range(length):
        key, offset = _read_msgpack_value(data, offset)
        value, offset = _read_msgpack_value(data, offset)
        result[key] = value
    return result, offset


def _unpack(fmt: str, data: bytes, offset: int) -> tuple[Any, int]:
    size = struct.calcsize(fmt)
    if offset + size > len(data):
        raise ValueError("numeric value extends past end of msgpack data")
    return struct.unpack_from(fmt, data, offset)[0], offset + size


class AnthbotCloudApiClient:
    """Client for Anthbot cloud account endpoints."""

    def __init__(
        self,
        *,
        session: ClientSession,
        host: str,
        bearer_token: str | None = None,
    ) -> None:
        self._session = session
        self._host = host
        self._bearer_token = bearer_token
        self._login_credentials: tuple[str, str, str] | None = None
        self._login_lock = asyncio.Lock()
        self._auth_headers = {
            "Accept": "application/json, text/plain, */*",
            "version": "v2",
            "language": "en",
            "User-Agent": ANDROID_APP_USER_AGENT,
        }
        if bearer_token:
            self._auth_headers["Authorization"] = bearer_token

    async def async_login(
        self, *, username: str, password: str, area_code: str
    ) -> str:
        """Login and return bearer token."""
        self._login_credentials = (username, password, area_code)
        url = f"https://{self._host}/api/v1/login"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "version": "v2",
            "language": "en",
            "User-Agent": ANDROID_APP_USER_AGENT,
        }
        payload = {"username": username, "password": password, "areaCode": area_code}

        try:
            async with self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"Login failed ({resp.status}): {body[:300]}",
                        status_code=resp.status,
                        temporary=resp.status in _RETRYABLE_HTTP_STATUS_CODES,
                    )
                data = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        if not isinstance(data, dict):
            raise AnthbotGenieApiError("Invalid login payload type")
        if data.get("code") != 0:
            raise AnthbotGenieApiError(f"Login rejected: code={data.get('code')!r}")

        token_data = data.get("data")
        if not isinstance(token_data, dict):
            raise AnthbotGenieApiError("Login payload missing data object")
        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise AnthbotGenieApiError("Login payload missing access_token")

        bearer_token = f"Bearer {access_token}"
        self._bearer_token = bearer_token
        self._auth_headers["Authorization"] = bearer_token
        return bearer_token

    async def async_reauthenticate(self) -> str:
        """Refresh the account bearer token using the configured credentials."""
        if self._login_credentials is None:
            raise AnthbotGenieApiError("Account credentials are not available for re-login")
        async with self._login_lock:
            username, password, area_code = self._login_credentials
            return await self.async_login(
                username=username,
                password=password,
                area_code=area_code,
            )

    def _require_token(self) -> None:
        if not self._bearer_token:
            raise AnthbotGenieApiError("Bearer token not configured")

    @staticmethod
    def build_verification_token(serial_number: str, timestamp: int | None = None) -> str:
        """Build the app-style verification token used by device file/STS APIs."""
        # The Android app uses Math.round(Date.now() / 1000), not floor().
        unix_timestamp = (
            timestamp
            if timestamp is not None
            else int(datetime.now(timezone.utc).timestamp() + 0.5)
        )
        token_suffix = str(unix_timestamp)
        token_prefix = hashlib.md5(
            f"{serial_number}{token_suffix}".encode("utf-8")
        ).hexdigest()
        return f"{token_prefix}{token_suffix}"

    async def async_get_bound_devices(self) -> list[AnthbotBoundDevice]:
        """Fetch account-bound Anthbot devices."""
        self._require_token()

        url = f"https://{self._host}/api/v1/device/bind/list"
        try:
            async with self._session.get(
                url, headers=self._auth_headers, timeout=15
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"Bind list failed ({resp.status}): {body[:300]}"
                    )
                payload = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        if not isinstance(payload, dict):
            raise AnthbotGenieApiError("Invalid bind list payload type")
        if payload.get("code") != 0:
            raise AnthbotGenieApiError(f"Bind list returned code={payload.get('code')}")

        data = payload.get("data")
        if not isinstance(data, list):
            raise AnthbotGenieApiError("Bind list payload missing data array")

        devices: list[AnthbotBoundDevice] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            serial_number = item.get("sn")
            if not isinstance(serial_number, str) or not serial_number:
                continue
            alias = item.get("alias")
            model_value = item.get("category_id")
            model_raw = str(model_value) if model_value is not None else ""
            # Prefer the friendly name from the app-side catalog when available;
            # otherwise fall back to the raw category_id.
            model = MODEL_NAME_BY_CATEGORY.get(
                model_raw,
                f"Anthbot {model_raw}" if model_raw else "",
            )
            owner_value = item.get("is_owner")
            is_owner = None
            if isinstance(owner_value, bool):
                is_owner = owner_value
            elif isinstance(owner_value, int):
                is_owner = owner_value == 1
            id_value = item.get("id")
            device_id = id_value if isinstance(id_value, int) and not isinstance(id_value, bool) else None
            devices.append(
                AnthbotBoundDevice(
                    serial_number=serial_number,
                    alias=alias if isinstance(alias, str) and alias else serial_number,
                    model=model if model else "Anthbot mower",
                    is_owner=is_owner,
                    device_id=device_id,
                )
            )

        return devices

    async def async_get_mowing_records(
        self,
        serial_number: str,
        *,
        page: int = 1,
        page_size: int = 20,
        device_id: int | None = None,
    ) -> dict[str, Any]:
        """Fetch the same completed mowing records shown by the mobile app.

        Confirmed against real HTTP Toolkit captures of the mobile app
        (2026-08-19): the mobile app calls ``GET /api/v1/device/area`` with
        ``sn``/``pagenum``/``pagesize`` query params -- NOT
        ``/api/v1/device/v3/record/list`` as previously guessed. The
        ``device_id`` parameter was never the issue; the endpoint path was
        simply wrong, which is why the old endpoint always returned
        ``code: 0`` with an empty, but technically "successful", result.
        """
        self._require_token()
        url = f"https://{self._host}/api/v1/device/area"
        params = {"sn": serial_number, "pagenum": page, "pagesize": page_size}

        try:
            async with self._session.get(
                url,
                headers=self._auth_headers,
                params=params,
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"Mowing records failed ({resp.status}): {body[:300]}"
                    )
                payload = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        if not isinstance(payload, dict) or payload.get("code") != 0:
            raise AnthbotGenieApiError(
                f"Invalid mowing record response (code={payload.get('code') if isinstance(payload, dict) else 'n/a'})"
            )

        data = payload.get("data")
        return data if isinstance(data, dict) else {"data": data or []}

    async def async_get_task_events(
        self,
        serial_number: str,
        *,
        page: int = 1,
        page_size: int = 20,
        language: str = "English",
    ) -> dict[str, Any]:
        """Fetch the mower cloud event list used for task-state decisions."""
        self._require_token()
        url = f"https://{self._host}/api/v1/device/v2/code/list"
        params = {
            "sn": serial_number,
            "pagenum": page,
            "pagesize": page_size,
            "language": language,
        }

        try:
            async with self._session.get(
                url,
                headers=self._auth_headers,
                params=params,
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"Task events failed ({resp.status}): {body[:300]}"
                    )
                payload = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        if not isinstance(payload, dict) or payload.get("code") != 0:
            raise AnthbotGenieApiError(
                f"Invalid task event response (code={payload.get('code') if isinstance(payload, dict) else 'n/a'})"
            )

        data = payload.get("data")
        return data if isinstance(data, dict) else {"data": data or []}

    async def async_get_device_region(self, serial_number: str) -> AnthbotDeviceRegion:
        """Fetch device cloud region metadata."""
        self._require_token()

        url = f"https://{self._host}/api/v1/device/v2/region"
        try:
            async with self._session.get(
                url,
                headers=self._auth_headers,
                params={"sn": serial_number},
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"Device region failed ({resp.status}): {body[:300]}"
                    )
                payload = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        if not isinstance(payload, dict):
            raise AnthbotGenieApiError("Invalid device region payload type")
        if payload.get("code") != 0:
            raise AnthbotGenieApiError(
                f"Device region returned code={payload.get('code')}"
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise AnthbotGenieApiError("Device region payload missing data object")

        region_name = data.get("region_name")
        iot_endpoint = data.get("iot_endpoint")
        if not isinstance(region_name, str) or not region_name:
            raise AnthbotGenieApiError("Device region missing region_name")
        if not isinstance(iot_endpoint, str) or not iot_endpoint:
            raise AnthbotGenieApiError("Device region missing iot_endpoint")

        return AnthbotDeviceRegion(
            serial_number=serial_number,
            region_name=region_name,
            iot_endpoint=iot_endpoint,
        )

    async def async_get_device_iot_credentials(
        self, serial_number: str
    ) -> AnthbotTemporaryIotCredentials:
        """Fetch temporary AWS IoT credentials for a mower."""
        self._require_token()

        url = f"https://{self._host}/api/v1/device/v2/iot/sts/arn"
        payload = {
            "sn": serial_number,
            "verification_token": self.build_verification_token(serial_number),
        }
        try:
            async with self._session.post(
                url,
                headers={**self._auth_headers, "content-type": "application/json"},
                json=payload,
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"IoT STS failed ({resp.status}): {body[:300]}",
                        status_code=resp.status,
                        temporary=resp.status in _RETRYABLE_HTTP_STATUS_CODES,
                    )
                response_payload = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(
                f"Network error: {err}",
                temporary=True,
            ) from err
        except TimeoutError as err:
            raise AnthbotGenieApiError(
                "Request timed out",
                temporary=True,
            ) from err

        if not isinstance(response_payload, dict):
            raise AnthbotGenieApiError("Invalid IoT STS payload type")
        if response_payload.get("code") != 0:
            raise AnthbotGenieApiError(
                f"IoT STS returned code={response_payload.get('code')}"
            )

        data = response_payload.get("data")
        if not isinstance(data, dict):
            raise AnthbotGenieApiError("IoT STS payload missing data object")

        access_key_id = data.get("access_key_id")
        secret_access_key = data.get("secret_access_key")
        session_token = data.get("session_token")
        region_name = data.get("region_name")
        endpoint = data.get("endpoint")
        if not all(
            isinstance(value, str) and value
            for value in (
                access_key_id,
                secret_access_key,
                session_token,
                region_name,
                endpoint,
            )
        ):
            raise AnthbotGenieApiError("IoT STS payload missing required fields")

        expiration = self._parse_expiration(data.get("expiration"))

        return AnthbotTemporaryIotCredentials(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
            region_name=region_name,
            endpoint=endpoint,
            expiration=expiration,
        )

    @staticmethod
    def _parse_expiration(value: Any) -> int | None:
        """Normalize STS expiration expressed as seconds, milliseconds or ISO text."""
        def _normalize_numeric(timestamp: int) -> int | None:
            if timestamp <= 0:
                return None
            if timestamp > 10_000_000_000:
                timestamp //= 1000
            # Anthbot currently returns the STS lifetime (typically 3600)
            # instead of an absolute Unix timestamp.  Treat small positive
            # values as a duration so credentials do not appear to have
            # expired in January 1970 and trigger an STS request loop.
            if timestamp < 946_684_800:  # 2000-01-01 UTC
                return int(time.time()) + timestamp
            return timestamp

        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return _normalize_numeric(int(value))
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            if raw.isdigit():
                return _normalize_numeric(int(raw))
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return int(parsed.timestamp())
            except ValueError:
                return None
        return None

    async def async_get_device_json_file(
        self,
        serial_number: str,
        *,
        file_prefix: str,
        sub_category: str,
        filename: str | None = None,
        category: str = "device",
        expected_md5: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Fetch a mower JSON file from the app-style presigned URL endpoint."""
        self._require_token()

        url = f"https://{self._host}/api/v1/device/v2/presigned_url"
        params = {
            "filename": filename or f"{file_prefix}_{serial_number}.txt",
            "sn": serial_number,
            "category": category,
            "sub_category": sub_category,
            "verification_token": self.build_verification_token(serial_number),
        }

        try:
            async with self._session.get(
                url,
                headers=self._auth_headers,
                params=params,
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"{sub_category} presigned URL failed ({resp.status}): {body[:300]}"
                    )
                payload = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        if not isinstance(payload, dict):
            raise AnthbotGenieApiError(
                f"Invalid {sub_category} presigned URL payload type"
            )
        if payload.get("code") != 0:
            raise AnthbotGenieApiError(
                f"{sub_category} presigned URL returned code={payload.get('code')}"
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise AnthbotGenieApiError(
                f"{sub_category} presigned URL payload missing data object"
            )
        presigned_url = data.get("presigned_url")
        if not isinstance(presigned_url, str) or not presigned_url:
            raise AnthbotGenieApiError(
                f"{sub_category} presigned URL payload missing presigned_url"
            )

        try:
            async with self._session.get(presigned_url, timeout=15) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"{sub_category} definition download failed ({resp.status}): {body[:300]}"
                    )
                raw_bytes = await resp.read()
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        content_md5 = _validate_definition_md5(raw_bytes, expected_md5)
        definition = decode_device_definition(raw_bytes, sub_category)

        if not isinstance(definition, (dict, list)):
            raise AnthbotGenieApiError(
                f"{sub_category} definition payload type is not JSON object/array"
            )
        if isinstance(definition, dict):
            definition["_download_source"] = {
                "filename": params["filename"],
                "category": category,
                "sub_category": sub_category,
                "content_md5": content_md5,
                "expected_md5": expected_md5,
                "md5_matches": (
                    content_md5 == expected_md5.strip().lower()
                    if isinstance(expected_md5, str)
                    and bool(re.fullmatch(r"[0-9A-Fa-f]{32}", expected_md5.strip()))
                    else None
                ),
            }

        return definition

    async def async_get_device_file_url(
        self,
        file_url: str,
        *,
        label: str,
    ) -> dict[str, Any] | list[Any]:
        """Fetch and decode an app-provided history/map file URL."""
        try:
            async with self._session.get(file_url, timeout=20) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"{label} URL download failed ({resp.status}): {body[:300]}"
                    )
                raw_bytes = await resp.read()
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        definition = decode_device_definition(raw_bytes, label)
        if not isinstance(definition, (dict, list)):
            raise AnthbotGenieApiError(
                f"{label} URL payload type is not JSON object/array"
            )
        if isinstance(definition, dict):
            definition["_download_source"] = {"url": file_url[:180], "label": label}
        return definition

    async def async_get_device_area_definition(
        self, serial_number: str
    ) -> dict[str, Any]:
        """Fetch the mower area definition file."""
        definition = await self.async_get_device_json_file(
            serial_number,
            file_prefix="area",
            sub_category="area",
        )
        if not isinstance(definition, dict):
            raise AnthbotGenieApiError("Area definition payload type is not an object")
        return definition

    async def async_get_device_ridable_area_definition(
        self, serial_number: str
    ) -> dict[str, Any] | list[Any]:
        """Fetch the editable edge file used by the mobile app."""
        return await self.async_get_device_json_file(
            serial_number,
            file_prefix="ridable_area",
            sub_category="ridable_area",
        )

    async def async_get_device_map_definition(
        self, serial_number: str
    ) -> dict[str, Any]:
        """Fetch and decode the mower's live full-map raster."""
        definition = await self.async_get_device_json_file(
            serial_number,
            file_prefix="map",
            sub_category="map",
        )
        if not isinstance(definition, dict) or not isinstance(
            definition.get("_map_raster"), dict
        ):
            raise AnthbotGenieApiError(
                "live map definition decode produced no raster"
            )
        return definition

    async def async_get_device_map_archive(
        self,
        serial_number: str,
        map_file_name: str | None = None,
        *,
        expected_md5: str | None = None,
    ) -> dict[str, Any]:
        """Fetch the app-style multi_maps archive (tar/gzip) for M5/M9 mowers.

        The map file name normally comes from the device shadow's
        ``multi_maps.map_list`` entry (for example ``map_<serial>_0``). The
        archive is a binary tar/gzip payload, decoded by
        :func:`_decode_map_archive`.
        """
        filename = map_file_name or f"map_{serial_number}_0"
        definition = await self.async_get_device_json_file(
            serial_number,
            file_prefix="map",
            sub_category="multi_maps",
            filename=filename,
            expected_md5=expected_md5,
        )
        if not isinstance(definition, dict) or not isinstance(
            definition.get("_map_raster"), dict
        ):
            raise AnthbotGenieApiError(
                "multi_maps map archive decode produced no raster"
            )
        return definition

    async def async_get_device_path_definition(
        self, serial_number: str
    ) -> dict[str, Any] | list[Any]:
        """Fetch the mower history/path file if the cloud exposes it."""
        attempts = (
            ("path", "path", f"path_{serial_number}.txt", "device"),
            ("his_path", "path", f"his_path_{serial_number}.txt", "device"),
            ("history_path", "path", f"history_path_{serial_number}.txt", "device"),
            ("record_path", "path", f"record_path_{serial_number}.txt", "device"),
            ("history_path_info", "path", f"history_path_info_{serial_number}.txt", "device"),
            ("path", "history_path_info", f"path_{serial_number}.txt", "device"),
            ("history_path", "history_path_info", f"history_path_{serial_number}.txt", "device"),
            ("record_path", "history_path_info", f"record_path_{serial_number}.txt", "device"),
        )
        errors: list[str] = []
        for file_prefix, sub_category, filename, category in attempts:
            try:
                return await self.async_get_device_json_file(
                    serial_number,
                    file_prefix=file_prefix,
                    sub_category=sub_category,
                    filename=filename,
                    category=category,
                )
            except AnthbotGenieApiError as err:
                errors.append(f"{filename}/{sub_category}: {err}")
        raise AnthbotGenieApiError(
            "No app-style history path file could be downloaded: "
            + " | ".join(errors[-4:])
        )

    async def async_get_mowing_record_detail(
        self,
        serial_number: str,
        *,
        area_url: str | None = None,
        map_url: str | None = None,
        path_url: str | None = None,
    ) -> dict[str, Any]:
        """Download and decode the per-record area/map/path files referenced
        by a single completed mowing-history record (as returned by
        :meth:`async_get_mowing_records` in its ``area_url``/``map_url``/
        ``path_url`` fields), so the mobile app's per-session "what got
        mowed" view can be reproduced on the card. Each requested file is
        fetched independently; a failure on one (e.g. an expired/garbage
        collected S3 object) does not prevent the others from being
        returned.
        """
        result: dict[str, Any] = {}
        errors: list[str] = []
        file_specs: tuple[tuple[str, str | None, str], ...] = (
            ("area", area_url, "area"),
            ("map", map_url, "map"),
            ("path", path_url, "path"),
        )
        for sub_category, filename, result_key in file_specs:
            if not filename:
                continue
            try:
                result[result_key] = await self.async_get_device_json_file(
                    serial_number,
                    file_prefix=sub_category,
                    sub_category=sub_category,
                    filename=filename,
                )
            except AnthbotGenieApiError as err:
                errors.append(f"{sub_category}({filename}): {err}")
        if errors:
            result["_errors"] = errors
        return result

    async def async_get_device_presigned_region(self, serial_number: str) -> str | None:
        """Fetch presigned_url metadata and extract AWS region."""
        self._require_token()

        url = f"https://{self._host}/api/v1/device/v2/presigned_url"
        try:
            async with self._session.get(
                url,
                headers=self._auth_headers,
                params={"sn": serial_number},
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise AnthbotGenieApiError(
                        f"Presigned URL failed ({resp.status}): {body[:300]}"
                    )
                payload = await resp.json(content_type=None)
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

        if not isinstance(payload, dict):
            raise AnthbotGenieApiError("Invalid presigned URL payload type")
        if payload.get("code") != 0:
            raise AnthbotGenieApiError(
                f"Presigned URL returned code={payload.get('code')}"
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise AnthbotGenieApiError("Presigned URL payload missing data object")
        presigned_url = data.get("presigned_url")
        if not isinstance(presigned_url, str) or not presigned_url:
            raise AnthbotGenieApiError("Presigned URL payload missing presigned_url")

        parsed = urlparse(presigned_url)
        host = parsed.netloc
        if host:
            host_parts = host.split(".")
            if len(host_parts) >= 4 and host_parts[0] == "s3":
                if host_parts[1] == "dualstack":
                    candidate = host_parts[2]
                else:
                    candidate = host_parts[1]
                if candidate and candidate not in {"amazonaws", "amazonaws.com"}:
                    return candidate

        query = parse_qs(parsed.query, keep_blank_values=False)
        credential_values = query.get("X-Amz-Credential", [])
        if credential_values:
            credential_parts = credential_values[0].split("/")
            if len(credential_parts) >= 3 and credential_parts[2]:
                return credential_parts[2]

        return None


class AnthbotShadowApiClient:
    """Client for Anthbot AWS IoT shadow endpoint."""

    def __init__(
        self,
        *,
        session: ClientSession,
        serial_number: str,
        region_name: str | None,
        iot_endpoint: str | None,
        account_client: "AnthbotCloudApiClient | None" = None,
    ) -> None:
        self._session = session
        self._serial_number = serial_number
        self._region_name = (
            region_name if isinstance(region_name, str) and region_name else None
        )
        self._iot_endpoint = self._normalize_endpoint(iot_endpoint)
        # account_client fetches short-lived STS credentials. No static cloud
        # credentials are embedded in this integration.
        self._account_client = account_client
        self._credentials: AnthbotTemporaryIotCredentials | None = None
        self._credentials_acquired_at: float | None = None
        self._credentials_generation = 0
        self._live_command_publisher: LiveCommandPublisher | None = None
        self._credentials_lock = asyncio.Lock()
        endpoint_region = self._guess_region_from_endpoint(self._iot_endpoint)
        if (
            self._region_name
            and endpoint_region
            and self._region_name != endpoint_region
        ):
            _LOGGER.debug(
                "Anthbot region mismatch for %s: api region=%s endpoint region=%s endpoint=%s; endpoint region will be used for signing",
                serial_number,
                self._region_name,
                endpoint_region,
                self._iot_endpoint,
            )

    def _credentials_are_valid(
        self, creds: AnthbotTemporaryIotCredentials | None
    ) -> bool:
        if creds is None:
            return False
        if creds.expiration is None:
            return (
                self._credentials_acquired_at is not None
                and time.time() - self._credentials_acquired_at
                < _CREDENTIALS_FALLBACK_TTL_SECONDS
            )
        # expiration is unix seconds; allow refresh buffer
        return creds.expiration - int(time.time()) > _CREDENTIALS_REFRESH_BUFFER_SECONDS

    def _credentials_are_usable(
        self, creds: AnthbotTemporaryIotCredentials | None
    ) -> bool:
        """Return whether cached credentials have not actually expired yet."""
        if creds is None:
            return False
        if creds.expiration is None:
            return (
                self._credentials_acquired_at is not None
                and time.time() - self._credentials_acquired_at
                < _CREDENTIALS_FALLBACK_TTL_SECONDS
            )
        return creds.expiration > int(time.time())

    async def _async_fetch_iot_credentials_with_retry(
        self,
    ) -> AnthbotTemporaryIotCredentials:
        """Fetch IoT credentials, retrying only temporary cloud failures."""
        if self._account_client is None:
            raise AnthbotGenieApiError(
                "Anthbot account client is required for temporary IoT credentials"
            )

        attempt_count = len(_IOT_CREDENTIAL_RETRY_DELAYS_SECONDS) + 1
        for attempt in range(attempt_count):
            try:
                return await self._account_client.async_get_device_iot_credentials(
                    self._serial_number
                )
            except AnthbotGenieApiError as err:
                if not err.is_temporary or attempt >= attempt_count - 1:
                    raise
                delay = _IOT_CREDENTIAL_RETRY_DELAYS_SECONDS[attempt]
                _LOGGER.debug(
                    "Temporary Anthbot IoT credential failure for %s "
                    "(attempt %d/%d); retrying in %d seconds: %s",
                    self._serial_number,
                    attempt + 1,
                    attempt_count,
                    delay,
                    err,
                )
                await asyncio.sleep(delay)

        raise AnthbotGenieApiError("IoT credential retry loop exhausted")

    async def async_request_all_properties(self) -> None:
        """Compatibility hook used after service commands."""
        await self.async_publish_service_command(cmd="app_state", data=1)
        await self.async_publish_service_command(cmd="get_all_props", data=1)

    async def _async_get_credentials(
        self, *, force_refresh: bool = False
    ) -> AnthbotTemporaryIotCredentials:
        """Return cached temp credentials or fetch fresh ones from STS."""
        if self._account_client is None:
            raise AnthbotGenieApiError(
                "Anthbot account client is required for temporary IoT credentials"
            )
        async with self._credentials_lock:
            if not force_refresh and self._credentials_are_valid(self._credentials):
                return self._credentials
            try:
                creds = await self._async_fetch_iot_credentials_with_retry()
            except AnthbotGenieApiError as err:
                if err.is_authentication_error:
                    _LOGGER.debug(
                        "Anthbot IoT credentials request was rejected for %s; "
                        "re-authenticating the account once",
                        self._serial_number,
                    )
                    try:
                        await self._account_client.async_reauthenticate()
                        creds = await self._async_fetch_iot_credentials_with_retry()
                    except AnthbotGenieApiError as retry_err:
                        err = retry_err
                    else:
                        err = None

                if err is not None:
                    # During an early refresh, credentials inside the refresh
                    # buffer can still work until their actual expiration.
                    # Never reuse credentials after a forced refresh: that path
                    # is entered because AWS has already rejected them.
                    if (
                        err.is_temporary
                        and not force_refresh
                        and self._credentials_are_usable(self._credentials)
                    ):
                        _LOGGER.warning(
                            "Unable to refresh Anthbot IoT credentials for %s; "
                            "using cached credentials until their expiration: %s",
                            self._serial_number,
                            err,
                        )
                        return self._credentials
                    _LOGGER.warning(
                        "Unable to obtain Anthbot IoT credentials for %s "
                        "after retries: %s",
                        self._serial_number,
                        err,
                    )
                    raise err
            self._credentials = creds
            self._credentials_acquired_at = time.time()
            self._credentials_generation += 1
            # Reuse the endpoint/region the cloud sent us if available — they
            # match the policy attached to the temp creds.
            if creds.endpoint:
                normalized = self._normalize_endpoint(creds.endpoint)
                if normalized:
                    self._iot_endpoint = normalized
            if creds.region_name:
                self._region_name = creds.region_name
            return creds

    @property
    def iot_credential_diagnostics(self) -> str:
        """Return non-secret metadata for diagnosing MQTT reconnects."""
        creds = self._credentials
        if creds is None:
            return "credential_generation=0, credential_id=none, expiration=unknown"
        fingerprint = hashlib.sha256(creds.access_key_id.encode("utf-8")).hexdigest()[:10]
        expiration = (
            datetime.fromtimestamp(creds.expiration, timezone.utc).isoformat()
            if creds.expiration is not None
            else "unknown"
        )
        return (
            f"credential_generation={self._credentials_generation}, "
            f"credential_id={fingerprint}, expiration={expiration}"
        )

    def set_live_command_publisher(
        self, publisher: LiveCommandPublisher | None
    ) -> None:
        """Register the active MQTT transport used for service commands."""
        self._live_command_publisher = publisher

    @staticmethod
    def _normalize_endpoint(iot_endpoint: str | None) -> str:
        if not isinstance(iot_endpoint, str) or not iot_endpoint:
            return DEFAULT_IOT_ENDPOINT
        endpoint = iot_endpoint.strip()
        endpoint = re.sub(r"^https?://", "", endpoint, flags=re.IGNORECASE)
        return endpoint.rstrip("/") or DEFAULT_IOT_ENDPOINT

    @staticmethod
    def _guess_region_from_endpoint(iot_endpoint: str) -> str | None:
        if ".iot." not in iot_endpoint:
            return None
        right_side = iot_endpoint.split(".iot.", 1)[1]
        region = right_side.split(".", 1)[0]
        return region or None

    @staticmethod
    def guess_region_from_endpoint(iot_endpoint: str) -> str | None:
        """Public helper to extract region from an IoT endpoint host."""
        return AnthbotShadowApiClient._guess_region_from_endpoint(iot_endpoint)

    @property
    def serial_number(self) -> str:
        """Return the configured device serial number."""
        return self._serial_number

    @property
    def session(self) -> ClientSession:
        """Return the shared Home Assistant HTTP session."""
        return self._session

    @property
    def iot_endpoint(self) -> str:
        """Return resolved IoT endpoint host."""
        return self._iot_endpoint

    @property
    def signing_region(self) -> str:
        """Return the signing region for AWS SigV4 requests."""
        endpoint_region = self._guess_region_from_endpoint(self._iot_endpoint)
        if endpoint_region:
            return endpoint_region
        return (
            self._region_name or DEFAULT_IOT_REGION
        )

    @staticmethod
    def build_default_iot_endpoint_for_region(region_name: str) -> str:
        """Build the default Anthbot IoT endpoint host for a region."""
        return IOT_ENDPOINT_TEMPLATE.format(region=region_name)

    def _access_key_id(
        self, creds: AnthbotTemporaryIotCredentials | None = None
    ) -> str:
        if creds is not None and creds.access_key_id:
            return creds.access_key_id
        raise AnthbotGenieApiError("Temporary IoT access key is unavailable")

    def _secret_access_key(
        self, creds: AnthbotTemporaryIotCredentials | None = None
    ) -> str:
        if creds is not None and creds.secret_access_key:
            return creds.secret_access_key
        raise AnthbotGenieApiError("Temporary IoT secret key is unavailable")

    @staticmethod
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _signing_key(
        self,
        date_stamp: str,
        creds: AnthbotTemporaryIotCredentials | None = None,
        *,
        service: str = "iotdata",
    ) -> bytes:
        k_date = self._sign(
            ("AWS4" + self._secret_access_key(creds)).encode("utf-8"), date_stamp
        )
        k_region = self._sign(k_date, self.signing_region)
        k_service = self._sign(k_region, service)
        return self._sign(k_service, "aws4_request")

    async def async_get_mqtt_websocket_url(
        self,
        *,
        force_refresh: bool = False,
        reauthenticate: bool = False,
    ) -> str:
        """Return the MQTT-over-WebSocket URL generated by the current app."""
        if reauthenticate:
            if self._account_client is None:
                raise AnthbotGenieApiError(
                    "Anthbot account client is required for re-authentication"
                )
            await self._account_client.async_reauthenticate()
            force_refresh = True
        creds = await self._async_get_credentials(force_refresh=force_refresh)
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        service = "iotdevicegateway"
        credential_scope = (
            f"{date_stamp}/{self.signing_region}/{service}/aws4_request"
        )
        query: dict[str, str] = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self._access_key_id(creds)}/{credential_scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = urlencode(
            sorted(query.items()), quote_via=quote, safe="-_.~"
        )
        payload_hash = hashlib.sha256(b"").hexdigest()
        canonical_request = (
            "GET\n/mqtt\n"
            f"{canonical_query}\n"
            f"host:{self._iot_endpoint}\n\n"
            f"host\n{payload_hash}"
        )
        string_to_sign = (
            "AWS4-HMAC-SHA256\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )
        signature = hmac.new(
            self._signing_key(date_stamp, creds, service=service),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signed_url = (
            f"wss://{self._iot_endpoint}/mqtt?{canonical_query}"
            f"&X-Amz-Signature={signature}"
        )
        # AWS IoT Core uses legacy WebSocket signing behavior for temporary
        # credentials: append the session token after calculating the
        # signature instead of including it in the canonical query.
        if creds.session_token:
            signed_url += (
                "&X-Amz-Security-Token="
                f"{quote(creds.session_token, safe='-_.~')}"
            )
        return signed_url

    def _build_authorization(
        self,
        amz_date: str,
        date_stamp: str,
        canonical_request: str,
        creds: AnthbotTemporaryIotCredentials | None = None,
    ) -> str:
        algorithm = "AWS4-HMAC-SHA256"
        signed_headers = self._signed_headers_from_request(canonical_request)
        credential_scope = (
            f"{date_stamp}/{self.signing_region}/iotdata/aws4_request"
        )
        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )
        signature = hmac.new(
            self._signing_key(date_stamp, creds),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return (
            f"{algorithm} Credential={self._access_key_id(creds)}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

    @staticmethod
    def _normalize_header_value(value: str) -> str:
        return " ".join(value.strip().split())

    @staticmethod
    def _canonical_headers(headers: dict[str, str]) -> tuple[str, str]:
        lowered = {
            key.lower(): AnthbotShadowApiClient._normalize_header_value(value)
            for key, value in headers.items()
        }
        ordered_keys = sorted(lowered.keys())
        canonical = "".join(f"{key}:{lowered[key]}\n" for key in ordered_keys)
        signed_headers = ";".join(ordered_keys)
        return canonical, signed_headers

    @staticmethod
    def _signed_headers_from_request(canonical_request: str) -> str:
        parts = canonical_request.split("\n")
        if len(parts) < 6:
            return "host;x-amz-content-sha256;x-amz-date"
        return parts[-2]

    @staticmethod
    def _canonical_uri_for_sigv4(request_uri: str) -> str:
        """Build SigV4 canonical URI.

        AWS canonicalization requires encoding '%' as '%25', so an already
        encoded request path (for example '/topics/%24aws%2F...') must be
        double-encoded only for signing.
        """
        encoded: list[str] = []
        for byte in request_uri.encode("utf-8"):
            if (
                0x30 <= byte <= 0x39  # 0-9
                or 0x41 <= byte <= 0x5A  # A-Z
                or 0x61 <= byte <= 0x7A  # a-z
                or byte in (45, 46, 95, 126, 47)  # - . _ ~ /
            ):
                encoded.append(chr(byte))
            else:
                encoded.append(f"%{byte:02X}")
        return "".join(encoded)

    async def _async_get_named_shadow_reported_state(
        self, shadow_name: str
    ) -> dict[str, Any]:
        """Fetch a named device shadow and return state.reported."""
        # Match the app's credential lifecycle: obtain one STS session and
        # retain it until expiry.  Refreshing STS after every HTTP shadow 403
        # races the MQTT handshake and can invalidate the URL that was signed
        # with the previous session.
        creds = await self._async_get_credentials()
        status, body, payload = await self._async_get_named_shadow_attempt(
            shadow_name, creds
        )
        if status != 200:
            raise AnthbotGenieApiError(
                f"Shadow request failed ({status}): {body[:300]}",
                status_code=status,
                temporary=status == 429,
            )
        if not isinstance(payload, dict):
            raise AnthbotGenieApiError("Invalid response payload type")
        state = payload.get("state")
        reported = state.get("reported") if isinstance(state, dict) else None
        if not isinstance(reported, dict):
            raise AnthbotGenieApiError("Missing state.reported in response")
        return reported

    async def _async_get_named_shadow_attempt(
        self,
        shadow_name: str,
        creds: AnthbotTemporaryIotCredentials | None,
    ) -> tuple[int, str, dict[str, Any] | None]:
        """Single signed GET attempt. Returns (status, body_text, payload_dict)."""
        request_uri = f"/things/{quote(self._serial_number, safe='-_.~')}/shadow"
        canonical_uri = self._canonical_uri_for_sigv4(request_uri)
        canonical_query = f"name={quote(shadow_name, safe='-_.~')}"
        payload_hash = hashlib.sha256(b"").hexdigest()

        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        signed_header_values = {
            "host": self._iot_endpoint,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        # If we have a session_token (temp STS creds), it MUST be signed and
        # sent as x-amz-security-token; otherwise AWS returns 403.
        if creds is not None and creds.session_token:
            signed_header_values["x-amz-security-token"] = creds.session_token
        canonical_headers, signed_headers = self._canonical_headers(signed_header_values)
        canonical_request = (
            "GET\n"
            f"{canonical_uri}\n"
            f"{canonical_query}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )
        authorization = self._build_authorization(
            amz_date=amz_date,
            date_stamp=date_stamp,
            canonical_request=canonical_request,
            creds=creds,
        )

        url = f"https://{self._iot_endpoint}{request_uri}?{canonical_query}"
        headers = {
            "Accept": "*/*",
            "Host": self._iot_endpoint,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization,
            "User-Agent": "LdMower/1581 CFNetwork/3860.400.51 Darwin/25.3.0",
        }
        if creds is not None and creds.session_token:
            headers["x-amz-security-token"] = creds.session_token

        try:
            async with self._session.get(url, headers=headers, timeout=15) as response:
                body = await response.text()
                payload: dict[str, Any] | None = None
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        payload = parsed
                except json.JSONDecodeError:
                    payload = None
                return response.status, body, payload
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

    async def async_get_shadow_reported_state(self) -> dict[str, Any]:
        """Fetch property shadow and return state.reported."""
        return await self._async_get_named_shadow_reported_state("property")

    async def async_get_service_reported_state(self) -> dict[str, Any]:
        """Fetch service shadow and return state.reported."""
        return await self._async_get_named_shadow_reported_state("service")

    async def _async_signed_post(
        self,
        *,
        request_uri: str,
        canonical_query: str,
        payload_bytes: bytes,
        include_sdk_headers: bool,
        canonical_uri_override: str | None = None,
        sign_content_length: bool = True,
        creds: AnthbotTemporaryIotCredentials | None = None,
    ) -> tuple[int, str, dict[str, Any] | None, dict[str, str]]:
        """Execute a signed IoTData POST request."""
        if creds is None:
            creds = await self._async_get_credentials()
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        signed_header_values = {
            "host": self._iot_endpoint,
            "content-type": "application/octet-stream",
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        headers = {
            "Accept": "*/*",
            "Host": self._iot_endpoint,
            "Content-Type": "application/octet-stream",
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if sign_content_length:
            signed_header_values["content-length"] = str(len(payload_bytes))
            headers["Content-Length"] = str(len(payload_bytes))

        if include_sdk_headers:
            invocation_id = str(uuid.uuid4())
            signed_header_values["amz-sdk-invocation-id"] = invocation_id
            signed_header_values["amz-sdk-request"] = "attempt=1; max=3"
            signed_header_values["x-amz-user-agent"] = "aws-sdk-js/3.846.0"
            headers["amz-sdk-invocation-id"] = invocation_id
            headers["amz-sdk-request"] = "attempt=1; max=3"
            headers["x-amz-user-agent"] = "aws-sdk-js/3.846.0"
            headers["User-Agent"] = (
                "aws-sdk-js/3.846.0 ua/2.1 os/other lang/js "
                "md/rn api/iot-data-plane#3.846.0 m/N,E,e"
            )
        else:
            headers["User-Agent"] = "LdMower/1581 CFNetwork/3860.400.51 Darwin/25.3.0"

        # Add x-amz-security-token when using STS temp creds.
        if creds is not None and creds.session_token:
            signed_header_values["x-amz-security-token"] = creds.session_token
            headers["x-amz-security-token"] = creds.session_token

        canonical_headers, signed_headers = self._canonical_headers(signed_header_values)
        canonical_uri = (
            canonical_uri_override
            if isinstance(canonical_uri_override, str)
            else self._canonical_uri_for_sigv4(request_uri)
        )
        canonical_request = (
            "POST\n"
            f"{canonical_uri}\n"
            f"{canonical_query}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )
        headers["Authorization"] = self._build_authorization(
            amz_date=amz_date,
            date_stamp=date_stamp,
            canonical_request=canonical_request,
            creds=creds,
        )

        url = f"https://{self._iot_endpoint}{request_uri}"
        if canonical_query:
            url = f"{url}?{canonical_query}"

        try:
            async with self._session.post(
                url,
                headers=headers,
                data=payload_bytes,
                timeout=15,
            ) as response:
                body_text = await response.text()
                payload: dict[str, Any] | None = None
                try:
                    parsed = json.loads(body_text)
                    if isinstance(parsed, dict):
                        payload = parsed
                except json.JSONDecodeError:
                    payload = None
                response_headers = {
                    "x-amzn-errortype": response.headers.get("x-amzn-errortype", ""),
                    "x-amzn-requestid": response.headers.get("x-amzn-requestid", ""),
                    "x-amzn-request-id": response.headers.get("x-amzn-request-id", ""),
                    "date": response.headers.get("date", ""),
                }
                return response.status, body_text, payload, response_headers
        except ClientError as err:
            raise AnthbotGenieApiError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise AnthbotGenieApiError("Request timed out") from err

    async def async_publish_service_command(self, *, cmd: str, data: Any = None) -> None:
        """Publish a service command to the mower service shadow topic."""
        desired: dict[str, Any] = {"cmd": cmd}
        # JavaScript JSON.stringify omits an undefined argument. Commands such
        # as mow_pause and charge_start are called by the app without data.
        if data is not None:
            desired["data"] = data
        body = {"state": {"desired": desired}}
        payload_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")
        topic = f"$aws/things/{self._serial_number}/shadow/name/service/update"
        if self._live_command_publisher is not None:
            await self._live_command_publisher(topic, payload_bytes)
            return
        raise AnthbotGenieApiError(
            f"MQTT is not connected; command '{cmd}' was not sent",
            temporary=True,
        )
