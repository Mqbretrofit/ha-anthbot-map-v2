"""Regression checks for the Home Assistant service definitions."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVICES_YAML = ROOT / "custom_components" / "anthbot_map" / "services.yaml"
MAPPING_KEY = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][A-Za-z0-9_]*):(?:\s|$)")


def duplicate_mapping_keys(source: str) -> list[tuple[int, str]]:
    """Return duplicate plain mapping keys at the same YAML nesting level."""
    levels: list[tuple[int, set[str]]] = []
    duplicates: list[tuple[int, str]] = []

    for line_number, line in enumerate(source.splitlines(), start=1):
        match = MAPPING_KEY.match(line)
        if match is None:
            continue

        indent = len(match.group("indent"))
        key = match.group("key")
        while levels and levels[-1][0] > indent:
            levels.pop()
        if not levels or levels[-1][0] < indent:
            levels.append((indent, set()))

        keys = levels[-1][1]
        if key in keys:
            duplicates.append((line_number, key))
        keys.add(key)

    return duplicates


class ServicesYamlTests(unittest.TestCase):
    def test_duplicate_mapping_key_is_detected(self) -> None:
        source = "service:\n  fields:\n    serial_number:\n    serial_number:\n"
        self.assertEqual([(4, "serial_number")], duplicate_mapping_keys(source))

    def test_same_key_under_different_parents_is_allowed(self) -> None:
        source = "first:\n  fields:\n    serial_number:\nsecond:\n  fields:\n    serial_number:\n"
        self.assertEqual([], duplicate_mapping_keys(source))

    def test_services_yaml_has_no_duplicate_mapping_keys(self) -> None:
        duplicates = duplicate_mapping_keys(SERVICES_YAML.read_text(encoding="utf-8"))
        self.assertEqual([], duplicates)


if __name__ == "__main__":
    unittest.main()
