"""Runtime isolation for M5/M9/M9 Pro coordinators.

Genie keeps the exact 2.4.3-beta.3 coordinator class. M-series compatibility
patches a dedicated subclass only and never the Genie class itself.
"""

from __future__ import annotations

import sys
from typing import Any

from .base import model_family_key
from .genie import AnthbotGenieDataUpdateCoordinator as GenieDataUpdateCoordinator
from . import m_series_common as common


class MSeriesDataUpdateCoordinator(GenieDataUpdateCoordinator):
    """Coordinator subclass used exclusively by M5/M9/M9 Pro."""


common.AnthbotGenieDataUpdateCoordinator = MSeriesDataUpdateCoordinator


def coordinator_factory(*args: Any, **kwargs: Any):
    device = kwargs.get("device")
    family = model_family_key(getattr(device, "model", None))
    coordinator_cls = MSeriesDataUpdateCoordinator if family in {"m5", "m9", "m9_pro"} else GenieDataUpdateCoordinator
    return coordinator_cls(*args, **kwargs)


def install_root_factory() -> None:
    package_name = __name__.rsplit(".models.", 1)[0]
    package = sys.modules.get(package_name)
    if package is not None:
        package.AnthbotGenieDataUpdateCoordinator = coordinator_factory
