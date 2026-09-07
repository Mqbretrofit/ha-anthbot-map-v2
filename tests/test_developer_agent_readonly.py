from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "anthbot_map"
FRONTEND = PACKAGE / "frontend"
WWW = ROOT / "www" / "anthbot-map"


class DeveloperAgentReadonlyTests(unittest.TestCase):
    def test_agent_is_separate_and_whitelisted(self) -> None:
        source = (PACKAGE / "developer_agent.py").read_text(encoding="utf-8")
        for probe in (
            "state_schema",
            "firmware_diagnostics",
            "area_definition",
            "ridable_area_definition",
            "map_definition",
            "map_archive",
            "path_definition",
            "task_events",
            "refresh_properties",
        ):
            self.assertIn(f'"{probe}"', source)
        self.assertIn("DEVELOPER_AGENT_ALLOWED_PROBES", source)
        self.assertIn("probe is not in the client whitelist", source)
        self.assertNotIn("async_publish_service_command", source)
        self.assertNotIn("start_mow", source)
        self.assertNotIn("stop_all_tasks", source)
        self.assertNotIn("factory_reset", source)

    def test_rest_definition_probes_use_account_client(self) -> None:
        source = (PACKAGE / "developer_agent.py").read_text(encoding="utf-8")
        for method in (
            "async_get_device_area_definition",
            "async_get_device_ridable_area_definition",
            "async_get_device_map_definition",
            "async_get_device_map_archive",
            "async_get_device_path_definition",
        ):
            self.assertIn(f"coordinator.account_client.{method}", source)
            self.assertNotIn(f"coordinator.client.{method}", source)

    def test_credentials_are_not_part_of_probe_results(self) -> None:
        source = (PACKAGE / "developer_agent.py").read_text(encoding="utf-8")
        self.assertIn('"password"', source)
        self.assertIn('"session_token"', source)
        self.assertIn('"bearer"', source)
        self.assertIn('"url"', source)
        self.assertIn("_is_sensitive_key", source)
        self.assertIn("safe_items", source)
        self.assertIn("serial_sha256", source)
        self.assertNotIn("serial_number\": serial", source)

    def test_agent_has_no_time_limit_and_server_can_pause(self) -> None:
        source = (PACKAGE / "developer_agent.py").read_text(encoding="utf-8")
        self.assertIn("while True", source)
        self.assertIn('response_data.get("server_enabled") is not True', source)
        self.assertIn("21_600", source)
        self.assertNotIn("expires_at", source)
        self.assertNotIn("ttl", source.lower())

    def test_agent_stays_separate_but_consent_popups_are_not_registered(self) -> None:
        tracker = (PACKAGE / "device_tracker.py").read_text(encoding="utf-8")
        config_flow = (PACKAGE / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("async_register_developer_agent", tracker)
        self.assertNotIn("async_register_developer_agent_optin", tracker)
        self.assertNotIn("async_register_developer_optin", tracker)
        self.assertNotIn("CONF_DEVELOPER_AGENT_ENABLED", config_flow)

    def test_legacy_popup_assets_remain_mirrored_but_are_not_auto_registered(self) -> None:
        source = (FRONTEND / "developer-agent-optin.js").read_text(encoding="utf-8")
        self.assertEqual(
            source,
            (WWW / "developer-agent-optin.js").read_text(encoding="utf-8"),
        )
        tracker = (PACKAGE / "device_tracker.py").read_text(encoding="utf-8")
        self.assertNotIn("developer-agent-optin.js", tracker)
        self.assertNotIn("developer-optin.js", tracker)

    def test_agent_endpoints_are_project_controlled(self) -> None:
        const = (PACKAGE / "const.py").read_text(encoding="utf-8")
        self.assertIn("reports.mqbretrofithungary.online/api/anthbot/developer-agent/poll", const)
        self.assertIn("reports.mqbretrofithungary.online/api/anthbot/developer-agent/result", const)
        self.assertNotIn("installer.tmt-automation.com/api/anthbot/developer-agent", const)


if __name__ == "__main__":
    unittest.main()
