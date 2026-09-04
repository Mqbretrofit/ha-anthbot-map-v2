"""ANTHBOT M9 Pro type module."""

from .base import is_m9_pro_model
from . import m_series_common as _common

TYPE_KEY = "m9_pro"


def matches(model: object) -> bool:
    return is_m9_pro_model(model)


def install_type_support() -> None:
    """M9 Pro uses the verified M-series transport implementation."""
    _common.install_m_series_compat()
