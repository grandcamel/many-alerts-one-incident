"""Ticket 44 status policy over synthetic, already sanitized source claims."""

from dataclasses import FrozenInstanceError

import pytest

from grafana_jsm_sandbox.audience_status import (
    AudienceStatusError,
    CurrentReference,
    PinnedReference,
    pinned_reference_status,
    qualified_count,
    section_freshness,
)


def _pin(**changes):
    fields = {"reference_id": "ref-1", "source_version": "v1", "body_digest": "a" * 64,
              "captured_state": "approved"}
    fields.update(changes)
    return PinnedReference(**fields)


def _current(**changes):
    fields = {"reference_id": "ref-1", "source_version": "v1", "body_digest": "a" * 64,
              "state": "approved", "verified": True}
    fields.update(changes)
    return CurrentReference(**fields)


@pytest.mark.parametrize(("now", "last", "expected"), [
    (0, 0, "fresh"),
    (30_000_000_000, 0, "fresh"),
    (30_000_000_001, 0, "stale"),
    (2**63 - 1, 0, "stale"),
    (None, 0, "unknown"),
    (10, None, "unknown"),
    (9, 10, "unknown"),
    (True, 0, "unknown"),
    (-1, 0, "unknown"),
    (2**63, 0, "unknown"),
])
def test_section_freshness_controlled_clock(now, last, expected):
    assert section_freshness(
        now, last, current_epoch="boot-1", last_success_epoch="boot-1",
    ) == expected


def test_clock_epoch_discontinuity_is_unknown_even_when_elapsed_looks_fresh():
    assert section_freshness(
        20_000_000_000, 10_000_000_000,
        current_epoch="boot-2", last_success_epoch="boot-1",
    ) == "unknown"
    assert section_freshness(
        31_000_000_010, 10, current_epoch="boot-2", last_success_epoch="boot-1",
    ) == "unknown"
    assert section_freshness(
        20_000_000_000, 10_000_000_000,
        current_epoch="", last_success_epoch="boot-1",
    ) == "unknown"


def test_cache_refresh_cannot_supply_source_verification():
    # A successful presentation refresh says nothing about source recency.
    assert section_freshness(
        10_000_000_000, 9_000_000_000,
        current_epoch="boot-1", last_success_epoch="boot-1",
    ) == "fresh"
    assert qualified_count(0, source_state="unverified", complete=True).value is None


@pytest.mark.parametrize(("value", "state", "complete", "expected"), [
    (0, "confirmed", True, (0, "confirmed")),
    (4, "confirmed", True, (4, "confirmed")),
    (None, "confirmed", True, (None, "missing")),
    (0, "confirmed", False, (None, "truncated")),
    (0, "missing", True, (None, "missing")),
    (0, "failed", True, (None, "failed")),
    (0, "unavailable", True, (None, "unavailable")),
    (0, "unverified", True, (None, "unverified")),
])
def test_count_never_invents_a_zero(value, state, complete, expected):
    result = qualified_count(value, source_state=state, complete=complete)
    assert (result.value, result.reason) == expected


@pytest.mark.parametrize(("value", "state", "complete", "code"), [
    (True, "confirmed", True, "count_value"),
    (-1, "confirmed", True, "count_value"),
    (2**53, "confirmed", True, "count_value"),
    (0, "invented", True, "count_source_state"),
    (0, "confirmed", 1, "count_completeness"),
])
def test_count_rejects_malformed_inputs(value, state, complete, code):
    with pytest.raises(AudienceStatusError) as exc:
        qualified_count(value, source_state=state, complete=complete)
    assert str(exc.value) == code


@pytest.mark.parametrize(("current", "expected"), [
    (None, ("unknown", "overlay_missing")),
    (_current(verified=False), ("unknown", "overlay_unverified")),
    (_current(reference_id="other"), ("unknown", "identity_conflict")),
    (_current(state="revoked"), ("unavailable", "revoked")),
    (_current(state="withdrawn"), ("unavailable", "withdrawn")),
    (_current(state="expired"), ("unavailable", "expired")),
    (_current(state="correction_required"), ("unavailable", "correction_required")),
    (_current(state="unavailable"), ("unknown", "unavailable")),
    (_current(state="unknown"), ("unknown", "unknown")),
    (_current(state="unapproved"), ("unavailable", "unapproved")),
    (_current(source_version="v2"), ("unavailable", "version_changed")),
    (_current(body_digest="b" * 64), ("unavailable", "version_changed")),
    (_current(), ("approved", "current_verified")),
])
def test_pin_requires_current_verified_overlay(current, expected):
    result = pinned_reference_status(_pin(), current)
    assert result.captured_state == "approved"
    assert (result.current_use, result.reason) == expected


def test_unapproved_historical_state_is_not_rewritten_by_current_state():
    result = pinned_reference_status(_pin(captured_state="unapproved"), _current())
    assert result.captured_state == "unapproved"
    assert result.current_use == "approved"


@pytest.mark.parametrize(("pin", "current"), [
    (_pin(reference_id="../secret"), None),
    (_pin(body_digest="not-a-digest"), None),
    (_pin(captured_state="published"), None),
    (_pin(), _current(verified=1)),
    (_pin(), _current(state="published")),
    (_pin(), _current(source_version="")),
])
def test_pin_rejects_malformed_safe_claims(pin, current):
    with pytest.raises(AudienceStatusError) as exc:
        pinned_reference_status(pin, current)
    assert str(exc.value) == "reference_argument"


def test_result_shapes_are_immutable():
    with pytest.raises(FrozenInstanceError):
        qualified_count(0, source_state="confirmed", complete=True).value = 1
    with pytest.raises(FrozenInstanceError):
        pinned_reference_status(_pin(), _current()).current_use = "revoked"
