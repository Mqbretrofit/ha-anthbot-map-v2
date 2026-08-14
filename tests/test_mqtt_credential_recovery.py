"""Regression tests for MQTT WebSocket credential recovery."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "anthbot_map" / "mqtt_live.py"
API_SOURCE = ROOT / "custom_components" / "anthbot_map" / "api.py"


class MqttCredentialRecoveryTests(unittest.TestCase):
    def test_websocket_subprotocol_matches_current_mobile_app(self) -> None:
        """ANTHBOT 2.15.15 uses the legacy AWS IoT subprotocol name."""
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('protocols=("mqttv3.1",)', source)

    def test_rejected_handshake_does_not_rotate_app_issued_credentials(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("credential_lifecycle=cached_until_expiry", source)
        self.assertNotIn("_force_credential_refresh", source)
        self.assertNotIn("_force_account_reauthentication", source)
        self.assertIn("async_get_mqtt_websocket_url()", source)

    def test_connect_packet_matches_app_sdk_defaults(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('?SDK=JavaScript&Version=2.2.15', source)
        self.assertIn('_connect_packet(str(uuid.uuid4()), 300)', source)

    def test_app_named_shadow_response_topics_are_subscribed(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        for suffix in (
            "get/accepted",
            "update/accepted",
            "update/documents",
        ):
            self.assertIn(f'"{suffix}"', source)

    def test_handshake_diagnostics_use_a_strict_safe_header_allow_list(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('error.headers.get("x-amzn-errortype")', source)
        self.assertIn('error.headers.get("x-amzn-requestid")', source)
        self.assertIn('error.headers.get("x-amzn-request-id")', source)
        self.assertIn('error.headers.get("server")', source)
        self.assertNotIn("dict(error.headers)", source)

    def test_websocket_query_matches_current_mobile_app(self) -> None:
        source = API_SOURCE.read_text(encoding="utf-8")
        websocket_method = source.split(
            "async def async_get_mqtt_websocket_url", 1
        )[1].split("def _build_authorization", 1)[0]
        self.assertIn('"X-Amz-Date": amz_date', websocket_method)
        self.assertIn('"X-Amz-SignedHeaders": "host"', websocket_method)
        self.assertNotIn("X-Amz-Expires", websocket_method)


if __name__ == "__main__":
    unittest.main()
