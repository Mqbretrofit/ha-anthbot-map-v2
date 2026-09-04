"""Attach stable mower identity metadata to setting entities.

The dashboard must never infer mower ownership from Home Assistant's generated
entity-id suffixes alone.  The old beta3 setting entities were created before
multi-mower model splitting and several of them do not expose serial_number in
their state attributes.  Add that metadata centrally without changing their
command/value behavior.
"""

from __future__ import annotations

from typing import Any

from ..number import AnthbotNumberEntity, AnthbotZoneNumberEntity
from ..select import AnthbotZoneMowingModeSelect
from ..switch import AnthbotSwitchEntity, AnthbotZoneSwitchEntity

_INSTALLED = False


def _base_identity(entity: Any) -> dict[str, Any]:
    coordinator = entity.coordinator
    return {
        "serial_number": coordinator.client.serial_number,
        "model": coordinator.device.model,
    }


def _global_identity(entity: Any) -> dict[str, Any]:
    return _base_identity(entity)


def _zone_number_identity(entity: AnthbotZoneNumberEntity) -> dict[str, Any]:
    return {
        **_base_identity(entity),
        "zone_kind": entity._zone_kind,
        "zone_id": entity._zone_id,
        "setting": entity._setting,
    }


def _zone_switch_identity(entity: AnthbotZoneSwitchEntity) -> dict[str, Any]:
    return {
        **_base_identity(entity),
        "zone_kind": entity._zone_kind,
        "zone_id": entity._zone_id,
        "setting": entity._setting,
    }


def _zone_select_identity(entity: AnthbotZoneMowingModeSelect) -> dict[str, Any]:
    zone = entity._find_zone()
    value = zone.get("mow_mode") if isinstance(zone, dict) else None
    name = zone.get("name") if isinstance(zone, dict) else None
    return {
        **_base_identity(entity),
        "zone_kind": entity._zone_kind,
        "zone_id": entity._zone_id,
        "zone_name": name,
        "raw_mow_mode": value,
    }


def install_setting_entity_identity() -> None:
    """Expose serial/model metadata on all dashboard setting entities."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    AnthbotNumberEntity.extra_state_attributes = property(_global_identity)
    AnthbotSwitchEntity.extra_state_attributes = property(_global_identity)
    AnthbotZoneNumberEntity.extra_state_attributes = property(_zone_number_identity)
    AnthbotZoneSwitchEntity.extra_state_attributes = property(_zone_switch_identity)
    AnthbotZoneMowingModeSelect.extra_state_attributes = property(_zone_select_identity)
