"""Shared model-family primitives for ANTHBOT mowers.

This module intentionally contains only model-neutral building blocks.  The
2.4.3-beta.3 Genie behaviour remains in ``genie.py`` unchanged; future model
families (for example M9 Pro) can live beside it without patching Genie code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class AnthbotModelFamily:
    """Describe one isolated mower model family."""

    key: str
    display_name: str


BASE_FAMILY: Final[AnthbotModelFamily] = AnthbotModelFamily(
    key="base",
    display_name="ANTHBOT base",
)


def normalize_model_name(model: object) -> str:
    """Return a stable uppercase model identifier for family dispatch."""

    return str(model or "").strip().upper()
