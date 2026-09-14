"""Regression coverage for Recorder-aware Anthbot location writes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "anthbot_map"

spec = importlib.util.spec_from_file_location(
    "anthbot_location_recorder_test_module",
    PACKAGE_DIR / "location_recorder.py",
)
assert spec and spec.loader
location_recorder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = location_recorder
spec.loader.exec_module(location_recorder)


class TestLocationRecorderHardening(unittest.TestCase):
    def snapshot(
        self,
        *,
        lat: float | None = 47.0,
        lon: float | None = 19.0,
        pose_type: object = 1,
        available: bool = True,
    ):
        return location_recorder.location_snapshot(
            latitude=lat,
            longitude=lon,
            pose_type=pose_type,
            available=available,
        )

    def test_first_update_is_written(self) -> None:
        self.assertTrue(
            location_recorder.should_write_location_state(
                None,
                self.snapshot(),
                last_write=0.0,
                now=100.0,
            )
        )

    def test_stationary_jitter_is_suppressed_until_heartbeat(self) -> None:
        previous = self.snapshot()
        # About 3.8 metres east at this latitude: below the 5 m jitter threshold.
        jitter = self.snapshot(lon=19.00005)
        self.assertFalse(
            location_recorder.should_write_location_state(
                previous,
                jitter,
                last_write=100.0,
                now=200.0,
            )
        )
        self.assertTrue(
            location_recorder.should_write_location_state(
                previous,
                jitter,
                last_write=100.0,
                now=100.0 + location_recorder.TRACKER_HEARTBEAT_SECONDS,
            )
        )

    def test_real_movement_waits_for_30_second_write_limit(self) -> None:
        previous = self.snapshot()
        # About 7.6 metres east at this latitude: clearly significant movement.
        moved = self.snapshot(lon=19.00010)
        self.assertGreater(
            location_recorder.location_distance_meters(previous, moved),
            location_recorder.TRACKER_SIGNIFICANT_MOVEMENT_METERS,
        )
        self.assertFalse(
            location_recorder.should_write_location_state(
                previous,
                moved,
                last_write=100.0,
                now=120.0,
            )
        )
        self.assertTrue(
            location_recorder.should_write_location_state(
                previous,
                moved,
                last_write=100.0,
                now=130.0,
            )
        )

    def test_availability_and_pose_type_transitions_are_immediate(self) -> None:
        previous = self.snapshot()
        unavailable = self.snapshot(available=False)
        changed_pose_type = self.snapshot(pose_type=2)

        self.assertTrue(
            location_recorder.should_write_location_state(
                previous,
                unavailable,
                last_write=100.0,
                now=101.0,
            )
        )
        self.assertTrue(
            location_recorder.should_write_location_state(
                previous,
                changed_pose_type,
                last_write=100.0,
                now=101.0,
            )
        )

    def test_position_presence_transition_is_immediate(self) -> None:
        previous = self.snapshot()
        missing = self.snapshot(lat=None, lon=None)
        self.assertTrue(
            location_recorder.should_write_location_state(
                previous,
                missing,
                last_write=100.0,
                now=101.0,
            )
        )

    def test_invalid_coordinates_are_not_treated_as_positions(self) -> None:
        invalid = location_recorder.location_snapshot(
            latitude=float("nan"),
            longitude=19.0,
            pose_type=1,
            available=True,
        )
        self.assertIsNone(invalid.latitude)
        self.assertIsNone(invalid.longitude)

    def test_runtime_wiring_does_not_touch_live_map_transport(self) -> None:
        tracker_source = (PACKAGE_DIR / "device_tracker.py").read_text(encoding="utf-8")
        self.assertIn("should_write_location_state(", tracker_source)
        self.assertIn("super()._handle_coordinator_update()", tracker_source)
        self.assertIn("_anthbot_location_recorder_snapshot", tracker_source)

        helper_source = (PACKAGE_DIR / "location_recorder.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("live_map_stream", helper_source)
        self.assertNotIn("account_client", helper_source)
        self.assertNotIn("shadow_client", helper_source)
        self.assertNotIn("async_refresh", helper_source)

    def test_existing_v2465_guard_remains_intact(self) -> None:
        source = (
            PACKAGE_DIR / "models" / "reliability_v2465.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_POSITION_STATE_MIN_SECONDS = 10.0", source)
        self.assertIn("_anthbot_last_location_write", source)


if __name__ == "__main__":
    unittest.main()
