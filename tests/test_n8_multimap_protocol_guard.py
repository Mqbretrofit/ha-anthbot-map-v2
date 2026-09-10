from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_n8_transport_claims_multi_map_commands_before_legacy_fallback() -> None:
    control = _read(INTEGRATION / "models" / "n8_control.py")

    assert '"multi_map_ctl"' in control
    assert '"delete_sub_map"' in control
    assert "if not _is_n8_client(self) or cmd not in _N8_COMMANDS:" in control
    assert "await previous_publish(self, cmd=cmd, data=data)" in control
    assert "cmd, data = _normalize_n8_command(cmd, data)" in control


def test_destructive_multi_map_controls_are_not_exposed_as_ha_buttons() -> None:
    buttons = _read(INTEGRATION / "button.py")

    for unsafe_key in (
        "save_map_backup",
        "update_map_backup",
        "restore_map_backup",
        "delete_map_backup",
        "delete_sub_map",
    ):
        assert f'key="{unsafe_key}"' not in buttons

    for unsafe_cmd in (
        'cmd="multi_map_ctl"',
        'cmd="delete_sub_map"',
    ):
        assert unsafe_cmd not in buttons
