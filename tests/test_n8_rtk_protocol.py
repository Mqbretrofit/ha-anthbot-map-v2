"""Regression guards for statically proven N8/MGS RTK routing."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_n8_rtk_service_commands_are_native_only() -> None:
    control = _read(MODELS / "n8_control.py")
    assert '"ctl_rtk_base"' in control
    assert '"req_rtk_base_info"' in control
    assert "if not _is_n8_client(self) or cmd not in _N8_COMMANDS:" in control
    assert "await previous_publish(self, cmd=cmd, data=data)" in control


def test_n8_rtk_mode_is_not_exposed_before_live_validation() -> None:
    public_sources = "\n".join(
        _read(INTEGRATION / name)
        for name in ("button.py", "switch.py", "select.py", "number.py")
    )
    assert 'cmd="ctl_rtk_base"' not in public_sources
    assert 'cmd="req_rtk_base_info"' not in public_sources


def test_sync_position_is_not_claimed_by_cloud_n8_transport() -> None:
    control = _read(MODELS / "n8_control.py")
    assert '"sync_position"' not in control
