"""Regression coverage for the Genie clear-error recovery probe."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUTTON_SOURCE = ROOT / "custom_components" / "anthbot_map" / "button.py"


def _source() -> str:
    return BUTTON_SOURCE.read_text(encoding="utf-8")


def test_clear_error_probe_is_genie_only() -> None:
    source = _source()
    assert 'key="clear_error_code_test"' in source
    assert 'model_family(getattr(coordinator.device, "model", "")) == "genie"' in source
    assert (
        'model_family(getattr(self.coordinator.device, "model", "")) != "genie"'
        in source
    )


def test_clear_error_probe_uses_confirmed_app_command_only() -> None:
    source = _source()
    block = source.split('elif key == "clear_error_code_test":', 1)[1].split(
        'elif key == "start_full_mow":', 1
    )[0]
    assert 'cmd="clear_err_code", data=1' in block
    assert "mow_start" not in block
    assert "mow_continue" not in block
    assert "stop_all_tasks" not in block
    assert "charge_start" not in block


def test_clear_error_probe_exposes_before_after_recovery_fields() -> None:
    source = _source()
    helper = source.split("def _error_clear_test_snapshot", 1)[1].split(
        "def _automatic_diagnostics_trigger", 1
    )[0]
    for field in ("safety_trigger", "err_code", "event_code", "robot_sta", "mode"):
        assert f'"{field}"' in helper

    attrs = source.split("def extra_state_attributes", 1)[1].split(
        "async def _async_export_firmware_diagnostics", 1
    )[0]
    assert '"current_safety_trigger"' in attrs
    assert '"last_test_before"' in source
    assert '"last_test_after"' in source
