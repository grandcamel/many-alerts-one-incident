"""Strict structural candidate audience cards for ticket 44.

Syntax validation is not source authentication, operator authorization,
redaction of arbitrary ID values, a source join, or a presentation decision.
Returned bytes remain untrusted and must not be displayed or exported.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from .forwarder_json import JSONPolicyError, canonical_json, parse_json

MAX_CARD_BYTES = 4_096
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z")
_SECTION_SOURCE = {
    "incident": "ops",
    "directory": "directory",
    "drafts": "draft",
    "references": "reference",
}
_DISPLAY_CODES = {
    "incident": frozenset({"incident_status"}),
    "directory": frozenset({"observation", "hypothesis"}),
    "drafts": frozenset({"draft_status"}),
    "references": frozenset({"reference_status"}),
}
_VERIFICATION = frozenset({"confirmed", "unverified", "conflict", "not_applicable"})
_AVAILABILITY = frozenset({
    "available", "unavailable", "missing", "unknown", "expired", "redacted",
})
_RETRIEVAL = frozenset({"retrieved", "not_retrieved", "unknown", "not_applicable"})
_REVIEW = frozenset({
    "not_applicable", "unreviewed", "pending", "reviewed", "disputed", "superseded",
})
_MUTATION = frozenset({
    "none", "write_pending", "write_failed", "correction_required", "revoked",
})
_MEMORY = frozenset({"cold", "memory_assisted", "unknown", "not_applicable"})
_GAPS = frozenset({
    "source_missing", "source_unverified", "receipt_missing", "truncated",
    "expired", "redacted", "scope_unknown", "write_failed",
    "revocation_unknown", "time_unknown",
})
_FIELDS = frozenset({
    "schema_version", "section", "projection_id", "record_id", "source_class",
    "rehearsal_id", "run_id", "incident_id", "source_revision",
    "source_observed_at", "source_verified_at", "projection_refreshed_at",
    "source_verification", "availability", "retrieval", "review_state",
    "mutation_state", "memory_condition", "display_code", "provenance_ref", "gaps",
})


class AudienceCardError(ValueError):
    """Fixed rejection code that cannot echo the candidate card."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True, repr=False)
class CandidateCard:
    section: str
    projection_id: str
    record_id: str
    source_class: str
    rehearsal_id: str
    run_id: str | None
    incident_id: str | None
    source_revision: str | None
    source_observed_at: str | None
    source_verified_at: str | None
    projection_refreshed_at: str | None
    source_verification: str
    availability: str
    retrieval: str
    review_state: str
    mutation_state: str
    memory_condition: str
    display_code: str
    provenance_ref: str | None
    gaps: tuple[str, ...]

    def __repr__(self) -> str:
        return "CandidateCard(unqualified)"


@dataclass(frozen=True, slots=True, repr=False)
class CardPreflight:
    card: CandidateCard
    body: bytes
    sha256: str
    authority: str = "unqualified"

    def __repr__(self) -> str:
        return "CardPreflight(unqualified)"


def _fail(code: str) -> None:
    raise AudienceCardError(code) from None


def _id(value: object, *, nullable: bool = False) -> bool:
    if value is None:
        return nullable
    return type(value) is str and _ID.fullmatch(value) is not None and ".." not in value


def _utc(value: object) -> bool:
    if value is None:
        return True
    if type(value) is not str or _UTC.fullmatch(value) is None:
        return False
    valid = True
    try:
        datetime.fromisoformat(value)
    except ValueError:
        valid = False
    return valid


def _enum(value: object, options: frozenset[str]) -> bool:
    return type(value) is str and value in options


def parse_candidate_card(data: object) -> CardPreflight:
    """Parse one bounded structural card; all input claims stay unqualified."""
    if type(data) is not bytes:
        _fail("card_argument")
    code = None
    try:
        value = parse_json(data, max_bytes=MAX_CARD_BYTES)
    except JSONPolicyError:
        code = "card_json_invalid"
    if code is not None:
        raise AudienceCardError(code) from None
    if type(value) is not dict or set(value) != _FIELDS:
        _fail("card_shape")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        _fail("card_shape")
    section = value["section"]
    if type(section) is not str or section not in _SECTION_SOURCE:
        _fail("card_section")
    if value["source_class"] != _SECTION_SOURCE[section]:
        _fail("card_section")
    if not _enum(value["display_code"], _DISPLAY_CODES[section]):
        _fail("card_section")
    for name in ("projection_id", "record_id", "rehearsal_id"):
        if not _id(value[name]):
            _fail("card_id")
    for name in ("run_id", "incident_id", "source_revision", "provenance_ref"):
        if not _id(value[name], nullable=True):
            _fail("card_id")
    if section in {"incident", "drafts"} and value["incident_id"] is None:
        _fail("card_id")
    for name in ("source_observed_at", "source_verified_at", "projection_refreshed_at"):
        if not _utc(value[name]):
            _fail("card_time")
    for name, options in (
        ("source_verification", _VERIFICATION), ("availability", _AVAILABILITY),
        ("retrieval", _RETRIEVAL), ("review_state", _REVIEW),
        ("mutation_state", _MUTATION), ("memory_condition", _MEMORY),
    ):
        if not _enum(value[name], options):
            _fail("card_state")
    if section == "incident" and value["mutation_state"] != "none":
        _fail("card_state")
    gaps = value["gaps"]
    if (type(gaps) is not tuple or len(gaps) > 8
            or any(not _enum(gap, _GAPS) for gap in gaps)
            or tuple(sorted(set(gaps))) != gaps):
        _fail("card_gap")
    body = canonical_json(value)
    if len(body) > MAX_CARD_BYTES:
        _fail("card_overflow")
    card = CandidateCard(**{name: value[name] for name in CandidateCard.__dataclass_fields__})
    return CardPreflight(card=card, body=body, sha256=hashlib.sha256(body).hexdigest())


__all__ = [
    "MAX_CARD_BYTES", "AudienceCardError", "CandidateCard", "CardPreflight",
    "parse_candidate_card",
]
