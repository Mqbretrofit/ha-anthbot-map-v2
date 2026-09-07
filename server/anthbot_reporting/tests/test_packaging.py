from __future__ import annotations

from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]


class ReportingServerPackagingTests(unittest.TestCase):
    def test_dockerfile_copies_developer_agent_runtime_files(self) -> None:
        dockerfile = (SERVER_DIR / "Dockerfile").read_text("utf-8")
        for filename in (
            "developer_agent_api.py",
            "developer_agent_dashboard.py",
            "developer_agent_dashboard.html",
        ):
            self.assertIn(f"COPY {filename} ./", dockerfile)


if __name__ == "__main__":
    unittest.main()
