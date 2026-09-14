"""Additive hardening for the stable ANTHBOT live-map WebSocket transport.

The v2.4.7.2 transport and model-specific decoders remain the source of truth.
This module only validates presentation-time position ownership, coalesces
concurrent initial snapshots and exposes sparse evidence-based capabilities.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import math
import time
from typing import Any

from .mower_status import mower_activity_name

POSITION_MAX_AGE_SECONDS = 90.0
LAST_POSITION_MAX_AGE_SECONDS = 24.0 * 60.0 * 60.0
DOCK_POSITION_MAX_AGE_SECONDS = 7.0 * 24.0 * 60.0 * 60.0
SNAPSHOT_CACHE_SECONDS = 1.0
POSITION_HEARTBEAT_SECONDS = 30.0

CAPABILITY_SUPPORTED = "supported"
CAPABILITY_UNSUPPORTED = "unsupported"
CAPABILITY_UNKNOWN = "unknown"
CAPABILITY_SOURCE_OBSERVED = "observed"
CAPABILITY_SOURCE_MODEL = "model"
CAPABILITY_SOURCE_ADVERTISED = "advertised"
CAPABILITY_SOURCE_UNKNOWN = "unknown"

FEATURE_LIVE_MAP_STREAM = "live_map_stream"
FEATURE_ABSOLUTE_PATH_DELTA = "absolute_path_delta"
FEATURE_MAP_RASTER = "map_raster"
FEATURE_EDITABLE_BOUNDARY = "editable_boundary"
FEATURE_KNOWN_DOCK_POSITION = "known_dock_position"

_INSTALLED = False

_GEOMETRY_KEYS = frozenset(
    {
        "id",
        "map_id",
        "zone_id",
        "area_id",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "min_x",
        "min_y",
        "max_x",
        "max_y",
        "bounds",
        "points",
        "point",
        "vertexs",
        "vertices",
        "boundary",
        "boundaries",
        "path",
        "paths",
        "coordinate_paths",
        "custom_areas",
        "customAreas",
        "zones",
        "region_areas",
        "regionAreas",
        "auto_zones",
        "autoZones",
        "forbid_areas",
        "forbidAreas",
        "remote_forbid_areas",
        "remoteForbidAreas",
        "no_go_areas",
        "noGoAreas",
        "ridable_areas",
        "ridableAreas",
        "areas",
        "data",
    }
)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _stable_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return str(value)


def _geometry_tree(value: Any) -> Any:
    """Return geometry-only data so settings changes do not rotate map identity."""
    if isinstance(value, dict):
        items: list[tuple[str, Any]] = []
        for key in sorted(value, key=str):
            key_text = str(key)
            if key_text not in _GEOMETRY_KEYS:
                continue
            items.append((key_text, _geometry_tree(value[key])))
        return tuple(items)
    if isinstance(value, (list, tuple)):
        return tuple(_geometry_tree(item) for item in value)
    return _stable_scalar(value)


def _map_binary_geometry(map_definition: Any) -> Any:
    if not isinstance(map_definition, dict):
        return ()
    probe = map_definition.get("_binary_probe")
    if not isinstance(probe, dict):
        return ()
    return _geometry_tree({"coordinate_paths": probe.get("coordinate_paths")})


def map_geometry_fingerprint(state: dict[str, Any]) -> str:
    """Fingerprint only map geometry, never moving pose/path telemetry."""
    definition = state.get("_map_definition")
    definition = definition if isinstance(definition, dict) else {}
    raster = definition.get("_map_raster")
    raster = raster if isinstance(raster, dict) else {}
    raster_identity = (
        _stable_scalar(definition.get("map_id")),
        _stable_scalar(raster.get("encoding")),
        _stable_scalar(raster.get("width")),
        _stable_scalar(raster.get("height")),
        _geometry_tree({"bounds": raster.get("bounds")}),
    )
    geometry = (
        raster_identity,
        _map_binary_geometry(definition),
        _geometry_tree(state.get("_area_definition")),
        _geometry_tree(state.get("_ridable_area_definition")),
    )
    return hashlib.sha256(repr(geometry).encode("utf-8")).hexdigest()


def geometry_object_token(state: dict[str, Any]) -> tuple[int, ...]:
    """Cheap identity token used to avoid hashing static geometry on live ticks."""
    definition = state.get("_map_definition")
    area = state.get("_area_definition")
    ridable = state.get("_ridable_area_definition")
    raster = definition.get("_map_raster") if isinstance(definition, dict) else None
    probe = definition.get("_binary_probe") if isinstance(definition, dict) else None
    return tuple(id(value) for value in (definition, raster, probe, area, ridable))


def _pose_mapping_signature(value: Any) -> tuple[Any, ...] | None:
    if not isinstance(value, dict):
        return None
    keys = ("x", "y", "z", "yaw", "heading", "angle", "type", "clean_time")
    return tuple((key, _stable_scalar(value.get(key))) for key in keys if key in value)


def pose_revision_token(state: dict[str, Any]) -> tuple[Any, ...]:
    """Track actual pose changes independently of rotating shadow metadata."""
    return (
        _pose_mapping_signature(state.get("pose")),
        _pose_mapping_signature(state.get("curPose") or state.get("cur_pose")),
        _pose_mapping_signature(state.get("mapScanPose") or state.get("map_scan_pose")),
    )


def _map_bounds(state: dict[str, Any]) -> tuple[float, float, float, float] | None:
    definition = state.get("_map_definition")
    raster = definition.get("_map_raster") if isinstance(definition, dict) else None
    bounds = raster.get("bounds") if isinstance(raster, dict) else None
    if isinstance(bounds, dict):
        min_x = _finite_number(bounds.get("min_x", bounds.get("x1")))
        max_x = _finite_number(bounds.get("max_x", bounds.get("x2")))
        min_y = _finite_number(bounds.get("min_y", bounds.get("y1")))
        max_y = _finite_number(bounds.get("max_y", bounds.get("y2")))
    elif isinstance(bounds, (list, tuple)) and len(bounds) >= 4:
        min_x, min_y, max_x, max_y = (_finite_number(item) for item in bounds[:4])
    else:
        return None
    if None in (min_x, min_y, max_x, max_y):
        return None
    assert min_x is not None and min_y is not None and max_x is not None and max_y is not None
    if max_x <= min_x or max_y <= min_y:
        return None
    return min_x, min_y, max_x, max_y


def _pose_within_bounds(pose: dict[str, Any], state: dict[str, Any]) -> bool:
    bounds = _map_bounds(state)
    if bounds is None:
        return True
    min_x, min_y, max_x, max_y = bounds
    span_x = max_x - min_x
    span_y = max_y - min_y
    # Be deliberately tolerant of decoder/raster rounding. This only rejects a
    # pose that is clearly outside the active map, not one near an edge.
    margin_x = max(10.0, span_x * 0.25)
    margin_y = max(10.0, span_y * 0.25)
    return (
        min_x - margin_x <= pose["x"] <= max_x + margin_x
        and min_y - margin_y <= pose["y"] <= max_y + margin_y
    )


def validated_pose(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first finite, map-plausible runtime pose."""
    for candidate in (
        state.get("pose"),
        state.get("curPose") or state.get("cur_pose"),
        state.get("mapScanPose") or state.get("map_scan_pose"),
    ):
        if not isinstance(candidate, dict):
            continue
        x = _finite_number(candidate.get("x"))
        y = _finite_number(candidate.get("y"))
        if x is None or y is None:
            continue
        pose = dict(candidate)
        pose["x"] = x
        pose["y"] = y
        heading = _finite_number(pose.get("heading"))
        if heading is not None:
            pose["heading"] = heading
        if _pose_within_bounds(pose, state):
            return pose
    return None


