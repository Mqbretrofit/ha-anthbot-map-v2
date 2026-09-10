from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "custom_components" / "anthbot_map" / "models" / "n8_plan_payload.py"
)

spec = importlib.util.spec_from_file_location("n8_plan_payload_test", MODULE_PATH)
assert spec is not None and spec.loader is not None
MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def test_old_firmware_version_uses_legacy_plan_feature_gates() -> None:
    # 1.0.42 is useful only as a generic old-version boundary example here;
    # the observed 1.0.42 live capture belongs to an M9 Pro, not an N8.
    assert MODULE.supports_incremental_plan("1.0.42") is False
    assert MODULE.supports_plan_end_time("1.0.42") is False


def test_feature_gate_boundaries_match_recovered_app_thresholds() -> None:
    assert MODULE.supports_plan_end_time("1.15.12") is False
    assert MODULE.supports_plan_end_time("1.15.13") is True
    assert MODULE.supports_incremental_plan("1.16.14") is False
    assert MODULE.supports_incremental_plan("1.16.15") is True
    assert MODULE.supports_incremental_plan("1.17.0") is True


def test_dnd_entry_matches_recovered_wire_shape() -> None:
    assert MODULE.build_dnd_entry(
        start_time="22:00",
        end_time="07:00",
        active=1,
    ) == {
        "start_time": "22:00",
        "end_time": "07:00",
        "active": 1,
        "unlock": 0,
        "week": [1, 2, 3, 4, 5, 6, 7],
        "repeat": 1,
        "workmode": 0,
    }


def test_full_plan_envelope_matches_mow_regular_data_shape() -> None:
    dnd = MODULE.build_dnd_entry(start_time=79200, end_time=25200, active=1)
    data = MODULE.build_full_plan_data([dnd], timezone_sec=7200)
    assert data == {
        "timezone": 2.0,
        "timezone_sec": 7200,
        "value": [dnd],
    }
    assert MODULE.build_mow_regular_command(data) == {
        "cmd": "mow_regular",
        "data": data,
    }


def test_fractional_timezone_is_preserved() -> None:
    data = MODULE.build_full_plan_data([], timezone_sec=19800)
    assert data["timezone"] == 5.5
    assert data["timezone_sec"] == 19800


def test_incremental_envelope_requires_version_but_does_not_guess_entries() -> None:
    changed = MODULE.build_dnd_entry(start_time=80000, end_time=20000, active=1)
    data = MODULE.build_incremental_plan_data(
        [changed], timezone_sec=3600, version=17
    )
    assert data == {
        "timezone": 1.0,
        "timezone_sec": 3600,
        "value": [changed],
        "version": 17,
    }

    try:
        MODULE.build_incremental_plan_data([], timezone_sec=0, version=None)
    except ValueError:
        pass
    else:
        raise AssertionError("incremental payload accepted a missing plan version")
