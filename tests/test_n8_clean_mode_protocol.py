"""Regression guards for statically recovered N8 cleaning mode."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_clean_mode_uses_n8_native_transport() -> None:
    control = _read(MODELS / "n8_control.py")
    assert '"clean_mode_cmd"' in control
    assert "if not _is_n8_client(self) or cmd not in _N8_COMMANDS:" in control
    assert 'body = {"state": {"desired": {"cmd": cmd, "data": data}}}' in control


def test_clean_mode_is_not_exposed_as_ha_button_yet() -> None:
    buttons = _read(INTEGRATION / "button.py")
    assert 'key="clean_mode"' not in buttons
    assert 'key="clean_mode_cmd"' not in buttons
    assert 'cmd="clean_mode_cmd"' not in buttons


def test_clean_mode_static_protocol_records_gating_and_result_states() -> None:
    notes = _read(ROOT / "N8_CLEAN_MODE_PROTOCOL.md")
    assert '"cmd": "clean_mode_cmd"' in notes
    assert '"data": 1' in notes
    assert "idle" in notes
    assert "pause" in notes
    assert "state == 3 -> success / resolve" in notes
    assert "state == 2 -> failure / reject" in notes
    assert "10-second timeout" in notes
    assert "descending_disk_failed" in notes
