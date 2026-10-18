"""Model capability guards for optional ANTHBOT hardware features."""

from __future__ import annotations

from typing import Any

from .base import model_family

# M-series models do not support spoken voice-package playback.
# M9/M9 Pro can still expose audible beep volume separately.
_VOICE_PACK_DENY_FAMILIES = frozenset({"m5", "m9", "m9_pro"})


def _normalized_model(model: object) -> str:
    return " ".join(
        str(model or "").upper().replace("-", " ").replace("_", " ").split()
    )


def supports_voice_volume(model: object, state: dict[str, Any] | None = None) -> bool:
    """Return whether the mower may expose audible volume control."""
    family = model_family(model)
    if family in {"m9", "m9_pro"}:
        return True

    if "GENIE" in _normalized_model(model):
        return True

    live = state if isinstance(state, dict) else {}
    return "volume" in live


def supports_voice_packages(
    model: object, state: dict[str, Any] | None = None
) -> bool:
    """Return whether spoken voice packs may be selected/installed."""
    family = model_family(model)
    if family in _VOICE_PACK_DENY_FAMILIES:
        return False

    if "GENIE" in _normalized_model(model):
        return True

    live = state if isinstance(state, dict) else {}
    return any(key in live for key in ("music_cfg", "voice_status"))
