"""M5/M9 command transport corrections.

The clean rebuild keeps Genie on the proven beta3 command path. M-series
mowers use the same AWS service shadow, but their simple app commands must keep
the scalar/null ``data`` value instead of being rewritten to ``{cmd: value}``.
This layer is installed after the legacy M-series compatibility wrapper and only
intercepts those native simple commands plus M-series ``param_set`` writes.
"""

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
}


def _is_m_series_client(client: AnthbotShadowApiClient) -> bool:
    model = str(getattr(client, "_device_model", "") or "").upper()
    return "M5" in model or "M9" in model


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
    for refresh_attempt in range(2):
        for request_uri, include_sdk_headers, canonical_uri_override, sign_content_length in attempts:
            status, body_text, response_payload, response_headers = await client._async_signed_post(
                request_uri=request_uri, canonical_query="", payload_bytes=payload,
                include_sdk_headers=include_sdk_headers,
                canonical_uri_override=canonical_uri_override,
                sign_content_length=sign_content_length,
            )
            last_status, last_body, last_headers = status, body_text, response_headers
            if status == 200 and isinstance(response_payload, dict):
                return
            if status != 403:
                break
        if last_status == 403 and refresh_attempt == 0:
            try:
                await client._async_get_credentials(force_refresh=True)
                continue
            except Exception:
                pass
        break
    publisher = getattr(client, "_live_command_publisher", None)
    if publisher is not None:
        await publisher(topic, payload)
        return
    raise AnthbotGenieApiError(
        f"M-series command '{cmd}' failed ({last_status}); "
        f"errortype={last_headers.get('x-amzn-errortype', '')}; body={last_body[:240]}"
    )


def _build_full_param_set(client: AnthbotShadowApiClient, changes: Any) -> dict[str, Any]:
    """Merge a setting into the already cached live M-series param_set."""
    if not isinstance(changes, dict) or not changes:
        raise AnthbotGenieApiError("M-series param_set requires a non-empty dict payload")

    coordinator = getattr(client, "_m_series_coordinator", None)
    reported = getattr(coordinator, "reported_state", None)
    current = reported.get("param_set") if isinstance(reported, dict) else None
    if not isinstance(current, dict) or not current:
        raise AnthbotGenieApiError(
            "Current M-series param_set is not available in the live coordinator state; refusing partial update"
        )

    merged = dict(current)
    normalized_changes = dict(changes)
    if "cutter_ctl_cutter_lift" in normalized_changes and "cutter_height" not in normalized_changes:
        normalized_changes["cutter_height"] = normalized_changes.pop("cutter_ctl_cutter_lift")
    merged.update(normalized_changes)
    _LOGGER.debug(
        "ANTHBOT M-SERIES cached full param_set update: sn=%s changed=%s fields=%s",
        client.serial_number, sorted(normalized_changes), sorted(merged),
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
        if _is_m_series_client(self.client):
            setattr(self.client, "_m_series_coordinator", self)

    async def publish_service_command(self: AnthbotShadowApiClient, *, cmd: str, data: Any = None) -> None:
        if not _is_m_series_client(self):
            await previous_publish(self, cmd=cmd, data=data)
            return
        if cmd == "param_set":
            full_param_set = _build_full_param_set(self, data)
            await _publish_native_simple_command(self, cmd=cmd, data=full_param_set)
            return
        if cmd not in _NATIVE_SIMPLE_COMMANDS:
            await previous_publish(self, cmd=cmd, data=data)
            return
        if cmd == "stop_all_tasks":
            data = 1
        await _publish_native_simple_command(self, cmd=cmd, data=data)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    install_m_series_log_probe()
    install_genie_log_probe()
