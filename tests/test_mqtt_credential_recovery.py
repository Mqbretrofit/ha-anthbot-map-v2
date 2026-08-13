"""Regression tests for MQTT WebSocket credential recovery."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "anthbot_map" / "mqtt_live.py"


class MqttCredentialRecoveryTests(unittest.TestCase):
    """Ensure rejected AWS IoT handshakes cannot loop cached credentials."""

    def test_403_and_404_trigger_bounded_credential_recovery(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("err.status not in (403, 404)", source)
        self.assertIn("self._force_credential_refresh = True", source)
        self.assertIn("self._force_account_reauthentication = True", source)


if __name__ == "__main__":
    unittest.main()
