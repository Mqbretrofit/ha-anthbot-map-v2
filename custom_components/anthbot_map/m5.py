"""ANTHBOT M5 type module."""

from .base import is_m5_model
from . import m_series_common as _common

TYPE_KEY = "m5"


def matches(model: object) -> bool:
    return is_m5_model(model)


def install_type_support() -> None:
    """Register M5; it currently uses the shared default M-series policies."""
    _common.register_family(TYPE_KEY)
    _common.install_m_series_compat()
