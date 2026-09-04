"""Backward-compatible coordinator import surface.

The working 2.4.3-beta.3 coordinator implementation now lives in
``genie.py``.  Existing imports keep working through this shim so the
refactor does not change runtime behaviour.
"""

from .genie import *  # noqa: F401,F403
