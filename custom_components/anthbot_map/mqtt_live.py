"""Minimal AWS IoT MQTT-over-WebSocket shadow listener."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import re
import struct
from typing import Any

from aiohttp import (
    ClientError,
    ClientResponseError,
    ClientSession,
    ClientWebSocketResponse,
    WSMsgType,
)
from yarl import URL

from .api import AnthbotGenieApiError, AnthbotShadowApiClient

_LOGGER = logging.getLogger(__name__)

_RECONNECT_INITIAL_SECONDS = 5
_RECONNECT_MAX_SECONDS = 30


def _safe_error(error: Exception) -> str:
    """Return an MQTT error without leaking the presigned AWS query string."""
    value = f"{type(error).__name__}: {error}"
    return re.sub(
        r"(wss://[^?\s']+)\?[^\s']+",
        r"\1?<redacted>",
        value,
    )

ShadowCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
ConnectionCallback = Callable[[bool, str | None], Awaitable[None]]


def _mqtt_length(value: int) -> bytes:
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        encoded.append(digit)
        if not value:
            return bytes(encoded)


def _mqtt_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("!H", len(raw)) + raw


def _packet(packet_type: int, payload: bytes) -> bytes:
    return bytes((packet_type,)) + _mqtt_length(len(payload)) + payload


def _connect_packet(client_id: str, keepalive: int) -> bytes:
    variable = _mqtt_string("MQTT") + bytes((4, 2)) + struct.pack("!H", keepalive)
    return _packet(0x10, variable + _mqtt_string(client_id))


def _subscribe_packet(packet_id: int, topics: list[str]) -> bytes:
    payload = struct.pack("!H", packet_id)
    payload += b"".join(_mqtt_string(topic) + b"\x00" for topic in topics)
    return _packet(0x82, payload)


def _publish_packet(topic: str, payload: bytes = b"{}") -> bytes:
    return _packet(0x30, _mqtt_string(topic) + payload)


def _decode_publish(packet: bytes) -> tuple[str, bytes] | None:
    if not packet or packet[0] >> 4 != 3:
        return None
    index = 1
    multiplier = 1
    remaining = 0
    while index < len(packet):
        digit = packet[index]
        index += 1
        remaining += (digit & 0x7F) * multiplier
        if not digit & 0x80:
            break
        multiplier *= 128
    if index + 2 > len(packet):
        return None
    topic_length = struct.unpack("!H", packet[index : index + 2])[0]
    index += 2
    if index + topic_length > len(packet):
        return None
    topic = packet[index : index + topic_length].decode("utf-8", errors="replace")
    index += topic_length
    qos = (packet[0] >> 1) & 0x03
    if qos:
        index += 2
    return topic, packet[index:]


def _reported_state(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract reported state from shadow get/update payload variants."""
    current = payload.get("current")
    if isinstance(current, dict):
        payload = current
    state = payload.get("state")
    if not isinstance(state, dict):
        return None
    reported = state.get("reported")
    return reported if isinstance(reported, dict) else None


