"""Tests for app-compatible editable edge settings."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import types
import unittest
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "anthbot_edge_test"


def _load_zones_module():
    """Load zones.py without importing Home Assistant or the integration."""
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components/anthbot_map")]
    sys.modules.setdefault(PACKAGE, package)

    api_module = types.ModuleType(f"{PACKAGE}.api")

    class AnthbotGenieApiError(Exception):
        """Minimal API error used by the zone helper."""

    api_module.AnthbotGenieApiError = AnthbotGenieApiError
    sys.modules.setdefault(f"{PACKAGE}.api", api_module)

    module_name = f"{PACKAGE}.zones"
    spec = importlib.util.spec_from_file_location(
        module_name,
        ROOT / "custom_components/anthbot_map/zones.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


zones = _load_zones_module()
async_update_edge_settings = zones.async_update_edge_settings


class TestEdgeSettings(unittest.IsolatedAsyncioTestCase):
    """Ensure one edge update preserves the app's complete edge list."""

    async def test_update_edge_settings_preserves_complete_edge_list(self) -> None:
        client = SimpleNamespace(
            async_publish_service_command=AsyncMock(),
            async_request_all_properties=AsyncMock(),
        )
        coordinator = SimpleNamespace(
            reported_state={
                "_area_definition": {
                    "ridable_areas": [
                        {
                            "id": 7,
                            "name": "North",
                            "cutter_height": 40,
                            "ride_distance": 5,
                            "vertexs": [1, 2],
                        },
                        {
                            "id": 8,
                            "name": "South",
                            "cutter_height": 60,
                            "ride_distance": 20,
                            "vertexs": [3, 4],
                        },
                    ]
                }
            },
            client=client,
            apply_ridable_area_settings=unittest.mock.Mock(),
            async_request_refresh=AsyncMock(),
        )

        with patch(
            f"{PACKAGE}.zones.asyncio.sleep",
            new=AsyncMock(),
        ):
            await async_update_edge_settings(
                coordinator,
                edge_id=7,
                cutter_height=50,
                ride_distance=10,
            )

        client.async_publish_service_command.assert_awaited_once_with(
            cmd="ridable_area_set",
            data={
                "ridable_areas": [
                    {
                        "id": 7,
                        "name": "North",
                        "cutter_height": 50,
                        "ride_distance": 10,
                        "vertexs": [1, 2],
                    },
                    {
                        "id": 8,
                        "name": "South",
                        "cutter_height": 60,
                        "ride_distance": 20,
                        "vertexs": [3, 4],
                    },
                ],
                "delete_ridable_area": [],
            },
        )
        client.async_request_all_properties.assert_awaited_once_with()
        coordinator.apply_ridable_area_settings.assert_called_once_with(
            [
                {
                    "id": 7,
                    "name": "North",
                    "cutter_height": 50,
                    "ride_distance": 10,
                    "vertexs": [1, 2],
                },
                {
                    "id": 8,
                    "name": "South",
                    "cutter_height": 60,
                    "ride_distance": 20,
                    "vertexs": [3, 4],
                },
            ]
        )
        coordinator.async_request_refresh.assert_awaited_once_with()

    def test_frontend_prefers_fresh_separate_edge_definition(self) -> None:
        source = (
            ROOT / "custom_components/anthbot_map/frontend/edge-settings.js"
        ).read_text(encoding="utf-8")
        direct = "card.entity?.attributes?.ridable_areas"
        embedded = 'for(const key of ["ridable_areas","ridableAreas"])'
        self.assertLess(source.index(direct), source.index(embedded))


if __name__ == "__main__":
    unittest.main()
