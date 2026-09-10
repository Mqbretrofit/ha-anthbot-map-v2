from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "custom_components" / "anthbot_map" / "models" / "n8_dump_payload.py"
)

spec = importlib.util.spec_from_file_location("n8_dump_payload_test", MODULE_PATH)
assert spec is not None and spec.loader is not None
MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def test_dump_area_matches_recovered_app_wire_shape() -> None:
    area = MODULE.build_dump_area(
        500,
        [[1000, 2000], [2500, 2000], [2500, 3500], [1000, 3500]],
    )
    assert area == {
        "vertexs": [[1000, 2000], [2500, 2000], [2500, 3500], [1000, 3500]],
        "id": 500,
        "grassId": 500,
        "eid": -1,
        "remote": False,
        "disable": False,
        "warningType": 0,
    }


def test_area_set_add_and_delete_payloads_are_separate() -> None:
    area = MODULE.build_dump_area(
        501,
        [[0, 0], [1500, 0], [1500, 1500], [0, 1500]],
    )
    assert MODULE.build_area_set_data([area], []) == {
        "dump_grass_areas": [area],
        "delete_dump_areas": [],
    }
    assert MODULE.build_area_set_data([], [501]) == {
        "dump_grass_areas": [],
        "delete_dump_areas": [501],
    }


def test_remote_dump_set_requires_remote_geometry() -> None:
    area = MODULE.build_dump_area(
        599,
        [[-1500, -1500], [0, -1500], [0, 0], [-1500, 0]],
        remote=True,
    )
    assert MODULE.build_remote_dump_data("build_dump_set", [area]) == {
        "dump_grass_areas": [area],
        "state": "build_dump_set",
    }
    assert MODULE.build_remote_dump_data("build_dump_init") == {
        "state": "build_dump_init"
    }
    assert MODULE.build_remote_dump_data("build_dump_continue") == {
        "state": "build_dump_continue"
    }
    assert MODULE.build_remote_dump_data("build_dump_finish") == {
        "state": "build_dump_finish"
    }


def test_dump_payload_rejects_invalid_ids_and_geometry() -> None:
    valid_vertices = [[0, 0], [1500, 0], [1500, 1500], [0, 1500]]
    for invalid_id in (499, 600, True, "500"):
        try:
            MODULE.build_dump_area(invalid_id, valid_vertices)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid dump id accepted: {invalid_id!r}")

    for invalid_vertices in (
        [],
        [[0, 0]],
        [[0, 0], [1, 0], [1, 1]],
        [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
        [[0, 0], [1, 0], [1, 1], [0, "1"]],
    ):
        try:
            MODULE.build_dump_area(500, invalid_vertices)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid geometry accepted: {invalid_vertices!r}")


def test_remote_set_rejects_local_area_and_unknown_state() -> None:
    local_area = MODULE.build_dump_area(
        500,
        [[0, 0], [1500, 0], [1500, 1500], [0, 1500]],
    )
    try:
        MODULE.build_remote_dump_data("build_dump_set", [local_area])
    except ValueError:
        pass
    else:
        raise AssertionError("remote build accepted a local dumping-area object")

    try:
        MODULE.build_remote_dump_data("build_dump_unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown remote dumping state was accepted")
