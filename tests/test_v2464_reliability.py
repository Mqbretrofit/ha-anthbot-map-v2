from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELIABILITY = ROOT / "custom_components/anthbot_map/models/reliability_v2464.py"
COMMON = ROOT / "custom_components/anthbot_map/models/m_series_common.py"


class V2464ReliabilitySourceTests(unittest.TestCase):
    def test_reliability_module_compiles(self) -> None:
        source = RELIABILITY.read_text(encoding="utf-8")
        compile(source, str(RELIABILITY), "exec")

    def test_live_shadow_supervisor_survives_runtime_transport_errors(self) -> None:
        source = RELIABILITY.read_text(encoding="utf-8")
        self.assertIn("async def _resilient_live_shadow_run", source)
        self.assertIn("except asyncio.CancelledError", source)
        self.assertIn("except Exception as err", source)
        self.assertIn("_CREDENTIAL_ROTATE_AFTER_FAILURES = 3", source)
        self.assertIn("force_refresh=True", source)
        self.assertIn("refresh_on_expiry_and_after_reconnect_failures", source)
        self.assertIn(
            "mqtt_live.AnthbotLiveShadowListener.async_run = _resilient_live_shadow_run",
            source,
        )

    def test_automatic_diagnostics_are_edge_triggered_not_hourly(self) -> None:
        source = RELIABILITY.read_text(encoding="utf-8")
        self.assertIn("active_signature", source)
        self.assertIn("if signature == active_signature", source)
        self.assertIn("active_signature = None", source)
        self.assertIn("initial[1] if initial is not None else None", source)
        self.assertIn('if trigger == "mower_error_code"', source)
        self.assertNotIn("60 * 60", source)

    def test_historical_task_event_errors_are_marked_and_not_replayed(self) -> None:
        source = RELIABILITY.read_text(encoding="utf-8")
        self.assertIn("_TASK_EVENT_FRESH_SECONDS = 15 * 60", source)
        self.assertIn('"active_task_event_error": bool(is_error and fresh)', source)
        self.assertIn("robot_error_reporting._is_error_event = _fresh_error_event", source)
        self.assertIn('report["latest_task_event_status"]', source)
        self.assertIn('attributes["latest_task_event_stale"]', source)

    def test_m_series_map_ids_are_kept_in_separate_protocol_layers(self) -> None:
        source = RELIABILITY.read_text(encoding="utf-8")
        self.assertIn('"identity_model": "separate_logical_and_raster_ids"', source)
        self.assertIn('"live_map_id"', source)
        self.assertIn('"area_id"', source)
        self.assertIn('"plan_id"', source)
        self.assertIn('"raster_map_id"', source)
        self.assertIn('"archive_naming": "serial_based"', source)
        self.assertIn("m_series_legacy._m_series_map_candidates = safe_legacy_candidates", source)
        self.assertIn("loaded_signature == signature", source)

    def test_reliability_layer_is_installed_after_existing_adapters(self) -> None:
        source = COMMON.read_text(encoding="utf-8")
        self.assertIn(
            "from .reliability_v2464 import install_runtime_reliability_fixes",
            source,
        )
        self.assertIn("install_runtime_reliability_fixes()", source)
        self.assertGreater(
            source.index("install_runtime_reliability_fixes()"),
            source.index("install_runtime_optimization_diagnostics()"),
        )


if __name__ == "__main__":
    unittest.main()
