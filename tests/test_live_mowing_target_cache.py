"""Regression guards for stopped mowing target presentation."""

from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "custom_components" / "anthbot_map" / "frontend" / "live-map-stream.js"
BUNDLED = ROOT / "www" / "anthbot-map" / "live-map-stream.js"


class TestLiveMowingTargetCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frontend = FRONTEND.read_text(encoding="utf-8")
        cls.bundled = BUNDLED.read_text(encoding="utf-8")

    def test_mirrors_are_identical(self) -> None:
        self.assertEqual(self.frontend, self.bundled)

    def test_generic_mowing_label_is_never_treated_as_exact_target(self) -> None:
        self.assertIn("function specificMowingTarget(card, value)", self.frontend)
        self.assertIn('String(card.translateStatus?.("mowing") || "")', self.frontend)
        self.assertIn("return generic.includes(normalized) ? \"\" : text;", self.frontend)

    def test_selected_target_is_captured_before_start(self) -> None:
        self.assertIn("function selectedMowingTarget(card)", self.frontend)
        self.assertIn("function armSelectedMowingTarget(card)", self.frontend)
        self.assertIn("card._anthbotLiveCurrentTaskTarget = target;", self.frontend)
        self.assertIn("writeLastMowingProgress(card, { target, progress: 0 });", self.frontend)
        self.assertIn("armSelectedMowingTarget(this);", self.frontend)

    def test_exact_command_target_beats_generic_rendered_status(self) -> None:
        self.assertIn(
            "rememberedTarget || commandTarget || currentSpecific || currentTarget",
            self.frontend,
        )
        self.assertIn(
            "rememberedTarget || commandTarget || currentSpecific || savedSpecific || currentTarget",
            self.frontend,
        )

    def test_hidden_active_line_can_start_at_zero_for_exact_command_target(self) -> None:
        self.assertIn("if (activeMowing && !commandTarget) return;", self.frontend)
        self.assertIn(
            "rememberedTarget || commandTarget || specificMowingTarget(card, saved?.target)",
            self.frontend,
        )

    def test_hidden_stopped_line_requires_an_exact_target(self) -> None:
        self.assertIn("if (!target) return;", self.frontend)
        self.assertIn("specificMowingTarget(card, saved?.target)", self.frontend)


if __name__ == "__main__":
    unittest.main()
