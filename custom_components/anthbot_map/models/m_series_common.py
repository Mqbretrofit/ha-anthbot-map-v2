"""Model compatibility entry point for the clean rebuild."""

from .entity_identity import install_setting_entity_identity
from .genie_path_diagnostics import install_genie_path_diagnostics
from .genie_status import install_genie_live_status_support
from .live_task_events import install_live_task_event_refresh
from .m_series_legacy import install_m_series_compat as _install_legacy
from .m_series_control import install_m_series_control_support
from .n8_control import install_n8_control_support
from .n8_map import install_n8_map_support
from .n8_path import install_n8_path_support
from .n8_status import install_n8_status_support
from .m_series_history import install_m_series_history_support
from .m_series_map import install_m_series_map_support
from .m_series_path import install_m_series_path_support
from .m_series_status import install_m_series_status_support
from .m_series_zones import install_m_series_zone_support
from .performance_diagnostics import install_performance_diagnostics
from .rain_battery_saver import install_rain_battery_saver_safety
from .runtime_optimizations import (
    install_runtime_optimization_diagnostics,
    install_runtime_optimizations,
)
from .shutdown_guard_stability import install_shutdown_guard_state_settle

_INSTALLED = False


def install_m_series_compat() -> None:
    """Install rebuild compatibility, then verified model-specific layers."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    install_setting_entity_identity()
    _install_legacy()
    install_m_series_control_support()
    # N8 has its own command transport and only intercepts N8 model strings.
    install_n8_control_support()
    install_m_series_path_support()
    # Reuse the proven MGS absolute-index assembler through an N8-only wrapper;
    # do not widen the M-series path model guard.
    install_n8_path_support()
    install_m_series_map_support()
    install_m_series_zone_support()
    # N8 uses the same MGS map-manager archive family but remains on its own
    # activation guard. The shared downloader also caches area_setting.json.
    install_n8_map_support()
    # Keep the proven M-series status/history layer untouched, then add an N8
    # wrapper that reuses only the confirmed common v3 record/task helpers.
    install_m_series_status_support()
    install_n8_status_support()
    install_m_series_history_support()
    install_genie_live_status_support()
    install_genie_path_diagnostics()
    install_live_task_event_refresh()
    install_rain_battery_saver_safety()
    install_shutdown_guard_state_settle()
    install_runtime_optimizations()
    install_performance_diagnostics()
    install_runtime_optimization_diagnostics()