def _position_record(
    pose: dict[str, Any],
    *,
    observed_at: float,
    geometry: str,
    status: str,
) -> dict[str, Any]:
    result = dict(pose)
    result.update(
        {
            "observed_at": observed_at,
            "map_fingerprint": geometry,
            "position_status": status,
        }
    )
    return result


def _position_record_signature(record: Any) -> tuple[Any, ...] | None:
    if not isinstance(record, dict):
        return None
    return (
        _finite_number(record.get("x")),
        _finite_number(record.get("y")),
        _finite_number(record.get("observed_at")),
        record.get("map_fingerprint"),
        record.get("position_status"),
    )


def _fresh_scoped_record(
    record: Any,
    *,
    geometry: str,
    now: float,
    max_age: float,
) -> dict[str, Any] | None:
    if not isinstance(record, dict) or record.get("map_fingerprint") != geometry:
        return None
    observed = _finite_number(record.get("observed_at"))
    if observed is None or not 0.0 <= now - observed <= max_age:
        return None
    return dict(record)


def _path_supports_absolute_delta(state: dict[str, Any]) -> bool:
    definition = state.get("_path_definition")
    if not isinstance(definition, dict):
        return False
    first = definition.get("_m_series_first_index")
    last = definition.get("_m_series_last_index")
    return (
        isinstance(first, int)
        and not isinstance(first, bool)
        and isinstance(last, int)
        and not isinstance(last, bool)
        and last >= first
    )


