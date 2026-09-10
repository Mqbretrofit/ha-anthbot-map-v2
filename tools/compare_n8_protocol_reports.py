#!/usr/bin/env python3
"""Compare two privacy-safe ANTHBOT N8 diagnostics reports.

Typical use while reverse engineering an official-app control:

    python tools/compare_n8_protocol_reports.py before.json after.json

Capture `before.json`, change exactly one setting in the official ANTHBOT app,
then capture `after.json`. The tool prints only the changed values from the
`n8_protocol` discovery block, making fields such as Child Lock or anti-loss
radius easy to identify without comparing full raw shadow dumps.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_MISSING = object()


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: report root must be an object")
    protocol = payload.get("n8_protocol")
    if not isinstance(protocol, dict):
        raise ValueError(f"{path}: report has no n8_protocol block")
    return payload


def _flatten(value: Any, prefix: str = "n8_protocol") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        if not value:
            result[prefix] = {}
        for key in sorted(value, key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(value[key], child))
        return result
    if isinstance(value, list):
        # Keep small diagnostic lists atomic. This makes ID-list changes much
        # easier to read than one changed line per array index.
        result[prefix] = value
        return result
    result[prefix] = value
    return result


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic field-level changes between two N8 reports."""
    before_protocol = before.get("n8_protocol")
    after_protocol = after.get("n8_protocol")
    if not isinstance(before_protocol, dict) or not isinstance(after_protocol, dict):
        raise ValueError("both reports must contain an n8_protocol object")

    before_flat = _flatten(before_protocol)
    after_flat = _flatten(after_protocol)
    changes: list[dict[str, Any]] = []
    for path in sorted(set(before_flat) | set(after_flat)):
        old = before_flat.get(path, _MISSING)
        new = after_flat.get(path, _MISSING)
        if old == new:
            continue
        if old is _MISSING:
            kind = "added"
        elif new is _MISSING:
            kind = "removed"
        else:
            kind = "changed"
        changes.append(
            {
                "path": path,
                "kind": kind,
                "before": None if old is _MISSING else old,
                "after": None if new is _MISSING else new,
            }
        )
    return changes


def _report_identity(report: dict[str, Any]) -> str:
    device = report.get("device")
    if not isinstance(device, dict):
        return "unknown"
    model = device.get("model") or "unknown-model"
    serial_hash = str(device.get("serial_sha256") or "")[:8]
    return f"{model} / {serial_hash or 'unknown'}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diff the privacy-safe n8_protocol blocks in two ANTHBOT diagnostics reports."
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of a text summary",
    )
    args = parser.parse_args()

    before = _load_report(args.before)
    after = _load_report(args.after)
    changes = compare_reports(before, after)

    if args.json:
        print(
            json.dumps(
                {
                    "before": _report_identity(before),
                    "after": _report_identity(after),
                    "change_count": len(changes),
                    "changes": changes,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"Before: {_report_identity(before)}")
    print(f"After:  {_report_identity(after)}")
    print(f"Changed N8 protocol fields: {len(changes)}")
    for change in changes:
        path = change["path"]
        kind = change["kind"]
        print(f"- {path} [{kind}]")
        print(f"    before: {change['before']!r}")
        print(f"    after:  {change['after']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
