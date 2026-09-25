"""Pure syntax for private accounting evidence *claims*, never billing facts.

No source is authenticated here. The claimed digest is not checked against a
payload, and a structurally valid candidate cannot reserve or settle spend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .forwarder_json import JSONPolicyError, canonical_json, parse_json

SCHEMA = "accounting-evidence-candidate.v1"
MAX_CANDIDATE_BYTES = 2_048
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_BATCH_CANDIDATES = 256

_REQUIRED = frozenset({
    "schema", "candidate_id", "source_kind_claim", "source_revision_claim",
    "acquired_at", "payload_sha256", "payload_bytes", "custody_ref",
})
_OPTIONAL = frozenset({
    "account_scope_ref_claim", "coverage_start_claim", "coverage_end_claim",
    "predecessor_candidate_id_claim",
})
_ID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_KIND = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_UTC = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T"
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})\.([0-9]{6})Z\Z"
)


class CandidateError(ValueError):
    """A fixed rejection code with no candidate data or nested parser error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _malformed() -> None:
    raise CandidateError("candidate_malformed") from None


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _utc(value: object) -> bool:
    if type(value) is not str:
        return False
    match = _UTC.fullmatch(value)
    if match is None:
        return False
    valid = True
    try:
        datetime(*(int(part) for part in match.groups()), tzinfo=UTC)
    except ValueError:
        valid = False
    return valid


@dataclass(frozen=True, slots=True, repr=False)
class CandidateClaim:
    candidate_id: str
    source_kind_claim: str
    source_revision_claim: str
    acquired_at: str
    payload_sha256: str
    payload_bytes: int
    custody_ref: str
    account_scope_ref_claim: str | None
    coverage_start_claim: str | None
    coverage_end_claim: str | None
    predecessor_candidate_id_claim: str | None

    def __repr__(self) -> str:
        return "CandidateClaim(<unverified>)"


@dataclass(frozen=True, slots=True, repr=False)
class CandidateBatch:
    claims: tuple[CandidateClaim, ...]
    exact_replays: int

    def __repr__(self) -> str:
        return "CandidateBatch(<unverified>)"


def parse_candidate_claim(raw: bytes) -> CandidateClaim:
    """Parse one canonical metadata envelope; all returned fields are claims."""
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_CANDIDATE_BYTES:
        _malformed()
    value = None
    code = None
    try:
        value = parse_json(raw, max_bytes=MAX_CANDIDATE_BYTES, ascii_only=True)
        canonical = canonical_json(value, ascii_only=True)
    except JSONPolicyError:
        code = "candidate_malformed"
    if code is not None:
        raise CandidateError(code) from None
    if type(value) is not dict or canonical != raw:
        _malformed()
    keys = frozenset(value)
    if not _REQUIRED <= keys or not keys <= _REQUIRED | _OPTIONAL:
        _malformed()
    if value["schema"] != SCHEMA or type(value["schema"]) is not str:
        _malformed()
    if not _id(value["candidate_id"]):
        _malformed()
    if (type(value["source_kind_claim"]) is not str or
            _KIND.fullmatch(value["source_kind_claim"]) is None):
        _malformed()
    if not _id(value["source_revision_claim"]) or not _utc(value["acquired_at"]):
        _malformed()
    if (type(value["payload_sha256"]) is not str or
            _DIGEST.fullmatch(value["payload_sha256"]) is None):
        _malformed()
    if (type(value["payload_bytes"]) is not int or
            not 0 <= value["payload_bytes"] <= MAX_PAYLOAD_BYTES):
        _malformed()
    if not _id(value["custody_ref"]):
        _malformed()
    for key in ("account_scope_ref_claim", "predecessor_candidate_id_claim"):
        if key in value and not _id(value[key]):
            _malformed()
    for key in ("coverage_start_claim", "coverage_end_claim"):
        if key in value and not _utc(value[key]):
            _malformed()
    if ("coverage_start_claim" in value and "coverage_end_claim" in value and
            value["coverage_start_claim"] >= value["coverage_end_claim"]):
        _malformed()
    if value.get("predecessor_candidate_id_claim") == value["candidate_id"]:
        _malformed()
    return CandidateClaim(
        candidate_id=value["candidate_id"],
        source_kind_claim=value["source_kind_claim"],
        source_revision_claim=value["source_revision_claim"],
        acquired_at=value["acquired_at"],
        payload_sha256=value["payload_sha256"],
        payload_bytes=value["payload_bytes"],
        custody_ref=value["custody_ref"],
        account_scope_ref_claim=value.get("account_scope_ref_claim"),
        coverage_start_claim=value.get("coverage_start_claim"),
        coverage_end_claim=value.get("coverage_end_claim"),
        predecessor_candidate_id_claim=value.get("predecessor_candidate_id_claim"),
    )


def parse_candidate_batch(raw_candidates: tuple[bytes, ...]) -> CandidateBatch:
    """Deduplicate exact envelope bytes by candidate ID, without source lookup."""
    if type(raw_candidates) is not tuple or len(raw_candidates) > MAX_BATCH_CANDIDATES:
        _malformed()
    seen: dict[str, bytes] = {}
    claims = []
    replays = 0
    for raw in raw_candidates:
        claim = parse_candidate_claim(raw)
        previous = seen.get(claim.candidate_id)
        if previous is not None:
            if previous != raw:
                raise CandidateError("candidate_conflict") from None
            replays += 1
        else:
            seen[claim.candidate_id] = raw
            claims.append(claim)
    return CandidateBatch(tuple(claims), replays)


__all__ = [
    "MAX_BATCH_CANDIDATES", "MAX_CANDIDATE_BYTES", "MAX_PAYLOAD_BYTES", "SCHEMA",
    "CandidateBatch", "CandidateClaim", "CandidateError",
    "parse_candidate_batch", "parse_candidate_claim",
]
