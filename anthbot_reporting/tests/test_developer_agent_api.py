from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import developer_agent_api as agent


class DeveloperAgentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["ANTHBOT_DB_PATH"] = str(
            Path(self.tempdir.name) / "reporting.sqlite3"
        )
        os.environ["ANTHBOT_ADMIN_TOKEN"] = "test-admin-token"
        agent.init_developer_agent_tables()
        app = FastAPI()
        app.include_router(agent.router)
        self.client_ctx = TestClient(app, base_url="https://testserver")
        self.client = self.client_ctx.__enter__()
        self.installation_id = str(uuid4())
        self.agent_key = "a" * 48

    def tearDown(self) -> None:
        self.client_ctx.__exit__(None, None, None)
        self.tempdir.cleanup()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-admin-token"}

    def _poll(self) -> dict:
        response = self.client.post(
            "/api/anthbot/developer-agent/poll",
            json={
                "schema": "anthbot-developer-agent-poll-v1",
                "installation_id": self.installation_id,
                "agent_key": self.agent_key,
                "integration_version": "2.4.6-beta.2",
                "models": ["N8"],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_poll_registers_agent_and_admin_can_pause_and_resume(self) -> None:
        body = self._poll()
        self.assertTrue(body["server_enabled"])
        self.assertIsNone(body["job"])

        agents = self.client.get(
            "/api/anthbot/admin/developer-agent/installations",
            headers=self._headers(),
        )
        self.assertEqual(agents.status_code, 200)
        self.assertEqual(agents.json()["items"][0]["models"], ["N8"])

        stopped = self.client.post(
            f"/api/anthbot/admin/developer-agent/installations/{self.installation_id}/enabled",
            json={"enabled": False},
            headers=self._headers(),
        )
        self.assertEqual(stopped.status_code, 200)
        body = self._poll()
        self.assertFalse(body["server_enabled"])
        self.assertGreaterEqual(body["next_poll_seconds"], 3600)

        resumed = self.client.post(
            f"/api/anthbot/admin/developer-agent/installations/{self.installation_id}/enabled",
            json={"enabled": True},
            headers=self._headers(),
        )
        self.assertEqual(resumed.status_code, 200)
        self.assertTrue(self._poll()["server_enabled"])

    def test_admin_can_queue_whitelisted_job_and_receive_chunked_result(self) -> None:
        self._poll()
        created = self.client.post(
            "/api/anthbot/admin/developer-agent/jobs",
            json={
                "installation_id": self.installation_id,
                "action": "map_definition",
                "target_model": "N8",
            },
            headers=self._headers(),
        )
        self.assertEqual(created.status_code, 201, created.text)
        job_id = created.json()["job_id"]

        poll = self._poll()
        self.assertEqual(poll["job"]["job_id"], job_id)
        self.assertEqual(poll["job"]["action"], "map_definition")
        self.assertEqual(poll["job"]["target_model"], "N8")

        result = {
            "status": "ok",
            "action": "map_definition",
            "targets": [
                {
                    "model": "N8",
                    "serial_sha256": "f" * 64,
                    "status": "ok",
                    "data": {"format": "probe", "points": list(range(100))},
                }
            ],
        }
        raw = json.dumps(result, separators=(",", ":"))
        midpoint = len(raw) // 2
        chunks = [raw[:midpoint], raw[midpoint:]]
        for index, chunk in enumerate(chunks):
            response = self.client.post(
                "/api/anthbot/developer-agent/result",
                json={
                    "schema": "anthbot-developer-agent-result-v1",
                    "installation_id": self.installation_id,
                    "agent_key": self.agent_key,
                    "job_id": job_id,
                    "chunk_index": index,
                    "chunk_count": len(chunks),
                    "chunk": chunk,
                },
            )
            self.assertEqual(response.status_code, 202, response.text)
        self.assertTrue(response.json()["completed"])

        jobs = self.client.get(
            "/api/anthbot/admin/developer-agent/jobs?include_result=true",
            headers=self._headers(),
        )
        self.assertEqual(jobs.status_code, 200)
        item = jobs.json()["items"][0]
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["result"]["targets"][0]["model"], "N8")

    def test_unknown_probe_is_rejected_by_admin_schema(self) -> None:
        self._poll()
        response = self.client.post(
            "/api/anthbot/admin/developer-agent/jobs",
            json={
                "installation_id": self.installation_id,
                "action": "publish_mqtt_command",
            },
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 422)

    def test_wrong_agent_key_cannot_poll_or_upload(self) -> None:
        self._poll()
        response = self.client.post(
            "/api/anthbot/developer-agent/poll",
            json={
                "schema": "anthbot-developer-agent-poll-v1",
                "installation_id": self.installation_id,
                "agent_key": "b" * 48,
                "integration_version": "2.4.6-beta.2",
                "models": ["N8"],
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_result_rejects_credential_like_field_names_after_reassembly(self) -> None:
        self._poll()
        created = self.client.post(
            "/api/anthbot/admin/developer-agent/jobs",
            json={"installation_id": self.installation_id, "action": "state_schema"},
            headers=self._headers(),
        )
        job_id = created.json()["job_id"]
        self._poll()
        raw = json.dumps({"status": "ok", "data": {"access_token": "bad"}})
        response = self.client.post(
            "/api/anthbot/developer-agent/result",
            json={
                "schema": "anthbot-developer-agent-result-v1",
                "installation_id": self.installation_id,
                "agent_key": self.agent_key,
                "job_id": job_id,
                "chunk_index": 0,
                "chunk_count": 1,
                "chunk": raw,
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
