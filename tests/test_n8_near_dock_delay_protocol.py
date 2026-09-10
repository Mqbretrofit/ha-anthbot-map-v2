"""Regression guards for statically recovered N8 near-dock/delay commands."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_proven_near_dock_and_delay_commands_use_n8_native_transport() -> None:
    control = _read(MODELS / "n8_control.py")

    assert '"ctl_near_chg_mow"' in control
    assert '"mow_delay"' in control
    assert "if not _is_n8_client(self) or cmd not in _N8_COMMANDS:" in control
    assert 'body = {"state": {"desired": {"cmd": cmd, "data": data}}}' in control


def test_near_dock_and_delay_writes_are_not_exposed_as_ha_entities_yet() -> None:
    # Static protocol recovery is not enough to expose controls before a real
    # N8 confirms the reported state and physical near-dock behavior.
    for filename in ("button.py", "number.py", "select.py", "switch.py"):
        source = _read(INTEGRATION / filename)
        assert 'cmd="ctl_near_chg_mow"' not in source
        assert 'cmd="mow_delay"' not in source


def test_delay_protocol_documents_current_app_minute_values() -> None:
    notes = _read(ROOT / "N8_NEAR_DOCK_DELAY_PROTOCOL.md")

    assert "3 hours -> 180" in notes
    assert "2 hours -> 120" in notes
    assert "1 hour  -> 60" in notes
    assert "Off     -> 0" in notes
    assert '"cmd":"mow_delay","data":180' in notes
    assert '"cmd": "ctl_near_chg_mow"' in notes
