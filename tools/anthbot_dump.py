#!/usr/bin/env python3
"""Download raw Anthbot map files for offline decoding.

This is a diagnostic helper. It does not talk to Home Assistant and it does not
change mower settings.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_HOST = "api.anthbot.com"
USER_AGENT = "LdMower/1581 CFNetwork/3860.400.51 Darwin/25.3.0"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download raw Anthbot area/map/path files."
    )
    parser.add_argument("--username", default=os.getenv("ANTHBOT_USERNAME"))
    parser.add_argument("--password", default=os.getenv("ANTHBOT_PASSWORD"))
    parser.add_argument("--area-code", default=os.getenv("ANTHBOT_AREA_CODE", "36"))
    parser.add_argument("--host", default=os.getenv("ANTHBOT_API_HOST", DEFAULT_HOST))
    parser.add_argument("--serial", default=os.getenv("ANTHBOT_SERIAL"))
    parser.add_argument(
        "--out",
        default="anthbot-dump",
        help="Output directory. Default: anthbot-dump",
    )
    args = parser.parse_args()

    username = args.username or input("Anthbot username/email: ").strip()
    password = args.password or getpass("Anthbot password: ")
    if not username or not password:
        print("Missing username or password.", file=sys.stderr)
        return 2

    token = login(args.host, username, password, args.area_code)
    devices = bound_devices(args.host, token)
    serial = args.serial or first_serial(devices)
    if not serial:
        print("No bound Anthbot device found. Pass --serial manually.", file=sys.stderr)
        return 3

    out_dir = Path(args.out) / serial / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "serial": serial,
        "host": args.host,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "devices": devices,
        "files": {},
    }

    for kind in ("area", "map", "path"):
        try:
            payload, raw = download_device_file(args.host, token, serial, kind)
        except Exception as err:  # noqa: BLE001 - diagnostic script should continue.
            summary["files"][kind] = {"error": str(err)}
            print(f"{kind}: ERROR: {err}")
            continue

        raw_path = out_dir / f"{kind}_{serial}.bin"
        raw_path.write_bytes(raw)

        presigned_path = out_dir / f"{kind}_{serial}.presigned.json"
        presigned_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        decoded_path = None
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        if decoded is not None:
            decoded_path = out_dir / f"{kind}_{serial}.json"
            decoded_path.write_text(
                json.dumps(decoded, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        preview = binary_preview(raw)
        summary["files"][kind] = {
            "raw": str(raw_path),
            "presigned_payload": str(presigned_path),
            "decoded_json": str(decoded_path) if decoded_path else None,
            "size": len(raw),
            "preview": preview,
        }
        print(f"{kind}: {len(raw)} bytes -> {raw_path}")

    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"summary: {summary_path}")
    return 0


def base_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "version": "v2",
        "language": "en",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = token
    return headers


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    data: dict[str, Any] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers = {**headers, "content-type": "application/json"}

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{method} {url} failed: HTTP {err.code}: {detail}") from err
    except URLError as err:
        raise RuntimeError(f"{method} {url} failed: {err}") from err


def request_bytes(url: str, *, timeout: int = 30) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"GET {url} failed: HTTP {err.code}: {detail}") from err
    except URLError as err:
        raise RuntimeError(f"GET {url} failed: {err}") from err


def login(host: str, username: str, password: str, area_code: str) -> str:
    payload = request_json(
        "POST",
        f"https://{host}/api/v1/login",
        headers=base_headers(),
        data={"username": username, "password": password, "areaCode": area_code},
    )
    if payload.get("code") != 0:
        raise RuntimeError(f"Login rejected: code={payload.get('code')!r}")
    access_token = payload.get("data", {}).get("access_token")
    if not access_token:
        raise RuntimeError("Login response has no access_token.")
    return f"Bearer {access_token}"


def bound_devices(host: str, token: str) -> list[dict[str, Any]]:
    payload = request_json(
        "GET",
        f"https://{host}/api/v1/device/bind/list",
        headers=base_headers(token),
    )
    if payload.get("code") != 0:
        raise RuntimeError(f"Bind list rejected: code={payload.get('code')!r}")
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    devices = []
    for item in data:
        if isinstance(item, dict):
            devices.append(
                {
                    "sn": item.get("sn"),
                    "alias": item.get("alias"),
                    "category_id": item.get("category_id"),
                    "is_owner": item.get("is_owner"),
                }
            )
    return devices


def first_serial(devices: list[dict[str, Any]]) -> str | None:
    for item in devices:
        serial = item.get("sn")
        if isinstance(serial, str) and serial:
            return serial
    return None


def verification_token(serial: str, timestamp: int | None = None) -> str:
    now = timestamp or int(time.time())
    suffix = str(now)
    prefix = hashlib.md5(f"{serial}{suffix}".encode("utf-8")).hexdigest()
    return f"{prefix}{suffix}"


def download_device_file(
    host: str,
    token: str,
    serial: str,
    kind: str,
) -> tuple[dict[str, Any], bytes]:
    query = urlencode(
        {
            "filename": f"{kind}_{serial}.txt",
            "sn": serial,
            "category": "device",
            "sub_category": kind,
            "verification_token": verification_token(serial),
        }
    )
    payload = request_json(
        "GET",
        f"https://{host}/api/v1/device/v2/presigned_url?{query}",
        headers=base_headers(token),
    )
    if payload.get("code") != 0:
        raise RuntimeError(f"{kind} presigned URL rejected: code={payload.get('code')!r}")
    presigned_url = payload.get("data", {}).get("presigned_url")
    if not presigned_url:
        raise RuntimeError(f"{kind} presigned URL response has no presigned_url.")
    return payload, request_bytes(presigned_url)


def binary_preview(raw: bytes) -> dict[str, Any]:
    return {
        "first_bytes": raw[:64].hex(" "),
        "int32le_header": unpack_many(raw[:32], "<I"),
        "int32be_header": unpack_many(raw[:32], ">I"),
        "int16le_header": unpack_many(raw[:32], "<h"),
        "int16be_header": unpack_many(raw[:32], ">h"),
    }


def unpack_many(data: bytes, fmt: str) -> list[int]:
    size = struct.calcsize(fmt)
    values = []
    for offset in range(0, len(data) - size + 1, size):
        values.append(int(struct.unpack_from(fmt, data, offset)[0]))
    return values


if __name__ == "__main__":
    raise SystemExit(main())
