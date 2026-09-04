"""Model-specific ANTHBOT package.

The working 2.4.3-beta.3 runtime stays unchanged.  This package only provides
model-specific module boundaries so model behaviour can be evolved without
mixing device families in the integration root.
"""

from __future__ import annotations

import sys

# m_series_common.py is an exact relocation of the proven beta3
# m_series_compat.py implementation.  These aliases let its original relative
# imports keep resolving identically after the move into models/.
from .. import api as _api
from .. import coordinator as _coordinator
from .. import definition_refresh as _definition_refresh
from .. import mqtt_live as _mqtt_live

sys.modules.setdefault(f"{__name__}.api", _api)
sys.modules.setdefault(f"{__name__}.coordinator", _coordinator)
sys.modules.setdefault(f"{__name__}.definition_refresh", _definition_refresh)
sys.modules.setdefault(f"{__name__}.mqtt_live", _mqtt_live)

from .base import model_family

__all__ = ["model_family"]
