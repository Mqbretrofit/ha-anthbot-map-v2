"""Regression checks for YAML-configurable initial map-card layout."""

from pathlib import Path
import unittest


CARD_PATH = Path(__file__).parents[1] / "www/anthbot-map/anthbot-map-card.js"


class TestDefaultMenuLayout(unittest.TestCase):
    """Keep default panel/menu/submenu startup behavior backward compatible."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = CARD_PATH.read_text(encoding="utf-8-sig")

    def test_default_panel_supports_snake_and_camel_case(self) -> None:
        self.assertIn("config.default_panel ?? config.defaultPanel", self.source)
        self.assertIn('validPanels.has(configuredPanel) ? configuredPanel : "control"', self.source)

    def test_menu_open_supports_snake_and_camel_case(self) -> None:
        self.assertIn('typeof config.menu_open === "boolean"', self.source)
        self.assertIn('typeof config.menuOpen === "boolean"', self.source)

    def test_default_submenu_supports_snake_and_camel_case(self) -> None:
        self.assertIn("config.default_submenu ?? config.defaultSubmenu", self.source)
        self.assertIn("this.defaultSubmenu === key", self.source)

    def test_remembered_open_section_survives_yaml_default_and_rerender(self) -> None:
        self.assertIn("const rememberedKey = window.localStorage.getItem", self.source)
        self.assertIn("rememberedKey === key", self.source)
        self.assertIn("rememberedZoneKey === zoneKey", self.source)

    def test_zone_submenu_can_open_its_parent(self) -> None:
        self.assertIn('key === "manual" || key === "auto"', self.source)
        self.assertIn("this.defaultSubmenu.startsWith", self.source)

    def test_control_zone_groups_can_be_preselected(self) -> None:
        self.assertIn('this.defaultSubmenu === "auto-zone-set"', self.source)
        self.assertIn('this.defaultSubmenu === "zone-set"', self.source)


if __name__ == "__main__":
    unittest.main()
