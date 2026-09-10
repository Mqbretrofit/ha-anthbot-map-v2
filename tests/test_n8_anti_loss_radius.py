"""Regression guards for the N8/MGS anti-loss radius setting."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


def _read(name: str) -> str:
    return (INTEGRATION / name).read_text(encoding="utf-8")


def test_n8_anti_loss_radius_uses_exact_app_range() -> None:
    numbers = _read("number.py")
    assert 'key="n8_anti_loss_radius_setting"' in numbers
    assert "native_min_value=50" in numbers
    assert "native_max_value=500" in numbers
    assert 'native_unit_of_measurement="m"' in numbers
    assert 'cmd="anti_loss_radius"' in numbers
    assert 'data=int_value' in numbers
    assert "N8 anti-loss radius must be 50..500 m" in numbers


def test_n8_anti_loss_radius_is_model_scoped() -> None:
    numbers = _read("number.py")
    assert "N8_NUMBERS:" in numbers
    assert 'if is_n8_model(getattr(coordinator.device, "model", None)):' in numbers


def test_n8_adapter_translates_radius_to_current_device_config() -> None:
    control = _read("models/n8_control.py")
    assert 'cmd == "anti_loss_radius"' in control
    assert 'return "device_config", {"anti_loss_radius": value}' in control
