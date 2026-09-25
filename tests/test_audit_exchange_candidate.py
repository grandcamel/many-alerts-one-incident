"""Untrusted exchange candidates cannot establish a captured response."""

import pytest

from grafana_jsm_sandbox.audit_exchange_candidate import (
    ExchangeCandidateError,
    ExchangeCandidatePrecheck,
    precheck_exchange_candidate,
)
from grafana_jsm_sandbox.audit_loss import LOSS_CODE_BY_STATE, encode_loss

BUNDLE = "00000000-0000-4000-8000-000000000001"
EXCHANGE = "00000000-0000-4000-8000-000000000002"
OTHER = "00000000-0000-4000-8000-000000000003"
REQUEST_LOSS = "00000000-0000-4000-8000-000000000004"
RESPONSE_LOSS = "00000000-0000-4000-8000-000000000005"
UTC = "2026-09-25T12:00:00.000000Z"


def _marker(side, state, **changes):
    value = {
        "schema_version": 1,
        "record_kind": "audit_loss",
        "loss_id": REQUEST_LOSS if side == "request" else RESPONSE_LOSS,
        "audit_bundle_id": BUNDLE,
        "exchange_id": EXCHANGE,
        "report_revision_id": None,
        "side": side,
        "state": state,
        "loss_code": LOSS_CODE_BY_STATE[state],
        "source": "unqualified_local",
        "detected_phase": "after_persistence",
        "observed_at": UTC,
    }
    value.update(changes)
    return encode_loss(value).body


def _pair(request_state="returned", response_state="returned", **changes):
    value = {
        "audit_bundle_id": BUNDLE,
        "exchange_id": EXCHANGE,
        "request_state": request_state,
        "response_state": response_state,
        "request_loss": (
            _marker("request", request_state)
            if request_state in LOSS_CODE_BY_STATE else None
        ),
        "response_loss": (
            _marker("response", response_state)
            if response_state in LOSS_CODE_BY_STATE else None
        ),
    }
    value.update(changes)
    return value


def _code(call, expected):
    with pytest.raises(ExchangeCandidateError) as caught:
        call()
    assert caught.value.code == expected
    assert caught.value.args == (expected,)


def test_returned_and_explicit_empty_stay_capture_unverified():
    for request_state, response_state in (("returned", "returned"),
                                          ("returned", "empty"),
                                          ("empty", "returned"),
                                          ("empty", "empty")):
        result = precheck_exchange_candidate(_pair(request_state, response_state))
        assert result == ExchangeCandidatePrecheck(())
        assert result.capture_status == "capture_unverified"


@pytest.mark.parametrize("state", sorted(LOSS_CODE_BY_STATE))
@pytest.mark.parametrize("side", ["request", "response"])
def test_each_gap_state_requires_its_canonical_side_marker(state, side):
    pair = _pair(**{f"{side}_state": state})
    assert precheck_exchange_candidate(pair).defects == ()
    pair[f"{side}_loss"] = None
    result = precheck_exchange_candidate(pair)
    assert result.defects == (f"{side}_loss_missing",)
    assert result.capture_status == "capture_unverified"


def test_empty_is_not_missing_and_an_extra_loss_never_completes_it():
    pair = _pair(response_state="empty", response_loss=_marker("response", "missing"))
    result = precheck_exchange_candidate(pair)
    assert result.defects == ("response_loss_mismatch", "response_loss_unexpected")
    assert result.capture_status == "capture_unverified"


def test_two_loss_records_cannot_reuse_one_identity():
    pair = _pair(request_state="missing", response_state="truncated")
    pair["response_loss"] = _marker("response", "truncated", loss_id=REQUEST_LOSS)
    result = precheck_exchange_candidate(pair)
    assert result.defects == ("loss_identity_duplicate",)
    assert result.capture_status == "capture_unverified"


@pytest.mark.parametrize("marker", [
    _marker("request", "missing"),
    _marker("response", "missing", exchange_id=OTHER),
    _marker("response", "missing", audit_bundle_id=OTHER),
    _marker("response", "truncated"),
])
def test_wrong_side_id_or_state_marker_is_a_fixed_mismatch(marker):
    result = precheck_exchange_candidate(_pair(
        response_state="missing", response_loss=marker,
    ))
    assert "response_loss_mismatch" in result.defects
    assert result.capture_status == "capture_unverified"


@pytest.mark.parametrize("marker", [
    b"\xff",
    b'{"side":"request","side":"response"}',
    b" " + _marker("response", "missing"),
    _marker("response", "missing") + b" " * 1025,
])
def test_malformed_duplicate_noncanonical_and_oversized_loss_bytes_fail(marker):
    _code(lambda: precheck_exchange_candidate(_pair(
        response_state="missing", response_loss=marker,
    )), "exchange_candidate_loss")


@pytest.mark.parametrize("value", [
    {**_pair(), "response_body": "private"},
    _pair(audit_bundle_id="wrong"),
    _pair(response_state="complete"),
    _pair(response_loss="not bytes"),
    _pair(request_state=True),
])
def test_malformed_content_or_type_fails_closed(value):
    _code(lambda: precheck_exchange_candidate(value), "exchange_candidate_shape")


def test_hostile_python_values_do_not_enter_comparison_or_formatting():
    class Hostile:
        __hash__ = object.__hash__

        def __eq__(self, other):
            raise AssertionError("hostile equality was reached")

        def __str__(self):
            raise AssertionError("hostile formatting was reached")

    for value in (
        _pair(response_state=Hostile()),
        _pair(response_loss=Hostile()),
        {"audit_bundle_id": BUNDLE, Hostile(): EXCHANGE},
    ):
        _code(lambda value=value: precheck_exchange_candidate(value),
              "exchange_candidate_shape")
