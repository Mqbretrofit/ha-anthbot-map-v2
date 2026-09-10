#!/usr/bin/env python3
"""Summarize N8/MGS RTK state from an API Explorer or diagnostics JSON.

The output intentionally avoids GPS/location coordinates and raw RTK station
identifiers. Station IDs are represented only by a short SHA-256 fingerprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

_MODE_LABELS = {1: "NRTK", 2: "RTK", 3: "Auto"}
_LOCATION_PARTS = ("latitude", "longitude", "lat", "lon", "lng", "position", "pose")


def _unwrap(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value and set(value).issubset(
        {"value", "time", "timestamp"}
    ):
        return value.get("value")
    return value


def _fingerprint(value: Any) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    text = str(value)
    return {
        "present": True,
        "length": len(text),
        "sha256_prefix": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
    }


def _walk(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, item in value.items():
            current = path + (str(key),)
            yield current, item
            yield from _walk(item, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, path + (str(index),))


def _path_is_location(path: tuple[str, ...]) -> bool:
    normalized = ".".join(path).lower().replace("-", "_")
    return any(part in normalized for part in _LOCATION_PARTS)


def _scalar(value: Any) -> Any:
    value = _unwrap(value)
    return value if value is None or isinstance(value, (bool, int, float, str)) else None


def summarize(payload: Any) -> dict[str, Any]:
    """Return a small privacy-safe RTK/NRTK evidence block."""
    result: dict[str, Any] = {
        "rtk_mode": None,
        "rtk_mode_label": None,
        "rtk_state": None,
        "rtk_base_state": None,
        "base_state": None,
        "base_id": None,
        "satellite_count": None,
        "satellite_list_count": None,
        "bt_satellite_time": None,
        "matched_fields": {},
    }

    for path, raw in _walk(payload):
        if not path or _path_is_location(path):
            continue
        key = path[-1].lower().replace("-", "_")
        scalar = _scalar(raw)
        path_text = ".".join(path)

        if key == "rtk_base_state" and scalar is not None:
            result["rtk_base_state"] = scalar
            # Prefer the current MGS acknowledgement field for mode selection.
            if result["rtk_mode"] is None:
                try:
                    result["rtk_mode"] = int(scalar)
                except (TypeError, ValueError):
                    pass
        elif key == "rtk_state" and scalar is not None:
            result["rtk_state"] = scalar
        elif key == "rtk_id":
            result["base_id"] = _fingerprint(_unwrap(raw))
        elif key == "bt_satellite_time" and scalar is not None:
            result["bt_satellite_time"] = scalar
        elif key in {"satellite_count", "satellitecount"} and scalar is not None:
            result["satellite_count"] = scalar
        elif key in {"satellite_list", "satellitelist"} and isinstance(raw, list):
            result["satellite_list_count"] = len(raw)
        elif key == "state" and len(path) >= 2 and path[-2].lower() == "rtk_base":
            if scalar is not None:
                result["base_state"] = scalar

        normalized_path = path_text.lower().replace("-", "_")
        if (
            ("rtk" in normalized_path or "satellite" in normalized_path or "gnss" in normalized_path)
            and scalar is not None
            and key != "rtk_id"
        ):
            result["matched_fields"][path_text] = scalar

    mode = result.get("rtk_mode")
    if isinstance(mode, int):
        result["rtk_mode_label"] = _MODE_LABELS.get(mode)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize N8/MGS RTK state without exporting coordinates or raw base IDs"
    )
    parser.add_argument("json_file", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    print(json.dumps(summarize(payload), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
