"""Content-free ticket-39 loss markers carry no capture or review authority."""

import hashlib
import json

import pytest

from grafana_jsm_sandbox.audit_loss import (
    LOSS_CODE_BY_STATE,
    AuditLossError,
    decode_loss,
    encode_loss,
)

LOSS = "a0000000-0000-4000-8000-000000000001"
BUNDLE = "00000000-0000-4000-8000-000000000002"
EXCHANGE = "00000000-0000-4000-8000-000000000003"
REVISION = "00000000-0000-4000-8000-000000000004"


def _marker(**changes):
    value = {
        "schema_version": 1,
        "record_kind": "audit_loss",
        "loss_id": LOSS,
        "audit_bundle_id": BUNDLE,
        "exchange_id": EXCHANGE,
        "report_revision_id": None,
        "side": "response",
        "state": "missing",
        "loss_code": "expected_record_missing",
        "source": "unqualified_local",
        "detected_phase": "after_persistence",
        "observed_at": "2026-09-25T12:34:56.123456Z",
    }
    value.update(changes)
    return value


def _code(call, expected):
    with pytest.raises(AuditLossError) as caught:
        call()
    assert caught.value.code == expected
    assert caught.value.args == (expected,)


def test_canonical_bytes_external_digest_and_local_roundtrip(tmp_path):
    value = _marker()
    artifact = encode_loss(value)
    expected = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    assert artifact.body == expected
    assert artifact.byte_count == len(expected) <= 1024
    assert artifact.sha256 == hashlib.sha256(expected).hexdigest()
    assert b"content_sha256" not in expected
    assert b"grade" not in expected
    assert decode_loss(expected) == artifact
    path = tmp_path / "loss.json"
    path.write_bytes(expected)
    assert decode_loss(path.read_bytes()) == artifact


@pytest.mark.parametrize("state", tuple(LOSS_CODE_BY_STATE))
def test_every_closed_loss_state_is_unqualified(state):
    artifact = encode_loss(_marker(state=state, loss_code=LOSS_CODE_BY_STATE[state]))
    assert decode_loss(artifact.body) == artifact
    assert b"unqualified_local" in artifact.body


def test_empty_is_not_missing_and_report_side_requires_report_identity():
    _code(lambda: encode_loss(_marker(state="empty")), "audit_loss_shape")
    _code(lambda: encode_loss(_marker(state="returned")), "audit_loss_shape")
    _code(lambda: encode_loss(_marker(side="report")), "audit_loss_id")
    report = _marker(side="report", exchange_id=None, report_revision_id=REVISION)
    assert decode_loss(encode_loss(report).body) == encode_loss(report)
    _code(lambda: encode_loss(_marker(side="request", report_revision_id=REVISION)),
          "audit_loss_id")


def test_state_code_registry_cannot_be_mutated_into_a_new_wire_semantics():
    with pytest.raises(TypeError):
        LOSS_CODE_BY_STATE["empty"] = "promoted"
    with pytest.raises(TypeError):
        LOSS_CODE_BY_STATE["missing"] = "changed"
    _code(lambda: encode_loss(_marker(state="empty", loss_code="promoted")),
          "audit_loss_shape")
    assert encode_loss(_marker()).body == decode_loss(encode_loss(_marker()).body).body


@pytest.mark.parametrize(("changes", "code"), [
    ({"loss_id": LOSS.upper()}, "audit_loss_id"),
    ({"loss_id": "00000000-0000-1000-8000-000000000001"}, "audit_loss_id"),
    ({"audit_bundle_id": "not-an-id"}, "audit_loss_id"),
    ({"observed_at": "2026-02-30T12:34:56.123456Z"}, "audit_loss_time"),
    ({"observed_at": "2026-09-25T12:34:56Z"}, "audit_loss_time"),
    ({"source": "native_capture"}, "audit_loss_shape"),
    ({"loss_code": "unknown"}, "audit_loss_shape"),
    ({"detected_phase": "after_send"}, "audit_loss_shape"),
    ({"schema_version": True}, "audit_loss_shape"),
    ({"raw_body": "credential"}, "audit_loss_shape"),
    ({"grade": "correct"}, "audit_loss_shape"),
])
def test_wrong_identity_time_or_authority_field_is_rejected(changes, code):
    _code(lambda: encode_loss(_marker(**changes)), code)


def test_malformed_duplicate_noncanonical_and_oversized_bytes_fail_closed():
    good = encode_loss(_marker()).body
    _code(lambda: decode_loss(b"\xff"), "json_encoding")
    _code(lambda: decode_loss(b'{"state":"missing","state":"missing"}'),
          "json_duplicate_key")
    _code(lambda: decode_loss(b" " + good), "audit_loss_noncanonical")
    _code(lambda: decode_loss(good + b" " * 1025), "audit_loss_overflow")
    _code(lambda: decode_loss("not bytes"), "audit_loss_argument")


def test_hostile_python_values_cannot_escape_fixed_errors():
    class Hostile:
        def __eq__(self, other):
            raise AssertionError("caller-controlled equality was reached")

        def __ne__(self, other):
            raise AssertionError("caller-controlled inequality was reached")

    _code(lambda: encode_loss(_marker(state=Hostile())), "audit_loss_shape")
    _code(lambda: encode_loss(_marker(source=Hostile())), "audit_loss_shape")
