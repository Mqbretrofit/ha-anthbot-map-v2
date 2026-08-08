"""Regression checks for visible Anthbot map-card command feedback."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
I18N_PATH = ROOT / "custom_components" / "anthbot_map" / "frontend" / "i18n.js"
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
        self.assertIn('anthbotFeedback(card, hass, "commandSentWaiting"', card)
        self.assertIn('anthbotFeedback(card, hass, "commandCloudAccepted"', card)
        self.assertIn('anthbotFeedback(card, hass, "commandCloudRejected"', card)
        self.assertIn('anthbotFeedback(card, hass, "commandConfirmed"', card)
        self.assertIn('anthbotFeedback(card, hass, "commandNotConfirmed"', card)
        self.assertNotIn("Parancs elküldve:", card)
        self.assertNotIn("A felhő elfogadta:", card)
        self.assertIn('start_zone_mow: ["mowing"', card)
        self.assertIn('"nyiras"', card)
        self.assertIn('background: "rgba(2, 119, 189, .92)"', card)
        handler_start = card.index("window.__anthbotFeedbackClickHandler = (event) => {")
        handler = card[handler_start:]
        card_guard = handler.index('if (!card) return;')
        control_lookup = handler.index('const control = path.find')
        self.assertLess(card_guard, control_lookup)
        sent = card.index('showAnthbotCommandToast(anthbotFeedback(card, hass, "commandSentWaiting"')
        pressed = card.index('void executeAnthbotCommand(hass, card, command')
        self.assertLess(sent, pressed)
        execute_start = card.index("async function executeAnthbotCommand(")
        execute_end = card.index("\nif (window.__anthbotFeedbackClickHandler)", execute_start)
        execute = card[execute_start:execute_end]
        accepted = execute.index('showAnthbotCommandToast(anthbotFeedback(card, hass, "commandCloudAccepted"')
        service_call = execute.index('await hass.callService("button", "press"')
        self.assertLess(service_call, accepted)

    def test_every_supported_language_has_all_feedback_stages(self) -> None:
        i18n = I18N_PATH.read_text(encoding="utf-8")
        language_block = i18n.split("export const LANGUAGES = [", 1)[1].split("];", 1)[0]
        languages = set(__import__("re").findall(r'\["([^\"]+)",', language_block)) - {"auto"}
        self.assertEqual(len(languages), 23)
        stage_block = i18n.split("const commandStageTranslations = {", 1)[1].split("\n};", 1)[0]
        for language in languages:
            marker = f'"{language}":' if "-" in language else f"  {language}:"
            self.assertIn(marker, stage_block, f"Missing command-stage translations for {language}")
        for key in ("commandSentWaiting", "commandCloudAccepted", "commandCloudRejected", "commandConfirmed", "commandNotConfirmed"):
            self.assertIn(key, i18n)


if __name__ == "__main__":
    unittest.main()
