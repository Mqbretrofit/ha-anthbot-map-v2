"""ANTHBOT M9 type module."""

from .base import is_m9_model
from . import m_series_common as _common

TYPE_KEY = "m9"


def matches(model: object) -> bool:
    return is_m9_model(model)


def install_type_support() -> None:
    """Register standard M9 with the shared transport layer."""
    _common.register_family(TYPE_KEY)
    _common.install_m_series_compat()
