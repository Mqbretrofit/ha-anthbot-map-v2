"""Regression coverage for isolated ANTHBOT N8 support."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_n8_has_its_own_model_family() -> None:
    base = _read(MODELS / "base.py")
    boundary = _read(MODELS / "n8.py")
    assert 'return "n8"' in base
    assert 'MODEL_FAMILY = "n8"' in boundary


def test_n8_control_is_installed_after_existing_m_series_layer() -> None:
    common = _read(MODELS / "m_series_common.py")
    assert "install_m_series_control_support()" in common
    assert "install_n8_control_support()" in common
    assert common.index("install_m_series_control_support()") < common.index(
        "install_n8_control_support()"
    )


def test_n8_control_does_not_claim_other_models() -> None:
    control = _read(MODELS / "n8_control.py")
    assert "if not _is_n8_client(self) or cmd not in _N8_COMMANDS:" in control
    assert "await previous_publish(self, cmd=cmd, data=data)" in control
    assert 'return "N8" in' in control


def test_n8_core_mowing_and_dump_commands_are_native() -> None:
    control = _read(MODELS / "n8_control.py")
    for command in (
        "mow_start",
        "mow_pause",
        "stop_all_tasks",
        "charge_start",
        "custom_area_mow_start",
        "region_mow_start",
        "start_dump",
        "stop_dump",
    ):
        assert f'"{command}"' in control
    assert 'body = {"state": {"desired": {"cmd": cmd, "data": data}}}' in control


def test_n8_skips_genie_app_state_without_changing_m_series_detection() -> None:
    commands = _read(INTEGRATION / "commands.py")
    assert 'return "M5" in model or "M9" in model' in commands
    assert "n8 = _is_n8(coordinator)" in commands
    assert "native_app_model = m_series or n8" in commands
    assert "if not m_series:" in commands
    assert "if not n8:" in commands
    assert 'cmd="app_state", data=app_state' in commands
    assert 'cmd="mow_start", data=1' in commands
