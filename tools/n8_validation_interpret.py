#!/usr/bin/env python3
"""Interpret an N8 validation diff into likely feature buckets.

This is intentionally heuristic: it never claims a field is proven. It helps
triage before/after captures by grouping changed paths into likely N8 feature
areas while preserving the raw machine-readable diff for review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FEATURE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("child_lock", ("child", "lock")),
    ("anti_loss_radius", ("anti_loss_radius", "anti_loss")),
    ("visual_obstacle_sensitivity", ("pobctl", "perception", "obstacle", "level")),
    ("near_dock_mowing", ("near_chg_mow", "nest_switch", "near_dock", "dock_mow")),
    ("mowing_delay", ("mow_delay", "delay_time")),
    ("dnd_schedule", ("time_setting", "dnd", "appointment", "plan_version")),
    ("dumping_area", ("dump_grass", "dumping", "grass_area")),
    ("work_mode_rtk", ("work_mode", "rtk", "nrtk")),
    ("voice_package", ("voice", "volume")),
    ("map_backup", ("backup", "restore", "map_manager")),
    ("cleaning_maintenance", ("clean", "maintenance")),
)


def _paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("diagnostics_changes", "map_manager_changes"):
        changes = payload.get(key)
        if not isinstance(changes, list):
            continue
        for item in changes:
            if isinstance(item, dict) and item.get("path") is not None:
                paths.append(str(item["path"]))
    return paths


def classify(paths: list[str]) -> dict[str, Any]:
    normalized = [path.lower() for path in paths]
    scores: dict[str, int] = {}
    matches: dict[str, list[str]] = {}

    for feature, patterns in FEATURE_PATTERNS:
        feature_matches = [
            path
            for path, lower in zip(paths, normalized)
            if any(pattern in lower for pattern in patterns)
        ]
        if feature_matches:
            scores[feature] = len(feature_matches)
            matches[feature] = feature_matches

    ranked = sorted(scores, key=lambda name: (-scores[name], name))
    primary = ranked[0] if ranked else None
    ambiguous = len(ranked) > 1 and scores[ranked[0]] == scores[ranked[1]]

    return {
        "likely_feature": None if ambiguous else primary,
        "ambiguous": ambiguous,
        "feature_scores": {name: scores[name] for name in ranked},
        "feature_matches": {name: matches[name] for name in ranked},
        "changed_path_count": len(paths),
        "changed_paths": paths,
        "note": (
            "Heuristic only; a live N8 capture is required before treating any path as proven."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpret ANTHBOT N8 validation diff")
    parser.add_argument("diff", type=Path, help="n8_validation_diff.json")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args()

    payload = json.loads(args.diff.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("validation diff root must be an object")

    result = classify(_paths(payload))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"Likely feature: {result['likely_feature'] or 'unknown/ambiguous'}")
    print(f"Changed paths: {result['changed_path_count']}")
    for path in result["changed_paths"]:
        print(f"- {path}")
    if result["feature_scores"]:
        print("Feature scores:")
        for name, score in result["feature_scores"].items():
            print(f"- {name}: {score}")
    print(result["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
