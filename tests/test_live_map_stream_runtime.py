"""Behavior tests for live-map hot-path runtime helpers."""

from __future__ import annotations

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1]
MODULE_PATH = (
    ROOT
    / "custom_components"
    / "anthbot_map"
    / "live_map_stream_runtime.py"
)
spec = spec_from_file_location("anthbot_live_map_stream_runtime_test", MODULE_PATH)
module = module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TestLiveMapStateFreeze(unittest.TestCase):
    def test_path_list_is_frozen_without_deep_copying_points(self) -> None:
        first = {"x": 1, "y": 2}
        second = {"x": 3, "y": 4}
        points = [first, second]
        fallback = [first, second]
        state = {
            "_path_definition": {
                "path_id": "p1",
                "_path_points": points,
            },
            "path": fallback,
        }

        frozen = module.freeze_live_state(state)

        points.append({"x": 5, "y": 6})
        fallback.append({"x": 7, "y": 8})
        state["_path_definition"]["path_id"] = "p2"

        self.assertIsNot(frozen, state)
        self.assertIsNot(frozen["_path_definition"], state["_path_definition"])
        self.assertEqual(frozen["_path_definition"]["path_id"], "p1")
        self.assertEqual(len(frozen["_path_definition"]["_path_points"]), 2)
        self.assertEqual(len(frozen["path"]), 2)
        self.assertIs(frozen["_path_definition"]["_path_points"][0], first)


class TestLatestOnlyCoalescer(unittest.IsolatedAsyncioTestCase):
    async def test_rapid_triggers_collapse_into_one_run(self) -> None:
        calls = 0

        async def runner() -> None:
            nonlocal calls
            calls += 1

        coalescer = module.LatestOnlyCoalescer(runner, delay=0.05)
        self.addCleanup(coalescer.close)

        coalescer.trigger()
        await asyncio.sleep(0.01)
        coalescer.trigger()
        await asyncio.sleep(0.01)
        coalescer.trigger()

        await asyncio.sleep(0.08)
        self.assertEqual(calls, 1)

    async def test_trigger_during_inflight_run_schedules_one_followup(self) -> None:
        calls = 0
        concurrent = 0
        max_concurrent = 0
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def runner() -> None:
            nonlocal calls, concurrent, max_concurrent
            calls += 1
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            try:
                if calls == 1:
                    first_started.set()
                    await release_first.wait()
            finally:
                concurrent -= 1

        coalescer = module.LatestOnlyCoalescer(runner, delay=0.01)
        self.addCleanup(coalescer.close)

        coalescer.trigger()
        await asyncio.wait_for(first_started.wait(), timeout=0.2)
        coalescer.trigger()
        coalescer.trigger()
        release_first.set()

        await asyncio.sleep(0.06)
        self.assertEqual(calls, 2)
        self.assertEqual(max_concurrent, 1)


if __name__ == "__main__":
    unittest.main()
