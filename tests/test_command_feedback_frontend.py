"""Regression checks for visible Anthbot map-card command feedback."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CARD_PATHS = (
    ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
    ROOT / "custom_components" / "anthbot_map" / "frontend" / "anthbot-map-card.js",
)


class CommandFeedbackFrontendTests(unittest.TestCase):
    def test_bundled_cards_are_identical_and_render_command_feedback(self) -> None:
        cards = [path.read_text(encoding="utf-8") for path in CARD_PATHS]
        self.assertEqual(cards[0], cards[1])
        card = cards[0]
        self.assertIn('toast.setAttribute("role", "status")', card)
        self.assertIn('toast.setAttribute("aria-live", "assertive")', card)
        self.assertIn("Parancs elküldve:", card)
        self.assertIn("A felhő elfogadta:", card)
        self.assertIn("A robot visszaigazolta:", card)
        self.assertIn("Nem érkezett állapot-visszaigazolás:", card)
        self.assertIn('start_zone_mow: ["mowing"', card)
        self.assertIn('"nyiras"', card)
        self.assertIn('background: "rgba(2, 119, 189, .92)"', card)
        sent = card.index('showAnthbotCommandToast(`Parancs elküldve:')
        pressed = card.index('void executeAnthbotCommand(hass, card, command')
        self.assertLess(sent, pressed)
        execute_start = card.index("async function executeAnthbotCommand(")
        execute_end = card.index("\nif (window.__anthbotFeedbackClickHandler)", execute_start)
        execute = card[execute_start:execute_end]
        accepted = execute.index('showAnthbotCommandToast(`A felhő elfogadta:')
        service_call = execute.index('await hass.callService("button", "press"')
        self.assertLess(service_call, accepted)


if __name__ == "__main__":
    unittest.main()
