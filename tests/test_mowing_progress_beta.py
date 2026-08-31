"""Regression checks for v2.4.3-beta.1 mowing progress features."""
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
SENSOR = ROOT / "custom_components/anthbot_map/sensor.py"
CARD = ROOT / "www/anthbot-map/anthbot-map-card.js"
INIT = ROOT / "custom_components/anthbot_map/__init__.py"

class TestMowingProgressBeta(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sensor = SENSOR.read_text(encoding="utf-8-sig")
        cls.card = CARD.read_text(encoding="utf-8-sig")
        cls.init = INIT.read_text(encoding="utf-8-sig")

    def test_production_sensor_names_have_no_test_suffix(self) -> None:
        self.assertIn('key="mowing_progress"', self.sensor)
        self.assertIn('key="active_zone_area"', self.sensor)
        self.assertNotIn('key="mowing_progress_test"', self.sensor)
        self.assertNotIn('key="active_zone_area_test"', self.sensor)

    def test_production_progress_not_cleaned_as_legacy(self) -> None:
        block = self.init.split("LEGACY_ENTITY_SUFFIXES", 1)[1].split(")", 1)[0]
        self.assertNotIn('"mowing_progress"', block)

    def test_no_go_overlap_is_subtracted(self) -> None:
        self.assertIn("_progress_polygon_union_intersection_area_raw", self.sensor)
        self.assertIn("no_go_active_overlap_m2", self.sensor)
        self.assertIn("calibrated_area_total_m2", self.sensor)

    def test_card_prefers_production_progress_sensor(self) -> None:
        self.assertIn('["mowing_progress", "mowing_progress_test"]', self.card)

    def test_live_completion_tolerance_and_latch(self) -> None:
        self.assertIn("boundedProgress >= 95", self.card)
        self.assertIn("mowingCompletionLatched", self.card)
        self.assertIn("anthbot-map-mowing-completion", self.card)

    def test_history_uses_calculated_progress(self) -> None:
        self.assertIn("calculateMowingHistoryProgress", self.card)
        self.assertIn("return calculated >= 95 ? 100 : calculated", self.card)
        self.assertIn("historyPolygonUnionIntersectionAreaRaw", self.card)

    def test_live_status_is_draggable_and_persisted(self) -> None:
        self.assertIn("setupMapLiveStatusDrag", self.card)
        self.assertIn("anthbot-map-live-status-position", self.card)

    def test_pr24_startup_layout_remains_present(self) -> None:
        self.assertIn("config.default_panel ?? config.defaultPanel", self.card)
        self.assertIn("config.default_submenu ?? config.defaultSubmenu", self.card)
        self.assertIn('typeof config.menu_open === "boolean"', self.card)

    def test_v242_custom_buttons_remain_present(self) -> None:
        self.assertIn("customButtonActions", self.card)
        self.assertIn("persistCustomButtonActions", self.card)

if __name__ == "__main__":
    unittest.main()
