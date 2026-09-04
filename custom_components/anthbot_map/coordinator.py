"""Backward-compatible coordinator import surface.

The working 2.4.3-beta.3 Genie coordinator implementation lives under
``models/genie.py``. Existing imports keep working through this shared shim.
"""

from .models.genie import *  # noqa: F401,F403
