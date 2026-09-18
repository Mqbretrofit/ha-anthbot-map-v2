"""Model capability guards for optional ANTHBOT hardware features."""

from __future__ import annotations

from typing import Any

from .base import model_family

# Confirmed on real hardware: M9 and M9 Pro do not have a speaker/voice output.
_VOICE_DENY_FAMILIES = frozenset({"m9", "m9_pro"})


def supports_voice(model: object, state: dict[str, Any] | None = None) -> bool:
    """Return whether voice controls may be exposed for this mower.

    M9/M9 Pro are an explicit hard deny even if a cloud payload later contains
    similarly named fields. Genie is confirmed voice-capable. Other families
    are fail-closed unless their live state actually exposes voice-package or
    voice-volume telemetry.
    """
    family = model_family(model)
    if family in _VOICE_DENY_FAMILIES:
        return False

    normalized_model = str(model or "").upper().replace("-", " ").replace("_", " ")
    if "GENIE" in " ".join(normalized_model.split()):
        return True

    live = state if isinstance(state, dict) else {}
    return any(
        key in live
        for key in ("music_cfg", "voice_status", "volume")
    )
