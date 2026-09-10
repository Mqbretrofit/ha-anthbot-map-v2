from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "compare_n8_protocol_reports.py"

spec = importlib.util.spec_from_file_location("compare_n8_protocol_reports", TOOL)
assert spec is not None and spec.loader is not None
MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def test_n8_protocol_diff_reports_only_changed_fields() -> None:
    before = {
        "n8_protocol": {
            "direct": {"anti_loss_radius": 50, "rain_switch": 1},
            "candidate_fields": {"device_config.child_lock_switch": 0},
            "dump_grass_areas": {"count": 1, "ids": [7]},
        }
    }
    after = {
        "n8_protocol": {
            "direct": {"anti_loss_radius": 75, "rain_switch": 1},
            "candidate_fields": {"device_config.child_lock_switch": 1},
            "dump_grass_areas": {"count": 2, "ids": [7, 8]},
        }
    }

    changes = MODULE.compare_reports(before, after)
    by_path = {item["path"]: item for item in changes}

    assert set(by_path) == {
        "n8_protocol.candidate_fields.device_config.child_lock_switch",
        "n8_protocol.direct.anti_loss_radius",
        "n8_protocol.dump_grass_areas.count",
        "n8_protocol.dump_grass_areas.ids",
    }
    assert by_path[
        "n8_protocol.candidate_fields.device_config.child_lock_switch"
    ]["before"] == 0
    assert by_path[
        "n8_protocol.candidate_fields.device_config.child_lock_switch"
    ]["after"] == 1
    assert by_path["n8_protocol.direct.anti_loss_radius"]["before"] == 50
    assert by_path["n8_protocol.direct.anti_loss_radius"]["after"] == 75


def test_n8_protocol_diff_marks_added_and_removed_fields() -> None:
    before = {"n8_protocol": {"candidate_fields": {"old_field": 1}}}
    after = {"n8_protocol": {"candidate_fields": {"new_field": 2}}}

    changes = MODULE.compare_reports(before, after)
    by_path = {item["path"]: item for item in changes}

    assert by_path["n8_protocol.candidate_fields.old_field"]["kind"] == "removed"
    assert by_path["n8_protocol.candidate_fields.new_field"]["kind"] == "added"
