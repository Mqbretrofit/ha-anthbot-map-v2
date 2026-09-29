"""Regression checks for the isolated announcements beta."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


class AnnouncementsBetaTests(unittest.TestCase):
    def test_beta_version_is_consistent(self) -> None:
        manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
        version = manifest["version"]
        self.assertEqual("2.4.9.5-beta4", version)
        self.assertIn(
            f'INTEGRATION_VERSION = "{version}"',
            (INTEGRATION / "const.py").read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"?v={version}",
            (INTEGRATION / "__init__.py").read_text(encoding="utf-8"),
        )

    def test_feed_is_best_effort_cached_and_uses_existing_random_id(self) -> None:
        source = (INTEGRATION / "announcements.py").read_text(encoding="utf-8")
        presence = (INTEGRATION / "presence.py").read_text(encoding="utf-8")
        self.assertIn('"version": INTEGRATION_VERSION', source)
        self.assertIn('"language": language', source)
        self.assertIn('params["models"]', source)
        self.assertIn('"installation_id": await async_get_presence_installation_id', source)
        self.assertIn("except Exception as err", source)
        self.assertIn("self.items", source)
        self.assertIn("Store(", source)
        self.assertNotIn("serial_number", source)
        self.assertNotIn("bearer_token", source)
        self.assertIn("async_get_presence_installation_id", presence)
        self.assertIn('return await _installation_id(hass)', presence)

    def test_frontend_has_news_panel_badge_and_popup_opt_in(self) -> None:
        card = (INTEGRATION / "frontend" / "anthbot-map-card.js").read_text(encoding="utf-8")
        for marker in (
            'this.callAnnouncementService("announcements_get"',
            'this.callAnnouncementService("announcements_mark_read"',
            'this.activePanel === "announcements"',
            "data-announcement-badge",
            "candidate.show_popup",
            "anthbot-announcement-dialog",
            "data-announcement-bell",
            "startAnnouncementPollTimer",
            'this.resolveAsset("logo.png?v=2495-beta4")',
        ):
            self.assertIn(marker, card)
        self.assertIn(
            'if (this.activePanel === "announcements" || this.activePanel === "more") this.renderAppPanel();',
            card,
        )
        self.assertIn("_INTERVAL = timedelta(minutes=1)", (INTEGRATION / "announcements.py").read_text(encoding="utf-8"))
        self.assertTrue((INTEGRATION / "frontend" / "logo.png").is_file())
        self.assertTrue((ROOT / "www" / "anthbot-map" / "logo.png").is_file())

    def test_all_card_languages_have_announcement_labels(self) -> None:
        source = (INTEGRATION / "frontend" / "i18n.js").read_text(encoding="utf-8")
        block = source.split("const announcementTranslations = {", 1)[1].split("\n};", 1)[0]
        languages = (
            "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs",
            "sk", "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr",
            "th", "vi", "ko", "km",
        )
        for language in languages:
            key = f'"{language}"' if "-" in language else language
            self.assertRegex(block, rf"(?m)^  {re.escape(key)}: \{{ announcements:")
            line = next(
                candidate for candidate in block.splitlines()
                if candidate.startswith(f"  {key}: ")
            )
            self.assertIn("announcementCategory_personal:", line)

    def test_frontend_mirrors_match(self) -> None:
        for name in ("anthbot-map-card.js", "i18n.js", "logo.png"):
            self.assertEqual(
                (INTEGRATION / "frontend" / name).read_bytes(),
                (ROOT / "www" / "anthbot-map" / name).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
