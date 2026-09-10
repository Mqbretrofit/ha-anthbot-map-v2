"""Regression guards for fields observed on a real N8 property shadow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_n8_child_lock_uses_real_reported_field_read_only() -> None:
    status = _read(MODELS / "n8_status.py")
    control = _read(MODELS / "n8_control.py")
    switches = _read(INTEGRATION / "switch.py")

    assert 'device_config.get("child_lock_switch")' in status
    assert 'state["_n8_child_lock"] = child_lock' in status
    assert "ui_lock" in status
    assert "different\n    # semantics" in status

    # Do not invent a writer from the read-side field. The app/device ui_lock
    # mechanism is also intentionally not exposed as the physical-panel lock.
    assert 'cmd == "child_lock_switch"' not in control
    assert 'key="n8_child_lock' not in switches


def test_n8_rtk_live_report_shape_is_normalized_without_public_writer() -> None:
    status = _read(MODELS / "n8_status.py")
    control = _read(MODELS / "n8_control.py")

    assert 'rtk_base_control = state.get("ctl_rtk_base")' in status
    assert 'rtk_base_control.get("rtk_base_state")' in status
    assert 'rtk_base_control.get("nrtk_base_sdk")' in status
    assert 'state["_n8_rtk_base_state"] = rtk_base_state' in status
    assert 'state["_n8_nrtk_base_sdk"] = nrtk_base_sdk' in status

    # Exact commands are routed N8-native, but an HA selector is still gated
    # on deliberate live command validation rather than the mere report shape.
    assert '"ctl_rtk_base"' in control
    assert '"req_rtk_base_info"' in control
