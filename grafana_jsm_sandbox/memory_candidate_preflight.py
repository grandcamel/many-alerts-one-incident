"""Advisory, synthetic prior-OPS-candidate preflight for ticket 32.

Supplied pages and clock are untrusted. This module never grants Run/model
admission or queries Jira.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timedelta

MAX_PAGES = 10
MAX_ITEMS_PER_PAGE = 100
MAX_PAGE_MS = 5_000
MAX_TOTAL_MS = 30_000
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z")
_ROOT_FIELDS = frozenset({"current_rehearsal_id", "jira_now", "pages"})
_PAGE_FIELDS = frozenset({
    "snapshot_marker", "cursor_in", "cursor_out", "exhausted",
    "total_count", "elapsed_ms", "items",
})
_ITEM_FIELDS = frozenset({
    "incident_id", "status", "created_at", "origin_rehearsal_id",
})


class CandidatePreflightError(ValueError):
    """Fixed, non-diagnostic malformed synthetic page rejection."""

    def __init__(self) -> None:
        self.code = "candidate_preflight_shape"
        super().__init__(self.code)


@dataclasses.dataclass(frozen=True)
class CandidatePreflight:
    finding: str
    prior_incident_ids: tuple[str, ...]
    admission_status: str = "held_unqualified"


def _fail() -> None:
    raise CandidatePreflightError() from None


def _keys(value: object, expected: frozenset[str]) -> bool:
    return (
        type(value) is dict
        and len(value) == len(expected)
        and all(type(key) is str for key in value)
        and set(value) == expected
    )


def _uuid4(value: object) -> bool:
    return type(value) is str and _UUID4.fullmatch(value) is not None


def _opaque(value: object, *, nullable: bool = False) -> bool:
    if value is None:
        return nullable
    return (type(value) is str and 1 <= len(value) <= 128
            and all(32 <= ord(char) <= 126 for char in value))


def _utc(value: object) -> datetime:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        _fail()
    result = None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        _fail()
    return result


def _number(value: object) -> bool:
    return type(value) is int and 0 <= value <= 9_007_199_254_740_991


def preflight_prior_candidates(value: object) -> CandidatePreflight:
    """Find incomplete coverage or eligible prior IDs in supplied pages only."""
    if not _keys(value, _ROOT_FIELDS) or not _uuid4(value["current_rehearsal_id"]):
        _fail()
    now = _utc(value["jira_now"])
    pages = value["pages"]
    if type(pages) not in (list, tuple):
        _fail()
    if not pages or len(pages) >= MAX_PAGES:
        return CandidatePreflight("incomplete", ())
    try:
        window_start = now - timedelta(minutes=30)
    except OverflowError:
        _fail()
    prior: set[str] = set()
    seen_ids: set[str] = set()
    seen_cursors: set[str] = set()
    marker = None
    cursor = None
    total = None
    elapsed = 0
    items_seen = 0
    for index, page in enumerate(pages):
        if not _keys(page, _PAGE_FIELDS):
            _fail()
        if (not _opaque(page["snapshot_marker"])
                or not _opaque(page["cursor_in"], nullable=True)
                or not _opaque(page["cursor_out"], nullable=True)
                or type(page["exhausted"]) is not bool
                or not _number(page["total_count"])
                or not _number(page["elapsed_ms"])
                or type(page["items"]) not in (list, tuple)):
            _fail()
        if len(page["items"]) > MAX_ITEMS_PER_PAGE:
            return CandidatePreflight("incomplete", tuple(sorted(prior)))
        elapsed += page["elapsed_ms"]
        if page["elapsed_ms"] > MAX_PAGE_MS or elapsed > MAX_TOTAL_MS:
            return CandidatePreflight("incomplete", tuple(sorted(prior)))
        if index == 0:
            marker = page["snapshot_marker"]
            total = page["total_count"]
        if (page["snapshot_marker"] != marker or page["total_count"] != total
                or page["cursor_in"] != cursor
                or (index < len(pages) - 1 and
                    (page["exhausted"] or page["cursor_out"] is None))
                or (page["exhausted"] and page["cursor_out"] is not None)
                or (page["cursor_out"] is not None
                    and (page["cursor_out"] == page["cursor_in"]
                         or page["cursor_out"] in seen_cursors))):
            return CandidatePreflight("incomplete", tuple(sorted(prior)))
        cursor = page["cursor_out"]
        if cursor is not None:
            seen_cursors.add(cursor)
        for item in page["items"]:
            if not _keys(item, _ITEM_FIELDS):
                _fail()
            if (not _opaque(item["incident_id"])
                    or type(item["status"]) is not str
                    or (item["origin_rehearsal_id"] is not None
                        and not _uuid4(item["origin_rehearsal_id"]))):
                _fail()
            created = _utc(item["created_at"])
            incident_id = item["incident_id"]
            if incident_id in seen_ids or item["status"] != "open" or created > now:
                return CandidatePreflight("incomplete", tuple(sorted(prior)))
            seen_ids.add(incident_id)
            items_seen += 1
            if created >= window_start:
                origin = item["origin_rehearsal_id"]
                if origin is None:
                    return CandidatePreflight("incomplete", tuple(sorted(prior)))
                if origin != value["current_rehearsal_id"]:
                    prior.add(incident_id)
    if not pages[-1]["exhausted"] or cursor is not None or items_seen != total:
        return CandidatePreflight("incomplete", tuple(sorted(prior)))
    finding = "prior_eligible" if prior else "no_prior_in_supplied_pages"
    return CandidatePreflight(finding, tuple(sorted(prior)))
