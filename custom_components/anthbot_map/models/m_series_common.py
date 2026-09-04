"""M-series compatibility entry point for the clean rebuild."""

from .entity_identity import install_setting_entity_identity
from .m_series_legacy import install_m_series_compat as _install_legacy
from .m_series_control import install_m_series_control_support
from .m_series_map import install_m_series_map_support
from .m_series_path import install_m_series_path_support
from .m_series_status import install_m_series_status_support

_INSTALLED = False


def install_m_series_compat() -> None:
    """Install rebuild compatibility, then verified model-specific layers."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    # Identity metadata is global (Genie + M-series), but installing it here is
    # safe because this module is imported before Home Assistant creates any of
    # the number/switch/select platform entities.
    install_setting_entity_identity()
    _install_legacy()
    install_m_series_control_support()
    install_m_series_path_support()
    install_m_series_map_support()
    install_m_series_status_support()
