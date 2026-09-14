"""Recorder-aware write policy for the Anthbot GPS device tracker.

The live map has its own WebSocket transport, so Recorder does not need every
anti-loss GPS sample.  This module keeps the device tracker useful for normal
Home Assistant location/zone use while suppressing stationary GPS jitter.

Only the Home Assistant entity write cadence is affected.  Coordinator/shadow
updates continue at their existing rate.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

TRACKER_MIN_WRITE_SECONDS = 30.0
TRACKER_HEARTBEAT_SECONDS = 300.0
TRACKER_SIGNIFICANT_MOVEMENT_METERS = 5.0

_EARTH_RADIUS_METERS = 6_371_008.8


@dataclass(frozen=True, slots=True)
class LocationRecorderSnapshot:
    """Small state signature for the last location published to Home Assistant."""

    latitude: float | None
    longitude: float | None
    pose_type: Any
    available: bool


def _coordinate(value: Any, minimum: float, maximum: float) -> float | None:
    """Return a finite coordinate inside its legal range."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        return None
    return result


def location_snapshot(
    *,
    latitude: Any,
    longitude: Any,
    pose_type: Any,
    available: bool,
) -> LocationRecorderSnapshot:
    """Normalize the fields that are meaningful to the Recorder-facing tracker."""
    lat = _coordinate(latitude, -90.0, 90.0)
    lon = _coordinate(longitude, -180.0, 180.0)
    if lat is None or lon is None:
        lat = None
        lon = None
    return LocationRecorderSnapshot(
        latitude=lat,
        longitude=lon,
        pose_type=pose_type,
        available=bool(available),
    )


def location_distance_meters(
    previous: LocationRecorderSnapshot,
    current: LocationRecorderSnapshot,
) -> float | None:
    """Return great-circle distance when both snapshots contain valid GPS data."""
    if (
        previous.latitude is None
        or previous.longitude is None
        or current.latitude is None
        or current.longitude is None
    ):
        return None

    lat1 = math.radians(previous.latitude)
    lat2 = math.radians(current.latitude)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(current.longitude - previous.longitude)
    haversine = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2.0) ** 2
    )
    haversine = min(1.0, max(0.0, haversine))
    return 2.0 * _EARTH_RADIUS_METERS * math.asin(math.sqrt(haversine))


def should_write_location_state(
    previous: LocationRecorderSnapshot | None,
    current: LocationRecorderSnapshot,
    *,
    last_write: float,
    now: float,
    minimum_write_seconds: float = TRACKER_MIN_WRITE_SECONDS,
    heartbeat_seconds: float = TRACKER_HEARTBEAT_SECONDS,
    movement_meters: float = TRACKER_SIGNIFICANT_MOVEMENT_METERS,
) -> bool:
    """Return whether the tracker should publish a new Home Assistant state.

    Important availability/pose-type/coordinate-presence transitions are not
    held back by the 30-second moving-position limiter.  Ordinary GPS movement
    must be significant enough to ignore stationary jitter, and an unchanged
    tracker gets only a sparse heartbeat.
    """
    if previous is None or last_write <= 0.0:
        return True
    if now < last_write:
        # A monotonic clock should not go backwards, but recover cleanly if a
        # synthetic/test clock or platform anomaly does.
        return True

    if current.available != previous.available:
        return True
    if current.pose_type != previous.pose_type:
        return True

    previous_has_position = (
        previous.latitude is not None and previous.longitude is not None
    )
    current_has_position = current.latitude is not None and current.longitude is not None
    if current_has_position != previous_has_position:
        return True

    elapsed = now - last_write
    distance = location_distance_meters(previous, current)
    if distance is not None and distance >= movement_meters:
        return elapsed >= minimum_write_seconds

    return elapsed >= heartbeat_seconds
