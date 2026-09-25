"""Pure operator-audience status decisions over prevalidated safe claims.

No source authentication, redaction, UI or Run-readable output lives here.
In particular a historical pin is never evidence of current approval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_NS = 2**63 - 1
STALE_AFTER_NS = 30_000_000_000
MAX_COUNT = 2**53 - 1
_ID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_STATES = frozenset({"confirmed", "unverified", "missing", "unavailable", "failed"})
_CAPTURED_STATES = frozenset({"approved", "unapproved", "unknown"})
_CURRENT_STATES = frozenset({
    "approved", "unapproved", "revoked", "withdrawn", "expired",
    "correction_required", "unavailable", "unknown",
})


class AudienceStatusError(ValueError):
    """Fixed code, with no caller content in the exception."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CountStatus:
    value: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class PinnedReference:
    reference_id: str
    source_version: str
    body_digest: str
    captured_state: str


@dataclass(frozen=True, slots=True)
class CurrentReference:
    reference_id: str
    source_version: str
    body_digest: str
    state: str
    verified: bool


@dataclass(frozen=True, slots=True)
class ReferenceStatus:
    captured_state: str
    current_use: str
    reason: str


def _valid_id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _valid_digest(value: object) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def section_freshness(
    now_ns: object, last_success_ns: object, *,
    current_epoch: object, last_success_epoch: object,
) -> str:
    """Return fresh, stale or unknown for a controlled monotonic clock.

    A successful cache refresh changes only ``last_success_ns``. Source
    observation and verification times are owned by their respective sources.
    """
    if (not _valid_id(current_epoch) or not _valid_id(last_success_epoch) or
            current_epoch != last_success_epoch or
            type(now_ns) is not int or not 0 <= now_ns <= MAX_NS or
            type(last_success_ns) is not int or
            not 0 <= last_success_ns <= MAX_NS or now_ns < last_success_ns):
        return "unknown"
    return "stale" if now_ns - last_success_ns > STALE_AFTER_NS else "fresh"


def qualified_count(value: object, *, source_state: str, complete: bool) -> CountStatus:
    """Show a number only for a complete, explicitly confirmed source count."""
    if type(source_state) is not str or source_state not in _SOURCE_STATES:
        raise AudienceStatusError("count_source_state") from None
    if type(complete) is not bool:
        raise AudienceStatusError("count_completeness") from None
    if value is not None and (type(value) is not int or not 0 <= value <= MAX_COUNT):
        raise AudienceStatusError("count_value") from None
    if source_state != "confirmed":
        return CountStatus(None, source_state)
    if not complete:
        return CountStatus(None, "truncated")
    if value is None:
        return CountStatus(None, "missing")
    return CountStatus(value, "confirmed")


def _valid_pin(pin: object) -> bool:
    return (type(pin) is PinnedReference and _valid_id(pin.reference_id) and
            _valid_id(pin.source_version) and _valid_digest(pin.body_digest) and
            type(pin.captured_state) is str and pin.captured_state in _CAPTURED_STATES)


def _valid_current(current: object) -> bool:
    return (type(current) is CurrentReference and _valid_id(current.reference_id) and
            _valid_id(current.source_version) and _valid_digest(current.body_digest) and
            type(current.state) is str and current.state in _CURRENT_STATES and
            type(current.verified) is bool)


def pinned_reference_status(
    pin: PinnedReference, current: CurrentReference | None,
) -> ReferenceStatus:
    """Keep captured history while requiring independent current approval."""
    if not _valid_pin(pin) or (current is not None and not _valid_current(current)):
        raise AudienceStatusError("reference_argument") from None
    if current is None:
        return ReferenceStatus(pin.captured_state, "unknown", "overlay_missing")
    if current.reference_id != pin.reference_id:
        return ReferenceStatus(pin.captured_state, "unknown", "identity_conflict")
    if not current.verified:
        return ReferenceStatus(pin.captured_state, "unknown", "overlay_unverified")
    if current.state in {"revoked", "withdrawn", "expired", "correction_required"}:
        return ReferenceStatus(pin.captured_state, "unavailable", current.state)
    if current.state in {"unknown", "unavailable"}:
        return ReferenceStatus(pin.captured_state, "unknown", current.state)
    if current.state == "unapproved":
        return ReferenceStatus(pin.captured_state, "unavailable", "unapproved")
    if (current.source_version != pin.source_version or
            current.body_digest != pin.body_digest):
        return ReferenceStatus(pin.captured_state, "unavailable", "version_changed")
    return ReferenceStatus(pin.captured_state, "approved", "current_verified")


__all__ = [
    "AudienceStatusError", "CountStatus", "CurrentReference", "PinnedReference",
    "ReferenceStatus", "pinned_reference_status", "qualified_count", "section_freshness",
]
