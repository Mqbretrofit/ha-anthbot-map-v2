"""Unit tests for the N8/MGS time_setting.json read-only probe."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import types


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.anthbot_map"
MODELS = f"{PACKAGE}.models"


def _load_module():
    custom_components = sys.modules.setdefault(
        "custom_components", types.ModuleType("custom_components")
    )
    custom_components.__path__ = [str(ROOT / "custom_components")]

    package = sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
    package.__path__ = [str(ROOT / "custom_components" / "anthbot_map")]

    models = sys.modules.setdefault(MODELS, types.ModuleType(MODELS))
    models.__path__ = [str(ROOT / "custom_components" / "anthbot_map" / "models")]

    coordinator = types.ModuleType(f"{PACKAGE}.coordinator")

    class AnthbotGenieDataUpdateCoordinator:
        async def _async_refresh_map_definition(self, *args, **kwargs):
            return {}, False

    coordinator.AnthbotGenieDataUpdateCoordinator = AnthbotGenieDataUpdateCoordinator
    sys.modules[f"{PACKAGE}.coordinator"] = coordinator

    m_series_map = types.ModuleType(f"{MODELS}.m_series_map")
    m_series_zones = types.ModuleType(f"{MODELS}.m_series_zones")
    n8_control = types.ModuleType(f"{MODELS}.n8_control")
    n8_control.is_n8_model = lambda model: str(model).upper() == "N8"
    sys.modules[f"{MODELS}.m_series_map"] = m_series_map
    sys.modules[f"{MODELS}.m_series_zones"] = m_series_zones
    sys.modules[f"{MODELS}.n8_control"] = n8_control

    name = f"{MODELS}.n8_map"
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / "custom_components" / "anthbot_map" / "models" / "n8_map.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


def _archive(payload: object, *, name: str = "maps/time_setting.json") -> bytes:
    raw = json.dumps(payload).encode("utf-8")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(raw)
        archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue()


def test_decodes_time_setting_from_nested_map_manager_path() -> None:
    payload = {
        "timezone": 2,
        "timezone_sec": 7200,
        "value": [
            {
                "start_time": 28800,
                "end_time": 36000,
                "active": 1,
                "unlock": 0,
                "week": [1, 2, 3, 4, 5, 6, 7],
                "repeat": 1,
                "workmode": 0,
            }
        ],
    }
    assert MODULE._decode_n8_time_setting(_archive(payload)) == payload


def test_summary_distinguishes_dnd_and_normal_plans_without_times() -> None:
    payload = {
        "timezone": 2,
        "timezone_sec": 7200,
        "version": 17,
        "value": [
            {
                "start_time": 28800,
                "end_time": 36000,
                "active": 1,
                "unlock": 0,
                "week": [1, 2, 3, 4, 5, 6, 7],
                "repeat": 1,
                "workmode": 0,
            },
            {
                "start_time": 57600,
                "end_time": 64800,
                "active": 1,
                "unlock": 4,
                "week": [1, 3, 5],
                "repeat": 1,
                "workmode": 1,
            },
        ],
    }
    summary = MODULE._summarize_n8_time_setting(payload)

    assert summary["top_level_keys"] == ["timezone", "timezone_sec", "value", "version"]
    assert summary["entry_count"] == 2
    assert summary["dnd_count"] == 1
    assert summary["appointment_count"] == 1
    assert summary["timezone"] == 2
    assert summary["timezone_sec"] == 7200
    assert summary["version"] == 17
    assert "start_time" not in summary
    assert "end_time" not in summary
    assert summary["entry_key_sets"] == [
        ["active", "end_time", "repeat", "start_time", "unlock", "week", "workmode"]
    ]


def test_invalid_or_missing_time_setting_is_ignored() -> None:
    assert MODULE._decode_n8_time_setting(b"") is None
    assert MODULE._decode_n8_time_setting(b"not a tar") is None
    assert MODULE._decode_n8_time_setting(_archive([], name="time_setting.json")) is None
    assert MODULE._decode_n8_time_setting(_archive({}, name="area_setting.json")) is None
