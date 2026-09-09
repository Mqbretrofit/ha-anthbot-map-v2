from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

import app as server


class ReportingServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["ANTHBOT_DB_PATH"] = str(
            Path(self.tempdir.name) / "reporting.sqlite3"
        )
        os.environ["ANTHBOT_ADMIN_TOKEN"] = "test-admin-token"
        self.client_ctx = TestClient(server.app, base_url="https://testserver")
        self.client = self.client_ctx.__enter__()
        self.installation_id = str(uuid4())

    def tearDown(self) -> None:
        self.client_ctx.__exit__(None, None, None)
        self.tempdir.cleanup()

    def _usage_payload(
        self,
        *,
        event: str = "installation",
        installation_id: str | None = None,
        country: str = "Hungary",
        models: list[str] | None = None,
        version: str = "2.4.5",
    ) -> dict:
        models = models or ["Anthbot Genie 1000", "M9 Pro"]
        counts = {model: models.count(model) for model in sorted(set(models))}
        return {
            "schema": server.USAGE_SCHEMA,
            "event": event,
            "generated_at": "2026-09-07T17:00:00+00:00",
            "installation_id": installation_id or self.installation_id,
            "integration_version": version,
            "home_assistant_version": "2026.9.1",
            "country": country,
            "device_count": len(models),
            "models": sorted(set(models)),
            "model_counts": counts,
        }

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-admin-token"}

    def test_telemetry_upserts_installation_and_stats(self) -> None:
        response = self.client.post(
            "/api/anthbot/telemetry", json=self._usage_payload()
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["accepted"])

        stats = self.client.get(
            "/api/anthbot/admin/stats", headers=self._admin_headers()
        )
        self.assertEqual(stats.status_code, 200)
        body = stats.json()
        self.assertEqual(body["installations"]["total"], 1)
        self.assertEqual(body["total_devices"], 2)
        self.assertEqual(body["by_country"][0]["name"], "Hungary")
        by_model = {item["name"]: item["count"] for item in body["by_model"]}
        self.assertEqual(by_model["M9 Pro"], 1)

    def test_usage_counts_must_be_consistent(self) -> None:
        payload = self._usage_payload()
        payload["device_count"] = 5
        response = self.client.post("/api/anthbot/telemetry", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_installation_filters_country_model_and_version(self) -> None:
        second_id = str(uuid4())
        self.client.post("/api/anthbot/telemetry", json=self._usage_payload())
        self.client.post(
            "/api/anthbot/telemetry",
            json=self._usage_payload(
                installation_id=second_id,
                country="Germany",
                models=["Anthbot M9 Pro"],
                version="2.4.6",
            ),
        )

        germany = self.client.get(
            "/api/anthbot/admin/installations?country=Germany",
            headers=self._admin_headers(),
        ).json()
        self.assertEqual(germany["count"], 1)
        self.assertEqual(germany["items"][0]["installation_id"], second_id)

        m9 = self.client.get(
            "/api/anthbot/admin/installations?model=Anthbot%20M9%20Pro",
            headers=self._admin_headers(),
        ).json()
        self.assertEqual(m9["count"], 1)
        self.assertEqual(m9["items"][0]["country"], "Germany")

        version = self.client.get(
            "/api/anthbot/admin/installations?version=2.4.5",
            headers=self._admin_headers(),
        ).json()
        self.assertEqual(version["count"], 1)
        self.assertEqual(version["items"][0]["country"], "Hungary")

    def test_diagnostics_returns_report_id(self) -> None:
        payload = {
            "schema": server.DIAGNOSTICS_SCHEMA,
            "generated_at": "2026-09-07T17:01:00+00:00",
            "installation_id": self.installation_id,
            "trigger": "mower_error_code",
            "report": {
                "schema": "anthbot-firmware-diagnostics-v1",
                "device": {"model": "M9 Pro", "serial_sha256": "abc"},
                "telemetry": {"err_code": 231},
            },
        }
        response = self.client.post("/api/anthbot/diagnostics", json=payload)
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["report_id"].startswith("AB-"))

    def test_diagnostics_rejects_credential_like_keys(self) -> None:
        payload = {
            "schema": server.DIAGNOSTICS_SCHEMA,
            "generated_at": "2026-09-07T17:01:00+00:00",
            "installation_id": self.installation_id,
            "trigger": "test",
            "report": {"nested": {"access_token": "should-never-arrive"}},
        }
        response = self.client.post("/api/anthbot/diagnostics", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_admin_requires_bearer_token_or_dashboard_cookie(self) -> None:
        response = self.client.get("/api/anthbot/admin/stats")
        self.assertEqual(response.status_code, 401)
        response = self.client.get(
            "/api/anthbot/admin/stats", headers=self._admin_headers()
        )
        self.assertEqual(response.status_code, 200)

    def test_dashboard_login_sets_secure_session_cookie(self) -> None:
        login_page = self.client.get("/dashboard")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("Admin felület", login_page.text)

        bad = self.client.post(
            "/dashboard/login", data={"token": "wrong"}, follow_redirects=False
        )
        self.assertEqual(bad.status_code, 401)

        good = self.client.post(
            "/dashboard/login",
            data={"token": "test-admin-token"},
            follow_redirects=False,
        )
        self.assertEqual(good.status_code, 303)
        self.assertIn(server._DASHBOARD_COOKIE, good.cookies)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Használati statisztikák és diagnosztika", dashboard.text)

        stats = self.client.get("/api/anthbot/admin/stats")
        self.assertEqual(stats.status_code, 200)

    def test_dashboard_does_not_expose_admin_token(self) -> None:
        page = self.client.get("/dashboard")
        self.assertNotIn("test-admin-token", page.text)
        self.client.post("/dashboard/login", data={"token": "test-admin-token"})
        page = self.client.get("/dashboard")
        self.assertNotIn("test-admin-token", page.text)

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])


if __name__ == "__main__":
    unittest.main()