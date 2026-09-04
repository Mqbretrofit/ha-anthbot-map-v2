"""ANTHBOT M9 model module."""

from .base import is_m9_model
from .m_series_family import install_family

TYPE_KEY = "m9"


def matches(model: object) -> bool:
    return is_m9_model(model)


def install_type_support() -> None:
    install_family(TYPE_KEY)
