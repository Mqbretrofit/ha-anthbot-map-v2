"""Compatibility helpers for ANTHBOT M5/M9 cloud/shadow behavior.

The M-series exposes its readable state through the property named shadow while
commands are still written to the service named shadow.  Keep this isolated so
existing Genie behavior remains unchanged.
"""

from __future__ import annotations

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
    original_subscribe_packet = mqtt_live._subscribe_packet
    original_publish_packet = mqtt_live._publish_packet

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        original_coordinator_init(self, *args, **kwargs)
        model = getattr(self.device, "model", None)
        is_m_series = _is_m_series(model)
        setattr(self.client, "_device_model", model)
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
            # M5/M9 readable state lives in the property shadow.  Trying to
            # read the service named shadow can be rejected by the IoT policy.
            return await self._async_get_named_shadow_reported_state("property")
        return await original_service_state(self)

    async def publish_service_command(self, *, cmd: str, data: Any = None) -> None:
        if not _is_m_series(getattr(self, "_device_model", None)):
            await original_publish(self, cmd=cmd, data=data)
            return

        # Reverse-engineered M5/M9 payload used by the working legacy
        # integration: service shadow stays writable, but selected settings use
        # the M-series property names inside the legacy cmd/data envelope.
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

        import json

        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        topic = f"$aws/things/{self.serial_number}/shadow/name/service/update"
        publisher = getattr(self, "_live_command_publisher", None)
        if publisher is None:
            # Preserve the integration's normal error/retry behavior.
            await original_publish(self, cmd=cmd, data=converted)
            return
        await publisher(topic, payload)

    def subscribe_packet(packet_id: int, topics: list[str]) -> bytes:
        filtered: list[str] = []
        for topic in topics:
            serial = _serial_from_topic(topic)
            if serial in _M_SERIES_SERIALS and "/service/" in topic:
                continue
            filtered.append(topic)
        return original_subscribe_packet(packet_id, filtered)

    def publish_packet(topic: str, payload: bytes = b"{}") -> bytes:
        serial = _serial_from_topic(topic)
        if serial in _M_SERIES_SERIALS and topic.endswith("/service/get"):
            topic = topic.replace("/service/get", "/property/get")
        return original_publish_packet(topic, payload)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotShadowApiClient.async_get_service_reported_state = service_state
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    mqtt_live._subscribe_packet = subscribe_packet
    mqtt_live._publish_packet = publish_packet
