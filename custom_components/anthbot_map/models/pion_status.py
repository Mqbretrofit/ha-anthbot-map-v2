"""ANTHBOT Pion / MGC reported-state compatibility.

The Pion family is exposed by the cloud as MGC500/MGC750/MGC1000 on some
accounts.  Its property shadow is flatter than Genie/M-series payloads, so keep
the raw vendor keys intact and publish a namespaced normalized snapshot for
Home Assistant consumers.  No command rewriting happens in this layer.
"""

from __future__ import annotations

from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from .base import model_family

_INSTALLED = False


def is_pion_model(model: object) -> bool:
    """Return whether a model belongs to the Pion/MGC family."""
    return model_family(model) == "pion"


def _scalar(value: Any) -> Any:
    """Unwrap the common AWS {value: ...} scalar envelope."""
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def _pion_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """Return the confirmed MGC/Pion fields without changing vendor values."""
    firmware = state.get("fw_version")
    breakpoint = state.get("breakpoint")
    snapshot = {
        "cutter_height": _scalar(state.get("cutter_height")),
        "mowing_progress": _scalar(state.get("mowing_progress")),
        "mowing_area": _scalar(state.get("mowing_area")),
        "mow_direction": _scalar(state.get("mow_direction")),
        "rain_enabled": _scalar(state.get("rainer_ctl")),
        "rain_effect": _scalar(state.get("rainer_effect")),
        "near_charge_mow": _scalar(state.get("near_chg_mow_ctl")),
        "rssi": _scalar(state.get("rssi")),
        "ip_address": _scalar(state.get("sta_ip_addr")),
        "maptime": _scalar(state.get("maptime")),
        "curpath": state.get("curpath"),
        "breakpoint": dict(breakpoint) if isinstance(breakpoint, dict) else None,
        "firmware": dict(firmware) if isinstance(firmware, dict) else None,
    }
    return {key: value for key, value in snapshot.items() if value is not None}


def _add_pion_status_aliases(state: dict[str, Any]) -> None:
    snapshot = _pion_snapshot(state)
    if snapshot:
        state["_pion"] = snapshot


def install_pion_status_support() -> None:
    """Install Pion/MGC-only reported-state normalization."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        await previous_live(self, shadow_name, reported)
        if not is_pion_model(getattr(self.device, "model", None)):
            return
        state = self.reported_state
        if not isinstance(state, dict):
            return
        enriched = dict(state)
        _add_pion_status_aliases(enriched)
        if enriched != state:
            self.async_set_updated_data(enriched)

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        if isinstance(state, dict) and is_pion_model(
            getattr(self.device, "model", None)
        ):
            _add_pion_status_aliases(state)
        return state

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data


__all__ = ["install_pion_status_support", "is_pion_model"]