def _has_map_raster(state: dict[str, Any]) -> bool:
    definition = state.get("_map_definition")
    raster = definition.get("_map_raster") if isinstance(definition, dict) else None
    return isinstance(raster, dict) and bool(raster)


def _has_editable_boundary(state: dict[str, Any]) -> bool:
    separate = state.get("_ridable_area_definition")
    if isinstance(separate, list):
        return bool(separate)
    if isinstance(separate, dict):
        for key in ("ridable_areas", "ridableAreas", "areas", "data"):
            if isinstance(separate.get(key), list) and separate[key]:
                return True
    area = state.get("_area_definition")
    if isinstance(area, dict):
        for key in ("ridable_areas", "ridableAreas"):
            if isinstance(area.get(key), list) and area[key]:
                return True
    return False


def _capability(observed: bool) -> dict[str, str]:
    return {
        "state": CAPABILITY_SUPPORTED if observed else CAPABILITY_UNKNOWN,
        "source": CAPABILITY_SOURCE_OBSERVED if observed else CAPABILITY_SOURCE_UNKNOWN,
    }


def feature_capabilities(
    state: dict[str, Any],
    *,
    known_dock_pose: Any = None,
) -> dict[str, dict[str, str]]:
    """Return sparse evidence-based support; missing evidence stays unknown."""
    return {
        FEATURE_LIVE_MAP_STREAM: _capability(True),
        FEATURE_ABSOLUTE_PATH_DELTA: _capability(_path_supports_absolute_delta(state)),
        FEATURE_MAP_RASTER: _capability(_has_map_raster(state)),
        FEATURE_EDITABLE_BOUNDARY: _capability(_has_editable_boundary(state)),
        FEATURE_KNOWN_DOCK_POSITION: _capability(isinstance(known_dock_pose, dict)),
    }


@dataclass(frozen=True)
class _SnapshotEntry:
    context: tuple[Any, ...]
    payload: dict[str, Any]
    cursor: Any
    hardening_revision: tuple[Any, ...]
    geometry: str
    created_at: float


def _position_attributes(hub: Any, state: dict[str, Any], *, now: float) -> dict[str, Any]:
    geometry = hub._anthbot_geometry_fingerprint
    pose = validated_pose(state)
    observed = hub._anthbot_pose_observed_at
    pose_geometry = hub._anthbot_pose_geometry

    if pose is None or observed is None:
        status = "unavailable"
    elif pose_geometry != geometry:
        status = "map_mismatch"
    elif not 0.0 <= now - observed <= POSITION_MAX_AGE_SECONDS:
        status = "stale"
    else:
        status = "current"

    last_known = _fresh_scoped_record(
        hub._anthbot_last_known_pose,
        geometry=geometry,
        now=now,
        max_age=LAST_POSITION_MAX_AGE_SECONDS,
    )
    known_dock = _fresh_scoped_record(
        hub._anthbot_known_dock_pose,
        geometry=geometry,
        now=now,
        max_age=DOCK_POSITION_MAX_AGE_SECONDS,
    )

    result: dict[str, Any] = {
        "position_status": status,
        "position_observed_at": observed,
        "map_fingerprint": geometry,
        "last_known_pose": last_known,
        "known_dock_pose": known_dock,
        "feature_capabilities": feature_capabilities(state, known_dock_pose=known_dock),
    }
    if status != "current":
        # Never display an old or wrong-map coordinate as the live robot pose.
        result.update({"pose": None, "cur_pose": None, "map_scan_pose": None})
    return result


