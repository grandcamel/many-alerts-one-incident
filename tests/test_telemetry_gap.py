"""Receiver-only synthetic gap bytes do not claim delivery or native evidence."""

import hashlib
import json

import pytest

from grafana_jsm_sandbox.telemetry_gap import (
    GAP_CODES_BY_KIND,
    TelemetryGapError,
    decode_gap,
    encode_gap,
)

RUN = "00000000-0000-4000-8000-000000000001"
REHEARSAL = "00000000-0000-4000-8000-000000000002"
GENERATION = "00000000-0000-4000-8000-000000000003"
SOURCE_ID = "00000000-0000-4000-8000-000000000004"
OTHER_RUN = "00000000-0000-4000-8000-000000000005"
UTC = "2026-09-25T12:34:56.123456Z"


def _draft(**changes):
    value = {
        "schema_version": 1,
        "feed": "run_gaps",
        "marker_source_id": SOURCE_ID,
        "run_id": RUN,
        "rehearsal_id": REHEARSAL,
        "producer_instance_id": None,
        "native_session_id": None,
        "projection_generation": GENERATION,
        "projection_seq": 7,
        "event_kind": "telemetry_omitted",
        "source": {"class": "receiver", "version": "receiver_projection_v1"},
        "observed_at": UTC,
        "ingested_at": UTC,
        "associations": None,
        "payload": {
            "loss_code": "unknown_receiver_shape",
            "count": 1,
            "first_observed_at": UTC,
            "last_observed_at": UTC,
            "affected_projection_seq_first": 6,
            "affected_projection_seq_last": 6,
        },
        "loss": ["unknown_receiver_shape"],
    }
    value.update(changes)
    return value


def _code(call, expected):
    with pytest.raises(TelemetryGapError) as caught:
        call()
    assert caught.value.code == expected
    assert caught.value.args == (expected,)


