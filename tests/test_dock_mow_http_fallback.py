"""Regression tests for app-style dock mowing over MQTT."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUTTON_SOURCE = ROOT / "custom_components" / "anthbot_map" / "button.py"
INIT_SOURCE = ROOT / "custom_components" / "anthbot_map" / "__init__.py"


class DockMowMqttTests(unittest.TestCase):
    """Dock mowing remains an MQTT service-shadow command."""

    def test_entity_button_still_publishes_after_unconfirmed_wake(self) -> None:
        source = BUTTON_SOURCE.read_text(encoding="utf-8")
        block = source.split('elif key == "start_dock_edge_mow":', 1)[1].split(
            'elif key == "stop_mow":', 1
        )[0]
        self.assertIn("if not await async_prepare_cloud_connection", block)
        self.assertIn('cmd="nest_mow_start", data=1', block)
        self.assertNotIn("raise AnthbotGenieApiError", block)

    def test_domain_service_still_publishes_after_unconfirmed_wake(self) -> None:
        source = INIT_SOURCE.read_text(encoding="utf-8")
        block = source.split("async def _handle_start_dock_edge_mow", 1)[1].split(
            "async def _handle_connect_cloud", 1
        )[0]
        self.assertIn("if not await async_prepare_cloud_connection", block)
        self.assertIn('cmd="nest_mow_start", data=1', block)
        self.assertNotIn("raise AnthbotGenieApiError", block)


if __name__ == "__main__":
    unittest.main()
