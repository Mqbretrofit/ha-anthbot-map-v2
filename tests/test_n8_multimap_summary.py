from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "summarize_n8_multi_maps.py"

spec = importlib.util.spec_from_file_location("summarize_n8_multi_maps", MODULE_PATH)
assert spec is not None and spec.loader is not None
MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def test_multi_map_summary_keeps_only_safe_values() -> None:
    payload = {
        "property": {
            "multi_maps": {
                "state": 2,
                "time": 123456,
                "map_list": [
                    {
                        "id": 17,
                        "map_file_name": "secret-map-file.tar.gz",
                        "md5": "do-not-copy-this-hash",
                        "time_stamp": 987654,
                        "download_url": "https://example.invalid/private-map",
                    }
                ],
            }
        }
    }

    summary = MODULE.summarize_multi_maps(payload)

    assert summary["found"] is True
    assert summary["state"] == 2
    assert summary["time"] == 123456
    assert summary["map_list_count"] == 1
    assert summary["map_list"][0]["id"] == 17
    assert summary["map_list"][0]["time_stamp"] == 987654
    assert summary["map_list"][0]["field_names"] == [
        "download_url",
        "id",
        "map_file_name",
        "md5",
        "time_stamp",
    ]

    serialized = repr(summary)
    assert "secret-map-file.tar.gz" not in serialized
    assert "do-not-copy-this-hash" not in serialized
    assert "https://example.invalid/private-map" not in serialized


def test_multi_map_summary_unwraps_shadow_value_envelope() -> None:
    payload = {
        "reported": {
            "multi_maps": {
                "value": {
                    "state": 1,
                    "map_list": [{"id": 3, "md5": "hidden"}],
                },
                "time": 111,
            }
        }
    }

    summary = MODULE.summarize_multi_maps(payload)

    assert summary["found"] is True
    assert summary["state"] == 1
    assert summary["map_list_count"] == 1
    assert summary["map_list"][0]["id"] == 3
    assert "hidden" not in repr(summary)


def test_multi_map_summary_reports_absent_state() -> None:
    assert MODULE.summarize_multi_maps({"reported": {"mode": "charge"}}) == {
        "found": False
    }


def test_multi_map_summary_caps_large_lists() -> None:
    payload = {
        "multi_maps": {
            "state": 0,
            "map_list": [{"id": index} for index in range(25)],
        }
    }

    summary = MODULE.summarize_multi_maps(payload)

    assert summary["map_list_count"] == 25
    assert summary["map_list_truncated"] is True
    assert len(summary["map_list"]) == 16