def test_canonical_identity_digest_and_byte_readback(tmp_path):
    draft = _draft()
    artifact = encode_gap(draft)
    identity = [RUN, GENERATION, 7, "telemetry_omitted", SOURCE_ID]
    identity_bytes = json.dumps(identity, separators=(",", ":")).encode()
    event_id = hashlib.sha256(b"maoi.run-gap.v1\x00" + identity_bytes).hexdigest()
    assert artifact.projected_event_id == event_id
    expected = json.dumps(
        {**draft, "projected_event_id": event_id}, sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert artifact.body == expected
    assert artifact.byte_count == len(expected) <= 2048
    assert artifact.sha256 == hashlib.sha256(expected).hexdigest()
    assert decode_gap(expected) == artifact
    path = tmp_path / "gap.json"
    path.write_bytes(expected)
    assert decode_gap(path.read_bytes()) == artifact
    assert b"raw" not in artifact.body and b"credential" not in artifact.body


def test_receiver_identity_includes_run_kind_generation_sequence_and_source():
    base = encode_gap(_draft()).projected_event_id
    for changes in (
        {"run_id": OTHER_RUN},
        {"projection_generation": OTHER_RUN},
        {"projection_seq": 8},
        {"marker_source_id": OTHER_RUN},
        {"event_kind": "telemetry_gap", "loss": ["projection_sequence_gap"],
         "payload": {**_draft()["payload"], "loss_code": "projection_sequence_gap"}},
    ):
        assert encode_gap(_draft(**changes)).projected_event_id != base
    # A coalesced count is excluded from event identity. A transport must
    # freeze the body before retry and reject a changed body under this ID.
    changed = _draft(payload={
        **_draft()["payload"], "count": 2,
        "affected_projection_seq_last": 7,
    })
    assert encode_gap(changed).projected_event_id == base
    assert encode_gap(changed).sha256 != encode_gap(_draft()).sha256


@pytest.mark.parametrize(("kind", "code"), [
    (kind, code) for kind, codes in GAP_CODES_BY_KIND.items() for code in codes
])
def test_initial_closed_kind_code_registry(kind, code):
    payload = {**_draft()["payload"], "loss_code": code}
    if code == "delivery_unknown":
        payload.update(count=None, affected_projection_seq_first=None,
                       affected_projection_seq_last=None)
    artifact = encode_gap(_draft(event_kind=kind, payload=payload, loss=[code]))
    assert decode_gap(artifact.body) == artifact
    assert b"receiver_projection_v1" in artifact.body


def test_known_omission_counts_and_ranges_cannot_be_unknown_or_zero():
    for code in ("unknown_receiver_shape", "receiver_privacy_rejected",
                 "projection_sequence_gap"):
        kind = "telemetry_gap" if code == "projection_sequence_gap" else "telemetry_omitted"
        base = {**_draft()["payload"], "loss_code": code}
        for changes in (
            {"count": None}, {"count": 0},
            {"count": 100},
            {"affected_projection_seq_first": None,
             "affected_projection_seq_last": None},
        ):
            _code(lambda changes=changes, kind=kind, base=base, code=code: encode_gap(_draft(
                event_kind=kind, payload={**base, **changes}, loss=[code],
            )), "telemetry_gap_shape")


def test_null_unknown_delivery_and_time_are_not_inferred_as_zero():
    payload = {**_draft()["payload"], "loss_code": "delivery_unknown",
               "count": None, "first_observed_at": None, "last_observed_at": None,
               "affected_projection_seq_first": None,
               "affected_projection_seq_last": None}
    artifact = encode_gap(_draft(
        event_kind="telemetry_gap", payload=payload,
        loss=["delivery_unknown"], observed_at=None,
    ))
    assert b'"count":null' in artifact.body
    assert b'"observed_at":null' in artifact.body
    assert decode_gap(artifact.body) == artifact


@pytest.mark.parametrize(("changes", "expected"), [
    ({"feed": "run_events"}, "telemetry_gap_shape"),
    ({"run_id": "not-an-id"}, "telemetry_gap_id"),
    ({"rehearsal_id": None}, "telemetry_gap_id"),
    ({"projection_seq": True}, "telemetry_gap_shape"),
    ({"source": {"class": "native_otel", "version": "receiver_projection_v1"}},
     "telemetry_gap_shape"),
    ({"native_session_id": SOURCE_ID}, "telemetry_gap_shape"),
    ({"ingested_at": "2026-02-30T12:34:56.123456Z"}, "telemetry_gap_time"),
    ({"raw_prompt": "secret"}, "telemetry_gap_shape"),
    ({"account_identity": "secret"}, "telemetry_gap_shape"),
])
def test_identity_privacy_and_time_rejections(changes, expected):
    _code(lambda: encode_gap(_draft(**changes)), expected)


def test_payload_order_and_loss_mismatch_are_rejected():
    base = _draft()["payload"]
    _code(lambda: encode_gap(_draft(payload={
        **base, "first_observed_at": "2026-09-25T12:34:57.123456Z",
    })), "telemetry_gap_time")
    _code(lambda: encode_gap(_draft(payload={
        **base, "affected_projection_seq_first": 8,
    })), "telemetry_gap_shape")
    _code(lambda: encode_gap(_draft(loss=["delivery_unknown"])), "telemetry_gap_shape")
    _code(lambda: encode_gap(_draft(payload={**base, "raw_event_name": "leak"})),
          "telemetry_gap_shape")


def test_malformed_duplicate_noncanonical_and_forged_event_id_fail_closed():
    artifact = encode_gap(_draft())
    _code(lambda: decode_gap(b"\xff"), "json_encoding")
    _code(lambda: decode_gap(b'{"feed":"run_gaps","feed":"run_gaps"}'),
          "json_duplicate_key")
    _code(lambda: decode_gap(b" " + artifact.body), "telemetry_gap_noncanonical")
    _code(lambda: decode_gap(artifact.body + b" " * 2049), "telemetry_gap_overflow")
    _code(lambda: decode_gap("not bytes"), "telemetry_gap_argument")
    forged = json.loads(artifact.body)
    forged["projected_event_id"] = "f" * 64
    forged_bytes = json.dumps(forged, sort_keys=True, separators=(",", ":")).encode()
    _code(lambda: decode_gap(forged_bytes), "telemetry_gap_id")


def test_hostile_python_type_returns_fixed_error():
    class Hostile:
        def __eq__(self, other):
            raise AssertionError("hostile equality was reached")

    _code(lambda: encode_gap(_draft(event_kind=Hostile())), "telemetry_gap_shape")
