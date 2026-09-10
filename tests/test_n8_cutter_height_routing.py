"""Regression guards for current MGS/N8 global cutter-height handling."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_n8_global_height_translates_shared_param_set_to_ctl_cutter() -> None:
    control = _read(MODELS / "n8_control.py")

    assert '"ctl_cutter"' in control
    assert 'set(data) == {"cutter_height"}' in control
    assert 'return "ctl_cutter", data["cutter_height"]' in control


def test_other_n8_param_set_payloads_are_not_rewritten_as_ctl_cutter() -> None:
    control = _read(MODELS / "n8_control.py")

    # The exact-set guard is intentional: work mode, mowing passes and heading
    # remain normal param_set payloads instead of being mistaken for height.
    assert 'set(data) == {"cutter_height"}' in control
    assert "return cmd, data" in control


def test_n8_direct_cutter_height_is_mirrored_for_existing_number_entity() -> None:
    status = _read(MODELS / "n8_status.py")
    numbers = _read(INTEGRATION / "number.py")

    assert 'state.get("cutter_height")' in status
    assert 'params["cutter_height"] = cutter_height' in status
    assert 'state["_n8_cutter_height"] = cutter_height' in status
    assert 'data.get("param_set", {}).get("cutter_height")' in numbers


def test_existing_height_range_matches_current_mgs_picker() -> None:
    numbers = _read(INTEGRATION / "number.py")

    assert "native_min_value=30" in numbers
    assert "native_max_value=70" in numbers
    assert "native_step=5" in numbers
    assert 'native_unit_of_measurement="mm"' in numbers
