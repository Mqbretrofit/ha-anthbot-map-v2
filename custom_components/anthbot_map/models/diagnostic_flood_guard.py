"""Stabilize automatic-diagnostics signatures for truncated cloud errors.

Field reports from M9 and N8 show AWS XML errors may be truncated in the
middle of RequestId/HostId values. Those values are request-specific and must
never participate in the automatic-diagnostics signature.

The v2.4.6.5 reliability layer already owns the proven singleton/episode-aware
reporting policy. This module deliberately changes only its normalization
helpers so real errors remain reportable while duplicate request metadata no
longer creates new episodes.
"""

from __future__ import annotations

import hashlib
import re

from . import reliability_v2465

_INSTALLED = False

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
# Match both complete and field-truncated AWS XML values. [^<]* stops before a
# following XML element when the closing tag is present, while also consuming a
# value that simply ends at the truncation boundary.
_REQUEST_ID_RE = re.compile(
    r"<RequestId>[^<]*(?:</RequestId>)?",
    re.IGNORECASE | re.DOTALL,
)
_HOST_ID_RE = re.compile(
    r"<HostId>[^<]*(?:</HostId>)?",
    re.IGNORECASE | re.DOTALL,
)


def _stable_error_text(value: object) -> str:
    """Remove request-specific cloud noise while preserving the real error."""
    text = str(value or "")
    text = _URL_RE.sub("<url>", text)
    text = _REQUEST_ID_RE.sub("<RequestId>", text)
    text = _HOST_ID_RE.sub("<HostId>", text)
    return " ".join(text.split())[:2048]


def _stable_error_signature(trigger: str, value: object) -> str:
    """Return a deterministic signature independent of AWS request metadata."""
    normalized = _stable_error_text(value)
    digest = hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:20]
    return f"{trigger}:{digest}"


def install_diagnostic_flood_guard() -> None:
    """Replace only v2.4.6.5 cloud-error normalization with the robust form."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # stable_automatic_diagnostics_trigger in reliability_v2465 resolves this
    # module global at call time, including from its already-installed reporter
    # closure. Replacing these helpers therefore fixes both initial and later
    # coordinator instances without stacking another reporter/listener wrapper.
    reliability_v2465._stable_error_text = _stable_error_text  # noqa: SLF001
    reliability_v2465._stable_error_signature = _stable_error_signature  # noqa: SLF001


__all__ = ["install_diagnostic_flood_guard"]
