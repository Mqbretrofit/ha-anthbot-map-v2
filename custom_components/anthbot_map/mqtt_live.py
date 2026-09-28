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
    current = payload.get("current")
    if isinstance(current, dict):
        payload = current
    state = payload.get("state")
    if not isinstance(state, dict):
        return None
    reported = state.get("reported")
    return reported if isinstance(reported, dict) else None


def _coerce_small_int(value: Any, allowed: tuple[int, ...]) -> int | None:
    if isinstance(value, bool):
        number = int(value)
    elif isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str):
        try:
            number = int(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if number in allowed else None


def _find_nested_setting(value: Any, names: tuple[str, ...], *, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value[name]
        for child in value.values():
            found = _find_nested_setting(child, names, depth=depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value[:20]:
            found = _find_nested_setting(child, names, depth=depth + 1)
            if found is not None:
                return found
    return None


def _visual_setting_patch_from_service_payload(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Mirror app-originated mower settings into HA immediately.

    The mobile app writes these settings through desired shadow commands.
    Different firmware revisions nest the same verified fields differently,
    therefore extract the concrete setting names recursively instead of
    depending on one exact command shape.
    """
    documents: list[dict[str, Any]] = []
    current = payload.get("current")
    if isinstance(current, dict):
        documents.append(current)
    documents.append(payload)
    previous = payload.get("previous")
    if isinstance(previous, dict):
        documents.append(previous)

    desired: dict[str, Any] | None = None
    for document in documents:
        state = document.get("state")
        candidate = state.get("desired") if isinstance(state, dict) else None
        if isinstance(candidate, dict) and candidate:
            desired = candidate
            break
    if desired is None:
        return None

    cmd = str(desired.get("cmd") or desired.get("command") or "").strip().lower()
    data = desired.get("data")
    search_root: Any = data if isinstance(data, (dict, list)) else desired

    mirror: dict[str, int] = {}
    patch: dict[str, Any] = {}

    raw_visual_switch = _find_nested_setting(
        search_root, ("pobctl_switch",)
    )
    if raw_visual_switch is None:
        pobctl_container = _find_nested_setting(search_root, ("pobctl",))
        if isinstance(pobctl_container, dict):
            raw_visual_switch = pobctl_container.get("switch")
    if raw_visual_switch is None and (
        cmd == "perception_obstacle_ctl"
        or "obstacle" in cmd
        or "pobctl" in cmd
    ):
        raw_visual_switch = _find_nested_setting(search_root, ("switch",))
    visual_switch = _coerce_small_int(raw_visual_switch, (0, 1))
    if visual_switch is not None:
        mirror["visual_switch"] = visual_switch
        patch.setdefault("device_config", {})["pobctl_switch"] = visual_switch
        patch.setdefault("pobctl", {})["switch"] = visual_switch
        patch["pobctl_switch"] = visual_switch

    raw_visual_level = _find_nested_setting(
        search_root, ("pobctl_level",)
    )
    if raw_visual_level is None and cmd == "perception_obstacle_ctl":
        raw_visual_level = _find_nested_setting(search_root, ("level",))
    visual_level = _coerce_small_int(raw_visual_level, (0, 1, 2))
    if visual_level is not None:
        mirror["visual_level"] = visual_level
        patch.setdefault("device_config", {})["pobctl_level"] = visual_level
        patch.setdefault("pobctl", {})["level"] = visual_level
        patch["pobctl_level"] = visual_level

    raw_mow_count = _find_nested_setting(search_root, ("mow_count",))
    mow_count = _coerce_small_int(raw_mow_count, (1, 2))
    if mow_count is not None:
        mirror["mow_count"] = mow_count
        patch.setdefault("param_set", {})["mow_count"] = mow_count
        patch["mow_count"] = mow_count

    raw_cutter_height = _find_nested_setting(
        search_root, ("cutter_height", "cutter_ctl_cutter_lift")
    )
    cutter_height = _coerce_small_int(
        raw_cutter_height, tuple(range(30, 71, 5))
    )
    if cutter_height is not None:
        mirror["cutter_height"] = cutter_height
        patch.setdefault("param_set", {})["cutter_height"] = cutter_height
        patch["cutter_height"] = cutter_height

    if not mirror:
        return None
    patch["_app_setting_mirror"] = mirror
    return patch



def _safe_probe_value(value: Any, *, depth: int = 0) -> Any:
    """Sanitize a command-shaped value for temporary diagnostics."""
    if depth > 4:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 120 else "<long-string>"
    if isinstance(value, list):
        out = [_safe_probe_value(item, depth=depth + 1) for item in value[:20]]
        return [item for item in out if item is not None]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        blocked = (
            "token", "secret", "credential", "password", "passwd", "auth",
            "sign", "cert", "key", "url", "uri", "endpoint", "account",
            "email", "phone", "imei", "mac", "ssid", "wifi", "ip",
        )
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if lowered in {"time", "timestamp", "ts", "clienttoken", "version"}:
                continue
            if any(part in lowered for part in blocked):
                continue
            safe = _safe_probe_value(item, depth=depth + 1)
            if safe is not None:
                out[key] = safe
        return out
    return None


def _service_probe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract desired/reported command data from service shadow responses."""
    result: dict[str, Any] = {}
    for label in ("previous", "current"):
        document = payload.get(label)
        if not isinstance(document, dict):
            continue
        state = document.get("state")
        if isinstance(state, dict):
            safe = _safe_probe_value(state)
            if isinstance(safe, dict) and safe:
                result[label] = safe
    state = payload.get("state")
    if isinstance(state, dict):
        safe = _safe_probe_value(state)
        if isinstance(safe, dict) and safe:
            result["state"] = safe
    return result


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
        self._stop.set()
        self._client.set_live_command_publisher(None)

    async def async_publish_command(self, topic: str, payload: bytes) -> None:
        async with self._send_lock:
            ws = self._active_ws
            if ws is None or ws.closed:
                raise RuntimeError("Anthbot live MQTT socket is not connected")
            try:
                await ws.send_bytes(_packet(0x30, _mqtt_string(topic) + payload))
            except (ClientError, OSError, RuntimeError):
                self._client.set_live_command_publisher(None)
                await ws.close()
                raise

    async def async_run(self) -> None:
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
                if self._consecutive_failures == 0:
                    delay = _RECONNECT_INITIAL_SECONDS
                error = (
                    f"{_safe_error(err)}; credential_lifecycle=cached_until_expiry; "
                    f"{self._client.iot_credential_diagnostics}"
                )
                self._consecutive_failures += 1
                log = _LOGGER.warning if self._consecutive_failures == 3 else _LOGGER.debug
                log(
                    "Anthbot live shadow unavailable for %s (attempt %d): %s",
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
                delay = min(delay * 2, _RECONNECT_MAX_SECONDS)

    async def _async_connected_session(self) -> None:
        url = URL(
            await self._client.async_get_mqtt_websocket_url(),
            encoded=True,
        )
        serial = self._client.serial_number
        base = f"$aws/things/{serial}/shadow/name"
        response_topics = [
            f"{base}/{name}/{suffix}"
            for name in ("property", "service")
            for suffix in ("get/accepted", "update/accepted", "update/documents")
        ]
        async with self._session.ws_connect(
            url,
            headers={"User-Agent": ANDROID_APP_USER_AGENT},
            protocols=("mqttv3.1",),
            autoping=False,
            heartbeat=None,
            timeout=20,
        ) as ws:
            self._active_ws = ws
            try:
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
                        message = await asyncio.wait_for(ws.receive(), timeout=receive_timeout)
                    except TimeoutError:
                        now = loop.time()
                        if now >= next_property_refresh:
                            await self._client.async_request_all_properties()
                            next_property_refresh = now + _PROPERTY_REFRESH_SECONDS
                        if ping_sent_at is None and now - last_received >= _MQTT_IDLE_PING_SECONDS:
                            await ws.send_bytes(b"\xc0\x00")
                            ping_sent_at = now
                        elif ping_sent_at is not None and now - ping_sent_at >= _MQTT_PING_RESPONSE_SECONDS:
                            raise TimeoutError("AWS IoT MQTT did not answer PINGREQ")
                        continue
                    if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSE, WSMsgType.ERROR):
                        detail = ws.exception()
                        raise ConnectionError(
                            "AWS IoT WebSocket closed "
                            f"(message_type={message.type.name}, close_code={ws.close_code}, exception={detail!r})"
                        )
                    if message.type != WSMsgType.BINARY:
                        continue
                    for packet in _mqtt_packets(message.data):
                        last_received = loop.time()
                        if packet[0] >> 4 == 13:
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

                        if "/service/" in topic and not topic.endswith("/get/accepted"):
                            probe = _service_probe_payload(payload)
                            if probe:
                                _LOGGER.warning(
                                    "ANTHBOT M9 SERVICE MQTT PROBE sn=%s topic=%s payload=%s",
                                    serial,
                                    topic.rsplit("/", 2)[-2] + "/" + topic.rsplit("/", 1)[-1],
                                    probe,
                                )

                        if (
                            "/service/" in topic
                            and not topic.endswith("/get/accepted")
                        ):
                            setting_patch = _visual_setting_patch_from_service_payload(
                                payload
                            )
                            if setting_patch:
                                _LOGGER.warning(
                                    "ANTHBOT APP SETTING SYNC sn=%s topic=%s patch=%s",
                                    serial,
                                    topic.rsplit("/", 2)[-2] + "/" + topic.rsplit("/", 1)[-1],
                                    setting_patch.get("_app_setting_mirror"),
                                )
                                await self._on_shadow("property", setting_patch)

                        reported = _reported_state(payload)
                        if reported is None:
                            continue
                        shadow_name = "service" if "/service/" in topic else "property"
                        await self._on_shadow(shadow_name, reported)
            finally:
                self._client.set_live_command_publisher(None)
                if self._active_ws is ws:
                    self._active_ws = None
