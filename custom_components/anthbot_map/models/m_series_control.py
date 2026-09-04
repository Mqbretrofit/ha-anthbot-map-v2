"""M5/M9 command transport corrections.

The clean rebuild keeps Genie on the proven beta3 command path.  M-series
mowers use the same AWS service shadow, but their simple app commands must keep
the scalar/null ``data`` value instead of being rewritten to ``{cmd: value}``.
This layer is installed after the legacy M-series compatibility wrapper and only
intercepts those native simple commands.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

from ..api import AnthbotGenieApiError, AnthbotShadowApiClient

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False

# Confirmed native command names from the official Android app protocol.  Dict
# payload commands (region/zone/param/volume/etc.) continue through the existing
# M-series compatibility wrapper unchanged.
_NATIVE_SIMPLE_COMMANDS = {
    "mow_start",
    "mow_pause",
    "mow_continue",
    "mow_stop",
    "ridable_mow_start",
    "nest_mow_start",
    "nest_mow_stop",
    "mow_point",
    "mow_point_stop",
    "charge_start",
    "charge_pause",
    "charge_continue",
}

# Genie uses stop_all_tasks.  The M-series app protocol exposes mow_stop instead.
_COMMAND_ALIASES = {
    "stop_all_tasks": "mow_stop",
}


def _is_m_series_client(client: AnthbotShadowApiClient) -> bool:
    model = str(getattr(client, "_device_model", "") or "").upper()
    return "M5" in model or "M9" in model


async def _publish_native_simple_command(
    client: AnthbotShadowApiClient,
    *,
    cmd: str,
    data: Any,
) -> None:
    """Publish an app-style M-series command without legacy data reshaping."""
    body = {"state": {"desired": {"cmd": cmd, "data": data}}}
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    topic = f"$aws/things/{client.serial_number}/shadow/name/service/update"
    encoded = "/topics/" + quote(topic, safe="-_.~")
    raw = f"/topics/{topic}"

    attempts = (
        (encoded, True, None, True),
        (encoded, True, encoded, True),
        (encoded, True, None, False),
        (encoded, False, None, True),
        (raw, True, None, True),
        (raw, True, raw, True),
        (raw, False, None, True),
    )

    last_status = 0
    last_body = ""
    last_headers: dict[str, str] = {}

    for refresh_attempt in range(2):
        for request_uri, include_sdk_headers, canonical_uri_override, sign_content_length in attempts:
            status, body_text, response_payload, response_headers = await client._async_signed_post(
                request_uri=request_uri,
                canonical_query="",
                payload_bytes=payload,
                include_sdk_headers=include_sdk_headers,
                canonical_uri_override=canonical_uri_override,
                sign_content_length=sign_content_length,
            )
            last_status = status
            last_body = body_text
            last_headers = response_headers
            if status == 200 and isinstance(response_payload, dict):
                _LOGGER.debug(
                    "ANTHBOT M-SERIES native command accepted: sn=%s cmd=%s data=%r",
                    client.serial_number,
                    cmd,
                    data,
                )
                return
            if status != 403:
                break

        if last_status == 403 and refresh_attempt == 0:
            try:
                await client._async_get_credentials(force_refresh=True)
                continue
            except Exception:  # noqa: BLE001 - preserve legacy fallback behavior.
                pass
        break

    publisher = getattr(client, "_live_command_publisher", None)
    if publisher is not None:
        await publisher(topic, payload)
        _LOGGER.debug(
            "ANTHBOT M-SERIES native command published over live MQTT: sn=%s cmd=%s data=%r",
            client.serial_number,
            cmd,
            data,
        )
        return

    raise AnthbotGenieApiError(
        f"M-series command '{cmd}' failed ({last_status}); "
        f"errortype={last_headers.get('x-amzn-errortype', '')}; "
        f"body={last_body[:240]}"
    )


def install_m_series_control_support() -> None:
    """Install M-series-only native simple-command transport."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_publish = AnthbotShadowApiClient.async_publish_service_command

    async def publish_service_command(
        self: AnthbotShadowApiClient,
        *,
        cmd: str,
        data: Any = None,
    ) -> None:
        if not _is_m_series_client(self):
            await previous_publish(self, cmd=cmd, data=data)
            return

        native_cmd = _COMMAND_ALIASES.get(cmd, cmd)
        if native_cmd not in _NATIVE_SIMPLE_COMMANDS:
            await previous_publish(self, cmd=cmd, data=data)
            return

        await _publish_native_simple_command(self, cmd=native_cmd, data=data)

    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
