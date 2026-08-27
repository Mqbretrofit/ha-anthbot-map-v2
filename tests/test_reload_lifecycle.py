"""Regression tests for config-entry reload cleanup."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "custom_components" / "anthbot_map" / "__init__.py"


class ReloadLifecycleTests(unittest.TestCase):
    def test_unload_service_names_are_imported(self) -> None:
        """Do not let a stale service name break config-entry reload."""
        tree = ast.parse(INIT_FILE.read_text(encoding="utf-8"))
        imported_constants = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "const"
            for alias in node.names
        }
        unload_entry = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "async_unload_entry"
        )
        used_services = {
            node.id
            for node in ast.walk(unload_entry)
            if isinstance(node, ast.Name) and node.id.startswith("SERVICE_")
        }

        self.assertTrue(used_services)
        self.assertEqual(set(), used_services - imported_constants)

    def test_platform_failure_leaves_background_tasks_running(self) -> None:
        """Only tear down coordinators after every entity platform unloads."""
        source = INIT_FILE.read_text(encoding="utf-8")
        unload = source.split("async def async_unload_entry", 1)[1]
        platform_unload = unload.index("async_unload_platforms")
        failure_return = unload.index("if not unloaded:")
        stop_battery_saver = unload.index("async_stop_battery_saver_monitor")
        stop_live_shadow = unload.index("async_stop_live_shadow")

        self.assertLess(platform_unload, failure_return)
        self.assertLess(failure_return, stop_battery_saver)
        self.assertLess(failure_return, stop_live_shadow)


if __name__ == "__main__":
    unittest.main()
