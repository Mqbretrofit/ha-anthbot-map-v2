"""ANTHBOT N8 command transport.

The N8 uses the same AWS named service shadow but has its own app command
surface.  Keep this layer isolated from Genie and the M5/M9/M9 Pro wrappers so
existing mower families retain their proven routing.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

from ..api import AnthbotGenieApiError, AnthbotShadowApiClient

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False

# Commands confirmed in the ANTHBOT 2.15.16 N8 app protocol.  Dict-payload
# commands are listed too because N8 must keep their app-native data object
# unchanged instead of passing through legacy Genie payload reshaping.
_N8_COMMANDS = {
    "mow_start",
    "mow_pause",
    "mow_continue",
    "stop_all_tasks",
    "charge_start",
    "charge_pause",
    "charge_continue",
    "custom_area_mow_start",
    "custom_area_mow_stop",
    "region_mow_start",
    "region_mow_stop",
    "ridable_mow_start",
    "nest_mow_start",
    "nest_mow_stop",
    "mow_point",
    "mow_point_stop",
    "start_dump",
    "stop_dump",
    "area_set",
    "ridable_area_set",
    "ctl_building_dump",
    "multi_map_ctl",
    "delete_sub_map",
    "anti_loss_switch",
    "anti_loss_radius",
    "maintenance_switch",
    "maintenance_check",
    "maintenance_ctrl",
    "robot_maintenance_reset",
    "ctl_rainer",
    "perception_obstacle_ctl",
    "param_set",
    "volume_ctl",
}


def is_n8_model(model: object) -> bool:
    """Return whether *model* identifies the N8 family."""
    value = str(model or "").upper().replace("-", " ").replace("_", " ")
    return "N8" in " ".join(value.split())


def _is_n8_client(client: AnthbotShadowApiClient) -> bool:
    return is_n8_model(getattr(client, "_device_model", ""))


async def _publish_n8_command(
    client: AnthbotShadowApiClient,
    *,
    cmd: str,
    data: Any,
) -> None:
    """Publish the exact app-style N8 service-shadow payload."""
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
                    "ANTHBOT N8 command accepted: sn=%s cmd=%s data=%r",
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
            except Exception:  # noqa: BLE001 - preserve existing fallback behavior.
                pass
        break

    publisher = getattr(client, "_live_command_publisher", None)
    if publisher is not None:
        await publisher(topic, payload)
        _LOGGER.debug(
            "ANTHBOT N8 command published over live MQTT: sn=%s cmd=%s data=%r",
            client.serial_number,
            cmd,
            data,
        )
        return

    raise AnthbotGenieApiError(
        f"N8 command '{cmd}' failed ({last_status}); "
        f"errortype={last_headers.get('x-amzn-errortype', '')}; "
        f"body={last_body[:240]}"
    )


def install_n8_control_support() -> None:
    """Install N8-only service-shadow routing."""
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
        if not _is_n8_client(self) or cmd not in _N8_COMMANDS:
            await previous_publish(self, cmd=cmd, data=data)
            return

        # The app sends scalar 1 for these one-shot N8 commands.
        if cmd in {"mow_start", "stop_all_tasks", "charge_start", "start_dump", "stop_dump"} and data is None:
            data = 1

        await _publish_n8_command(self, cmd=cmd, data=data)

    AnthbotShadowApiClient.async_publish_service_command = publish_service_command


__all__ = ["install_n8_control_support", "is_n8_model"]
