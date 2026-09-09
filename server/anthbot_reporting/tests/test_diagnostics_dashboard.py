from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

import asgi
import app as server


class DiagnosticDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["ANTHBOT_DB_PATH"] = str(
            Path(self.tempdir.name) / "reporting.sqlite3"
        )
        os.environ["ANTHBOT_ADMIN_TOKEN"] = "test-admin-token"
        self.client_ctx = TestClient(asgi.app, base_url="https://testserver")
        self.client = self.client_ctx.__enter__()
        self.installation_id = str(uuid4())

    def tearDown(self) -> None:
        self.client_ctx.__exit__(None, None, None)
        self.tempdir.cleanup()

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-admin-token"}

    def _create_report(self) -> str:
        response = self.client.post(
            "/api/anthbot/diagnostics",
            json={
                "schema": server.DIAGNOSTICS_SCHEMA,
                "generated_at": "2026-09-09T09:00:00+00:00",
                "installation_id": self.installation_id,
                "trigger": "live_shadow_error",
                "report": {
                    "schema": "anthbot-firmware-diagnostics-v1",
                    "device": {"model": "M9 Pro", "serial_sha256": "abc"},
                    "telemetry": {"err_code": 100},
                    "path": {"path_id": "live-7", "points": 42},
                },
            },
        )
        self.assertEqual(response.status_code, 202)
        return response.json()["report_id"]

    def test_single_diagnostic_detail_api_returns_full_report(self) -> None:
        report_id = self._create_report()
        response = self.client.get(
            f"/api/anthbot/admin/diagnostics/{report_id}",
            headers=self._admin_headers(),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["report_id"], report_id)
        self.assertEqual(body["trigger"], "live_shadow_error")
        self.assertEqual(body["report"]["device"]["model"], "M9 Pro")
        self.assertEqual(body["report"]["telemetry"]["err_code"], 100)

    def test_single_diagnostic_detail_api_returns_404(self) -> None:
        response = self.client.get(
            "/api/anthbot/admin/diagnostics/AB-missing",
            headers=self._admin_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_dashboard_cards_are_wired_to_detail_page(self) -> None:
        self._create_report()
        login = self.client.post(
            "/dashboard/login",
            data={"token": "test-admin-token"},
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 303)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("diagnosticLinked", dashboard.text)
        self.assertIn("/dashboard/diagnostics/", dashboard.text)

    def test_diagnostic_detail_page_requires_dashboard_session(self) -> None:
        report_id = self._create_report()
        unauthenticated = self.client.get(
            f"/dashboard/diagnostics/{report_id}",
            follow_redirects=False,
        )
        self.assertEqual(unauthenticated.status_code, 303)
        self.assertEqual(unauthenticated.headers["location"], "/dashboard")

        self.client.post("/dashboard/login", data={"token": "test-admin-token"})
        page = self.client.get(f"/dashboard/diagnostics/{report_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Teljes diagnosztikai riport", page.text)
        self.assertIn("JSON másolása", page.text)


if __name__ == "__main__":
    unittest.main()
