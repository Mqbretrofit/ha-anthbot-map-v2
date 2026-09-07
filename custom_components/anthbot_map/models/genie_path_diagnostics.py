"""Read-only no-go crossing diagnostics for Genie mower paths.

Genie keeps the proven shared coordinator/path decoding untouched.  This layer
only inspects the already decoded path exposed by that coordinator and records
diagnostics in ``_no_go_path_check`` for the existing problem binary sensor.
It never filters, rewrites, rejects or otherwise changes mower telemetry.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..path_zone_check import evaluate_path_no_go, no_go_geometry_signature
from .base import model_family

if TYPE_CHECKING:
    from ..coordinator import AnthbotGenieDataUpdateCoordinator

_INSTALLED = False


def _genie_path_definition(state: dict[str, Any]) -> dict[str, Any] | None:
    definition = state.get("_path_definition")
    return definition if isinstance(definition, dict) else None


def _genie_path_points(state: dict[str, Any]) -> list[Any]:
    """Return the decoded Genie trajectory without changing its representation."""
    definition = _genie_path_definition(state)
    if isinstance(definition, dict):
        points = definition.get("_path_points")
        if isinstance(points, list):
            return points

    for key in ("path", "mowed_path", "cloud_path", "trajectory"):
        points = state.get(key)
        if isinstance(points, list):
            return points
    return []


def _genie_path_id(state: dict[str, Any]) -> Any:
    definition = _genie_path_definition(state)
    if isinstance(definition, dict) and definition.get("path_id") is not None:
        return definition.get("path_id")
    return state.get("path_id")


def _point_token(point: Any) -> tuple[Any, ...] | None:
    if not isinstance(point, dict):
        return None
    return (
        point.get("x"),
        point.get("y"),
        point.get("type"),
        point.get("break_before"),
    )


def _update_no_go_check(
    coordinator: Any,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate a Genie path only when path or no-go geometry changed."""
    points = _genie_path_points(state)
    path_id = _genie_path_id(state)
    signature = (
        id(points),
        len(points),
        path_id,
        state.get("path_time"),
        _point_token(points[0]) if points else None,
        _point_token(points[-1]) if points else None,
        no_go_geometry_signature(state),
    )
    if getattr(coordinator, "_genie_no_go_check_signature", None) == signature:
        cached = getattr(coordinator, "_genie_no_go_check", None)
        if isinstance(cached, dict):
            return cached

    check = evaluate_path_no_go(points, state, path_id=path_id)
    check["source"] = "genie_decoded_path"
    coordinator._genie_no_go_check_signature = signature
    coordinator._genie_no_go_check = check
    return check


def _pending_genie_state(coordinator: Any) -> dict[str, Any]:
    """Build the state that will be visible after the pending live flush."""
    current = getattr(coordinator, "reported_state", {})
    state = dict(current) if isinstance(current, dict) else {}

    pending_property = getattr(coordinator, "_pending_live_property", None)
    if isinstance(pending_property, dict) and pending_property:
        state.update(pending_property)

    pending_service = getattr(coordinator, "_pending_live_service", None)
    if isinstance(pending_service, dict) and pending_service:
        existing = state.get("_service_reported")
        service = dict(existing) if isinstance(existing, dict) else {}
        service.update(pending_service)
        state["_service_reported"] = service
    return state


def install_genie_path_diagnostics() -> None:
    """Attach no-go diagnostics to Genie periodic and live state updates."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # Imported lazily so this module's pure helpers stay unit-testable without
    # importing Home Assistant itself.
    from ..coordinator import AnthbotGenieDataUpdateCoordinator

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__
    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        if model_family(getattr(self.device, "model", None)) == "genie":
            self._genie_no_go_check_signature = None
            self._genie_no_go_check = None

    async def live_shadow(
        self: AnthbotGenieDataUpdateCoordinator,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        await previous_live(self, shadow_name, reported)
        if model_family(getattr(self.device, "model", None)) != "genie":
            return

        state = _pending_genie_state(self)
        check = _update_no_go_check(self, state)
        pending = getattr(self, "_pending_live_property", None)
        if isinstance(pending, dict):
            # Let the normal coordinator flush publish the diagnostic together
            # with the telemetry that produced it. No extra HA update is forced.
            pending["_no_go_path_check"] = check

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        if (
            model_family(getattr(self.device, "model", None)) != "genie"
            or not isinstance(state, dict)
        ):
            return state
        result = dict(state)
        result["_no_go_path_check"] = _update_no_go_check(self, result)
        return result

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
