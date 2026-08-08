"""Regression checks for the HACS-updated bundled frontend."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


class TestFrontendBundle(unittest.TestCase):
    def test_all_frontend_assets_are_bundled_byte_for_byte(self) -> None:
        source = ROOT / "www" / "anthbot-map"
        bundled = INTEGRATION / "frontend"
        for source_file in source.iterdir():
            if source_file.is_file():
                self.assertEqual(
                    source_file.read_bytes(),
                    (bundled / source_file.name).read_bytes(),
                    source_file.name,
                )

    def test_static_path_is_registered_without_cache_headers(self) -> None:
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('StaticPathConfig("/anthbot-map-v2"', source)
        self.assertIn('Path(__file__).parent / "frontend"', source)
        self.assertIn('str(frontend_path), False', source)

    def test_frontend_is_mirrored_to_config_www(self) -> None:
        source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('hass.config.path("www", "anthbot-map-v2")', source)
        self.assertIn("_sync_standalone_frontend", source)
        self.assertIn("shutil.copytree", source)


if __name__ == "__main__":
    unittest.main()
