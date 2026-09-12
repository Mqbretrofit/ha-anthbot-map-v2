"""Privacy-preserving robot identity helpers for diagnostics reports."""

from __future__ import annotations

from typing import Any


def serial_suffix(value: object) -> str | None:
    """Return only the last four serial characters for human identification."""
    text = str(value or "").strip()
    return text[-4:] if text else None


def add_serial_suffix(report: Any, coordinator: Any) -> Any:
    """Add a masked robot serial suffix without exposing the full serial number."""
    if not isinstance(report, dict):
        return report
    client = getattr(coordinator, "client", None)
    suffix = serial_suffix(getattr(client, "serial_number", None))
    device = report.get("device")
    if suffix and isinstance(device, dict):
        device["serial_suffix"] = suffix
    return report
