"""Genie/M5/M9 command transport corrections for verified settings writes."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

from ..api import AnthbotGenieApiError, AnthbotShadowApiClient
from ..coordinator import AnthbotGenieDataUpdateCoordinator
from .genie_log_probe import install_genie_log_probe
from .m_series_log_probe import install_m_series_log_probe

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False

_NATIVE_SIMPLE_COMMANDS = {
    "mow_start", "mow_pause", "mow_continue", "stop_all_tasks",
    "ridable_mow_start", "nest_mow_start", "nest_mow_stop", "mow_point",
    "mow_point_stop", "charge_start", "charge_pause", "charge_continue",
    "perception_obstacle_ctl", "device_config",
}


def _model(client: AnthbotShadowApiClient) -> str:
    return str(getattr(client, "_device_model", "") or "").upper()


def _is_m_series_client(client: AnthbotShadowApiClient) -> bool:
    model = _model(client)
    return "M5" in model or "M9" in model


def _is_m9_client(client: AnthbotShadowApiClient) -> bool:
    return "M9" in _model(client)


def _is_genie_client(client: AnthbotShadowApiClient) -> bool:
    return "GENIE" in _model(client)


def _safe_data(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(k): _safe_data(v) for k, v in data.items()}
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    return f"<{type(data).__name__}>"


async def _publish_native_simple_command(client: AnthbotShadowApiClient, *, cmd: str, data: Any) -> None:
    body = {"state": {"desired": {"cmd": cmd, "data": data}}}
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    topic = f"$aws/things/{client.serial_number}/shadow/name/service/update"
    encoded = "/topics/" + quote(topic, safe="-_.~")
    raw = f"/topics/{topic}"
    attempts = (
        (encoded, True, None, True), (encoded, True, encoded, True),
        (encoded, True, None, False), (encoded, False, None, True),
        (raw, True, None, True), (raw, True, raw, True), (raw, False, None, True),
    )
    last_status = 0
    last_body = ""
    last_headers: dict[str, str] = {}
    _LOGGER.warning(
        "ANTHBOT COMMAND PROBE stage=transport_start sn=%s model=%s cmd=%s data=%s",
        client.serial_number, _model(client), cmd, _safe_data(data),
    )
    for refresh_attempt in range(2):
        for attempt_no, (request_uri, include_sdk_headers, canonical_uri_override, sign_content_length) in enumerate(attempts, 1):
            status, body_text, response_payload, response_headers = await client._async_signed_post(
                request_uri=request_uri, canonical_query="", payload_bytes=payload,
                include_sdk_headers=include_sdk_headers,
                canonical_uri_override=canonical_uri_override,
                sign_content_length=sign_content_length,
            )
            last_status, last_body, last_headers = status, body_text, response_headers
            _LOGGER.warning(
                "ANTHBOT COMMAND PROBE stage=http_result sn=%s model=%s cmd=%s refresh=%s attempt=%s status=%s response_dict=%s",
                client.serial_number, _model(client), cmd, refresh_attempt, attempt_no,
                status, isinstance(response_payload, dict),
            )
            if status == 200 and isinstance(response_payload, dict):
                _LOGGER.warning(
                    "ANTHBOT COMMAND PROBE stage=accepted sn=%s model=%s cmd=%s transport=http",
                    client.serial_number, _model(client), cmd,
                )
                return
            if status != 403:
                break
        if last_status == 403 and refresh_attempt == 0:
            try:
                await client._async_get_credentials(force_refresh=True)
                _LOGGER.warning(
                    "ANTHBOT COMMAND PROBE stage=credential_refresh sn=%s model=%s cmd=%s result=ok",
                    client.serial_number, _model(client), cmd,
                )
                continue
            except Exception as err:
                _LOGGER.warning(
                    "ANTHBOT COMMAND PROBE stage=credential_refresh sn=%s model=%s cmd=%s result=failed error=%s",
                    client.serial_number, _model(client), cmd, type(err).__name__,
                )
        break
    publisher = getattr(client, "_live_command_publisher", None)
    if publisher is not None:
        try:
            await publisher(topic, payload)
        except Exception as err:
            _LOGGER.warning(
                "ANTHBOT COMMAND PROBE stage=live_result sn=%s model=%s cmd=%s result=failed error=%s",
                client.serial_number, _model(client), cmd, type(err).__name__,
            )
            raise
        _LOGGER.warning(
            "ANTHBOT COMMAND PROBE stage=accepted sn=%s model=%s cmd=%s transport=live_mqtt",
            client.serial_number, _model(client), cmd,
        )
        return
    _LOGGER.warning(
        "ANTHBOT COMMAND PROBE stage=failed sn=%s model=%s cmd=%s status=%s errortype=%s",
        client.serial_number, _model(client), cmd, last_status,
        last_headers.get("x-amzn-errortype", ""),
    )
    raise AnthbotGenieApiError(
        f"Command '{cmd}' failed ({last_status}); "
        f"errortype={last_headers.get('x-amzn-errortype', '')}; body={last_body[:240]}"
    )


def _build_full_param_set(client: AnthbotShadowApiClient, changes: Any) -> dict[str, Any]:
    if not isinstance(changes, dict) or not changes:
        raise AnthbotGenieApiError("param_set requires a non-empty dict payload")

    coordinator = getattr(client, "_settings_param_coordinator", None)
    reported = getattr(coordinator, "reported_state", None)
    current = reported.get("param_set") if isinstance(reported, dict) else None
    if not isinstance(current, dict) or not current:
        _LOGGER.warning(
            "ANTHBOT COMMAND PROBE stage=build_failed sn=%s model=%s cmd=param_set requested=%s reason=no_cached_param_set",
            client.serial_number, _model(client), _safe_data(changes),
        )
        raise AnthbotGenieApiError(
            "Current param_set is not available in the live coordinator state; refusing partial update"
        )

    merged = dict(current)
    normalized_changes = dict(changes)
    if "cutter_ctl_cutter_lift" in normalized_changes and "cutter_height" not in normalized_changes:
        normalized_changes["cutter_height"] = normalized_changes.pop("cutter_ctl_cutter_lift")
    merged.update(normalized_changes)
    _LOGGER.warning(
        "ANTHBOT COMMAND PROBE stage=build sn=%s model=%s cmd=param_set requested=%s full_param_set=%s",
        client.serial_number, _model(client), _safe_data(normalized_changes), _safe_data(merged),
    )
    return merged


def install_m_series_control_support() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_publish = AnthbotShadowApiClient.async_publish_service_command
    previous_coordinator_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        previous_coordinator_init(self, *args, **kwargs)
        if _is_m_series_client(self.client) or _is_genie_client(self.client):
            setattr(self.client, "_settings_param_coordinator", self)

    async def publish_service_command(self: AnthbotShadowApiClient, *, cmd: str, data: Any = None) -> None:
        is_m_series = _is_m_series_client(self)
        is_genie = _is_genie_client(self)
        _LOGGER.warning(
            "ANTHBOT COMMAND PROBE stage=request sn=%s model=%s cmd=%s requested=%s route_m_series=%s route_genie=%s",
            self.serial_number, _model(self), cmd, _safe_data(data), is_m_series, is_genie,
        )

        if cmd == "param_set" and (is_m_series or is_genie):
            full_param_set = _build_full_param_set(self, data)
            await _publish_native_simple_command(self, cmd=cmd, data=full_param_set)
            return

        # Verified from the official app's live M9 Pro service/property shadows:
        # device_config.pobctl_switch is the independent on/off control, while
        # device_config.pobctl_level is sensitivity (0/1/2). Preserve the
        # existing entity API and translate only M9/M9 Pro commands.
        if cmd == "perception_obstacle_ctl" and _is_m9_client(self):
            if not isinstance(data, dict):
                raise AnthbotGenieApiError("M9 visual obstacle command requires a dict payload")
            if "switch" in data:
                switch = data.get("switch")
                if switch not in (0, 1, False, True):
                    raise AnthbotGenieApiError("M9 pobctl_switch must be 0 or 1")
                _LOGGER.warning(
                    "ANTHBOT COMMAND PROBE stage=translate sn=%s model=%s from_cmd=%s to_cmd=device_config pobctl_switch=%s",
                    self.serial_number, _model(self), cmd, int(bool(switch)),
                )
                await _publish_native_simple_command(
                    self, cmd="device_config", data={"pobctl_switch": int(bool(switch))}
                )
                return
            level = data.get("level")
            if level not in (0, 1, 2):
                raise AnthbotGenieApiError("M9 pobctl_level must be 0, 1 or 2")
            _LOGGER.warning(
                "ANTHBOT COMMAND PROBE stage=translate sn=%s model=%s from_cmd=%s to_cmd=device_config pobctl_level=%s",
                self.serial_number, _model(self), cmd, level,
            )
            await _publish_native_simple_command(
                self, cmd="device_config", data={"pobctl_level": int(level)}
            )
            return

        if not is_m_series:
            _LOGGER.warning(
                "ANTHBOT COMMAND PROBE stage=delegate sn=%s model=%s cmd=%s route=legacy",
                self.serial_number, _model(self), cmd,
            )
            await previous_publish(self, cmd=cmd, data=data)
            return
        if cmd not in _NATIVE_SIMPLE_COMMANDS:
            _LOGGER.warning(
                "ANTHBOT COMMAND PROBE stage=delegate sn=%s model=%s cmd=%s route=existing_non_simple",
                self.serial_number, _model(self), cmd,
            )
            await previous_publish(self, cmd=cmd, data=data)
            return
        if cmd == "stop_all_tasks":
            data = 1
        await _publish_native_simple_command(self, cmd=cmd, data=data)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    install_m_series_log_probe()
    install_genie_log_probe()
