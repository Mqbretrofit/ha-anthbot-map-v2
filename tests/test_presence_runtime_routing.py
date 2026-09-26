from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "custom_components" / "anthbot_map" / "__init__.py"


def _load_all_coordinators():
    source = INIT_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(INIT_FILE))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_all_coordinators"
    )
    namespace = {"DOMAIN": "anthbot_map"}
    isolated = "from __future__ import annotations\n" + ast.unparse(function)
    exec(compile(isolated, str(INIT_FILE), "exec"), namespace)
    return namespace["_all_coordinators"]


def test_presence_runtime_metadata_is_not_treated_as_coordinators() -> None:
    first = object()
    second = object()
    hass = SimpleNamespace(
        data={
            "anthbot_map": {
                "entry-a": [first],
                "_presence_heartbeat_started": True,
                "_presence_heartbeat_unsubscribe": object(),
                "entry-b": [second],
            }
        }
    )

    assert _load_all_coordinators()(hass) == [first, second]


def test_runtime_metadata_is_guarded_in_config_entry_service_loops() -> None:
    source = INIT_FILE.read_text(encoding="utf-8")
    guarded_loop = (
        "for entry_id, coordinators in hass.data.get(DOMAIN, {}).items():\n"
        "            if not isinstance(coordinators, list):\n"
        "                continue"
    )
    assert source.count(guarded_loop) == 2


def test_unload_ignores_runtime_metadata_when_last_mower_entry_is_removed() -> None:
    source = INIT_FILE.read_text(encoding="utf-8")
    unload = source.split("async def async_unload_entry", 1)[1]
    assert "isinstance(value, list) and value" in unload
