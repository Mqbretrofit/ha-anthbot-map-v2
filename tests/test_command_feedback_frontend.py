"""Regression checks for visible Anthbot map-card command feedback."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CARD_PATHS = (
    ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
    ROOT / "custom_components" / "anthbot_map" / "frontend" / "anthbot-map-card.js",
)


class CommandFeedbackFrontendTests(unittest.TestCase):
    def test_bundled_cards_are_identical_and_render_local_feedback(self) -> None:
        cards = [path.read_text(encoding="utf-8") for path in CARD_PATHS]
        self.assertEqual(cards[0], cards[1])
        card = cards[0]
        self.assertIn('data-role="command-feedback"', card)
        self.assertIn('role="status" aria-live="polite"', card)
        self.assertIn("feedback.hidden = false", card)
        self.assertIn('this.feedback("commandSentWaiting"', card)
        self.assertIn('this.feedback("commandConfirmed"', card)
        self.assertIn('this.feedback("commandNotConfirmed"', card)
        self.assertIn('this.feedback("commandFailed"', card)
        self.assertIn("position:fixed; z-index:10000", card)
        sent = card.index('this.notify(this.feedback("commandSentWaiting", label));')
        pressed = card.index('await this._hass.callService("button", "press"')
        self.assertLess(sent, pressed)
        self.assertIn("const confirmationService = ({", card)


if __name__ == "__main__":
    unittest.main()
