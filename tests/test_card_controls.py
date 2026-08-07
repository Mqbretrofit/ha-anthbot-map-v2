"""Regression checks for native button routing in the map card."""

from pathlib import Path
import unittest


CARD_PATH = Path(__file__).parents[1] / "www/anthbot-map/anthbot-map-card.js"


class TestCardControls(unittest.TestCase):
    """Ensure the card prefers the v2 native button entities."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = CARD_PATH.read_text(encoding="utf-8-sig")

    def test_configured_controls_use_button_press(self) -> None:
        self.assertIn("this.getControlEntity(command)", self.source)
        self.assertIn('callService("button", "press"', self.source)

    def test_zone_controls_prefer_zone_button_entity(self) -> None:
        self.assertIn("const zoneButton = this.getZoneButtonEntity(zone)", self.source)
        self.assertIn('pressButtonEntity(zoneButton, "zone")', self.source)

    def test_zone_tiles_survive_temporarily_unavailable_map_entity(self) -> None:
        self.assertIn("return this.discoverZoneButtons()", self.source)
        self.assertIn("_zone_zone_", self.source)
        self.assertIn("zone.entity_id", self.source)

    def test_numbered_entity_suffixes_are_discovered_automatically(self) -> None:
        self.assertIn("const pattern = new RegExp", self.source)
        self.assertIn("Number(right.match?.[1] || 1)", self.source)
        self.assertIn(".replace(/_map(?:_\\d+)?$/", self.source)
        self.assertIn('state.state !== "unavailable"', self.source)


if __name__ == "__main__":
    unittest.main()
