#!/usr/bin/env python3
"""Compare N8 validation captures without exposing map geometry or schedule times.

The normal Home Assistant ``Export & send firmware diagnostics`` button is used
for the before/after JSON reports. Optionally pass the matching N8 map-manager
archives as well; this tool extracts only structural fingerprints from
``area_setting.json`` and ``time_setting.json``.

Typical workflow::

    python tools/n8_validation_bundle.py before.json after.json \
        --before-map before_map_manager.tar.gz \
        --after-map after_map_manager.tar.gz

Change exactly one setting/action in the official ANTHBOT app between captures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from typing import Any

_MISSING = object()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return payload


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _scalar(value: Any) -> Any:
    return value if value is None or isinstance(value, (bool, int, float, str)) else None


def _member_json(archive_path: Path, basename: str) -> dict[str, Any] | None:
    try:
        with tarfile.open(archive_path, mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile() or member.name.rsplit("/", 1)[-1] != basename:
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    return None
                payload = json.loads(extracted.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else None
    except (tarfile.TarError, OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError(f"{archive_path}: cannot read {basename}: {err}") from err
    return None


def _area_list_summary(value: Any, *, geometry_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    items = value if isinstance(value, list) else []
    ids: list[Any] = []
    key_sets: set[tuple[str, ...]] = set()
    fingerprints: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_id = item.get("id", item.get("grassId", index))
        ids.append(_scalar(item_id))
        key_sets.add(tuple(sorted(str(key) for key in item)))
        geometry = {key: item.get(key) for key in geometry_keys if key in item}
        if geometry:
            fingerprints.append({"id": _scalar(item_id), "geometry_sha256_16": _hash(geometry)})
    return {
        "count": len(items),
        "ids": ids,
        "key_sets": [list(keys) for keys in sorted(key_sets)],
        "geometry_fingerprints": fingerprints,
    }


def summarize_area_setting(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return map-area structure without coordinates or user labels."""
    if not isinstance(payload, dict):
        return {"present": False}

    area_id = payload.get("area_id")
    result: dict[str, Any] = {
        "present": True,
        "top_level_keys": sorted(str(key) for key in payload),
        "area_id_sha256_16": _hash(area_id) if area_id not in (None, "") else None,
    }
    list_specs = {
        "dump_grass_areas": ("vertexs", "points"),
        "custom_areas": ("vertexs", "points", "polygon"),
        "region_areas": ("vertexs", "points", "polygon"),
        "ridable_areas": ("vertexs", "points", "path"),
        "forbid_areas": ("vertexs", "points", "polygon"),
        "bridge_areas": ("vertexs", "points", "path"),
    }
    for key, geometry_keys in list_specs.items():
        if key in payload:
            result[key] = _area_list_summary(payload.get(key), geometry_keys=geometry_keys)
    return result


