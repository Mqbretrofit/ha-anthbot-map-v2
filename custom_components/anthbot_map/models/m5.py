"""ANTHBOT M5 model module."""

from .base import is_m5_model
from .m_series_family import install_family

TYPE_KEY = "m5"


def matches(model: object) -> bool:
    return is_m5_model(model)


def install_type_support() -> None:
    install_family(TYPE_KEY)