def _hardening_revision(attributes: dict[str, Any]) -> tuple[Any, ...]:
    capabilities = attributes.get("feature_capabilities") or {}
    capability_signature = tuple(
        (name, value.get("state"), value.get("source"))
        for name, value in sorted(capabilities.items())
        if isinstance(value, dict)
    )
    return (
        attributes.get("position_status"),
        _finite_number(attributes.get("position_observed_at")),
        attributes.get("map_fingerprint"),
        _position_record_signature(attributes.get("last_known_pose")),
        _position_record_signature(attributes.get("known_dock_pose")),
        capability_signature,
    )


def _geometry_payload(core: Any, state: dict[str, Any]) -> dict[str, Any]:
    map_definition = state.get("_map_definition")
    map_definition = map_definition if isinstance(map_definition, dict) else {}
    raster = map_definition.get("_map_raster")
    path_definition = state.get("_path_definition")
    path_definition = path_definition if isinstance(path_definition, dict) else {}
    return {
        "map_time": state.get("map_time"),
        "area_time": state.get("area_time"),
        "ridable_area_time": state.get("ridable_area_time"),
        "area_definition": state.get("_area_definition") or {},
        "ridable_areas": core._ridable_areas(state),  # noqa: SLF001
        "ridable_area_error": state.get("_ridable_area_definition_error"),
        "map_definition_status": core._definition_status(map_definition),  # noqa: SLF001
        "map_raster": raster if isinstance(raster, dict) else None,
        "map_binary_paths": core._binary_paths(map_definition),  # noqa: SLF001
        "path_binary_paths": core._binary_paths(path_definition),  # noqa: SLF001
        "map_definition_error": state.get("_map_definition_error"),
    }


def _snapshot_context(core: Any, state: dict[str, Any], geometry: str) -> tuple[Any, ...]:
    definition = state.get("_path_definition")
    definition = definition if isinstance(definition, dict) else {}
    points = core._path_points(state)  # noqa: SLF001
    first, last = core._absolute_path_bounds(definition, len(points))  # noqa: SLF001
    return (
        geometry,
        core._path_identity(state, definition),  # noqa: SLF001
        len(points),
        first,
        last,
        core._mapping_point_signature(points[-1]) if points else None,  # noqa: SLF001
        pose_revision_token(state),
    )


