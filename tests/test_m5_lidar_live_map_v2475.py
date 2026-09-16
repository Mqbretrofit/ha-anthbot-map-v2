from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.anthbot_map.models"
MODULE_NAME = f"{PACKAGE}.m5_lidar_live_map_v2475"


def _load_module(previous_refresh):
    cc = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    cc.__path__ = [str(ROOT / "custom_components")]
    am = sys.modules.setdefault("custom_components.anthbot_map", types.ModuleType("custom_components.anthbot_map"))
    am.__path__ = [str(ROOT / "custom_components/anthbot_map")]
    models = sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
    models.__path__ = [str(ROOT / "custom_components/anthbot_map/models")]

    coordinator_mod = types.ModuleType("custom_components.anthbot_map.coordinator")

    class Coordinator:
        _async_refresh_map_definition = previous_refresh

    coordinator_mod.AnthbotGenieDataUpdateCoordinator = Coordinator
    sys.modules["custom_components.anthbot_map.coordinator"] = coordinator_mod

    def select_map_archive(state):
        return types.SimpleNamespace(
            filename=None,
            md5=None,
            map_id=None,
            map_time=str(state.get("map_time") or "") or None,
            map_tar_time=None,
        )

    def map_archive_diagnostics(state, selection):
        del state
        return {"selected_file": selection.filename, "map_time": selection.map_time}

    def map_definition_cache_key(serial, state, selection):
        del selection
        return f"live_file=map_{serial}.txt|live_map_time={state.get('map_time', '')}|archive=file="

    defn = types.ModuleType("custom_components.anthbot_map.definition_refresh")
    defn.MAP_DEFINITION_REFRESH_SECONDS = 900.0
    defn.MAP_DEFINITION_RETRY_SECONDS = 60.0
    defn.select_map_archive = select_map_archive
    defn.map_archive_diagnostics = map_archive_diagnostics
    defn.map_definition_cache_key = map_definition_cache_key
    sys.modules["custom_components.anthbot_map.definition_refresh"] = defn

    sys.modules.pop(MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        ROOT / "custom_components/anthbot_map/models/m5_lidar_live_map_v2475.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, Coordinator


class FakeAccount:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def async_get_device_map_definition(self, serial):
        self.calls.append(serial)
        if self.error is not None:
            raise self.error
        return self.result


class Device:
    def __init__(self, model):
        self.model = model


class Client:
    def __init__(self, serial):
        self.serial_number = serial


def make_coordinator(cls, model, account):
    obj = cls()
    obj.device = Device(model)
    obj.client = Client("26060LGQ00000641")
    obj.account_client = account
    obj._map_definition = None
    obj._map_definition_source = None
    obj._map_definition_error = None
    obj._last_map_download_monotonic = 0.0
    obj._last_map_time = None
    obj._last_map_key = None
    return obj


class M5LidarLiveMapTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_m5_lidar_is_intercepted(self):
        calls = []

        async def previous(self, state, now, *, allow_periodic):
            del now
            calls.append((self.device.model, state, allow_periodic))
            return {"legacy": True}, True

        module, Coordinator = _load_module(previous)
        module.install_m5_lidar_live_map_fix()
        for model in ("Anthbot M5", "Anthbot M9 Pro", "Anthbot N8", "Genie 1000"):
            obj = make_coordinator(
                Coordinator,
                model,
                FakeAccount(result={"_map_raster": {}}),
            )
            result = await obj._async_refresh_map_definition(
                {"map_time": 1}, 10.0, allow_periodic=False
            )
            self.assertEqual(result, ({"legacy": True}, True))
            self.assertEqual(obj.account_client.calls, [])
        self.assertEqual(len(calls), 4)

    async def test_m5_lidar_prefers_verified_live_file(self):
        previous_calls = []

        async def previous(self, state, now, *, allow_periodic):
            del self, state, now, allow_periodic
            previous_calls.append(True)
            return {"legacy": True}, True

        module, Coordinator = _load_module(previous)
        module.install_m5_lidar_live_map_fix()
        live = {
            "_map_raster": {"width": 10},
            "_download_source": {
                "filename": "map_26060LGQ00000641.txt",
                "category": "device",
                "sub_category": "map",
            },
        }
        account = FakeAccount(result=live)
        obj = make_coordinator(Coordinator, "Anthbot M5 LiDAR", account)
        diagnostics, attempted = await obj._async_refresh_map_definition(
            {"map_time": 1789549862427}, 100.0, allow_periodic=False
        )
        self.assertTrue(attempted)
        self.assertEqual(account.calls, ["26060LGQ00000641"])
        self.assertEqual(previous_calls, [])
        self.assertIs(obj._map_definition, live)
        self.assertEqual(obj._map_definition_source, "live_map")
        self.assertEqual(diagnostics["preferred_source"], "live_map")
        self.assertEqual(
            diagnostics["m5_lidar_live_map_probe"]["filename"],
            "map_26060LGQ00000641.txt",
        )
        self.assertEqual(
            diagnostics["m5_lidar_live_map_probe"]["sub_category"], "map"
        )

    async def test_live_failure_preserves_entire_previous_fallback_chain(self):
        previous_calls = []

        async def previous(self, state, now, *, allow_periodic):
            del state, now, allow_periodic
            previous_calls.append(True)
            self._map_definition = {"_map_raster": {"fallback": 1}}
            self._map_definition_source = "multi_maps_fallback"
            return {"active_source": "multi_maps_fallback"}, True

        module, Coordinator = _load_module(previous)
        module.install_m5_lidar_live_map_fix()
        obj = make_coordinator(
            Coordinator,
            "MGS02Radar",
            FakeAccount(error=RuntimeError("404")),
        )
        diagnostics, attempted = await obj._async_refresh_map_definition(
            {"map_time": 5}, 100.0, allow_periodic=False
        )
        self.assertTrue(attempted)
        self.assertEqual(previous_calls, [True])
        self.assertEqual(obj._map_definition_source, "multi_maps_fallback")
        self.assertEqual(diagnostics["m5_lidar_live_map_probe"]["status"], "error")

    async def test_transient_error_never_replaces_existing_live_map(self):
        previous_calls = []

        async def previous(self, state, now, *, allow_periodic):
            del state, now, allow_periodic
            previous_calls.append(True)
            self._map_definition_source = "legacy_should_not_run"
            return {}, True

        module, Coordinator = _load_module(previous)
        module.install_m5_lidar_live_map_fix()
        obj = make_coordinator(
            Coordinator,
            "Anthbot M5 LiDAR",
            FakeAccount(error=RuntimeError("temporary")),
        )
        obj._map_definition = {"_map_raster": {"width": 1}}
        obj._map_definition_source = "live_map"
        obj._m5_lidar_live_signature = "map_26060LGQ00000641.txt|map_time=1"
        obj._m5_lidar_live_success_last = 1.0
        diagnostics, attempted = await obj._async_refresh_map_definition(
            {"map_time": 2}, 1000.0, allow_periodic=False
        )
        self.assertTrue(attempted)
        self.assertEqual(previous_calls, [])
        self.assertEqual(obj._map_definition_source, "live_map")
        self.assertEqual(diagnostics["m5_lidar_live_map_probe"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
