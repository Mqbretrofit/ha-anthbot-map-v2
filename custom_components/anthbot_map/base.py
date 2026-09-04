"""Shared model/type primitives for ANTHBOT mowers.

Every mower type is routed explicitly. Model-specific behavior lives in its
own module (genie.py, m5.py, m9.py, m9_pro.py, ...).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class AnthbotModelFamily:
    """Describe one isolated mower model family."""

    key: str
    display_name: str


BASE_FAMILY: Final = AnthbotModelFamily("base", "ANTHBOT base")
GENIE_FAMILY: Final = AnthbotModelFamily("genie", "ANTHBOT Genie")
M5_FAMILY: Final = AnthbotModelFamily("m5", "ANTHBOT M5")
M9_FAMILY: Final = AnthbotModelFamily("m9", "ANTHBOT M9")
M9_PRO_FAMILY: Final = AnthbotModelFamily("m9_pro", "ANTHBOT M9 Pro")
UNKNOWN_FAMILY: Final = AnthbotModelFamily("unknown", "ANTHBOT unknown")


def normalize_model_name(model: object) -> str:
    return str(model or "").strip().upper().replace("-", " ").replace("_", " ")


def model_family(model: object) -> AnthbotModelFamily:
    """Return the explicit mower type; specific variants win before base names."""

    value = " ".join(normalize_model_name(model).split())
    if "GENIE" in value:
        return GENIE_FAMILY
    if "M9" in value and "PRO" in value:
        return M9_PRO_FAMILY
    if "M9" in value:
        return M9_FAMILY
    if "M5" in value:
        return M5_FAMILY
    if not value:
        return UNKNOWN_FAMILY
    return BASE_FAMILY


def model_family_key(model: object) -> str:
    """Return the stable type key used for dispatch."""

    return model_family(model).key


def is_genie_model(model: object) -> bool:
    return model_family_key(model) == "genie"


def is_m5_model(model: object) -> bool:
    return model_family_key(model) == "m5"


def is_m9_model(model: object) -> bool:
    return model_family_key(model) == "m9"


def is_m9_pro_model(model: object) -> bool:
    return model_family_key(model) == "m9_pro"
