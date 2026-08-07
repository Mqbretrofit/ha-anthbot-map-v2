"""Regression test for Anthbot cloud timestamp timezone handling."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest


SENSOR_PATH = Path(__file__).parents[1] / "custom_components/anthbot_map/sensor.py"


def _load_datetime_helper():
    source = SENSOR_PATH.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(SENSOR_PATH))
    selected = [
        node
        for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_as_datetime"
    ]
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
    }
    exec(compile(module, str(SENSOR_PATH), "exec"), namespace)
    return namespace["_as_datetime"]


as_datetime = _load_datetime_helper()


class TestTimestampParsing(unittest.TestCase):
    def test_anthbot_local_timestamp_is_converted_from_utc_plus_8(self) -> None:
        self.assertEqual(
            as_datetime("20260808012600"),
            datetime(2026, 8, 7, 17, 26, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