class AnthbotLiveShadowListener:
    """Maintain a live subscription to property and service shadows."""

    def __init__(
        self,
        *,
        session: ClientSession,
        client: AnthbotShadowApiClient,
        on_shadow: ShadowCallback,
        on_connection: ConnectionCallback,
    ) -> None:
        self._session = session
        self._client = client
        self._on_shadow = on_shadow
        self._on_connection = on_connection
        self._stop = asyncio.Event()
        self._consecutive_failures = 0
        # A rejected WebSocket upgrade may be caused by stale STS
        # credentials.  Recovery is deliberately bounded per outage: first
        # refresh STS, then re-authenticate the Anthbot account and refresh
        # STS once.  Repeating those two operations forever only churns
        # credentials while AWS IoT is returning a transient 403/404.
        self._credential_recovery_stage = 0
        self._force_credential_refresh = False
        self._force_account_reauthentication = False
        self._last_recovery_action = "initial"
        self._active_ws: ClientWebSocketResponse | None = None
        self._send_lock = asyncio.Lock()

    async def async_stop(self) -> None:
        """Stop reconnecting and close the current WebSocket via cancellation."""
        self._stop.set()
        self._client.set_live_command_publisher(None)

    async def async_publish_command(self, topic: str, payload: bytes) -> None:
        """Publish a service-shadow command over the active MQTT socket."""
        async with self._send_lock:
            ws = self._active_ws
            if ws is None or ws.closed:
                raise RuntimeError("Anthbot live MQTT socket is not connected")
            try:
                await ws.send_bytes(_packet(0x30, _mqtt_string(topic) + payload))
            except (ClientError, OSError, RuntimeError):
                # Do not leave a failed socket registered as the primary
                # command transport.  The caller can immediately use the
                # signed HTTP Publish fallback, while closing the socket wakes
                # the receive loop and starts the persistent reconnect cycle.
                self._client.set_live_command_publisher(None)
                await ws.close()
                raise

    async def async_run(self) -> None:
        """Connect until stopped, using bounded reconnect backoff."""
        delay = _RECONNECT_INITIAL_SECONDS
        while not self._stop.is_set():
            try:
                await self._async_connected_session()
                delay = _RECONNECT_INITIAL_SECONDS
            except asyncio.CancelledError:
                raise
            except (
                AnthbotGenieApiError,
                ClientError,
                TimeoutError,
                OSError,
                ValueError,
            ) as err:
                self._client.set_live_command_publisher(None)
                # If this attempt had reached an accepted MQTT CONNECT, start
                # a fresh short reconnect sequence after the later socket
                # close instead of retaining the previous outage's delay.
                if self._consecutive_failures == 0:
                    delay = _RECONNECT_INITIAL_SECONDS
                error = (
                    f"{_safe_error(err)}; recovery={self._last_recovery_action}; "
                    f"{self._client.iot_credential_diagnostics}"
                )
                self._consecutive_failures += 1
                # A rejected WebSocket upgrade can leave otherwise unexpired
                # STS credentials cached.  Retrying freshly signed URLs with
                # the same rejected credentials only repeats the failure, so
                # force one new STS credential request on the next attempt.
                self._schedule_credential_recovery(err)
                # Brief AWS IoT reconnect races can return a single 404/403
                # and then recover on the next freshly signed URL.  Do not
                # create a visible Home Assistant warning for a self-healing
                # one-off failure; warn only when the fallback persists.
                log = (
                    _LOGGER.warning
                    if self._consecutive_failures == 3
                    else _LOGGER.debug
                )
                log(
                    "Anthbot live shadow unavailable for %s "
                    "(attempt %d); using HTTP fallback: %s",
                    self._client.serial_number,
                    self._consecutive_failures,
                    error,
                )
                await self._on_connection(False, error)
            else:
                self._client.set_live_command_publisher(None)
                await self._on_connection(False, "MQTT connection closed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except TimeoutError:
                # The live shadow drives both fast position updates and
                # commands.  A five-minute backoff made a transient AWS IoT
                # 404 look permanent.  Keep retry traffic bounded, but never
                # leave recovery more than 30 seconds away.
                delay = min(delay * 2, _RECONNECT_MAX_SECONDS)

    def _schedule_credential_recovery(self, err: Exception) -> None:
        """Schedule at most two credential recovery steps per MQTT outage."""
        # AWS IoT has returned both 403 and 404 for expired/rejected
        # presigned WebSocket sessions.  Treat both as authentication
        # recovery signals; otherwise a 404 retries the same cached STS
        # credentials forever and the integration remains on HTTP fallback.
        if not isinstance(err, ClientResponseError) or err.status not in (403, 404):
            return
        if self._credential_recovery_stage == 0:
            self._force_credential_refresh = True
            self._credential_recovery_stage = 1
            return
        if self._credential_recovery_stage == 1:
            self._force_credential_refresh = True
            self._force_account_reauthentication = True
            self._credential_recovery_stage = 2

    async def _async_connected_session(self) -> None:
        # SigV4 covers the exact percent-encoded query string.  aiohttp/yarl
        # normally canonicalizes URLs before sending them, which can turn
        # signed values such as ``%2F`` back into ``/`` and make AWS reject the
        # WebSocket upgrade with HTTP 403.  Mark the presigned URL as already
        # encoded so its raw query is sent byte-for-byte unchanged.
        if self._force_account_reauthentication:
            recovery_action = "account_reauthentication_and_sts_refresh"
        elif self._force_credential_refresh:
            recovery_action = "sts_refresh"
        elif self._credential_recovery_stage >= 2:
            recovery_action = "cached_credentials_after_bounded_recovery"
        else:
            recovery_action = "initial_or_cached_credentials"
        self._last_recovery_action = recovery_action
        url = URL(
            await self._client.async_get_mqtt_websocket_url(
                force_refresh=self._force_credential_refresh,
                reauthenticate=self._force_account_reauthentication,
            ),
            encoded=True,
        )
        self._force_credential_refresh = False
        self._force_account_reauthentication = False
        serial = self._client.serial_number
        base = f"$aws/things/{serial}/shadow/name"
        response_topics = [
            f"{base}/{name}/{suffix}"
            for name in ("property", "service")
            for suffix in ("get/accepted", "update/accepted", "update/documents")
        ]
        async with self._session.ws_connect(
            url,
            protocols=("mqtt",),
            autoping=False,
            heartbeat=None,
            timeout=20,
        ) as ws:
            self._active_ws = ws
            try:
                await ws.send_bytes(_connect_packet(f"ha-anthbot-{serial[-12:]}", 45))
                message = await asyncio.wait_for(ws.receive(), timeout=15)
                if (
                    message.type != WSMsgType.BINARY
                    or len(message.data) < 4
                    or message.data[:3] != b" \x02\x00"
                    or message.data[3] != 0
                ):
                    raise ValueError("AWS IoT MQTT connection was not accepted")
                self._credential_recovery_stage = 0
                self._force_credential_refresh = False
                self._force_account_reauthentication = False
                await ws.send_bytes(_subscribe_packet(1, response_topics))
                for name in ("property", "service"):
                    await ws.send_bytes(_publish_packet(f"{base}/{name}/get"))
                self._consecutive_failures = 0
                self._client.set_live_command_publisher(self.async_publish_command)
                await self._on_connection(True, None)
                while not self._stop.is_set():
                    try:
                        message = await asyncio.wait_for(ws.receive(), timeout=30)
                    except TimeoutError:
                        await ws.send_bytes(b"\xc0\x00")
                        continue
                    if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSE, WSMsgType.ERROR):
                        detail = ws.exception()
                        raise ConnectionError(
                            "AWS IoT WebSocket closed "
                            f"(message_type={message.type.name}, "
                            f"close_code={ws.close_code}, exception={detail!r})"
                        )
                    if message.type != WSMsgType.BINARY:
                        continue
                    decoded = _decode_publish(message.data)
                    if decoded is None:
                        continue
                    topic, raw_payload = decoded
                    try:
                        payload = json.loads(raw_payload)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    reported = _reported_state(payload)
                    if reported is None:
                        continue
                    shadow_name = "service" if "/service/" in topic else "property"
                    await self._on_shadow(shadow_name, reported)
            finally:
                self._client.set_live_command_publisher(None)
                if self._active_ws is ws:
                    self._active_ws = None
