"""Pure cache-selection helpers for Anthbot map and area definitions.

This module deliberately has no Home Assistant imports. Apart from making
the selection rules easy to test, it keeps the behaviour aligned with the
official Android application: the live view uses the ``map`` file identified
by ``map_time``; ``multi_maps.map_list[0]`` is only a saved-map fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


AREA_DEFINITION_REFRESH_SECONDS = 15 * 60.0
MAP_DEFINITION_REFRESH_SECONDS = 15 * 60.0
MAP_DEFINITION_RETRY_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class MapArchiveSelection:
    """Archive metadata selected from the mower property shadow."""

    filename: str | None
    md5: str | None
    map_id: str | None
    map_time: str | None
    map_tar_time: str | None

    def cache_key(self, serial_number: str) -> str:
        """Return a stable identity that changes for every relevant update."""
        return "|".join(
            (
                f"file={self.filename or f'map_{serial_number}_0'}",
                f"md5={self.md5 or ''}",
                f"map_id={self.map_id or ''}",
                f"map_time={self.map_time or ''}",
                f"map_tar_time={self.map_tar_time or ''}",
            )
        )


def _scalar_text(value: Any) -> str | None:
    """Normalize non-secret scalar shadow metadata to text."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def select_map_archive(data: dict[str, Any]) -> MapArchiveSelection:
    """Select the same saved-map archive as the official Anthbot app.

    The app's backup-map feature reads ``multi_maps.map_list[0]``. Its main
    live map view does not: it downloads the ordinary ``map`` file using
    ``map_time`` as the local cache identity.
    """
    multi_maps = data.get("multi_maps")
    map_list = multi_maps.get("map_list") if isinstance(multi_maps, dict) else None
    first = map_list[0] if isinstance(map_list, list) and map_list else None
    first = first if isinstance(first, dict) else {}

    filename = _scalar_text(first.get("map_file_name"))
    md5 = _scalar_text(first.get("md5"))
    if md5 is not None:
        md5 = md5.lower()

    return MapArchiveSelection(
        filename=filename,
        md5=md5,
        map_id=_scalar_text(first.get("map_id")),
        map_time=_scalar_text(data.get("map_time")),
        map_tar_time=_scalar_text(data.get("map_tar_time")),
    )


def map_definition_cache_key(
    serial_number: str,
    data: dict[str, Any],
    archive: MapArchiveSelection,
) -> str:
    """Return the live-map identity plus its saved-map fallback identity.

    ``map_<serial>.txt`` is a fixed cloud filename, so ``map_time`` is the
    primary invalidation signal. The archive identity is included only so a
    changed fallback can be retried immediately if the live file is absent.
    A periodic safety refresh still catches servers that replace the fixed
    live file without updating ``map_time``.
    """
    map_time = _scalar_text(data.get("map_time"))
    return "|".join(
        (
            f"live_file=map_{serial_number}.txt",
            f"live_map_time={map_time or ''}",
            f"archive={archive.cache_key(serial_number)}",
        )
    )


def map_archive_diagnostics(
    data: dict[str, Any], selection: MapArchiveSelection
) -> dict[str, Any]:
    """Return safe metadata showing why an archive was selected."""
    multi_maps = data.get("multi_maps")
    map_list = multi_maps.get("map_list") if isinstance(multi_maps, dict) else None
    preview: list[dict[str, Any]] = []
    allowed_keys = (
        "map_id",
        "map_file_name",
        "md5",
        "map_name",
        "name",
        "map_time",
        "map_tar_time",
        "create_time",
        "update_time",
        "updated_at",
        "timestamp",
        "active",
        "current",
        "selected",
        "is_active",
        "is_current",
        "is_selected",
    )
    if isinstance(map_list, list):
        for index, item in enumerate(map_list):
            if not isinstance(item, dict):
                continue
            entry: dict[str, Any] = {"index": index}
            for key in allowed_keys:
                value = item.get(key)
                if isinstance(value, (str, int, float, bool)):
                    entry[key] = value
            preview.append(entry)

    return {
        "selected_index": 0 if selection.filename is not None else None,
        "selected_file": selection.filename,
        "selected_md5": selection.md5,
        "selected_map_id": selection.map_id,
        "map_time": selection.map_time,
        "map_tar_time": selection.map_tar_time,
        "map_count": len(preview),
        "map_list": preview,
    }


def should_refresh_map_definition(
    *,
    has_definition: bool,
    has_error: bool,
    selection_key: str,
    last_selection_key: str | None,
    now: float,
    last_download: float,
    allow_periodic: bool,
) -> bool:
    """Return whether the live map definition should be downloaded now.

    A changed timestamp/file/MD5 is immediate.  Failed downloads are throttled
    to one attempt per minute, and the safety refresh is only performed by the
    normal HTTP coordinator (never by every MQTT fragment).
    """
    if selection_key != last_selection_key or last_download == 0.0:
        return True
    elapsed = now - last_download
    if not has_definition or has_error:
        return elapsed >= MAP_DEFINITION_RETRY_SECONDS
    return allow_periodic and elapsed >= MAP_DEFINITION_REFRESH_SECONDS


def should_refresh_area_definition(
    *,
    has_definition: bool,
    area_time: str | None,
    last_area_time: str | None,
    now: float,
    last_download: float,
) -> bool:
    """Return whether the area file should be downloaded again."""
    return (
        not has_definition
        or (area_time is not None and area_time != last_area_time)
        or last_download == 0.0
        or now - last_download >= AREA_DEFINITION_REFRESH_SECONDS
    )


def definition_content(
    definition: dict[str, Any] | list[Any] | None,
) -> dict[str, Any] | list[Any] | None:
    """Return comparable definition content without download diagnostics."""
    if not isinstance(definition, dict):
        return definition
    return {
        key: value
        for key, value in definition.items()
        if key != "_download_source"
    }