def summarize_time_setting(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return plan/DND structure without exporting start/end times."""
    if not isinstance(payload, dict):
        return {"present": False}

    entries = payload.get("value") if isinstance(payload.get("value"), list) else []
    dnd_count = 0
    appointment_count = 0
    key_sets: set[tuple[str, ...]] = set()
    fingerprints: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        key_sets.add(tuple(sorted(str(key) for key in item)))
        if item.get("unlock") == 0:
            dnd_count += 1
        else:
            appointment_count += 1
        # Hash the complete entry locally so a change can be detected without
        # printing personal start/end times or weekday selections.
        fingerprints.append(_hash(item))

    result: dict[str, Any] = {
        "present": True,
        "top_level_keys": sorted(str(key) for key in payload),
        "entry_count": len(entries),
        "dnd_count": dnd_count,
        "appointment_count": appointment_count,
        "entry_key_sets": [list(keys) for keys in sorted(key_sets)],
        "entry_fingerprints": fingerprints,
    }
    for key in ("version",):
        if key in payload:
            result[key] = _scalar(payload.get(key))
    for key in ("plan_id", "id"):
        if key in payload and payload.get(key) not in (None, ""):
            result[f"{key}_sha256_16"] = _hash(payload.get(key))
    return result


def summarize_map_manager(path: Path) -> dict[str, Any]:
    """Summarize the two high-value N8 JSON members in one archive."""
    return {
        "area_setting": summarize_area_setting(_member_json(path, "area_setting.json")),
        "time_setting": summarize_time_setting(_member_json(path, "time_setting.json")),
    }


def _diagnostics_subset(report: dict[str, Any]) -> dict[str, Any]:
    protocol = report.get("n8_protocol")
    if not isinstance(protocol, dict):
        raise ValueError("diagnostics report has no n8_protocol block")
    device = report.get("device") if isinstance(report.get("device"), dict) else {}
    return {
        "firmware_version": device.get("firmware_version"),
        "n8_protocol": protocol,
    }


def _identity(report: dict[str, Any]) -> str:
    device = report.get("device") if isinstance(report.get("device"), dict) else {}
    model = device.get("model") or "unknown-model"
    serial_hash = str(device.get("serial_sha256") or "")[:8]
    return f"{model} / {serial_hash or 'unknown'}"


def _assert_same_device(before: dict[str, Any], after: dict[str, Any]) -> None:
    before_device = before.get("device") if isinstance(before.get("device"), dict) else {}
    after_device = after.get("device") if isinstance(after.get("device"), dict) else {}
    before_hash = before_device.get("serial_sha256")
    after_hash = after_device.get("serial_sha256")
    if before_hash and after_hash and before_hash != after_hash:
        raise ValueError("before/after diagnostics belong to different mowers")


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        if not value:
            result[prefix] = {}
        for key in sorted(value, key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(value[key], child))
        return result
    if isinstance(value, list):
        result[prefix] = value
        return result
    result[prefix] = value
    return result


def compare_structures(before: Any, after: Any) -> list[dict[str, Any]]:
    """Return deterministic changes between already privacy-safe summaries."""
    before_flat = _flatten(before)
    after_flat = _flatten(after)
    changes: list[dict[str, Any]] = []
    for path in sorted(set(before_flat) | set(after_flat)):
        old = before_flat.get(path, _MISSING)
        new = after_flat.get(path, _MISSING)
        if old == new:
            continue
        kind = "added" if old is _MISSING else "removed" if new is _MISSING else "changed"
        changes.append(
            {
                "path": path,
                "kind": kind,
                "before": None if old is _MISSING else old,
                "after": None if new is _MISSING else new,
            }
        )
    return changes


def build_validation_result(
    before_report: dict[str, Any],
    after_report: dict[str, Any],
    *,
    before_map: dict[str, Any] | None = None,
    after_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one shareable privacy-safe validation result."""
    _assert_same_device(before_report, after_report)
    diagnostics_changes = compare_structures(
        _diagnostics_subset(before_report),
        _diagnostics_subset(after_report),
    )
    map_changes: list[dict[str, Any]] = []
    if before_map is not None or after_map is not None:
        map_changes = compare_structures(before_map or {}, after_map or {})
    return {
        "schema": "anthbot-n8-validation-diff-v1",
        "before": _identity(before_report),
        "after": _identity(after_report),
        "diagnostics_change_count": len(diagnostics_changes),
        "diagnostics_changes": diagnostics_changes,
        "map_manager_change_count": len(map_changes),
        "map_manager_changes": map_changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare privacy-safe N8 before/after diagnostics and optional map-manager archives."
    )
    parser.add_argument("before", type=Path, help="before firmware diagnostics JSON")
    parser.add_argument("after", type=Path, help="after firmware diagnostics JSON")
    parser.add_argument("--before-map", type=Path, help="optional before map_manager tar.gz")
    parser.add_argument("--after-map", type=Path, help="optional after map_manager tar.gz")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    if bool(args.before_map) != bool(args.after_map):
        parser.error("--before-map and --after-map must be supplied together")

    before_report = _read_json(args.before)
    after_report = _read_json(args.after)
    before_map = summarize_map_manager(args.before_map) if args.before_map else None
    after_map = summarize_map_manager(args.after_map) if args.after_map else None
    result = build_validation_result(
        before_report,
        after_report,
        before_map=before_map,
        after_map=after_map,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"Before: {result['before']}")
    print(f"After:  {result['after']}")
    print(f"Diagnostics changes: {result['diagnostics_change_count']}")
    for change in result["diagnostics_changes"]:
        print(f"- {change['path']} [{change['kind']}] {change['before']!r} -> {change['after']!r}")
    print(f"Map-manager structural changes: {result['map_manager_change_count']}")
    for change in result["map_manager_changes"]:
        print(f"- {change['path']} [{change['kind']}] {change['before']!r} -> {change['after']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
