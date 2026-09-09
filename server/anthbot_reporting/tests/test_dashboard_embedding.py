from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

import asgi
import diagnostics_dashboard


class DashboardEmbeddingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["ANTHBOT_DB_PATH"] = str(Path(self.tempdir.name) / "reporting.sqlite3")
        os.environ["ANTHBOT_ADMIN_TOKEN"] = "test-admin-token"
        self.client_ctx = TestClient(asgi.app)
        self.client = self.client_ctx.__enter__()

    def tearDown(self) -> None:
        self.client_ctx.__exit__(None, None, None)
        self.tempdir.cleanup()

    def test_dashboard_can_be_framed_only_by_known_home_assistant_origins(self) -> None:
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("x-frame-options", response.headers)
        csp = response.headers.get("content-security-policy", "")
        self.assertIn("frame-ancestors", csp)
        self.assertIn("http://192.168.8.91:8123", csp)
        self.assertIn("https://ha.mqbretrofithungary.online", csp)
        self.assertIn("Automatikus hibariportok", response.text)
        self.assertIn("diagnostic_event", response.text)
        self.assertIn("Gyári hibariport", response.text)

    def test_dashboard_login_cookie_allows_iframe_session(self) -> None:
        response = self.client.post(
            "/dashboard/login",
            data={"token": "test-admin-token"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        cookie = response.headers.get("set-cookie", "")
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=None", cookie)

    def test_automatic_error_summary_extracts_display_fields(self) -> None:
        summary = diagnostics_dashboard._diagnostic_event_summary(
            {
                "diagnostic_event": {
                    "trigger": "mower_error_code",
                    "err_code": 2072,
                    "err_description": "Example mower error",
                    "event_code": 2072,
                    "cloud_task_event_code": 1036,
                    "mode": "auto",
                    "robot_sta": "error",
                    "online": True,
                    "task_event": {
                        "code": 2072,
                        "code_type": "error",
                        "message": "Wheel blocked",
                    },
                }
            }
        )
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["err_code"], 2072)
        self.assertEqual(summary["cloud_task_event_code"], 1036)
        self.assertEqual(summary["task_event_message"], "Wheel blocked")


if __name__ == "__main__":
    unittest.main()
