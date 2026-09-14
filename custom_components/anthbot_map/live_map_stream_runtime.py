"""Small runtime helpers for the dedicated ANTHBOT live-map transport.

This module intentionally has no Home Assistant imports so the hot-path
coalescing and state-freeze behavior can be regression-tested without a Home
Assistant runtime.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

DEFAULT_DELTA_COALESCE_SECONDS = 0.05


def freeze_live_state(state: dict[str, Any]) -> dict[str, Any]:
    """Freeze the mutable path container used by snapshot/delta builders.

    Coordinator updates normally replace the top-level reported-state mapping,
    but the assembled ``_path_points`` list can be extended while an executor
    job is preparing a frame.  Copy only the path container and point list;
    individual point mappings are immutable for live-map purposes and do not
    need an expensive deep copy.
    """
    frozen = dict(state)

    definition = state.get("_path_definition")
    if isinstance(definition, dict):
        frozen_definition = dict(definition)
        points = definition.get("_path_points")
        if isinstance(points, list):
            frozen_definition["_path_points"] = list(points)
        frozen["_path_definition"] = frozen_definition

    fallback_path = state.get("path")
    if isinstance(fallback_path, list):
        frozen["path"] = list(fallback_path)

    return frozen


class LatestOnlyCoalescer:
    """Run one async job at a time while collapsing bursts to the latest state."""

    def __init__(
        self,
        runner: Callable[[], Awaitable[None]],
        *,
        delay: float = DEFAULT_DELTA_COALESCE_SECONDS,
        task_factory: Callable[[Awaitable[None]], Any] | None = None,
    ) -> None:
        self._runner = runner
        self._delay = max(0.0, float(delay))
        self._task_factory = task_factory or asyncio.create_task
        self._task: Any = None
        self._dirty = False
        self._closed = False

    @property
    def active(self) -> bool:
        task = self._task
        return task is not None and not task.done()

    def trigger(self) -> None:
        """Mark work dirty and ensure exactly one worker is scheduled."""
        if self._closed:
            return
        self._dirty = True
        if self.active:
            return
        self._task = self._task_factory(self._run())

    async def _run(self) -> None:
        try:
            while not self._closed:
                if not self._dirty:
                    return

                # Start a short debounce window. Any number of triggers during
                # this sleep are represented by the single run below.
                self._dirty = False
                if self._delay:
                    await asyncio.sleep(self._delay)
                if self._closed:
                    return

                # Triggers received during the debounce window are consumed by
                # this run. Triggers received while the runner itself is in
                # flight set _dirty again and cause one later run.
                self._dirty = False
                await self._runner()
        finally:
            self._task = None
            # There is no await between the loop exit and this check, so a
            # trigger cannot be lost in the task hand-off on the event loop.
            if self._dirty and not self._closed:
                self.trigger()

    def close(self) -> None:
        """Stop pending work and prevent future scheduling."""
        self._closed = True
        self._dirty = False
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()


__all__ = [
    "DEFAULT_DELTA_COALESCE_SECONDS",
    "LatestOnlyCoalescer",
    "freeze_live_state",
]
