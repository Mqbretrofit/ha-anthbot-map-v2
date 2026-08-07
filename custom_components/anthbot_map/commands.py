"""Reliable Anthbot command sequences."""

from __future__ import annotations

import asyncio
import logging

from .api import AnthbotGenieApiError
from .coordinator import AnthbotGenieDataUpdateCoordinator, is_robot_online

_LOGGER = logging.getLogger(__name__)


async def async_prepare_cloud_connection(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    *,
    attempts: int = 2,
    wait_seconds: int = 4,
) -> bool:
    """Emulate opening the app and wait for a fresh mower shadow response."""
    for attempt in range(attempts):
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
            try:
                state = await coordinator.client.async_get_shadow_reported_state()
            except Exception:  # noqa: BLE001 - keep waiting within this attempt.
                continue
            if is_robot_online(state, max_age_seconds=45):
                await coordinator.async_request_refresh()
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

    await coordinator.async_request_refresh()
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
            try:
                state = await coordinator.client.async_get_shadow_reported_state()
            except Exception:  # noqa: BLE001 - verification is retried below.
                continue
            robot_sta = state.get("robot_sta")
            mode = robot_sta.get("value") if isinstance(robot_sta, dict) else None
            mode = str(mode or state.get("mower_status") or "").lower()
            if mode in expected:
                await coordinator.async_request_refresh()
                return True

        _LOGGER.warning(
            "Anthbot start was not confirmed for %s (attempt %s/2)",
            coordinator.client.serial_number,
            attempt + 1,
        )

    await coordinator.async_request_refresh()
    return False
