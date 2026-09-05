"""Model compatibility entry point for the clean rebuild."""

from .entity_identity import install_setting_entity_identity
from .genie_status import install_genie_live_status_support
from .live_task_events import install_live_task_event_refresh
from .m_series_legacy import install_m_series_compat as _install_legacy
from .m_series_control import install_m_series_control_support
from .m_series_history import install_m_series_history_support
from .m_series_map import install_m_series_map_support
from .m_series_path import install_m_series_path_support
from .m_series_status import install_m_series_status_support
from .m_series_zones import install_m_series_zone_support

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
    # M-series app zones are stored inside the same map-manager archive as the
    # verified iot_map.bin boundary. Install this after map support so both
    # layers share one archive download and map.area_id can invalidate zones.
    install_m_series_zone_support()
    # Status owns the confirmed /device/v3/record/list refresh. Install it
    # before history so the history wrapper always enriches the freshly loaded
    # M-series records instead of having status overwrite the enriched payload.
    install_m_series_status_support()
    # Completed M-series zone-mowing rows can omit their zone id. Enrich the
    # v3 records after status refresh, using exact/live task data when present
    # and the conservative start-position fallback otherwise.
    install_m_series_history_support()
    # Genie may report live robot state on the service named shadow. Promote
    # only those telemetry fields into the same HA update path used by the
    # M-series property shadow, without changing any M-series behavior.
    install_genie_live_status_support()
    # Both Genie and M-series task-event sensors use the same REST event list.
    # Refresh it immediately after a real MQTT status transition so the cloud
    # event code does not remain stale for the five-minute ancillary interval.
    install_live_task_event_refresh()
