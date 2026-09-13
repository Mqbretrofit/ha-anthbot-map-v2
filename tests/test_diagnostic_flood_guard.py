"""Regression tests for the v2.4.7 automatic-diagnostics flood guard."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re
from typing import Any
import unittest


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
GUARD = INTEGRATION / "models" / "diagnostic_flood_guard.py"
COMMON = INTEGRATION / "models" / "m_series_common.py"

_PURE_NAMES = {
    "_URL_RE",
    "_REQUEST_ID_RE",
    "_HOST_ID_RE",
    "_stable_error_text",
    "_stable_error_signature",
}


def _load_pure_guard_namespace() -> dict[str, Any]:
    """Load only pure helpers so these tests do not require Home Assistant."""
    tree = ast.parse(GUARD.read_text(encoding="utf-8"))
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & _PURE_NAMES:
                selected.append(node)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in _PURE_NAMES:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in _PURE_NAMES:
            selected.append(node)

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Any": Any,
        "hashlib": hashlib,
        "re": re,
    }
    exec(compile(module, str(GUARD), "exec"), namespace)
    return namespace


NS = _load_pure_guard_namespace()


def _m9_missing_multi_maps(request_id: str, host_id: str) -> str:
    return (
        'multi_maps definition download failed (404): <?xml version="1.0" '
        'encoding="UTF-8"?><Error><Code>NoSuchKey</Code>'
        '<Message>The specified key does not exist.</Message>'
        '<Key>MGS02/device/26060LGR00002199/multi_maps/'
        'map_26060LGR00002199_0</Key>'
        f'<RequestId>{request_id}</RequestId><HostId>{host_id}'
    )


def _n8_missing_multi_maps(request_id: str, host_id: str) -> str:
    return (
        'multi_maps definition download failed (404): <?xml version="1.0" '
        'encoding="UTF-8"?><Error><Code>NoSuchKey</Code>'
        '<Message>The specified key does not exist.</Message>'
        '<Key>MGS03/device/2617LLGU000L0187/multi_maps/'
        'map_2617LLGU000L0187_0</Key>'
        f'<RequestId>{request_id}</RequestId><HostId>{host_id}'
    )


class DiagnosticFloodGuardTests(unittest.TestCase):
    def test_m9_truncated_aws_ids_do_not_change_signature(self) -> None:
        first = _m9_missing_multi_maps("A7C5MKCC82NTWXSA", "HOST-ONE-TRUNCATED")
        second = _m9_missing_multi_maps("DIFFERENT-REQUEST", "HOST-TWO-TRUNCATED")

        normalize = NS["_stable_error_text"]
        signature = NS["_stable_error_signature"]

        self.assertEqual(normalize(first), normalize(second))
        self.assertEqual(
            signature("map_definition_error", first),
            signature("map_definition_error", second),
        )
        self.assertNotIn("A7C5MKCC82NTWXSA", normalize(first))
        self.assertNotIn("HOST-ONE-TRUNCATED", normalize(first))

    def test_n8_truncated_aws_ids_do_not_change_signature(self) -> None:
        first = _n8_missing_multi_maps("REQ-N8-A", "HOST-N8-A")
        second = _n8_missing_multi_maps("REQ-N8-B", "HOST-N8-B")
        signature = NS["_stable_error_signature"]
        self.assertEqual(
            signature("map_definition_error", first),
            signature("map_definition_error", second),
        )

    def test_complete_aws_ids_do_not_change_signature(self) -> None:
        first = (
            "NoSuchKey <RequestId>REQ-ONE</RequestId>"
            "<HostId>HOST-ONE</HostId>"
        )
        second = (
            "NoSuchKey <RequestId>REQ-TWO</RequestId>"
            "<HostId>HOST-TWO</HostId>"
        )
        signature = NS["_stable_error_signature"]
        self.assertEqual(
            signature("map_definition_error", first),
            signature("map_definition_error", second),
        )

    def test_real_error_content_still_changes_signature(self) -> None:
        signature = NS["_stable_error_signature"]
        missing = _m9_missing_multi_maps("REQ-A", "HOST-A")
        decode = "map_manager downloaded but iot_map.bin was not recognized"
        self.assertNotEqual(
            signature("map_definition_error", missing),
            signature("map_definition_error", decode),
        )

    def test_path_errors_are_stabilized_without_being_reclassified(self) -> None:
        signature = NS["_stable_error_signature"]
        first = (
            "path download failed <RequestId>REQ-A</RequestId><HostId>HOST-A"
        )
        second = (
            "path download failed <RequestId>REQ-B</RequestId><HostId>HOST-B"
        )
        result = signature("path_definition_error", first)
        self.assertEqual(result, signature("path_definition_error", second))
        self.assertTrue(result.startswith("path_definition_error:"))

    def test_guard_is_installed_after_v2465_reliability(self) -> None:
        source = COMMON.read_text(encoding="utf-8")
        v2465 = source.index("install_v2465_reliability_fixes()")
        guard = source.index("install_diagnostic_flood_guard()", v2465)
        rescue = source.index("install_m9_map_rescue_v2465()", guard)
        self.assertLess(v2465, guard)
        self.assertLess(guard, rescue)

    def test_guard_reuses_existing_reporter_instead_of_stacking_listener(self) -> None:
        source = GUARD.read_text(encoding="utf-8")
        self.assertIn(
            "reliability_v2465._stable_error_signature = _stable_error_signature",
            source,
        )
        self.assertIn(
            "reliability_v2465._stable_error_text = _stable_error_text",
            source,
        )
        self.assertNotIn("_install_automatic_diagnostics_reporting =", source)
        self.assertNotIn("async_add_listener", source)


if __name__ == "__main__":
    unittest.main()
