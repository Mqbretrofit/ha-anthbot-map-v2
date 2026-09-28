"""Regression coverage for the clean v2.4.9.3 M9 settings rebuild."""

from __future__ import annotations

import ast
from pathlib import Path
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _load_functions(path: Path, names: set[str]) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations")],
                level=0,
            ),
            *selected,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {"time": time}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


class M9CleanSettingsRebuildTests(unittest.TestCase):
    def test_app_desired_command_is_mirrored_as_property_settings(self) -> None:
        namespace = _load_functions(
            INTEGRATION / "mqtt_live.py",
            {
                "_coerce_small_int",
                "_find_nested_setting",
                "_setting_patch_from_service_payload",
            },
        )
        extract = namespace["_setting_patch_from_service_payload"]
        patch = extract(
            {
                "current": {
                    "state": {
                        "desired": {
                            "cmd": "device_config",
                            "data": {
                                "pobctl_switch": 0,
                                "pobctl_level": 2,
                                "mow_count": 2,
                                "cutter_height": 45,
                            },
                        }
                    }
                }
            }
        )
        self.assertEqual(patch["device_config"]["pobctl_switch"], 0)
        self.assertEqual(patch["device_config"]["pobctl_level"], 2)
        self.assertEqual(patch["param_set"]["mow_count"], 2)
        self.assertEqual(patch["param_set"]["cutter_height"], 45)

    def test_app_zone_command_mirrors_manual_and_automatic_zone_settings(self) -> None:
        namespace = _load_functions(
            INTEGRATION / "mqtt_live.py",
            {
                "_coerce_small_int",
                "_find_nested_setting",
                "_setting_patch_from_service_payload",
            },
        )
        extract = namespace["_setting_patch_from_service_payload"]
        patch = extract(
            {
                "state": {
                    "desired": {
                        "cmd": "area_set",
                        "data": {
                            "custom_areas": [
                                {"id": 1, "mow_count": 2, "cutter_height": 45}
                            ],
                            "region_areas": [
                                {"id": 7, "mow_count": 1, "obstacle_avoid_level": 2}
                            ],
                        },
                    }
                }
            }
        )
        zones = patch["_app_zone_definition_mirror"]
        self.assertEqual(zones["custom_areas"][0]["mow_count"], 2)
        self.assertEqual(zones["region_areas"][0]["obstacle_avoid_level"], 2)

    def test_m9_device_config_is_authoritative_and_nested_state_is_preserved(self) -> None:
        namespace = _load_functions(
            INTEGRATION / "coordinator.py",
            {"_setting_int", "_merge_live_setting_patch"},
        )
        namespace["_SETTING_NESTED_KEYS"] = (
            "device_config",
            "pobctl",
            "param_set",
            "nest_param_set",
        )
        merge = namespace["_merge_live_setting_patch"]
        state = {
            "device_config": {"pobctl_switch": 1, "unrelated": 9},
            "pobctl": {"switch": 1, "level": 1},
            "param_set": {"mow_count": 1, "rid_switch": 1},
        }
        merge(
            state,
            {
                "device_config": {"pobctl_switch": 0, "pobctl_level": 2},
                "pobctl": {"switch": 1, "level": 0},
                "param_set": {"mow_count": 2},
            },
            "M9 PRO",
        )
        self.assertEqual(state["device_config"]["pobctl_switch"], 0)
        self.assertEqual(state["pobctl"]["switch"], 0)
        self.assertEqual(state["pobctl"]["level"], 2)
        self.assertEqual(state["device_config"]["unrelated"], 9)
        self.assertEqual(state["param_set"]["rid_switch"], 1)
        self.assertEqual(state["param_set"]["mow_count"], 2)

    def test_m9_writes_keep_switch_and_level_independent(self) -> None:
        control = _read(
            "custom_components/anthbot_map/models/m_series_control.py"
        )
        number = _read("custom_components/anthbot_map/number.py")
        switch = _read("custom_components/anthbot_map/switch.py")
        self.assertIn('data={"pobctl_switch": int(bool(switch))}', control)
        self.assertIn('data={"pobctl_level": int(level)}', control)
        self.assertIn('data = {"level": int_value}', number)
        self.assertIn('data = {"switch": 1 if enabled else 0}', switch)

    def test_param_set_is_complete_and_global_identity_is_unambiguous(self) -> None:
        control = _read(
            "custom_components/anthbot_map/models/m_series_control.py"
        )
        identity = _read(
            "custom_components/anthbot_map/models/entity_identity.py"
        )
        self.assertIn('current = reported.get("param_set")', control)
        self.assertIn("merged.update(normalized_changes)", control)
        self.assertIn('"setting": entity.entity_description.key', identity)

    def test_frontend_uses_global_setting_metadata_and_refreshes_open_panel(self) -> None:
        runtime = _read(
            "custom_components/anthbot_map/frontend/anthbot-map-card.js"
        )
        standalone = _read("www/anthbot-map/anthbot-map-card.js")
        self.assertEqual(runtime, standalone)
        self.assertIn("findSettingEntity(domain, setting)", runtime)
        self.assertIn("&& !attrs.zone_kind", runtime)
        self.assertIn("&& attrs.zone_id === undefined", runtime)
        self.assertIn("this.refreshOpenPanelValues();", runtime)

    def test_frontend_scopes_both_zone_kinds_by_stable_metadata(self) -> None:
        runtime = _read(
            "custom_components/anthbot_map/frontend/anthbot-map-card.js"
        )
        identity = _read(
            "custom_components/anthbot_map/models/entity_identity.py"
        )
        coordinator = _read("custom_components/anthbot_map/coordinator.py")
        resolver = _read(
            "custom_components/anthbot_map/frontend/serial-entity-resolver.js"
        )
        self.assertIn('String(attrs.zone_kind || "") === kind', runtime)
        self.assertIn("Number(attrs.zone_id) === zoneId", runtime)
        self.assertIn('String(attrs.setting || "") === setting', runtime)
        self.assertIn('data-zone-control="number"', runtime)
        self.assertIn('data-zone-obstacle="true"', runtime)
        self.assertIn('"setting": "mowing_mode"', identity)
        self.assertIn('reported["_area_definition"] = self._area_definition', coordinator)
        self.assertIn("retries=3", coordinator)
        self.assertIn("exactSettingKeys.has(requestedSetting)", resolver)
        self.assertIn("function (switchEntityId, levelEntityId, ...rest)", resolver)

    def test_zone_updates_preserve_open_drawers_without_forced_refresh(self) -> None:
        runtime = _read(
            "custom_components/anthbot_map/frontend/anthbot-map-card.js"
        )
        resolver = _read(
            "custom_components/anthbot_map/frontend/serial-entity-resolver.js"
        )
        self.assertIn("this.openSettingsSections = new Set();", runtime)
        self.assertIn("this.openZoneSettings = new Set();", runtime)
        self.assertIn("this.openSettingsSections.has(key)", runtime)
        self.assertIn("this.openZoneSettings.has(zoneKey)", runtime)
        self.assertIn("readPanelSessionState(config.entity)", runtime)
        self.assertIn("this.savePanelSessionState();", runtime)
        self.assertIn("liveZoneForControl(tile)", runtime)
        self.assertIn("liveValue !== undefined && liveValue !== null", runtime)
        self.assertIn("liveZone?.obstacle_avoid_level", runtime)
        self.assertIn("this.refreshOpenPanelValues?.();", resolver)
        availability_refresh = resolver.split(
            "const originalUpdateRenderer = proto.updateRenderer;", 1
        )[1]
        self.assertNotIn("this.renderAppPanel?.();", availability_refresh)
        self.assertGreaterEqual(
            runtime.count("if (!zoneContext?.zone) this.scheduleRefresh();"),
            5,
        )

    def test_information_popover_uses_active_zone_height(self) -> None:
        runtime = _read(
            "custom_components/anthbot_map/frontend/anthbot-map-card.js"
        )
        self.assertIn("resolveActiveMowingContext(progressEntity", runtime)
        self.assertIn('taskType === "manual_zone"', runtime)
        self.assertIn('taskType === "auto_zone"', runtime)
        self.assertIn("mowingZonesFromPoints(taskData.points)", runtime)
        self.assertIn("zone?.cutter_height ?? zone?.cutting_height", runtime)
        self.assertIn(
            '`${progressText} · ${mowingContext.label}`',
            runtime,
        )
        self.assertIn(
            'label: allNames.length ? allNames.join(" + ") : fallback',
            runtime,
        )
        self.assertIn("mowingCutHeights(mowingContext, cuttingHeight)", runtime)


if __name__ == "__main__":
    unittest.main()
