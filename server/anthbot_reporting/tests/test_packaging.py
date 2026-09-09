from __future__ import annotations

from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]


class ReportingServerPackagingTests(unittest.TestCase):
    def test_dockerfile_copies_all_runtime_modules_and_templates(self) -> None:
        dockerfile = (SERVER_DIR / "Dockerfile").read_text("utf-8")
        for filename in (
            "developer_agent_api.py",
            "developer_agent_dashboard.py",
            "developer_agent_dashboard.html",
            "diagnostics_dashboard.py",
            "diagnostic_detail.html",
        ):
            self.assertIn(f"COPY {filename} ./", dockerfile)

    def test_app_has_independent_version(self) -> None:
        config = (SERVER_DIR / "config.yaml").read_text("utf-8")
        self.assertIn('name: ANTHBOT Reports', config)
        self.assertIn('version: "1.0.0-test.11"', config)
        self.assertIn('slug: anthbot_reporting', config)


if __name__ == "__main__":
    unittest.main()
