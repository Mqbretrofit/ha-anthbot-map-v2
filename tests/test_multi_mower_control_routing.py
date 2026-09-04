"""Regression coverage for Genie + M-series control routing.

These tests intentionally inspect the small model/router layers instead of the
large card bundle. They protect the multi-mower fixes without changing the
proven beta3 map/path/history implementation.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
RUNTIME_FRONTEND = INTEGRATION / "frontend"
WWW_FRONTEND = ROOT / "www" / "anthbot-map"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_and_www_control_resolvers_are_identical() -> None:
    """HA runtime and standalone /local mirror must execute the same resolver."""
    assert _read(RUNTIME_FRONTEND / "serial-entity-resolver.js") == _read(
        WWW_FRONTEND / "serial-entity-resolver.js"
    )


def test_control_resolver_is_serial_scoped_and_fail_closed() -> None:
    """One mower may never fall through to another mower's HA entities."""
    source = _read(RUNTIME_FRONTEND / "serial-entity-resolver.js")

    assert 'ANTHBOT_CONTROL_ROUTER_VERSION = "2026-09-04-control-v6"' in source
    assert "serialOf(state) === identity.serial" in source
    assert 'return String(this.config?.entity || "")' in source
    assert 'return this.findEntity("switch", ["battery_saver_mode", "battery saver mode"])' in source
    assert "serial_number: identity.serial" in source
    assert "window.__anthbotFeedbackClickHandler" in source
    assert 'window.setInterval(disableLegacyCommandRouter, 25)' in source
    assert "document.removeEventListener(\"click\", handler, true)" in source


def test_primary_mowing_tile_uses_direct_anthbot_services() -> None:
    """Start/Pause/Resume must not depend on command-button discovery."""
    source = _read(RUNTIME_FRONTEND / "serial-entity-resolver.js")
    assert "proto.handlePrimaryMowingAction = async function (action)" in source
    assert 'await this.callAnthbotService("pause_mow")' in source
    assert 'await this.callAnthbotService("resume_mow")' in source
    assert 'await this.callAnthbotService("start_full_mow")' in source
    assert 'await this.callAnthbotService("start_zone_mow"' in source
    assert 'await this.callAnthbotService("start_auto_zone_mow"' in source
    assert 'await this.callAnthbotService("start_outer_edge_mow")' in source
    assert 'await this.callAnthbotService("start_dock_edge_mow")' in source


def test_native_buttons_expose_serial_number() -> None:
    """Native entities remain uniquely attributable to a mower."""
    source = _read(INTEGRATION / "button.py")
    assert "def extra_state_attributes" in source
    assert 'return {"serial_number": self.coordinator.client.serial_number}' in source
    assert "active_manual_zone_ids" in source


def test_m_series_native_control_layer_installs_after_legacy_wrapper() -> None:
    """M-series simple commands must override only the legacy scalar reshaping."""
    common = _read(INTEGRATION / "models" / "m_series_common.py")
    control = _read(INTEGRATION / "models" / "m_series_control.py")

    legacy_pos = common.index("_install_legacy()")
    control_pos = common.index("install_m_series_control_support()")
    assert legacy_pos < control_pos

    for command in (
        "mow_start",
        "mow_pause",
        "mow_continue",
        "mow_stop",
        "ridable_mow_start",
        "nest_mow_start",
        "charge_start",
    ):
        assert f'"{command}"' in control

    assert '"stop_all_tasks": "mow_stop"' in control
    assert 'body = {"state": {"desired": {"cmd": cmd, "data": data}}}' in control
    assert 'if not _is_m_series_client(self):' in control
    assert 'await previous_publish(self, cmd=cmd, data=data)' in control


def test_genie_command_sequence_remains_beta3_style() -> None:
    """M-series corrections must not remove Genie's app_state + mow_start path."""
    source = _read(INTEGRATION / "commands.py")
    assert "if not m_series:" in source
    assert 'cmd="app_state", data=app_state' in source
    assert 'cmd="mow_start", data=1' in source
