"""ANTHBOT M9 Pro model module."""

from .base import is_m9_pro_model
from .m_series_family import install_family

TYPE_KEY = "m9_pro"


def matches(model: object) -> bool:
    return is_m9_pro_model(model)


def install_type_support() -> None:
    install_family(TYPE_KEY)