def _refresh_hub_observation(hub: Any, state: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    geometry_token = geometry_object_token(state)
    if geometry_token != hub._anthbot_geometry_object_token:
        hub._anthbot_geometry_object_token = geometry_token
        hub._anthbot_geometry_fingerprint = map_geometry_fingerprint(state)

    token = pose_revision_token(state)
    if token != hub._anthbot_pose_token:
        hub._anthbot_pose_token = token
        pose = validated_pose(state)
        if pose is not None:
            hub._anthbot_pose_observed_at = now
            hub._anthbot_pose_geometry = hub._anthbot_geometry_fingerprint
            record = _position_record(
                pose,
                observed_at=now,
                geometry=hub._anthbot_geometry_fingerprint,
                status="last_known",
            )
            hub._anthbot_last_known_pose = record
            # Only a fresh pose observed while already docked establishes dock
            # coordinates. A charging flag never manufactures a location.
            if mower_activity_name(state) == "docked":
                hub._anthbot_known_dock_pose = _position_record(
                    pose,
                    observed_at=now,
                    geometry=hub._anthbot_geometry_fingerprint,
                    status="known_dock",
                )
        else:
            hub._anthbot_pose_observed_at = None
            hub._anthbot_pose_geometry = None
    return state


async def _position_heartbeat(hub: Any) -> None:
    try:
        while not hub._closed:
            await asyncio.sleep(POSITION_HEARTBEAT_SECONDS)
            if hub._closed or not hub._subscribers:
                continue
            state = dict(hub.coordinator.reported_state)
            _refresh_hub_observation(hub, state)
            for subscriber in tuple(hub._subscribers.values()):
                hub._send_current_delta(subscriber, state)
    except asyncio.CancelledError:
        raise


def install_live_map_hardening() -> None:
    """Patch only the presentation transport; model decoders remain untouched."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import live_map_stream as stream
    from . import live_map_stream_core as core

    hub_type = stream.LiveMapHub
    original_init = hub_type.__init__
    original_close = hub_type.close
    original_compact_attributes = stream._compact_extra_state_attributes  # noqa: SLF001

    def patched_init(self: Any, hass: Any, coordinator: Any) -> None:
        original_init(self, hass, coordinator)
        state = dict(coordinator.reported_state)
        self._anthbot_geometry_object_token = geometry_object_token(state)
        self._anthbot_geometry_fingerprint = map_geometry_fingerprint(state)
        self._anthbot_pose_token = pose_revision_token(state)
        initial_pose = validated_pose(state)
        now = time.time()
        self._anthbot_pose_observed_at = now if initial_pose is not None else None
        self._anthbot_pose_geometry = (
            self._anthbot_geometry_fingerprint if initial_pose is not None else None
        )
        self._anthbot_last_known_pose = (
            _position_record(
                initial_pose,
                observed_at=now,
                geometry=self._anthbot_geometry_fingerprint,
                status="last_known",
            )
            if initial_pose is not None
            else None
        )
        # Never infer dock coordinates from an inherited charging state.
        self._anthbot_known_dock_pose = None
        self._anthbot_snapshot_lock = asyncio.Lock()
        self._anthbot_snapshot_inflight = None
        self._anthbot_snapshot_cache = None
        self._anthbot_position_heartbeat = hass.async_create_background_task(
            _position_heartbeat(self),
            f"anthbot_live_map_position_{self.serial_number}",
        )

    async def async_prepare_snapshot(self: Any, subscriber: Any) -> Any:
        if self._closed or subscriber.closed:
            return None

        while True:
            state = dict(self.coordinator.reported_state)
            _refresh_hub_observation(self, state)
            geometry = self._anthbot_geometry_fingerprint
            context = _snapshot_context(core, state, geometry)
            now_mono = time.monotonic()
            cached = self._anthbot_snapshot_cache
            if (
                isinstance(cached, _SnapshotEntry)
                and cached.context == context
                and now_mono - cached.created_at <= SNAPSHOT_CACHE_SECONDS
            ):
                subscriber._anthbot_hardening_revision = cached.hardening_revision
                subscriber._anthbot_geometry_fingerprint = cached.geometry
                return cached.payload, cached.cursor

            async with self._anthbot_snapshot_lock:
                cached = self._anthbot_snapshot_cache
                now_mono = time.monotonic()
                if (
                    isinstance(cached, _SnapshotEntry)
                    and cached.context == context
                    and now_mono - cached.created_at <= SNAPSHOT_CACHE_SECONDS
                ):
                    subscriber._anthbot_hardening_revision = cached.hardening_revision
                    subscriber._anthbot_geometry_fingerprint = cached.geometry
                    return cached.payload, cached.cursor

                task = self._anthbot_snapshot_inflight
                task_context = getattr(task, "_anthbot_snapshot_context", None)
                if task is None or task.done() or task_context != context:
                    if task is not None and not task.done() and task_context != context:
                        wait_for_previous = task
                    else:
                        wait_for_previous = None
                    if wait_for_previous is None:
                        snapshot_state = dict(state)

                        async def build() -> _SnapshotEntry:
                            payload, cursor = await self.hass.async_add_executor_job(
                                core.build_snapshot,
                                self.serial_number,
                                0,
                                snapshot_state,
                            )
                            attrs = _position_attributes(self, snapshot_state, now=time.time())
                            payload.setdefault("attributes", {}).update(attrs)
                            revision = _hardening_revision(attrs)
                            return _SnapshotEntry(
                                context,
                                payload,
                                cursor,
                                revision,
                                geometry,
                                time.monotonic(),
                            )

                        task = self.hass.async_create_background_task(
                            build(),
                            f"anthbot_live_map_snapshot_{self.serial_number}",
                        )
                        setattr(task, "_anthbot_snapshot_context", context)
                        self._anthbot_snapshot_inflight = task
                else:
                    wait_for_previous = None

            if wait_for_previous is not None:
                try:
                    await asyncio.shield(wait_for_previous)
                except Exception:  # noqa: BLE001 - retry against fresh state.
                    pass
                continue

            try:
                entry = await asyncio.shield(task)
            finally:
                if self._anthbot_snapshot_inflight is task and task.done():
                    self._anthbot_snapshot_inflight = None
            if self._closed or subscriber.closed:
                return None
            self._anthbot_snapshot_cache = entry
            subscriber._anthbot_hardening_revision = entry.hardening_revision
            subscriber._anthbot_geometry_fingerprint = entry.geometry
            return entry.payload, entry.cursor

    def send_current_delta(self: Any, subscriber: Any, state: Any = None) -> None:
        if not subscriber.ready or subscriber.closed or subscriber.cursor is None:
            return
        current_state = dict(state) if isinstance(state, dict) else dict(self.coordinator.reported_state)
        _refresh_hub_observation(self, current_state)
        next_sequence = subscriber.sequence + 1
        payload, cursor = core.build_delta(
            self.serial_number,
            next_sequence,
            subscriber.cursor,
            current_state,
        )
        subscriber.cursor = cursor

        attrs = _position_attributes(self, current_state, now=time.time())
        revision = _hardening_revision(attrs)
        previous_revision = getattr(subscriber, "_anthbot_hardening_revision", None)
        previous_geometry = getattr(subscriber, "_anthbot_geometry_fingerprint", None)
        geometry = self._anthbot_geometry_fingerprint

        if revision != previous_revision or geometry != previous_geometry:
            if payload is None:
                payload = {
                    "protocol": core.PROTOCOL_VERSION,
                    "kind": "delta",
                    "sequence": next_sequence,
                    "serial_number": self.serial_number,
                    "attributes": {},
                }
            payload.setdefault("attributes", {}).update(attrs)
            if geometry != previous_geometry:
                payload["attributes"].update(_geometry_payload(core, current_state))
            subscriber._anthbot_hardening_revision = revision
            subscriber._anthbot_geometry_fingerprint = geometry

        if payload is None:
            return
        subscriber.sequence = next_sequence
        self._send_event(subscriber, payload)

    def handle_coordinator_update(self: Any) -> None:
        if self._closed or not self._subscribers:
            return
        state = dict(self.coordinator.reported_state)
        _refresh_hub_observation(self, state)
        for subscriber in tuple(self._subscribers.values()):
            self._send_current_delta(subscriber, state)

    def patched_close(self: Any) -> None:
        heartbeat = getattr(self, "_anthbot_position_heartbeat", None)
        if heartbeat is not None and not heartbeat.done():
            heartbeat.cancel()
        self._anthbot_position_heartbeat = None
        original_close(self)

    def compact_attributes(sensor_module: Any, entity: Any) -> dict[str, Any]:
        attributes = original_compact_attributes(sensor_module, entity)
        state = entity.coordinator.reported_state
        attributes["map_fingerprint"] = map_geometry_fingerprint(state)
        attributes["feature_capabilities"] = feature_capabilities(state)
        return attributes

    hub_type.__init__ = patched_init
    hub_type.async_prepare_snapshot = async_prepare_snapshot
    hub_type._send_current_delta = send_current_delta
    hub_type._handle_coordinator_update = handle_coordinator_update
    hub_type.close = patched_close
    stream._compact_extra_state_attributes = compact_attributes  # noqa: SLF001
    _INSTALLED = True


__all__ = [
    "CAPABILITY_SUPPORTED",
    "CAPABILITY_UNSUPPORTED",
    "CAPABILITY_UNKNOWN",
    "DOCK_POSITION_MAX_AGE_SECONDS",
    "LAST_POSITION_MAX_AGE_SECONDS",
    "POSITION_MAX_AGE_SECONDS",
    "feature_capabilities",
    "geometry_object_token",
    "install_live_map_hardening",
    "map_geometry_fingerprint",
    "pose_revision_token",
    "validated_pose",
]
