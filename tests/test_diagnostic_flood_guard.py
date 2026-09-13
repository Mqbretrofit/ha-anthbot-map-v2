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
    "_ERROR_KEYS",
    "_stable_error_text",
    "_stable_error_signature",
    "_state_has_usable_map_fallback",
    "_is_expected_optional_map_miss",
    "_guard_detected_trigger",
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
    def test_truncated_aws_ids_do_not_change_signature(self) -> None:
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

    def test_m9_optional_multi_maps_miss_is_suppressed_with_live_path(self) -> None:
        state = {
            "_map_definition_error": _m9_missing_multi_maps("REQ-1", "HOST-1"),
            "map_time": 1789310369646,
            "_path_definition": {"_path_points": [{"x": -40, "y": -110}]},
            "_history_path_source": "m_series_curpath",
        }
        result = NS["_guard_detected_trigger"](
            state,
            ("map_definition_error", "legacy-unstable-signature"),
        )
        self.assertIsNone(result)

    def test_n8_optional_multi_maps_miss_is_suppressed_with_curpath(self) -> None:
        state = {
            "_map_definition_error": _n8_missing_multi_maps("REQ-2", "HOST-2"),
            "_history_path_source": "n8_curpath",
        }
        result = NS["_guard_detected_trigger"](
            state,
            ("map_definition_error", "legacy-unstable-signature"),
        )
        self.assertIsNone(result)

    def test_missing_multi_maps_without_fallback_still_reports(self) -> None:
        state = {
            "_map_definition_error": _m9_missing_multi_maps("REQ-3", "HOST-3")
        }
        result = NS["_guard_detected_trigger"](
            state,
            ("map_definition_error", "legacy-unstable-signature"),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result[0], "map_definition_error")
        self.assertTrue(result[1].startswith("map_definition_error:"))

    def test_real_map_decode_failure_is_not_suppressed(self) -> None:
        state = {
            "_map_definition_error": (
                "map_manager downloaded but iot_map.bin was not recognized"
            ),
            "_history_path_source": "m_series_curpath",
        }
        result = NS["_guard_detected_trigger"](
            state,
            ("map_definition_error", "legacy-signature"),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result[0], "map_definition_error")

    def test_path_error_remains_reportable_but_request_ids_are_stable(self) -> None:
        first_state = {
            "_path_definition_error": (
                "path download failed <RequestId>REQ-A</RequestId><HostId>HOST-A"
            )
        }
        second_state = {
            "_path_definition_error": (
                "path download failed <RequestId>REQ-B</RequestId><HostId>HOST-B"
            )
        }
        first = NS["_guard_detected_trigger"](
            first_state,
            ("path_definition_error", "old-a"),
        )
        second = NS["_guard_detected_trigger"](
            second_state,
            ("path_definition_error", "old-b"),
        )
        self.assertEqual(first, second)
        self.assertIsNotNone(first)

    def test_non_error_triggers_are_preserved(self) -> None:
        detected = ("no_go_path_crossing", "no-go:7:301")
        self.assertEqual(NS["_guard_detected_trigger"]({}, detected), detected)

    def test_guard_is_installed_after_v2465_reliability(self) -> None:
        source = COMMON.read_text(encoding="utf-8")
        v2465 = source.index("install_v2465_reliability_fixes()")
        guard = source.index("install_diagnostic_flood_guard()", v2465)
        rescue = source.index("install_m9_map_rescue_v2465()", guard)
        self.assertLess(v2465, guard)
        self.assertLess(guard, rescue)

    def test_guard_replaces_report_installer_and_keeps_single_listener(self) -> None:
        source = GUARD.read_text(encoding="utf-8")
        self.assertIn("_install_automatic_diagnostics_reporting", source)
        self.assertIn("_anthbot_auto_diag_listener_remove", source)
        self.assertIn("_anthbot_auto_diag_active_signature", source)
        self.assertIn("_DIAGNOSTIC_HARD_REPEAT_SECONDS", source)
        self.assertIn('trigger == "mower_error_code"', source)


if __name__ == "__main__":
    unittest.main()
