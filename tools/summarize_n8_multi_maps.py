#!/usr/bin/env python3
"""Summarize ANTHBOT N8 ``multi_maps`` state without leaking map payloads.

This helper is intended for reverse-engineering captures from the API Explorer
or a diagnostics/raw-shadow export. It reports only structural metadata needed
to validate the N8 map-backup protocol; URLs, hashes and other opaque values are
not copied into the output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_MAX_DEPTH = 10
_MAX_ITEMS = 16
_SAFE_MULTI_MAP_SCALARS = ("state", "time")
_SAFE_ENTRY_SCALARS = ("id", "time_stamp")


def _unwrap(value: Any) -> Any:
    """Unwrap common one-value shadow envelopes."""
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value and set(value).issubset(
        {"value", "time", "timestamp"}
    ):
        identity = id(value)
        if identity in seen:
            break
        seen.add(identity)
        value = value.get("value")
    return value


def _scalar(value: Any) -> Any:
    value = _unwrap(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return None


def _find_multi_maps(value: Any, *, depth: int = 0) -> dict[str, Any] | None:
    """Locate the first plausible ``multi_maps`` object recursively."""
    if depth > _MAX_DEPTH:
        return None
    value = _unwrap(value)
    if isinstance(value, dict):
        direct = _unwrap(value.get("multi_maps"))
        if isinstance(direct, dict):
            return direct
        if "map_list" in value and any(key in value for key in ("state", "time")):
            return value
        for item in value.values():
            found = _find_multi_maps(item, depth=depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value[:64]:
            found = _find_multi_maps(item, depth=depth + 1)
            if found is not None:
                return found
    return None


def summarize_multi_maps(payload: Any) -> dict[str, Any]:
    """Return a privacy-safe structural summary of N8 ``multi_maps`` state."""
    multi_maps = _find_multi_maps(payload)
    if multi_maps is None:
        return {"found": False}

    summary: dict[str, Any] = {"found": True}
    for key in _SAFE_MULTI_MAP_SCALARS:
        if key in multi_maps:
            summary[key] = _scalar(multi_maps.get(key))

    raw_list = _unwrap(multi_maps.get("map_list"))
    if not isinstance(raw_list, list):
        summary["map_list_count"] = None
        summary["map_list"] = []
        return summary

    entries: list[dict[str, Any]] = []
    for raw_item in raw_list[:_MAX_ITEMS]:
        item = _unwrap(raw_item)
        if not isinstance(item, dict):
            entries.append({"type": type(item).__name__})
            continue

        entry: dict[str, Any] = {
            "field_names": sorted(str(key) for key in item.keys()),
        }
        for key in _SAFE_ENTRY_SCALARS:
            if key in item:
                entry[key] = _scalar(item.get(key))
        entries.append(entry)

    summary["map_list_count"] = len(raw_list)
    summary["map_list_truncated"] = len(raw_list) > _MAX_ITEMS
    summary["map_list"] = entries
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize ANTHBOT N8 multi_maps state without map URLs/hashes"
    )
    parser.add_argument("json_file", type=Path, help="API Explorer/shadow JSON file")
    args = parser.parse_args()

    payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    print(json.dumps(summarize_multi_maps(payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
