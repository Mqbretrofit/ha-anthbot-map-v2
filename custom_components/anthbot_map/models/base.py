"""Shared model-family detection only; no runtime side effects."""

from __future__ import annotations


def model_family(model: object) -> str:
    """Return the normalized ANTHBOT model family."""
    value = str(model or "").upper().replace("-", " ").replace("_", " ")
    compact = " ".join(value.split())
    if "M9 PRO" in compact or "M9PRO" in compact.replace(" ", ""):
        return "m9_pro"
    if "M9" in compact:
        return "m9"
    if "M5" in compact:
        return "m5"
    return "genie"
