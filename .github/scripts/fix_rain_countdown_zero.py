from pathlib import Path

CARD_PATHS = [
    Path("custom_components/anthbot_map/frontend/anthbot-map-card.js"),
    Path("www/anthbot-map/anthbot-map-card.js"),
]

old = '''    const endAt = detectedAt + duration * 1000;\n    return Math.max(0, Math.ceil((endAt - Date.now()) / 1000));\n'''
new = '''    const endAt = detectedAt + duration * 1000;\n    const remaining = Math.ceil((endAt - Date.now()) / 1000);\n    return remaining > 0 ? remaining : null;\n'''

for path in CARD_PATHS:
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise SystemExit(f"{path}: countdown block not found exactly once")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

test_path = Path("tests/test_rain_hold_status.py")
tests = test_path.read_text(encoding="utf-8")
needle = "        self.assertIn('detected_at', card)\n"
replacement = needle + "        self.assertIn('return remaining > 0 ? remaining : null;', card)\n"
if tests.count(needle) != 1:
    raise SystemExit("test insertion point not found exactly once")
test_path.write_text(tests.replace(needle, replacement, 1), encoding="utf-8")
