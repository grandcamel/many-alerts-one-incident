"""Untrusted candidate metadata stays syntax-only and bounded."""

from dataclasses import FrozenInstanceError

import pytest

from grafana_jsm_sandbox.accounting_evidence_candidate import (
    MAX_BATCH_CANDIDATES,
    MAX_CANDIDATE_BYTES,
    MAX_PAYLOAD_BYTES,
    SCHEMA,
    CandidateError,
    parse_candidate_batch,
    parse_candidate_claim,
)
from grafana_jsm_sandbox.forwarder_json import canonical_json


def candidate(**changes):
    value = {
        "schema": SCHEMA,
        "candidate_id": "candidate-1",
        "source_kind_claim": "unreviewed-export",
        "source_revision_claim": "rev-1",
        "acquired_at": "2026-09-25T00:01:02.000003Z",
        "payload_sha256": "f" * 64,
        "payload_bytes": 0,
        "custody_ref": "private-1",
    }
    value.update(changes)
    return value


def encoded(**changes):
    return canonical_json(candidate(**changes), ascii_only=True)


def test_minimal_claim_is_only_metadata_and_not_verified():
    claim = parse_candidate_claim(encoded())
    assert claim.candidate_id == "candidate-1"
    assert claim.source_kind_claim == "unreviewed-export"
    assert claim.payload_bytes == 0
    assert claim.account_scope_ref_claim is None
    assert claim.coverage_start_claim is None
    assert claim.coverage_end_claim is None
    assert claim.predecessor_candidate_id_claim is None
    assert not hasattr(claim, "verified")
    assert not hasattr(claim, "reserve")
    assert "private-1" not in repr(claim)
    with pytest.raises(FrozenInstanceError):
        claim.candidate_id = "other"


def test_optional_claims_do_not_establish_coverage_or_payload_verification():
    claim = parse_candidate_claim(encoded(
        account_scope_ref_claim="account-ref-1",
        coverage_start_claim="2026-09-01T00:00:00.000000Z",
        coverage_end_claim="2026-09-25T00:00:00.000000Z",
        predecessor_candidate_id_claim="candidate-0",
        payload_bytes=MAX_PAYLOAD_BYTES,
    ))
    assert claim.account_scope_ref_claim == "account-ref-1"
    assert claim.coverage_start_claim < claim.coverage_end_claim
    assert claim.payload_sha256 == "f" * 64  # No payload was supplied or checked.


@pytest.mark.parametrize("change", [
    {"schema": "accounting-evidence-candidate.v2"},
    {"candidate_id": "bad id"},
    {"candidate_id": "x" * 129},
    {"source_kind_claim": "UNKNOWN"},
    {"source_revision_claim": False},
    {"acquired_at": "2026-02-30T00:00:00.000000Z"},
    {"acquired_at": "2026-09-25T00:01:02Z"},
    {"payload_sha256": "F" * 64},
    {"payload_bytes": True},
    {"payload_bytes": -1},
    {"payload_bytes": MAX_PAYLOAD_BYTES + 1},
    {"custody_ref": "/private/path"},
    {"account_scope_ref_claim": None},
    {"coverage_start_claim": "2026-13-01T00:00:00.000000Z"},
    {"coverage_start_claim": "2026-09-26T00:00:00.000000Z",
     "coverage_end_claim": "2026-09-25T00:00:00.000000Z"},
    {"coverage_start_claim": "2026-09-25T00:00:00.000000Z",
     "coverage_end_claim": "2026-09-25T00:00:00.000000Z"},
    {"predecessor_candidate_id_claim": "candidate-1"},
    {"raw_charge_line": "secret"},
])
def test_malformed_field_shapes_fail_closed(change):
    with pytest.raises(CandidateError) as error:
        parse_candidate_claim(encoded(**change))
    assert error.value.code == "candidate_malformed"


@pytest.mark.parametrize("raw", [
    b"",
    b" ",
    b'{"schema":"accounting-evidence-candidate.v1"}',
    b'{"a":1,"a":2}',
    b"\xef\xbb\xbf{}",
    b' {"a":1}',
    b'{"x":"\xff"}',
    b"{" + b"x" * (MAX_CANDIDATE_BYTES + 1) + b"}",
])
def test_noncanonical_or_invalid_bytes_fail_without_echo(raw):
    with pytest.raises(CandidateError) as error:
        parse_candidate_claim(raw)
    assert error.value.code == "candidate_malformed"
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    if raw:
        assert raw[:20].decode("latin-1") not in repr(error.value)


def test_key_order_and_whitespace_must_be_canonical():
    raw = encoded()
    with pytest.raises(CandidateError, match="^candidate_malformed$"):
        parse_candidate_claim(raw + b"\n")
    with pytest.raises(CandidateError, match="^candidate_malformed$"):
        parse_candidate_claim(raw.replace(b'"acquired_at":', b' "acquired_at":', 1))


def test_exact_batch_replay_and_conflict():
    first = encoded()
    second = encoded(candidate_id="candidate-2", payload_sha256="0" * 64)
    batch = parse_candidate_batch((first, first, second))
    assert [claim.candidate_id for claim in batch.claims] == ["candidate-1", "candidate-2"]
    assert batch.exact_replays == 1
    assert "private-1" not in repr(batch)
    with pytest.raises(FrozenInstanceError):
        batch.exact_replays = 0
    with pytest.raises(CandidateError) as error:
        parse_candidate_batch((first, encoded(payload_sha256="0" * 64)))
    assert error.value.code == "candidate_conflict"


def test_batch_type_and_count_are_bounded():
    first = encoded()
    with pytest.raises(CandidateError, match="^candidate_malformed$"):
        parse_candidate_batch([first])
    with pytest.raises(CandidateError, match="^candidate_malformed$"):
        parse_candidate_batch((first,) * (MAX_BATCH_CANDIDATES + 1))
    accepted = parse_candidate_batch((first,) * MAX_BATCH_CANDIDATES)
    assert len(accepted.claims) == 1
    assert accepted.exact_replays == MAX_BATCH_CANDIDATES - 1
