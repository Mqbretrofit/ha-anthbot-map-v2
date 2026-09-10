from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "summarize_n8_rtk.py"


def _module():
    spec = importlib.util.spec_from_file_location("summarize_n8_rtk", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rtk_summarizer_decodes_mode_without_leaking_location_or_base_id() -> None:
    module = _module()
    payload = {
        "ctl_rtk_base": {"rtk_base_state": 3},
        "rtk_state": 2,
        "rtk_base": {"rtk_id": "station-secret-123", "state": 1},
        "satelliteCount": 19,
        "satelliteList": [{"sn": 1}, {"sn": 2}],
        "bt_satellite_time": 123456,
        "gps_latitude": 47.1,
        "gps_longitude": 18.2,
        "position_rtk_status": 9,
    }
    result = module.summarize(payload)

    assert result["rtk_mode"] == 3
    assert result["rtk_mode_label"] == "Auto"
    assert result["rtk_state"] == 2
    assert result["base_state"] == 1
    assert result["satellite_count"] == 19
    assert result["satellite_list_count"] == 2
    assert result["base_id"]["present"] is True
    assert result["base_id"]["sha256_prefix"]
    rendered = str(result)
    assert "station-secret-123" not in rendered
    assert "47.1" not in rendered
    assert "18.2" not in rendered
    assert "position_rtk_status" not in rendered


def test_rtk_summarizer_maps_all_current_mgs_modes() -> None:
    module = _module()
    for raw, label in ((1, "NRTK"), (2, "RTK"), (3, "Auto")):
        result = module.summarize({"ctl_rtk_base": {"rtk_base_state": raw}})
        assert result["rtk_mode"] == raw
        assert result["rtk_mode_label"] == label
