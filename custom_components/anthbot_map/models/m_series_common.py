"""Model compatibility entry point for the clean rebuild."""

from .cloud_api_resilience import install_cloud_api_resilience
from .entity_identity import install_setting_entity_identity
from .genie_live_motion import install_genie_live_motion_support
from .genie_live_path_refresh import install_genie_live_path_refresh
from .genie_path_diagnostics import install_genie_path_diagnostics
from .genie_progress_posttrim import install_genie_progress_posttrim
from .genie_progress_presentation import install_genie_progress_presentation
from .genie_status import install_genie_live_status_support
from .issue64_cpu_hotpath import install_issue64_cpu_hotpath_fix
from .live_task_events import install_live_task_event_refresh
from .m5_lidar_live_map_v2475 import install_m5_lidar_live_map_fix
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
from .m9_map_rescue_v2465 import install_m9_map_rescue_v2465
from .m9_progress_posttrim import install_m9_progress_posttrim
from .performance_diagnostics import install_performance_diagnostics
from .pion_status import install_pion_status_support
from .rain_battery_saver import install_rain_battery_saver_safety
from .recorder_v2465 import install_recorder_v2465
from .recorder_v2467 import install_recorder_v2467
from .recorder_idle_semantics_v2467 import install_recorder_idle_semantics_v2467
from .reliability_v2464 import install_runtime_reliability_fixes
from .reliability_v2465 import install_v2465_reliability_fixes
from .report_identity_suffix import install_report_identity_suffix
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
    install_cloud_api_resilience()
    install_setting_entity_identity()
    _install_legacy()
    install_m_series_control_support()
    install_n8_control_support()
    install_m_series_path_support()
    install_n8_path_support()
    install_m_series_map_support()
    install_m_series_zone_support()
    install_n8_map_support()
    install_m_series_status_support()
    install_n8_status_support()
    install_pion_status_support()
    install_m_series_history_support()
    install_genie_live_status_support()
    install_genie_path_diagnostics()
    install_genie_live_path_refresh()
    # Issue #64: patch only lookup/diagnostic CPU hot paths after the model
    # modules have installed their proven behavior wrappers.
    install_issue64_cpu_hotpath_fix()
    install_genie_live_motion_support()
    install_live_task_event_refresh()
    install_rain_battery_saver_safety()
    install_shutdown_guard_state_settle()
    install_runtime_optimizations()
    install_performance_diagnostics()
    install_runtime_optimization_diagnostics()
    install_runtime_reliability_fixes()
    install_report_identity_suffix()
    install_v2465_reliability_fixes()
    install_m9_map_rescue_v2465()
    install_m5_lidar_live_map_fix()
    install_recorder_v2465()
    install_recorder_v2467()
    install_recorder_idle_semantics_v2467()
    install_genie_progress_presentation()
    install_genie_progress_posttrim()
    install_m9_progress_posttrim()
