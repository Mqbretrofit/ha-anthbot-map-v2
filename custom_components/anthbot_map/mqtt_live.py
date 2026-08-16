"""Minimal AWS IoT MQTT-over-WebSocket shadow listener."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import re
import struct
import uuid
from typing import Any

from aiohttp import (
    ClientError,
    ClientResponseError,
    ClientSession,
    ClientWebSocketResponse,
    WSMsgType,
)
from yarl import URL

from .api import (
    ANDROID_APP_USER_AGENT,
    AnthbotGenieApiError,
    AnthbotShadowApiClient,
)

_LOGGER = logging.getLogger(__name__)

_RECONNECT_INITIAL_SECONDS = 5
_RECONNECT_MAX_SECONDS = 30
_PROPERTY_REFRESH_SECONDS = 5
_MQTT_IDLE_PING_SECONDS = 30
_MQTT_PING_RESPONSE_SECONDS = 15


def _safe_error(error: Exception) -> str:
    """Return an MQTT error without leaking the presigned AWS query string."""
    value = f"{type(error).__name__}: {error}"
    value = re.sub(
        r"(wss://[^?\s']+)\?[^\s']+",
        r"\1?<redacted>",
        value,
    )
    if not isinstance(error, ClientResponseError) or not error.headers:
        return value

    # AWS usually explains a rejected WebSocket upgrade in response headers.
    # Include only this strict allow-list: never copy arbitrary headers because
    # the request contains temporary credentials in its presigned URL.
    diagnostic_headers = {
        "aws_error_type": error.headers.get("x-amzn-errortype"),
        "aws_request_id": (
            error.headers.get("x-amzn-requestid")
            or error.headers.get("x-amzn-request-id")
        ),
        "server": error.headers.get("server"),
    }
    details = ", ".join(
        f"{name}={header_value}"
        for name, header_value in diagnostic_headers.items()
        if header_value
    )
    return f"{value}; handshake={details}" if details else value

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
    # aws-iot-device-sdk-js 2.2.15 defaults: clean session, 300 second
    # keepalive and enabled SDK metrics in the MQTT username.
    username = "?SDK=JavaScript&Version=2.2.15"
    variable = _mqtt_string("MQTT") + bytes((4, 0x82)) + struct.pack("!H", keepalive)
    return _packet(
        0x10,
        variable + _mqtt_string(client_id) + _mqtt_string(username),
    )


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


def _mqtt_packets(data: bytes) -> list[bytes]:
    """Split all complete MQTT packets carried by one WebSocket message."""
    packets: list[bytes] = []
    offset = 0
    while offset < len(data):
        index = offset + 1
        multiplier = 1
        remaining = 0
        for _ in range(4):
            if index >= len(data):
                return packets
            digit = data[index]
            index += 1
            remaining += (digit & 0x7F) * multiplier
            if not digit & 0x80:
                end = index + remaining
                if end > len(data):
                    return packets
                packets.append(data[offset:end])
                offset = end
                break
            multiplier *= 128
        else:
            return packets
    return packets


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
                # Do not leave a failed socket registered as the command
                # transport. Closing it wakes the persistent reconnect loop.
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
                    f"{_safe_error(err)}; credential_lifecycle=cached_until_expiry; "
                    f"{self._client.iot_credential_diagnostics}"
                )
                self._consecutive_failures += 1
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
                    "(attempt %d): %s",
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

    async def _async_connected_session(self) -> None:
        # SigV4 covers the exact percent-encoded query string.  aiohttp/yarl
        # normally canonicalizes URLs before sending them, which can turn
        # signed values such as ``%2F`` back into ``/`` and make AWS reject the
        # WebSocket upgrade with HTTP 403.  Mark the presigned URL as already
        # encoded so its raw query is sent byte-for-byte unchanged.
        url = URL(
            await self._client.async_get_mqtt_websocket_url(),
            encoded=True,
        )
        serial = self._client.serial_number
        base = f"$aws/things/{serial}/shadow/name"
        response_topics = [
            f"{base}/{name}/{suffix}"
            for name in ("property", "service")
            # This is the response set accepted by the mower's IoT policy and
            # used by the app's two named-shadow registrations.
            for suffix in ("get/accepted", "update/accepted", "update/documents")
        ]
        async with self._session.ws_connect(
            url,
            headers={"User-Agent": ANDROID_APP_USER_AGENT},
            # aws-iot-device-sdk-js used by ANTHBOT 2.15.15 explicitly sends
            # ``Sec-WebSocket-Protocol: mqttv3.1``.  AWS performs this check
            # during the HTTP upgrade, before the MQTT CONNECT packet.
            protocols=("mqttv3.1",),
            autoping=False,
            heartbeat=None,
            timeout=20,
        ) as ws:
            self._active_ws = ws
            try:
                # Match the official app/AWS IoT SDK: every connection uses a
                # fresh UUID v4 client identifier.
                await ws.send_bytes(_connect_packet(str(uuid.uuid4()), 300))
                message = await asyncio.wait_for(ws.receive(), timeout=15)
                if (
                    message.type != WSMsgType.BINARY
                    or len(message.data) < 4
                    or message.data[:3] != b" \x02\x00"
                    or message.data[3] != 0
                ):
                    raise ValueError("AWS IoT MQTT connection was not accepted")
                await ws.send_bytes(_subscribe_packet(1, response_topics))
                suback = await asyncio.wait_for(ws.receive(), timeout=15)
                suback_packets = (
                    _mqtt_packets(suback.data)
                    if suback.type == WSMsgType.BINARY
                    else []
                )
                accepted_suback = next(
                    (packet for packet in suback_packets if packet[0] == 0x90),
                    None,
                )
                if accepted_suback is None:
                    raise ValueError(
                        "AWS IoT MQTT subscriptions were not accepted "
                        f"(message_type={suback.type.name}, "
                        f"packet_types={[hex(packet[0]) for packet in suback_packets]})"
                    )
                for name in ("property", "service"):
                    await ws.send_bytes(_publish_packet(f"{base}/{name}/get"))
                self._consecutive_failures = 0
                self._client.set_live_command_publisher(self.async_publish_command)
                await self._on_connection(True, None)
                loop = asyncio.get_running_loop()
                last_received = loop.time()
                next_property_refresh = last_received + _PROPERTY_REFRESH_SECONDS
                ping_sent_at: float | None = None
                while not self._stop.is_set():
                    now = loop.time()
                    deadlines = [next_property_refresh]
                    if ping_sent_at is None:
                        deadlines.append(last_received + _MQTT_IDLE_PING_SECONDS)
                    else:
                        deadlines.append(ping_sent_at + _MQTT_PING_RESPONSE_SECONDS)
                    receive_timeout = max(0.1, min(deadlines) - now)
                    try:
                        message = await asyncio.wait_for(
                            ws.receive(), timeout=receive_timeout
                        )
                    except TimeoutError:
                        now = loop.time()
                        if now >= next_property_refresh:
                            # Match the cloud-connect action: ask the mower,
                            # over the active MQTT service shadow, to publish
                            # a fresh complete property state. Reading only
                            # property/get can return an already stale pose.
                            await self._client.async_request_all_properties()
                            next_property_refresh = now + _PROPERTY_REFRESH_SECONDS
                        if (
                            ping_sent_at is None
                            and now - last_received >= _MQTT_IDLE_PING_SECONDS
                        ):
                            await ws.send_bytes(b"\xc0\x00")
                            ping_sent_at = now
                        elif (
                            ping_sent_at is not None
                            and now - ping_sent_at >= _MQTT_PING_RESPONSE_SECONDS
                        ):
                            raise TimeoutError(
                                "AWS IoT MQTT did not answer PINGREQ"
                            )
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
                    for packet in _mqtt_packets(message.data):
                        last_received = loop.time()
                        if packet[0] >> 4 == 13:  # PINGRESP
                            ping_sent_at = None
                            continue
                        decoded = _decode_publish(packet)
                        if decoded is None:
                            continue
                        topic, raw_payload = decoded
                        if topic.endswith("/rejected"):
                            _LOGGER.debug(
                                "Anthbot shadow request rejected for %s on %s",
                                serial,
                                topic,
                            )
                            continue
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
