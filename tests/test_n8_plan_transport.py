"""Regression checks for the statically recovered N8 plan transport."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


def test_mow_regular_is_recognized_only_by_n8_native_adapter() -> None:
    control = (INTEGRATION / "models" / "n8_control.py").read_text("utf-8")
    assert '"mow_regular"' in control
    assert "if not _is_n8_client(self) or cmd not in _N8_COMMANDS:" in control
    assert "await previous_publish(self, cmd=cmd, data=data)" in control


def test_dnd_write_is_not_exposed_before_live_n8_validation() -> None:
    for filename in ("switch.py", "number.py", "select.py", "button.py"):
        source = (INTEGRATION / filename).read_text("utf-8")
        assert 'cmd="mow_regular"' not in source
        assert "cmd='mow_regular'" not in source
