"""Additional regression guards for the stable v2.4.7.2 live-map transport.

These tests deliberately protect the already field-tested WebSocket architecture
instead of introducing a second map transport.  In particular, delayed M-series
and N8 absolute-index chunks must never corrupt the browser-side trajectory.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
CORE_PATH = INTEGRATION / "live_map_stream_core.py"

spec = spec_from_file_location("anthbot_live_map_stream_v2472_test", CORE_PATH)
core = module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def point(index: int, *, break_before: bool = False) -> dict:
    value = {"x": index, "y": 0, "type": 1}
    if break_before:
        value["break_before"] = True
    return value


def sparse_state(
    indices: list[int],
    *,
    path_id: str = "live-7",
    first: int | None = None,
    last: int | None = None,
) -> dict:
    points: list[dict] = []
    previous: int | None = None
    for index in indices:
        points.append(point(index, break_before=previous is not None and index != previous + 1))
        previous = index

    definition = {
        "path_id": path_id,
        "point_count": len(points),
        "coordinate_scale": 10,
        "_path_points": points,
    }
    if first is not None:
        definition["_m_series_first_index"] = first
    if last is not None:
        definition["_m_series_last_index"] = last

    return {
        "_path_definition": definition,
        "path_time": len(points),
        "pose": {"x": indices[-1] if indices else 0, "y": 0, "yaw": 0},
        "_map_definition": {
            "map_id": "map-1",
            "_map_raster": {
                "width": 10,
                "height": 10,
                "bounds": {"min_x": 0, "max_x": 10, "min_y": 0, "max_y": 10},
            },
        },
        "_area_definition": {},
    }


class TestLiveMapStreamV2472Hardening(unittest.TestCase):
    def test_delayed_middle_chunk_forces_safe_reset(self) -> None:
        """Filling an old gap must reset, not append shifted list positions."""
        before = sparse_state([0, 1, 4, 5], first=0, last=5)
        _snapshot, cursor = core.build_snapshot("SERIAL", 0, before)
        self.assertIsNone(cursor.path_first_index)
        self.assertIsNone(cursor.path_last_index)

        after = sparse_state([0, 1, 2, 3, 4, 5], first=0, last=5)
        payload, current = core.build_delta("SERIAL", 1, cursor, after)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["path"]["op"], "reset")
        self.assertEqual([item["x"] for item in payload["path"]["points"]], [0, 1, 2, 3, 4, 5])
        self.assertEqual(current.path_first_index, 0)
        self.assertEqual(current.path_last_index, 5)

    def test_sparse_tail_growth_can_stay_incremental(self) -> None:
        """A still-sparse path may append at its tail without resending it all."""
        before = sparse_state([0, 1, 4, 5], first=0, last=5)
        _snapshot, cursor = core.build_snapshot("SERIAL", 0, before)

        after = sparse_state([0, 1, 4, 5, 6], first=0, last=6)
        payload, _current = core.build_delta("SERIAL", 1, cursor, after)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["path"]["op"], "append")
        self.assertEqual(payload["path"]["append_from_index"], 4)
        self.assertEqual([item["x"] for item in payload["path"]["points"]], [6])

    def test_path_id_change_never_mixes_sessions(self) -> None:
        before = sparse_state([0, 1, 2], path_id="old", first=0, last=2)
        _snapshot, cursor = core.build_snapshot("SERIAL", 0, before)
        after = sparse_state([0, 1], path_id="new", first=0, last=1)

        payload, _current = core.build_delta("SERIAL", 1, cursor, after)

        self.assertEqual(payload["path"]["op"], "reset")
        self.assertEqual(payload["path"]["path_id"], "new")

    def test_websocket_transport_reads_coordinator_cache_only(self) -> None:
        """Opening a dashboard must not turn into cloud or coordinator refresh I/O."""
        source = (INTEGRATION / "live_map_stream.py").read_text(encoding="utf-8")
        self.assertIn("self.coordinator.reported_state", source)
        self.assertIn("_build_snapshot_frozen", source)
        self.assertIn("_build_delta_frozen", source)
        self.assertIn("self.hass.async_add_executor_job", source)
        self.assertNotIn("await self.coordinator.async_refresh", source)
        self.assertNotIn("await coordinator.async_refresh", source)
        self.assertNotIn("account_client.", source)
        self.assertNotIn("shadow_client.", source)

    def test_serial_lookup_has_no_cross_mower_fallback(self) -> None:
        source = (INTEGRATION / "live_map_stream.py").read_text(encoding="utf-8")
        self.assertIn('hub = hubs.get(msg["serial_number"])', source)
        self.assertIn('"not_found"', source)

    def test_frontend_keeps_downgrade_fallback(self) -> None:
        source = (INTEGRATION / "frontend" / "live-map-stream.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("attributes.live_stream_available !== true", source)
        self.assertIn("originalStartRefreshTimer", source)
        self.assertIn("originalRefreshEntities", source)
        self.assertIn("sequence gap", source)
        self.assertIn("path continuity mismatch", source)


if __name__ == "__main__":
    unittest.main()
