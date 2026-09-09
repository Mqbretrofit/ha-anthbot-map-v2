from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

import asgi


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


if __name__ == "__main__":
    unittest.main()
