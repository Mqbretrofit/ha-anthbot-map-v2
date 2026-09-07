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
        self.client_ctx = TestClient(server.app)
        self.client = self.client_ctx.__enter__()
        self.installation_id = str(uuid4())

    def tearDown(self) -> None:
        self.client_ctx.__exit__(None, None, None)
        self.tempdir.cleanup()

    def _usage_payload(self, *, event: str = "installation") -> dict:
        return {
            "schema": server.USAGE_SCHEMA,
            "event": event,
            "generated_at": "2026-09-07T17:00:00+00:00",
            "installation_id": self.installation_id,
            "integration_version": "2.4.5",
            "home_assistant_version": "2026.9.1",
            "country": "Hungary",
            "device_count": 2,
            "models": ["Anthbot Genie 1000", "M9 Pro"],
            "model_counts": {"Anthbot Genie 1000": 1, "M9 Pro": 1},
        }

    def test_telemetry_upserts_installation_and_stats(self) -> None:
        response = self.client.post(
            "/api/anthbot/telemetry", json=self._usage_payload()
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["accepted"])

        stats = self.client.get(
            "/api/anthbot/admin/stats",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        self.assertEqual(stats.status_code, 200)
        body = stats.json()
        self.assertEqual(body["installations"]["total"], 1)
        self.assertEqual(body["by_country"][0]["name"], "Hungary")
        by_model = {item["name"]: item["count"] for item in body["by_model"]}
        self.assertEqual(by_model["M9 Pro"], 1)

    def test_usage_counts_must_be_consistent(self) -> None:
        payload = self._usage_payload()
        payload["device_count"] = 5
        response = self.client.post("/api/anthbot/telemetry", json=payload)
        self.assertEqual(response.status_code, 422)

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

    def test_admin_requires_bearer_token(self) -> None:
        response = self.client.get("/api/anthbot/admin/stats")
        self.assertEqual(response.status_code, 401)

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])


if __name__ == "__main__":
    unittest.main()
