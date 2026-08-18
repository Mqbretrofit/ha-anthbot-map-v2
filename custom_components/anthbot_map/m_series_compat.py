"""Compatibility helpers for ANTHBOT M5/M9 cloud/shadow behavior.

M5/M9 can expose readable REST state via the property named shadow while still
publishing useful live status fragments on the service shadow MQTT topics.
Commands remain writable through the service named shadow.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from . import mqtt_live
from .api import AnthbotShadowApiClient
from .coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("ANTHBOT TEST: m_series_compat.py loaded")

_M_SERIES_SERIALS: set[str] = set()
_INSTALLED = False


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _serial_from_topic(topic: str) -> str | None:
    marker = "$aws/things/"
    if not topic.startswith(marker):
        return None
    remainder = topic[len(marker):]
    serial, separator, _ = remainder.partition("/")
    return serial if separator and serial else None


def install_m_series_compat() -> None:
    """Install model-aware M5/M9 behavior once per Home Assistant process."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_coordinator_init = AnthbotGenieDataUpdateCoordinator.__init__
    original_service_state = AnthbotShadowApiClient.async_get_service_reported_state
    original_publish = AnthbotShadowApiClient.async_publish_service_command
    original_publish_packet = mqtt_live._publish_packet

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        original_coordinator_init(self, *args, **kwargs)
        model = getattr(self.device, "model", None)
        setattr(self.client, "_device_model", model)
        is_m_series = _is_m_series(model)
        _LOGGER.warning(
            "ANTHBOT MODEL TEST: serial=%s, model=%s, m_series=%s",
            self.client.serial_number,
            model,
            is_m_series,
        )
        if is_m_series:
            _M_SERIES_SERIALS.add(self.client.serial_number)

    async def service_state(self) -> dict[str, Any]:
        if _is_m_series(getattr(self, "_device_model", None)):
            # REST reads of the service named shadow can be rejected for M5/M9.
            # Use property for polling, but keep MQTT service subscriptions: M9
            # firmware may publish robot status there even when telemetry such
            # as battery arrives through property.
            return await self._async_get_named_shadow_reported_state("property")
        return await original_service_state(self)

    async def publish_service_command(self, *, cmd: str, data: Any = None) -> None:
        if not _is_m_series(getattr(self, "_device_model", None)):
            await original_publish(self, cmd=cmd, data=data)
            return

        converted = data
        if cmd == "param_set":
            value = data
            if isinstance(data, dict):
                value = next(
                    (
                        data[key]
                        for key in (
                            "mow_head",
                            "value",
                            "cutter_ctl_cutter_lift",
                            "cutter_height",
                        )
                        if key in data
                    ),
                    next(iter(data.values()), None),
                )
            if value is not None:
                converted = {"cutter_ctl_cutter_lift": int(value)}
        elif cmd == "volume_ctl":
            value = data
            if isinstance(data, dict):
                value = next(
                    (
                        data[key]
                        for key in ("volume", "volume_ctl", "value")
                        if key in data
                    ),
                    next(iter(data.values()), None),
                )
            if value is not None:
                converted = {"volume_ctl": int(value)}

        desired: dict[str, Any] = {"cmd": cmd}
        if converted is not None:
            desired["data"] = converted
        body = {"state": {"desired": desired}}
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        topic = f"$aws/things/{self.serial_number}/shadow/name/service/update"
        publisher = getattr(self, "_live_command_publisher", None)
        if publisher is None:
            await original_publish(self, cmd=cmd, data=converted)
            return
        await publisher(topic, payload)

    def publish_packet(topic: str, payload: bytes = b"{}") -> bytes:
        serial = _serial_from_topic(topic)
        if serial in _M_SERIES_SERIALS and topic.endswith("/service/get"):
            # Do not REST/MQTT GET the M-series service shadow. We intentionally
            # remain subscribed to service update/accepted/documents, because
            # live M9 status can arrive there unsolicited.
            topic = topic.replace("/service/get", "/property/get")
        return original_publish_packet(topic, payload)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotShadowApiClient.async_get_service_reported_state = service_state
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    mqtt_live._publish_packet = publish_packet
