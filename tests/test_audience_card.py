"""Structural audience candidates only; no source, operator or UI acceptance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from grafana_jsm_sandbox.audience_card import AudienceCardError, parse_candidate_card


def _candidate(section="incident", **changes):
    pairs = {
        "incident": ("ops", "incident_status"),
        "directory": ("directory", "observation"),
        "drafts": ("draft", "draft_status"),
        "references": ("reference", "reference_status"),
    }
    source, code = pairs[section]
    value = {
        "schema_version": 1, "section": section,
        "projection_id": "projection-1", "record_id": "record-1",
        "source_class": source, "rehearsal_id": "rehearsal-1",
        "run_id": None, "incident_id": "OPS-1", "source_revision": "revision-1",
        "source_observed_at": "2026-09-25T12:00:00.000000Z",
        "source_verified_at": "2026-09-25T12:00:01.000000Z",
        "projection_refreshed_at": "2026-09-25T12:00:02.000000Z",
        "source_verification": "unverified", "availability": "unknown",
        "retrieval": "not_retrieved", "review_state": "not_applicable",
        "mutation_state": "none", "memory_condition": "not_applicable",
        "display_code": code, "provenance_ref": None, "gaps": ["source_unverified"],
    }
    value.update(changes)
    return value


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.parametrize("section", ["incident", "directory", "drafts", "references"])
def test_four_primary_sources_are_only_unqualified_candidates(section):
    parsed = parse_candidate_card(_bytes(_candidate(section)))
    assert parsed.card.section == section
    assert parsed.authority == "unqualified"
    assert json.loads(parsed.body)["section"] == section
    assert parsed.sha256 == hashlib.sha256(parsed.body).hexdigest()
    with pytest.raises(FrozenInstanceError):
        parsed.card.section = "references"


def test_independent_axes_and_times_survive_without_upgrading_source():
    value = _candidate(
        section="directory", source_verification="confirmed",
        availability="available", retrieval="not_retrieved",
        source_verified_at=None, projection_refreshed_at="2026-09-25T12:30:00.000000Z",
        memory_condition="cold", display_code="hypothesis", gaps=[],
    )
    parsed = parse_candidate_card(_bytes(value))
    assert parsed.card.source_verification == "confirmed"  # an untrusted claim
    assert parsed.card.availability == "available"
    assert parsed.card.retrieval == "not_retrieved"
    assert parsed.card.source_verified_at is None
    assert parsed.card.projection_refreshed_at == value["projection_refreshed_at"]
    assert parsed.card.memory_condition == "cold"
    assert parsed.authority == "unqualified"


@pytest.mark.parametrize("change", [
    {"summary": "private body"},
    {"count": 0},
    {"url": "https://internal.example"},
    {"raw_error": "private error"},
    {"ground_truth": "private answer"},
])
def test_arbitrary_content_and_unproven_counts_are_rejected(change):
    with pytest.raises(AudienceCardError) as exc:
        parse_candidate_card(_bytes(_candidate(**change)))
    assert exc.value.code == "card_shape"


@pytest.mark.parametrize("change,code", [
    ({"source_class": "draft"}, "card_section"),
    ({"display_code": "diagnosis_confirmed"}, "card_section"),
    ({"projection_id": "https://example.test/a"}, "card_id"),
    ({"record_id": "../secret"}, "card_id"),
    ({"incident_id": None}, "card_id"),
    ({"provenance_ref": "user@example.test"}, "card_id"),
    ({"source_observed_at": "2026-02-30T00:00:00.000000Z"}, "card_time"),
    ({"source_verified_at": "2026-09-25"}, "card_time"),
    ({"availability": "fresh"}, "card_state"),
    ({"retrieval": "delivered"}, "card_state"),
    ({"gaps": ["source_unverified", "source_unverified"]}, "card_gap"),
    ({"gaps": ["unknown-field"]}, "card_gap"),
    ({"schema_version": True}, "card_shape"),
])
def test_closed_identity_state_and_gap_grammar(change, code):
    with pytest.raises(AudienceCardError) as exc:
        parse_candidate_card(_bytes(_candidate(**change)))
    assert exc.value.code == code


def test_incident_card_cannot_encode_secondary_memory_mutation():
    with pytest.raises(AudienceCardError) as exc:
        parse_candidate_card(_bytes(_candidate(mutation_state="write_failed")))
    assert exc.value.code == "card_state"
    parsed = parse_candidate_card(_bytes(_candidate("drafts", mutation_state="write_failed")))
    assert parsed.card.mutation_state == "write_failed"


def test_draft_requires_incident_link_but_opaque_ids_remain_untrusted():
    with pytest.raises(AudienceCardError) as exc:
        parse_candidate_card(_bytes(_candidate("drafts", incident_id=None)))
    assert exc.value.code == "card_id"
    parsed = parse_candidate_card(_bytes(_candidate(record_id="credentialshapedvalue")))
    assert parsed.card.record_id == "credentialshapedvalue"
    assert b"credentialshapedvalue" in parsed.body
    assert parsed.authority == "unqualified"
    assert "credentialshapedvalue" not in repr(parsed)
    assert "credentialshapedvalue" not in repr(parsed.card)
    assert "credentialshapedvalue" not in str(parsed)


@pytest.mark.parametrize("raw", [
    b'{"schema_version":1,"schema_version":1}',
    b'\xff',
    b'{}',
    b'[]',
    b'"canary"',
    b'{' + b'"x":"canary",' * 1000 + b'"end":1}',
])
def test_bad_json_never_echoes_candidate_bytes(raw):
    with pytest.raises(AudienceCardError) as exc:
        parse_candidate_card(raw)
    assert "canary" not in str(exc.value)
    assert exc.value.__cause__ is None
    assert exc.value.__context__ is None


def test_canonical_readback_does_not_create_display_authority():
    first = parse_candidate_card(_bytes(_candidate()))
    second = parse_candidate_card(first.body)
    assert second.body == first.body
    assert second.sha256 == first.sha256
    assert second.authority == "unqualified"
