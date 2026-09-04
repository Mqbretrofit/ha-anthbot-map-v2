"""Model-specific ANTHBOT implementations and routing helpers.

The models package owns all mower-family code. Shared integration modules stay
one level up; aliases below let moved legacy model code keep its proven relative
imports without duplicating common modules inside this package.
"""

from __future__ import annotations

import sys

from .. import api as api
from .. import const as const
from .. import definition_refresh as definition_refresh
from .. import mqtt_live as mqtt_live
from .. import task_events as task_events
from .. import zones as zones

# Compatibility aliases for shared modules used by model code moved from the
# package root. These are aliases only; there are no duplicate files under
# models/.
for _name, _module in {
    "api": api,
    "const": const,
    "definition_refresh": definition_refresh,
    "mqtt_live": mqtt_live,
    "task_events": task_events,
    "zones": zones,
}.items():
    sys.modules[f"{__name__}.{_name}"] = _module

from .base import model_family, model_family_key

# Import the single shared coordinator only after the aliases above are ready:
# root coordinator -> models.genie can then resolve its legacy relative imports.
from .. import coordinator as coordinator
sys.modules[f"{__name__}.coordinator"] = coordinator

__all__ = ["model_family", "model_family_key"]
