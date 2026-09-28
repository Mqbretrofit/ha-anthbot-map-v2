"""Genie/M5/M9 command transport corrections for verified settings writes.

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
from ..coordinator import AnthbotGenieDataUpdateCoordinator
from .genie_log_probe import install_genie_log_probe
from .m_series_log_probe import install_m_series_log_probe

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False

# Confirmed native command names from the official Android app protocol.  Dict
# payload commands (region/zone/param/volume/etc.) continue through the existing
# M-series compatibility wrapper unchanged.
_NATIVE_SIMPLE_COMMANDS = {
    "mow_start",
    "mow_pause",
    "mow_continue",
    "stop_all_tasks",
    "ridable_mow_start",
    "nest_mow_start",
    "nest_mow_stop",
    "mow_point",
    "mow_point_stop",
    "charge_start",
    "charge_pause",
    "charge_continue",
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


def _build_full_param_set(
    client: AnthbotShadowApiClient, changes: Any
) -> dict[str, Any]:
    """Merge a settings change into the mower's complete cached param_set."""
    if not isinstance(changes, dict) or not changes:
        raise AnthbotGenieApiError("param_set requires a non-empty dict payload")

    coordinator = getattr(client, "_settings_param_coordinator", None)
    reported = getattr(coordinator, "reported_state", None)
    current = reported.get("param_set") if isinstance(reported, dict) else None
    if not isinstance(current, dict) or not current:
        raise AnthbotGenieApiError(
            "Current param_set is not available in the live coordinator state; "
            "refusing partial update"
        )

    normalized_changes = dict(changes)
    if (
        "cutter_ctl_cutter_lift" in normalized_changes
        and "cutter_height" not in normalized_changes
    ):
        normalized_changes["cutter_height"] = normalized_changes.pop(
            "cutter_ctl_cutter_lift"
        )
    merged = dict(current)
    merged.update(normalized_changes)
    return merged


def install_m_series_control_support() -> None:
    """Install M-series-only native simple-command transport."""
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

    async def publish_service_command(
        self: AnthbotShadowApiClient,
        *,
        cmd: str,
        data: Any = None,
    ) -> None:
        is_m_series = _is_m_series_client(self)
        is_genie = _is_genie_client(self)

        if cmd == "param_set" and (is_m_series or is_genie):
            await _publish_native_simple_command(
                self,
                cmd=cmd,
                data=_build_full_param_set(self, data),
            )
            return

        # M9/M9 Pro exposes the independent camera toggle and sensitivity in
        # device_config. Keep the entity API stable and translate only here.
        if cmd == "perception_obstacle_ctl" and _is_m9_client(self):
            if not isinstance(data, dict):
                raise AnthbotGenieApiError(
                    "M9 visual obstacle command requires a dict payload"
                )
            if "switch" in data:
                switch = data.get("switch")
                if switch not in (0, 1, False, True):
                    raise AnthbotGenieApiError("M9 pobctl_switch must be 0 or 1")
                await _publish_native_simple_command(
                    self,
                    cmd="device_config",
                    data={"pobctl_switch": int(bool(switch))},
                )
                return
            level = data.get("level")
            if level not in (0, 1, 2):
                raise AnthbotGenieApiError("M9 pobctl_level must be 0, 1 or 2")
            await _publish_native_simple_command(
                self,
                cmd="device_config",
                data={"pobctl_level": int(level)},
            )
            return

        if not _is_m_series_client(self):
            await previous_publish(self, cmd=cmd, data=data)
            return

        if cmd not in _NATIVE_SIMPLE_COMMANDS:
            await previous_publish(self, cmd=cmd, data=data)
            return

        # M9 Pro STOP capture from the official app confirms the exact payload
        # uses scalar data=1 for stop_all_tasks.  Force that value only for the
        # M-series transport so Genie and every other command remain untouched.
        if cmd == "stop_all_tasks":
            data = 1

        await _publish_native_simple_command(self, cmd=cmd, data=data)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    install_m_series_log_probe()
    install_genie_log_probe()
