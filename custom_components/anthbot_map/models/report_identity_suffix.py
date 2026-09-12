"""Install privacy-safe robot identity enrichment for diagnostics reports."""

from __future__ import annotations

from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..report_identity import add_serial_suffix

_INSTALLED = False
_PATCHED = False


def _patch_report_builders() -> None:
    """Wrap already-installed diagnostics builders after module imports settle."""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    from .. import button as button_module
    from .. import firmware_diagnostics
    from .. import robot_error_reporting

    previous_builder = firmware_diagnostics.build_firmware_diagnostics_report

    def build_report_with_serial_suffix(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = previous_builder(*args, **kwargs)
        coordinator = args[0] if args else kwargs.get("coordinator")
        enriched = add_serial_suffix(report, coordinator)
        return enriched if isinstance(enriched, dict) else report

    firmware_diagnostics.build_firmware_diagnostics_report = build_report_with_serial_suffix
    button_module.build_firmware_diagnostics_report = build_report_with_serial_suffix
    robot_error_reporting.build_firmware_diagnostics_report = build_report_with_serial_suffix


def install_report_identity_suffix() -> None:
    """Install the report-only wrapper without touching mower/model behavior."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: Any, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        _patch_report_builders()

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
