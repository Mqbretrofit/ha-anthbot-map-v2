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


def test_n8_map_is_installed_after_shared_map_and_zone_decoders() -> None:
    common = _read(MODELS / "m_series_common.py")
    assert "install_m_series_map_support()" in common
    assert "install_m_series_zone_support()" in common
    assert "install_n8_map_support()" in common
    assert common.index("install_m_series_map_support()") < common.index(
        "install_m_series_zone_support()"
    ) < common.index("install_n8_map_support()")


def test_n8_path_and_status_install_without_expanding_m_series_guards() -> None:
    common = _read(MODELS / "m_series_common.py")
    path = _read(MODELS / "n8_path.py")
    status = _read(MODELS / "n8_status.py")
    m_path = _read(MODELS / "m_series_path.py")
    m_status = _read(MODELS / "m_series_status.py")

    assert "install_n8_path_support()" in common
    assert "install_n8_status_support()" in common
    assert 'return "M5" in value or "M9" in value' in m_path
    assert 'return "M5" in value or "M9" in value' in m_status
    assert "is_n8_model(getattr(self.device, \"model\", None))" in path
    assert "_legacy._decode_live_curpath" in path
    assert '"n8_curpath"' in path
    assert "is_n8_model(getattr(self.device, \"model\", None))" in status
    assert 'state["_n8_dumping"]' in status
    assert 'state["_n8_grass_bag_in_position"]' in status
    assert 'state["_n8_grass_shield_in_position"]' in status


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


def test_n8_rain_payload_is_normalized_inside_n8_layer_only() -> None:
    control = _read(MODELS / "n8_control.py")
    init = _read(INTEGRATION / "__init__.py")
    assert 'cmd == "ctl_rainer"' in control
    assert 'normalized["rain_switch"] = normalized.pop("switch")' in control
    assert 'normalized["rain_continue_time"] = normalized.pop("continue_time")' in control
    assert '"switch": switch_value' in init
    assert '"continue_time": rain_continue_time * 3600' in init


def test_n8_skips_genie_app_state_without_changing_m_series_detection() -> None:
    commands = _read(INTEGRATION / "commands.py")
    assert 'return "M5" in model or "M9" in model' in commands
    assert "n8 = _is_n8(coordinator)" in commands
    assert "native_app_model = m_series or n8" in commands
    assert "if not m_series:" in commands
    assert "if not n8:" in commands
    assert 'cmd="app_state", data=app_state' in commands
    assert 'cmd="mow_start", data=1' in commands


def test_n8_map_adapter_reuses_decoders_without_expanding_m_series_guard() -> None:
    map_source = _read(MODELS / "m_series_map.py")
    n8_map = _read(MODELS / "n8_map.py")
    assert 'return "M5" in value or "M9" in value' in map_source
    assert "if not is_n8_model(model):" in n8_map
    assert "m_series_map._download_current_map_manager" in n8_map
    assert "m_series_map._decode_map_manager_archive" in n8_map
    assert "m_series_zones._publish_area_definition" in n8_map
    assert '"dump_grass_area_count"' in n8_map


def test_n8_dump_buttons_are_only_added_for_n8() -> None:
    buttons = _read(INTEGRATION / "button.py")
    assert "N8_BUTTONS:" in buttons
    assert 'key="start_dump"' in buttons
    assert 'key="stop_dump"' in buttons
    assert 'if is_n8_model(getattr(coordinator.device, "model", None)):' in buttons
    assert 'cmd="start_dump", data=1' in buttons
    assert 'cmd="stop_dump", data=1' in buttons


def test_n8_work_mode_select_is_model_scoped() -> None:
    selects = _read(INTEGRATION / "select.py")
    assert '"Mulch": 0' in selects
    assert '"Collect": 1' in selects
    assert '"Sweep": 2' in selects
    assert "AnthbotN8WorkModeSelect" in selects
    assert 'if is_n8_model(getattr(coordinator.device, "model", None)):' in selects
    assert 'cmd="param_set"' in selects
    assert 'data={"work_mode": raw_value}' in selects
    assert '"Normal": 0' in selects
    assert '"Efficient": 1' in selects
    assert "AnthbotZoneMowingModeSelect" in selects


def test_n8_anti_loss_switch_is_model_scoped() -> None:
    switches = _read(INTEGRATION / "switch.py")
    assert "N8_SWITCHES:" in switches
    assert 'key="n8_anti_loss_enabled"' in switches
    assert 'if is_n8_model(getattr(coordinator.device, "model", None)):' in switches
    assert 'cmd="anti_loss_switch", data=1 if enabled else 0' in switches
    for existing in (
        "custom_mowing_direction_enabled",
        "visual_obstacle_detection_enabled",
        "rain_perception_enabled",
        "edge_following_return_enabled",
        "automatic_dock_mowing_enabled",
    ):
        assert f'key="{existing}"' in switches


def test_n8_binary_sensors_are_model_scoped_and_generic_sensors_remain() -> None:
    sensors = _read(INTEGRATION / "binary_sensor.py")
    assert "N8_BINARY_SENSORS:" in sensors
    assert 'key="n8_dumping"' in sensors
    assert 'key="n8_grass_bag_in_position"' in sensors
    assert 'key="n8_grass_shield_in_position"' in sensors
    assert 'if is_n8_model(getattr(coordinator.device, "model", None)):' in sensors
    for existing in (
        "connection",
        "charging",
        "cellular_connected",
        "cellular_heartbeat",
        "bluetooth_active",
        "sim_present",
        "map_available",
        "rtk_moving",
        "accelerometer_active",
        "mowing_border",
        "mowing_nest",
        "full_yard_mowing",
        "anti_loss_state",
        "camera_state",
        "edge_cut_state",
        "indoor_mode_state",
        "auto_upgrade_state",
        "obstacle_avoidance_state",
        "drc_enabled",
        "log_upload_enabled",
        "factory_reset_pending",
        "unbind_pending",
    ):
        assert f'key="{existing}"' in sensors


def test_existing_core_button_keys_are_preserved() -> None:
    buttons = _read(INTEGRATION / "button.py")
    for key in (
        "connect_cloud",
        "start_full_mow",
        "start_outer_edge_mow",
        "start_dock_edge_mow",
        "stop_mow",
        "return_to_dock",
        "resume_mow",
        "pause_mow",
        "reset_blade_maintenance",
        "reset_camera_maintenance",
        "reset_dock_contact_maintenance",
        "export_firmware_diagnostics",
    ):
        assert f'key="{key}"' in buttons
