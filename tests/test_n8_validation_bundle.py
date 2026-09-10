from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "n8_validation_bundle.py"

spec = importlib.util.spec_from_file_location("n8_validation_bundle_test", MODULE_PATH)
assert spec is not None and spec.loader is not None
MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def _report(*, child_lock: int = 0, firmware: str = "1.2.3") -> dict[str, object]:
    return {
        "schema": "anthbot-firmware-diagnostics-v1",
        "device": {
            "model": "N8",
            "firmware_version": firmware,
            "serial_sha256": "a" * 64,
        },
        "n8_protocol": {
            "candidate_fields": {
                "device_config.child_lock_switch": child_lock,
                "device_config.anti_loss_radius": 50,
            }
        },
    }


def _archive(path: Path, *, dump_id: int, start_time: str, plan_version: int) -> None:
    area = {
        "area_id": f"area-{dump_id}",
        "dump_grass_areas": [
            {
                "id": dump_id,
                "grassId": dump_id,
                "vertexs": [[1000, 2000], [2500, 2000], [2500, 3500], [1000, 3500]],
                "remote": False,
            }
        ],
    }
    time_setting = {
        "version": plan_version,
        "timezone": 2,
        "timezone_sec": 7200,
        "value": [
            {
                "start_time": start_time,
                "end_time": "07:00",
                "active": 1,
                "unlock": 0,
                "week": [1, 2, 3, 4, 5, 6, 7],
                "repeat": 1,
                "workmode": 0,
            }
        ],
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in (
            ("nested/area_setting.json", area),
            ("nested/time_setting.json", time_setting),
        ):
            raw = json.dumps(payload).encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))


def test_diagnostics_diff_detects_one_child_lock_change() -> None:
    result = MODULE.build_validation_result(_report(child_lock=0), _report(child_lock=1))
    assert result["diagnostics_change_count"] == 1
    assert result["diagnostics_changes"] == [
        {
            "path": "n8_protocol.candidate_fields.device_config.child_lock_switch",
            "kind": "changed",
            "before": 0,
            "after": 1,
        }
    ]


def test_rejects_reports_from_different_mowers() -> None:
    before = _report()
    after = _report()
    after["device"] = dict(after["device"], serial_sha256="b" * 64)
    try:
        MODULE.build_validation_result(before, after)
    except ValueError as err:
        assert "different mowers" in str(err)
    else:
        raise AssertionError("different mower reports were accepted")


def test_map_manager_summary_hides_geometry_and_schedule_times(tmp_path: Path) -> None:
    path = tmp_path / "map_manager.tar.gz"
    _archive(path, dump_id=500, start_time="22:00", plan_version=7)

    summary = MODULE.summarize_map_manager(path)
    encoded = json.dumps(summary, sort_keys=True)

    assert summary["area_setting"]["dump_grass_areas"]["count"] == 1
    assert summary["area_setting"]["dump_grass_areas"]["ids"] == [500]
    assert summary["time_setting"]["dnd_count"] == 1
    assert summary["time_setting"]["version"] == 7
    assert "22:00" not in encoded
    assert "1000" not in encoded
    assert "3500" not in encoded
    assert "vertexs" in encoded
    assert "geometry_sha256_16" in encoded
    assert "entry_fingerprints" in encoded


def test_map_manager_diff_detects_dump_and_plan_change_without_raw_values(tmp_path: Path) -> None:
    before_path = tmp_path / "before.tar.gz"
    after_path = tmp_path / "after.tar.gz"
    _archive(before_path, dump_id=500, start_time="22:00", plan_version=7)
    _archive(after_path, dump_id=501, start_time="23:00", plan_version=8)

    before_map = MODULE.summarize_map_manager(before_path)
    after_map = MODULE.summarize_map_manager(after_path)
    result = MODULE.build_validation_result(
        _report(),
        _report(),
        before_map=before_map,
        after_map=after_map,
    )
    encoded = json.dumps(result, sort_keys=True)

    assert result["map_manager_change_count"] > 0
    assert any(
        change["path"] == "area_setting.dump_grass_areas.ids"
        for change in result["map_manager_changes"]
    )
    assert any(
        change["path"] == "time_setting.version"
        for change in result["map_manager_changes"]
    )
    assert "22:00" not in encoded
    assert "23:00" not in encoded
    assert "1000" not in encoded
