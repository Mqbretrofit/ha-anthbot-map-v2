"""Reliable Anthbot command sequences."""

from __future__ import annotations

import asyncio
import logging

from .api import AnthbotGenieApiError
from .coordinator import AnthbotGenieDataUpdateCoordinator, is_robot_online
from .m_series_compat import install_m_series_compat

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("ANTHBOT TEST: commands.py loaded")

# __init__.py imports this module before any mower coordinator is created, so
# install the model-aware shadow behavior here without touching Genie paths.
install_m_series_compat()


async def async_prepare_cloud_connection(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    *,
    attempts: int = 2,
    wait_seconds: int = 4,
) -> bool:
    """Request app-style MQTT properties and wait for live shadow state."""
    for attempt in range(attempts):
        if not coordinator.live_shadow_connected:
            await asyncio.sleep(1)
            if not coordinator.live_shadow_connected:
                continue
        try:
            await coordinator.client.async_request_all_properties()
        except Exception as err:  # noqa: BLE001 - retry the wake handshake.
            _LOGGER.warning(
                "Anthbot cloud wake request failed for %s (%s/%s): %s",
                coordinator.client.serial_number,
                attempt + 1,
                attempts,
                err,
            )
            continue

        for _ in range(wait_seconds):
            await asyncio.sleep(1)
            state = coordinator.reported_state
            if is_robot_online(state, max_age_seconds=45):
                _LOGGER.debug(
                    "Anthbot cloud wake confirmed for %s",
                    coordinator.client.serial_number,
                )
                return True

        _LOGGER.warning(
            "Anthbot cloud wake was not confirmed for %s (%s/%s)",
            coordinator.client.serial_number,
            attempt + 1,
            attempts,
        )

    return False


async def async_start_mowing(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    *,
    app_state: int = 1,
    expected_modes: set[str] | None = None,
) -> bool:
    """Wake the mower, start it, verify the mode and retry once if needed."""
    expected = expected_modes or {"globalmowing", "mowing", "gototarget"}

    if not await async_prepare_cloud_connection(coordinator):
        raise AnthbotGenieApiError(
            "The mower did not confirm its cloud connection; start command was not sent"
        )

    for attempt in range(2):
        await coordinator.client.async_publish_service_command(
            cmd="app_state", data=app_state
        )
        await asyncio.sleep(1.5)
        await coordinator.client.async_publish_service_command(cmd="mow_start", data=1)

        for _ in range(4):
            await asyncio.sleep(2)
            state = coordinator.reported_state
            robot_sta = state.get("robot_sta")
            mode = robot_sta.get("value") if isinstance(robot_sta, dict) else None
            if mode is None:
                m_series_mode = state.get("mode")
                mode = (
                    m_series_mode.get("value")
                    if isinstance(m_series_mode, dict)
                    else m_series_mode
                )
            mode = str(mode or state.get("mower_status") or "").lower()
            if mode in expected:
                return True

        _LOGGER.warning(
            "Anthbot start was not confirmed for %s (attempt %s/2)",
            coordinator.client.serial_number,
            attempt + 1,
        )

    return False


async def async_start_outer_edge_mowing(
    coordinator: AnthbotGenieDataUpdateCoordinator,
) -> bool:
    """Start outer-edge mowing with the command used by the official app."""
    if not await async_prepare_cloud_connection(coordinator):
        raise AnthbotGenieApiError(
            "The mower did not confirm its cloud connection; edge command was not sent"
        )

    expected = {"bordermowing", "edgemowing", "gototarget"}
    for attempt in range(2):
        await coordinator.client.async_publish_service_command(
            cmd="ridable_mow_start", data=1
        )

        for _ in range(4):
            await asyncio.sleep(2)
            state = coordinator.reported_state
            robot_sta = state.get("robot_sta")
            mode = robot_sta.get("value") if isinstance(robot_sta, dict) else None
            if mode is None:
                m_series_mode = state.get("mode")
                mode = (
                    m_series_mode.get("value")
                    if isinstance(m_series_mode, dict)
                    else m_series_mode
                )
            mode = str(mode or state.get("mower_status") or "").lower()
            if mode in expected:
                return True

        _LOGGER.warning(
            "Anthbot outer-edge start was not confirmed for %s (attempt %s/2)",
            coordinator.client.serial_number,
            attempt + 1,
        )

    return False
