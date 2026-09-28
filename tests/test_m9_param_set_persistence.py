from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "custom_components" / "anthbot_map" / "models" / "m_series_control.py"


def _source() -> str:
    return CONTROL.read_text(encoding="utf-8")


def test_m_series_param_set_reads_property_shadow_before_write() -> None:
    source = _source()
    assert 'cmd == "param_set"' in source
    assert '_async_get_named_shadow_reported_state("property")' in source
    assert 'reported.get("param_set")' in source


def test_m_series_param_set_merges_change_into_complete_object() -> None:
    source = _source()
    assert "merged = dict(current)" in source
    assert "merged.update(normalized_changes)" in source
    assert "data=full_param_set" in source


def test_m_series_param_set_does_not_use_legacy_single_cutter_payload() -> None:
    source = _source()
    param_block = source[source.index('if cmd == "param_set":'):]
    assert 'full_param_set = await _build_full_param_set(self, data)' in param_block
    assert 'data=full_param_set' in param_block


def test_legacy_cutter_key_is_normalized_to_real_m9_field() -> None:
    source = _source()
    assert '"cutter_ctl_cutter_lift" in normalized_changes' in source
    assert 'normalized_changes["cutter_height"]' in source
    assert 'normalized_changes.pop("cutter_ctl_cutter_lift")' in source
