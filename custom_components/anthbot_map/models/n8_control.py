"""ANTHBOT N8 command transport.

The N8 uses the same AWS named service shadow but has its own app command
surface. Keep this layer isolated from Genie and the M5/M9/M9 Pro wrappers so
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

# Commands confirmed in the ANTHBOT 2.15.16 N8/MGS app protocol. Dict-payload
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
    "ctl_near_chg_mow",
    "mow_delay",
    "clean_mode_cmd",
    "ctl_cutter",
    "mow_point",
    "mow_point_stop",
    "mow_regular",
    "start_dump",
    "stop_dump",
    "area_set",
    "ridable_area_set",
    "ctl_building_dump",
    "multi_map_ctl",
    "delete_sub_map",
    "device_config",
    # The current 2.15.16 MGS voice flow publishes voice_set through the same
    # service-shadow transport. The exact package payload is documented in
    # N8_VOICE_PROTOCOL.md. Transport recognition only: no public HA voice-pack
    # selector is exposed until a real N8 validates package compatibility and
    # report-side state transitions.
    "voice_set",
    # Current MGS RTK/NRTK service-shadow commands. Static 2.15.16 analysis
    # proves ctl_rtk_base takes scalar 1=NRTK, 2=RTK, 3=Auto, while the info
    # request takes an empty object. They are transport-recognized only; no new
    # public Home Assistant RTK writer is exposed from this evidence alone.
    "ctl_rtk_base",
    "req_rtk_base_info",
    # Older/shared integration entry points retained here so the N8 adapter can
    # translate them to the current 2.15.16 MGS command surface.
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


def _binary_flag(value: Any) -> Any:
    """Preserve valid 0/1 app values without coercing unknown input."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1):
        return value
    return value


def _normalize_n8_command(cmd: str, data: Any) -> tuple[str, Any]:
    """Translate shared controls to the current N8/MGS app command shape.

    Static analysis of ANTHBOT 2.15.16 shows that current MGS settings use a
    mixture of the generic ``device_config`` writer and dedicated commands.
    Callers can keep their established shared API while this N8-only adapter
    emits the current app-native payload.
    """
    if cmd == "anti_loss_switch":
        return "device_config", {"anti_loss_switch": _binary_flag(data)}

    if cmd == "anti_loss_radius":
        value = data
        if isinstance(data, dict):
            if "anti_loss_radius" in data:
                value = data["anti_loss_radius"]
            elif set(data) == {"data"}:
                value = data["data"]
        return "device_config", {"anti_loss_radius": value}

    if cmd == "ctl_rainer" and isinstance(data, dict):
        normalized: dict[str, Any] = {}
        if "rain_switch" in data:
            normalized["rain_switch"] = _binary_flag(data["rain_switch"])
        elif "switch" in data:
            normalized["rain_switch"] = _binary_flag(data["switch"])

        if "rain_continue_time" in data:
            normalized["rain_continue_time"] = data["rain_continue_time"]
        elif "continue_time" in data:
            normalized["rain_continue_time"] = data["continue_time"]

        if normalized:
            return "device_config", normalized
        return cmd, data

    if cmd == "perception_obstacle_ctl" and isinstance(data, dict):
        normalized = {}
        if "pobctl_switch" in data:
            normalized["pobctl_switch"] = _binary_flag(data["pobctl_switch"])
        elif "switch" in data:
            normalized["pobctl_switch"] = _binary_flag(data["switch"])

        if "pobctl_level" in data:
            normalized["pobctl_level"] = data["pobctl_level"]
        elif "level" in data:
            normalized["pobctl_level"] = data["level"]

        if normalized:
            return "device_config", normalized
        return cmd, data

    # The existing shared HA number uses param_set for global cutting height.
    # Current MGS 2.15.16 instead sends the selected 30..70 mm scalar through
    # ctl_cutter. Translate only the one-field global height payload; other
    # param_set settings (work mode, mowing passes, heading, etc.) stay intact.
    if cmd == "param_set" and isinstance(data, dict) and set(data) == {"cutter_height"}:
        return "ctl_cutter", data["cutter_height"]

    return cmd, data


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

        cmd, data = _normalize_n8_command(cmd, data)
        await _publish_n8_command(self, cmd=cmd, data=data)

    AnthbotShadowApiClient.async_publish_service_command = publish_service_command


__all__ = ["install_n8_control_support", "is_n8_model"]
