"""ANTHBOT M9 type module."""

from .base import is_m9_model, model_family_key
from . import m_series_common as _common

TYPE_KEY = "m9"


def matches(model: object) -> bool:
    return is_m9_model(model)


def _compat_family(model: object) -> str:
    """Map standard M9 onto the proven M-series transport behavior only."""
    key = model_family_key(model)
    return "m9_pro" if key == "m9" else key


def install_type_support() -> None:
    """Register standard M9 with the shared M-series transport layer."""
    _common._model_family = _compat_family
    _common.install_m_series_compat()
