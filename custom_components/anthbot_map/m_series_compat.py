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
from .api import AnthbotGenieApiError, AnthbotShadowApiClient
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .definition_refresh import map_archive_diagnostics, select_map_archive

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("ANTHBOT TEST: m_series_compat.py loaded")

_M_SERIES_SERIALS: set[str] = set()
_INSTALLED = False
_M_SERIES_MAP_PROBE_RETRY_SECONDS = 60.0
_M_SERIES_MAP_CANDIDATES = (
    "multi_maps.tar.gz",
    "map_manager.tar.gz",
)


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
    original_refresh_map = AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition

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

    async def refresh_map_definition(
        self,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        model = getattr(self.device, "model", None)
        if not _is_m_series(model):
            return await original_refresh_map(
                self,
                property_state,
                now,
                allow_periodic=allow_periodic,
            )

        last_probe = float(getattr(self, "_m_series_map_probe_last", 0.0) or 0.0)
        already_using_probe = str(getattr(self, "_map_definition_source", "")).startswith(
            "m_series_probe:"
        )
        should_probe = (
            not already_using_probe
            and (last_probe == 0.0 or now - last_probe >= _M_SERIES_MAP_PROBE_RETRY_SECONDS)
        )

        if should_probe:
            setattr(self, "_m_series_map_probe_last", now)
            errors: list[str] = []
            for filename in _M_SERIES_MAP_CANDIDATES:
                _LOGGER.warning(
                    "ANTHBOT M-SERIES MAP TEST: serial=%s model=%s probing filename=%s sub_category=multi_maps",
                    self.client.serial_number,
                    model,
                    filename,
                )
                try:
                    definition = await self.account_client.async_get_device_map_archive(
                        self.client.serial_number,
                        filename,
                    )
                except AnthbotGenieApiError as err:
                    error_text = str(err).replace("\n", " ")[:240]
                    errors.append(f"{filename}: {error_text}")
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES MAP TEST: serial=%s filename=%s failed: %s",
                        self.client.serial_number,
                        filename,
                        error_text,
                    )
                    continue

                self._map_definition = definition
                self._map_definition_source = f"m_series_probe:{filename}"
                self._map_definition_error = None
                self._last_map_download_monotonic = now
                diagnostics = map_archive_diagnostics(
                    property_state,
                    select_map_archive(property_state),
                )
                diagnostics.update(
                    {
                        "preferred_source": "m_series_archive_probe",
                        "active_source": self._map_definition_source,
                        "probe_file": filename,
                        "probe_candidates": list(_M_SERIES_MAP_CANDIDATES),
                    }
                )
                _LOGGER.warning(
                    "ANTHBOT M-SERIES MAP TEST: SUCCESS serial=%s model=%s filename=%s",
                    self.client.serial_number,
                    model,
                    filename,
                )
                return diagnostics, True

            if errors:
                self._map_definition_error = "M-series archive probe failed: " + " | ".join(errors)

        # Keep the existing v2 map logic as a fallback. This preserves current
        # Genie behavior and lets M-series devices that do expose map_<sn>.txt
        # or multi_maps.map_list continue to work.
        return await original_refresh_map(
            self,
            property_state,
            now,
            allow_periodic=allow_periodic,
        )

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition
    AnthbotShadowApiClient.async_get_service_reported_state = service_state
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    mqtt_live._publish_packet = publish_packet
