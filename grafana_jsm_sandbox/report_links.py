"""Content-free structural precheck for untrusted Report claim links.

Every outcome is support-unverified. Actual retrieval and human support review
belong to ticket 39's private capture boundary, not this local checker.
"""

from __future__ import annotations

import dataclasses
import re

MAX_CLAIMS = 64
MAX_CITATIONS = 128
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_ROOT_FIELDS = frozenset({"claims", "citations"})
_CLAIM_FIELDS = frozenset({
    "claim_id", "observed_or_inferred", "status", "evidence_refs", "derived_from",
})
_CITATION_FIELDS = frozenset({
    "citation_id", "exchange_id", "provenance", "source_interface",
    "observation_status",
})
_CLAIM_MODES = frozenset({"observed", "inferred"})
_CLAIM_STATUSES = frozenset({"asserted", "unreviewed", "unknown"})
_PROVENANCE = frozenset({"native_returned", "local_association", "unknown"})
_INTERFACES = frozenset({
    "native_capture", "forwarder_receipt", "query_result", "fixture", "unknown",
})
_OBSERVATION_STATUSES = frozenset({
    "returned", "empty", "missing", "truncated", "redacted", "transport_error",
    "unknown",
})


class ReportLinkError(ValueError):
    """Fixed, non-diagnostic malformed-stub rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclasses.dataclass(frozen=True)
class LinkPrecheck:
    defects: tuple[str, ...]
    support_status: str = "support_unverified"


def _fail() -> None:
    raise ReportLinkError("report_link_shape") from None


def _keys(value: object, expected: frozenset[str]) -> bool:
    return (
        type(value) is dict
        and len(value) == len(expected)
        and all(type(key) is str for key in value)
        and set(value) == expected
    )


def _uuid4(value: object) -> bool:
    return type(value) is str and _UUID4.fullmatch(value) is not None


def _refs(value: object, maximum: int) -> bool:
    return (type(value) in (list, tuple) and len(value) <= maximum
            and all(_uuid4(item) for item in value))


def _validate(value: object) -> None:
    if not _keys(value, _ROOT_FIELDS):
        _fail()
    claims = value["claims"]
    citations = value["citations"]
    if (type(claims) not in (list, tuple) or len(claims) > MAX_CLAIMS
            or type(citations) not in (list, tuple) or len(citations) > MAX_CITATIONS):
        _fail()
    for claim in claims:
        if not _keys(claim, _CLAIM_FIELDS):
            _fail()
        if not _uuid4(claim["claim_id"]):
            _fail()
        for key, accepted in (("observed_or_inferred", _CLAIM_MODES),
                              ("status", _CLAIM_STATUSES)):
            item = claim[key]
            if type(item) is not str or item not in accepted:
                _fail()
        if (not _refs(claim["evidence_refs"], MAX_CITATIONS)
                or not _refs(claim["derived_from"], MAX_CLAIMS)):
            _fail()
    for citation in citations:
        if not _keys(citation, _CITATION_FIELDS):
            _fail()
        if (not _uuid4(citation["citation_id"])
                or citation["exchange_id"] is not None
                and not _uuid4(citation["exchange_id"])):
            _fail()
        for key, accepted in (("provenance", _PROVENANCE),
                              ("source_interface", _INTERFACES),
                              ("observation_status", _OBSERVATION_STATUSES)):
            item = citation[key]
            if type(item) is not str or item not in accepted:
                _fail()


def precheck_claim_links(value: object) -> LinkPrecheck:
    """Find only structural defects; never qualify claim support."""
    _validate(value)
    claims = value["claims"]
    citations = value["citations"]
    defects: set[str] = set()
    claim_modes: dict[str, str] = {}
    citation_ids: set[str] = set()
    for claim in claims:
        claim_id = claim["claim_id"]
        if claim_id in claim_modes:
            defects.add("claim_duplicate")
        claim_modes[claim_id] = claim["observed_or_inferred"]
    for citation in citations:
        citation_id = citation["citation_id"]
        exchange_id = citation["exchange_id"]
        if citation_id in citation_ids:
            defects.add("citation_duplicate")
        citation_ids.add(citation_id)
        if (citation["provenance"] == "native_returned"
                and citation["source_interface"] != "native_capture"):
            defects.add("native_provenance_mismatch")
        if citation["observation_status"] == "returned" and exchange_id is None:
            defects.add("returned_without_exchange")
    for claim in claims:
        refs = claim["evidence_refs"]
        derived = claim["derived_from"]
        if len(set(refs)) != len(refs) or len(set(derived)) != len(derived):
            defects.add("reference_duplicate")
        if any(ref not in citation_ids for ref in refs):
            defects.add("citation_dangling")
        if any(ref not in claim_modes for ref in derived):
            defects.add("derivation_dangling")
        if claim["observed_or_inferred"] == "observed":
            if derived:
                defects.add("observed_has_derivation")
            if claim["status"] == "asserted" and not refs:
                defects.add("asserted_observed_unlinked")
        elif not derived:
            defects.add("inference_without_observation")
        elif any(claim_modes.get(ref) == "inferred" for ref in derived):
            defects.add("derivation_not_observed")
    return LinkPrecheck(tuple(sorted(defects)))
