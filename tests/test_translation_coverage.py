"""Ensure the v2.3 user-facing features are translated in every language."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "custom_components" / "anthbot_map" / "frontend"


class TranslationCoverageTests(unittest.TestCase):
    def test_calibration_and_mowing_history_have_no_english_fallbacks(self) -> None:
        complements = base64.b64encode(
            (FRONTEND / "i18n-complements.js").read_bytes()
        ).decode("ascii")
        source = (FRONTEND / "i18n.js").read_text(encoding="utf-8")
        source = source.replace(
            'from "./i18n-complements.js?v=138"',
            f'from "data:text/javascript;base64,{complements}"',
            1,
        )
        source += "\nexport { translations, settingsTranslations, feedbackTranslations, commandStageTranslations, commandTranslations, menuTranslations };\n"
        module = base64.b64encode(source.encode("utf-8")).decode("ascii")
        script = f"""
const i18n = await import("data:text/javascript;base64,{module}");
const stores = [
  i18n.translations,
  i18n.settingsTranslations,
  i18n.feedbackTranslations,
  i18n.commandStageTranslations,
  i18n.commandTranslations,
  i18n.menuTranslations,
];
const languages = i18n.LANGUAGES.map(([code]) => code).filter((code) => code !== "auto");
const keys = [
  "mapFit", "robotFit", "mowingPathFit", "robotDirection", "boundaryFit",
  "up", "left", "right", "down", "narrower", "wider", "shorter",
  "taller", "rotation", "reset", "mowingHistory", "mowingHistoryEmpty",
  "mowingHistoryTotalCount", "mowingHistoryTotalArea", "mowingHistoryArea",
  "mowingHistoryProgress", "mowingHistoryDuration", "mowingHistoryMode",
  "mowingHistoryStartedBy", "mowingHistoryRawFields", "mowingHistoryUnknownTime",
  "mowingModeZones", "mowingModeGlobal", "mowingModeEdge", "mowingModeDockEdge",
  "mowingSourceApp", "mowingSourceSchedule", "mowingSourceButton",
  "mowingSourceVoice", "mowingHistoryDetailLoading",
  "mowingHistoryDetailUnavailable",
];
const missing = [];
for (const language of languages) {{
  for (const key of keys) {{
    const localized = stores.some((store) => Object.hasOwn(store[language] || {{}}, key));
    if (!localized) missing.push(`${{language}}:${{key}}`);
  }}
}}
process.stdout.write(JSON.stringify(missing));
"""
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=script,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
