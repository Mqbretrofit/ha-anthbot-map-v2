"""Guard automatic diagnostics against duplicate cloud-error floods.

Field reports from M9 and N8 show AWS XML errors may be truncated in the
middle of RequestId/HostId values.  Those values are request-specific, so they
must never participate in the automatic diagnostics signature.  In addition,
a missing optional multi_maps object is not an actionable map failure while a
usable live/path fallback is already present.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator

_INSTALLED = False
_PLATFORM_PATCHED = False
_DIAGNOSTIC_CLEAR_GRACE_SECONDS = 60.0
_DIAGNOSTIC_HARD_REPEAT_SECONDS = 60.0 * 60.0

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
# AWS/XML bodies in field diagnostics are sometimes truncated before the
# closing tag.  Match both complete and cut-off forms without consuming the
# next XML element when a closing tag is present.
_REQUEST_ID_RE = re.compile(
    r"<RequestId>[^<]*(?:</RequestId>)?",
    re.IGNORECASE | re.DOTALL,
)
_HOST_ID_RE = re.compile(
    r"<HostId>[^<]*(?:</HostId>)?",
    re.IGNORECASE | re.DOTALL,
)

_ERROR_KEYS = {
    "path_definition_error": "_path_definition_error",
    "map_definition_error": "_map_definition_error",
    "live_shadow_error": "_live_shadow_error",
}


def _stable_error_text(value: object) -> str:
    """Remove request-specific cloud noise while preserving the real error."""
    text = str(value or "")
    text = _URL_RE.sub("<url>", text)
    text = _REQUEST_ID_RE.sub("<RequestId>", text)
    text = _HOST_ID_RE.sub("<HostId>", text)
    return " ".join(text.split())[:2048]


def _stable_error_signature(trigger: str, value: object) -> str:
    """Return a deterministic signature independent of AWS request metadata."""
    normalized = _stable_error_text(value)
    digest = hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:20]
    return f"{trigger}:{digest}"


def _state_has_usable_map_fallback(state: dict[str, Any]) -> bool:
    """Return whether live/path data is already usable without multi_maps."""
    if state.get("map_time") not in (None, "", 0, False):
        return True

    archive = state.get("_map_archive_selection")
    if isinstance(archive, dict):
        for key in ("live_file", "live_map_time", "map_time"):
            if archive.get(key) not in (None, "", 0, False):
                return True

    definition = state.get("_path_definition")
    if isinstance(definition, dict):
        points = definition.get("_path_points")
        if isinstance(points, list) and bool(points):
            return True

    for key in ("path", "mowed_path", "cloud_path"):
        points = state.get(key)
        if isinstance(points, list) and bool(points):
            return True

    history_source = str(state.get("_history_path_source") or "").lower()
    if history_source in {"m_series_curpath", "n8_curpath"}:
        return True

    return False


def _is_expected_optional_map_miss(
    state: dict[str, Any], value: object
) -> bool:
    """Return whether multi_maps NoSuchKey is harmless due to a live fallback."""
    text = str(value or "")
    lowered = text.lower()
    if "nosuchkey" not in lowered:
        return False
    if "multi_maps" not in lowered:
        return False
    return _state_has_usable_map_fallback(state)


def _patch_platform_modules() -> None:
    """Install stable trigger signatures and the episode-aware report listener."""
    global _PLATFORM_PATCHED
    if _PLATFORM_PATCHED:
        return
    _PLATFORM_PATCHED = True

    from .. import button as button_module

    previous_trigger = button_module._automatic_diagnostics_trigger  # noqa: SLF001

    def guarded_automatic_diagnostics_trigger(
        state: dict[str, Any],
    ) -> tuple[str, str] | None:
        detected = previous_trigger(state)
        if detected is None:
            return None

        trigger, signature = detected
        error_key = _ERROR_KEYS.get(trigger)
        if error_key is None:
            return trigger, signature

        value = state.get(error_key)
        if trigger == "map_definition_error" and _is_expected_optional_map_miss(
            state, value
        ):
            return None

        return trigger, _stable_error_signature(trigger, value)

    button_module._automatic_diagnostics_trigger = (  # noqa: SLF001
        guarded_automatic_diagnostics_trigger
    )

    def install_guarded_automatic_diagnostics(
        hass: Any,
        entry: Any,
        coordinator: AnthbotGenieDataUpdateCoordinator,
    ) -> None:
        # Platform reloads must not add a second listener to one coordinator.
        existing = getattr(coordinator, "_anthbot_auto_diag_listener_remove", None)
        if callable(existing):
            return

        initial_state = coordinator.reported_state
        initial = (
            guarded_automatic_diagnostics_trigger(initial_state)
            if isinstance(initial_state, dict)
            else None
        )
        coordinator._anthbot_auto_diag_active_signature = (  # type: ignore[attr-defined]
            initial[1] if initial is not None else None
        )
        coordinator._anthbot_auto_diag_clear_since = None  # type: ignore[attr-defined]
        if not isinstance(
            getattr(coordinator, "_anthbot_auto_diag_last_sent", None), dict
        ):
            coordinator._anthbot_auto_diag_last_sent = {}  # type: ignore[attr-defined]

        def handle_update() -> None:
            if not button_module._entry_option_enabled(  # noqa: SLF001
                entry,
                button_module.CONF_SEND_AUTOMATIC_DIAGNOSTICS,
            ):
                return

            installation_id = entry.data.get(
                button_module.CONF_DEVELOPER_INSTALLATION_ID
            )
            if not isinstance(installation_id, str) or not installation_id:
                return

            state = coordinator.reported_state
            if not isinstance(state, dict):
                return

            now = time.monotonic()
            detected = guarded_automatic_diagnostics_trigger(state)
            active_signature = getattr(
                coordinator, "_anthbot_auto_diag_active_signature", None
            )
            clear_since = getattr(
                coordinator, "_anthbot_auto_diag_clear_since", None
            )

            if detected is None:
                if active_signature is not None and clear_since is None:
                    coordinator._anthbot_auto_diag_clear_since = now  # type: ignore[attr-defined]
                return

            trigger, signature = detected
            if clear_since is not None:
                if now - float(clear_since) >= _DIAGNOSTIC_CLEAR_GRACE_SECONDS:
                    active_signature = None
                    coordinator._anthbot_auto_diag_active_signature = None  # type: ignore[attr-defined]
                coordinator._anthbot_auto_diag_clear_since = None  # type: ignore[attr-defined]

            # Robot error codes already have their dedicated reporting path.
            if trigger == "mower_error_code":
                coordinator._anthbot_auto_diag_active_signature = signature  # type: ignore[attr-defined]
                return
            if signature == active_signature:
                return

            sent_at = coordinator._anthbot_auto_diag_last_sent  # type: ignore[attr-defined]
            previous = sent_at.get(signature)
            coordinator._anthbot_auto_diag_active_signature = signature  # type: ignore[attr-defined]
            if (
                previous is not None
                and now - float(previous) < _DIAGNOSTIC_HARD_REPEAT_SECONDS
            ):
                return

            report = button_module.build_firmware_diagnostics_report(
                coordinator,
                include_raw_state=False,
                include_identifiers=False,
            )
            sent_at[signature] = now
            session = button_module.async_get_clientsession(hass)
            hass.async_create_task(
                button_module.async_send_diagnostics_report(
                    session,
                    button_module.DEVELOPER_DIAGNOSTICS_ENDPOINT,
                    installation_id=installation_id,
                    report=report,
                    trigger=trigger,
                )
            )

        unsubscribe = coordinator.async_add_listener(handle_update)
        coordinator._anthbot_auto_diag_listener_remove = unsubscribe  # type: ignore[attr-defined]

        def remove_listener() -> None:
            current = getattr(
                coordinator, "_anthbot_auto_diag_listener_remove", None
            )
            if callable(current):
                current()
            coordinator._anthbot_auto_diag_listener_remove = None  # type: ignore[attr-defined]

        entry.async_on_unload(remove_listener)

    button_module._install_automatic_diagnostics_reporting = (  # noqa: SLF001
        install_guarded_automatic_diagnostics
    )


def install_diagnostic_flood_guard() -> None:
    """Install after v2.4.6.5 reliability so this guard is the final reporter."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: Any, *args: Any, **kwargs: Any) -> None:
        # v2.4.6.5's wrapper runs first and installs its base reliability patch;
        # this guard then becomes the final automatic diagnostics implementation.
        previous_init(self, *args, **kwargs)
        _patch_platform_modules()

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init


__all__ = ["install_diagnostic_flood_guard"]
