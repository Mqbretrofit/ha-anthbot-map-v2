from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "custom_components" / "anthbot_map" / "frontend"
WWW = ROOT / "www" / "anthbot-map"

LANGUAGES = (
    "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "sk", "ro",
    "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr", "th", "vi", "ko", "km",
)
CLASSIC_KEYS = (
    "classicMowingArea",
    "classicZonesOrder",
    "classicAll",
    "classicBack",
    "classicZonesAndOrder",
    "classicDone",
    "classicSelected",
)


class MultiFrontendLocalizationTests(unittest.TestCase):
    def test_frontend_mirrors_match(self) -> None:
        for name in ("anthbot-map-card.js", "i18n.js"):
            self.assertEqual(
                (FRONTEND / name).read_bytes(),
                (WWW / name).read_bytes(),
                name,
            )

    def test_classic_mobile_controls_are_not_hungarian_english_branches(self) -> None:
        card = (FRONTEND / "anthbot-map-card.js").read_text(encoding="utf-8")
        self.assertNotIn('this.language === "hu"', card)
        for key in CLASSIC_KEYS:
            self.assertIn(f'this.t("{key}")', card)

    def test_classic_mobile_controls_have_all_23_languages(self) -> None:
        source = (FRONTEND / "i18n.js").read_text(encoding="utf-8")
        block = source.split("const classicMobileTranslations = ", 1)[1].split(
            "for (const [language, values] of Object.entries(classicMobileTranslations))",
            1,
        )[0]
        self.assertEqual(len(LANGUAGES), 23)
        for language in LANGUAGES:
            self.assertIn(f'"{language}": {{', block)
        for key in CLASSIC_KEYS:
            self.assertEqual(block.count(f'"{key}"'), 23, key)


if __name__ == "__main__":
    unittest.main()
