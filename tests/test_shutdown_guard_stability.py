"""Regression coverage for recurring Battery Saver shutdown-guard pulses."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"
STABILITY = COMPONENT / "models" / "shutdown_guard_stability.py"


class ShutdownGuardStabilityTests(unittest.TestCase):
    def test_guard_waits_for_smart_plug_off_before_next_cycle(self) -> None:
        source = STABILITY.read_text(encoding="utf-8")
        common = (COMPONENT / "models" / "m_series_common.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("_SHUTDOWN_GUARD_STATE_SETTLE_SECONDS = 12.0", source)
        self.assertIn(
            "asyncio.current_task() is self._battery_saver_shutdown_guard_task",
            source,
        )
        self.assertIn('if switch_value == "off":', source)
        self.assertIn("await asyncio.sleep(", source)
        self.assertIn("self._battery_saver_shutdown_guard_due_at is None", source)
        self.assertIn("install_shutdown_guard_state_settle()", common)

    def test_fix_does_not_change_normal_battery_saver_transitions(self) -> None:
        source = STABILITY.read_text(encoding="utf-8")
        guarded_block = source.split("# Only the OFF transition", 1)[1]

        self.assertIn("enabled", guarded_block)
        self.assertIn("guard_pulse", guarded_block)
        self.assertIn("not caller_is_guard", guarded_block)
        self.assertIn("not self._battery_saver_enabled", guarded_block)


if __name__ == "__main__":
    unittest.main()
