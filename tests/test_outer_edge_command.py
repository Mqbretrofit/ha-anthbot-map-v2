"""Regression tests for official-app outer-edge mowing semantics."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OuterEdgeCommandTests(unittest.TestCase):
    def test_outer_edge_uses_official_app_command(self) -> None:
        commands = (ROOT / "custom_components/anthbot_map/commands.py").read_text()
        block = commands.split("async def async_start_outer_edge_mowing", 1)[1]
        self.assertIn('cmd="ridable_mow_start", data=1', block)
        self.assertNotIn('cmd="app_state"', block)
        self.assertNotIn('cmd="mow_start"', block)

    def test_all_outer_edge_entry_points_use_dedicated_helper(self) -> None:
        init_source = (ROOT / "custom_components/anthbot_map/__init__.py").read_text()
        button_source = (ROOT / "custom_components/anthbot_map/button.py").read_text()
        self.assertEqual(
            init_source.count("await async_start_outer_edge_mowing(coordinator)"), 2
        )
        self.assertEqual(
            button_source.count(
                "await async_start_outer_edge_mowing(self.coordinator)"
            ),
            2,
        )
        self.assertNotIn("app_state=2", init_source)
        self.assertNotIn("app_state=2", button_source)

    def test_frontend_accepts_official_edge_mode(self) -> None:
        source = (
            ROOT
            / "custom_components/anthbot_map/frontend/anthbot-map-card.js"
        ).read_text()
        self.assertEqual(source.count('"bordermowing", "edgemowing"'), 2)
