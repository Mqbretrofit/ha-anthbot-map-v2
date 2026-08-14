"""Source-level checks for automatic Lovelace resource registration."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INIT_SOURCE = (ROOT / "custom_components/anthbot_map/__init__.py").read_text()
MANIFEST = (ROOT / "custom_components/anthbot_map/manifest.json").read_text()


class LovelaceResourceRegistrationTests(unittest.TestCase):
    """Protect the storage-safe automatic registration flow."""

    def test_lovelace_is_an_integration_dependency(self) -> None:
        self.assertIn('"lovelace"', MANIFEST)

    def test_existing_resources_are_loaded_before_create(self) -> None:
        load_at = INIT_SOURCE.index("await resources.async_get_info()")
        create_at = INIT_SOURCE.index("await resources.async_create_item(")
        self.assertLess(load_at, create_at)

    def test_manual_resource_is_reused(self) -> None:
        self.assertIn('str(item.get("url", "")).split("?", 1)[0]', INIT_SOURCE)
        self.assertIn("await resources.async_update_item(", INIT_SOURCE)

    def test_yaml_mode_is_not_modified(self) -> None:
        self.assertIn(
            'getattr(lovelace, "resource_mode", None) != MODE_STORAGE',
            INIT_SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
