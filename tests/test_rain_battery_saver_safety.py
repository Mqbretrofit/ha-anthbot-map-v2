"""Regression coverage for rain-safe Battery Saver and Shutdown Guard behavior."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"
RAIN_SAFETY = COMPONENT / "models" / "rain_battery_saver.py"


class RainBatterySaverSafetyTests(unittest.TestCase):
    def test_1038_is_treated_as_rain_hold_for_battery_saver(self) -> None:
        source = RAIN_SAFETY.read_text(encoding="utf-8")
        common = (COMPONENT / "models" / "m_series_common.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("_RAIN_PROTECTION_EVENT_CODE = 1038", source)
        self.assertIn("coordinator_module._RAIN_RETURN_EVENT_CODE", source)
        self.assertIn("_RAIN_PROTECTION_EVENT_CODE,", source)
        self.assertIn('return "rain_return"', source)
        self.assertIn("_live_rain_protection(self)", source)
        self.assertIn("install_rain_battery_saver_safety()", common)
        self.assertGreater(
            common.index("install_rain_battery_saver_safety()"),
            common.index("install_live_task_event_refresh()"),
        )

    def test_recovery_resume_rechecks_rain_before_and_after_continue(self) -> None:
        source = RAIN_SAFETY.read_text(encoding="utf-8")

        self.assertIn('self._battery_saver_phase == "recovery_charge"', source)
        self.assertGreaterEqual(
            source.count("self._last_task_event_download_monotonic = 0.0"), 2
        )
        self.assertGreaterEqual(
            source.count("await self._async_refresh_task_events()"), 2
        )
        self.assertIn("_RESUME_RAIN_VERIFY_SECONDS = 5.2", source)
        self.assertIn("await asyncio.sleep(_RESUME_RAIN_VERIFY_SECONDS)", source)
        self.assertIn('self._battery_saver_phase = "rain_hold"', source)

    def test_shared_rtk_power_stays_on_during_rain_hold(self) -> None:
        source = RAIN_SAFETY.read_text(encoding="utf-8")
        shared_block = source.split(
            "async def maintain_idle_charge", 1
        )[1].split("async def evaluate", 1)[0]

        self.assertIn('self._battery_saver_phase == "rain_hold"', shared_block)
        self.assertIn(
            "self.battery_saver_config[CONF_SHARED_RTK_POWER]", shared_block
        )
        self.assertIn("await self._async_set_charger(True)", shared_block)
        self.assertIn(
            "await previous_maintain_idle_charge(self, battery)", shared_block
        )

    def test_separate_rtk_power_keeps_existing_shutdown_guard(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        source = RAIN_SAFETY.read_text(encoding="utf-8")

        self.assertIn("previous_maintain_idle_charge", source)
        self.assertIn("off_since + 55 * 60", coordinator)
        self.assertIn(
            "self._battery_saver_shutdown_guard_pulse_until = time.time() + 60",
            coordinator,
        )
        self.assertIn("self._ensure_shutdown_guard()", coordinator)

    def test_enabling_saver_during_known_rain_hold_preserves_rain_phase(self) -> None:
        source = RAIN_SAFETY.read_text(encoding="utf-8")
        enabled_block = source.split("async def set_enabled", 1)[1].split(
            "async def maintain_idle_charge", 1
        )[0]

        self.assertIn('self._battery_saver_phase == "initial_charge"', enabled_block)
        self.assertIn("_current_rain_hold_signal(self)", enabled_block)
        self.assertIn('self._battery_saver_phase = "rain_hold"', enabled_block)


if __name__ == "__main__":
    unittest.main()
