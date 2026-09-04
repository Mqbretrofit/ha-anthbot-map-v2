"""Shared model-family primitives for ANTHBOT mowers.

The v2.4.3-beta.3 Genie implementation remains isolated in ``genie.py``.
Model dispatch belongs here so model-specific modules do not have to guess
families with ad-hoc string checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class AnthbotModelFamily:
    """Describe one isolated mower model family."""

    key: str
    display_name: str


BASE_FAMILY: Final[AnthbotModelFamily] = AnthbotModelFamily("base", "ANTHBOT base")
GENIE_FAMILY: Final[AnthbotModelFamily] = AnthbotModelFamily("genie", "ANTHBOT Genie")
M9_PRO_FAMILY: Final[AnthbotModelFamily] = AnthbotModelFamily("m9_pro", "ANTHBOT M9 Pro")
M5_FAMILY: Final[AnthbotModelFamily] = AnthbotModelFamily("m5", "ANTHBOT M5")
UNKNOWN_FAMILY: Final[AnthbotModelFamily] = AnthbotModelFamily("unknown", "ANTHBOT unknown")


def normalize_model_name(model: object) -> str:
    """Return a stable uppercase model identifier for family dispatch."""

    return str(model or "").strip().upper()


def model_family(model: object) -> AnthbotModelFamily:
    """Return the explicit model family for one mower model string."""

    value = normalize_model_name(model)
    if "GENIE" in value:
        return GENIE_FAMILY
    if "M9" in value:
        return M9_PRO_FAMILY
    if "M5" in value:
        return M5_FAMILY
    if not value:
        return UNKNOWN_FAMILY
    return BASE_FAMILY


def is_genie_model(model: object) -> bool:
    """Return whether the model belongs to the Genie family."""

    return model_family(model) is GENIE_FAMILY


def is_m9_pro_model(model: object) -> bool:
    """Return whether the model belongs to the M9 Pro family."""

    return model_family(model) is M9_PRO_FAMILY


def is_m5_model(model: object) -> bool:
    """Return whether the model belongs to the M5 family."""

    return model_family(model) is M5_FAMILY
