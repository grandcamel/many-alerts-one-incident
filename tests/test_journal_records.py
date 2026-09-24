"""Known-answer and closed-vocabulary tests for ``journal_records`` (unit 15,
module 1; ticket 37 cases A1-A5, the record parts of A11, and A12 for this
module). The sanitized-source-record cases (A6-A10, the source parts of A11,
and A12 for ``journal_source``) live in ``tests/test_journal_source.py``.

Golden values are recomputed independently here with
``json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)`` and
``hashlib.sha256``, per the implementation plan, rather than trusted from the
module under test. Building admission/dedupe_decision test records needs a
sanitized source, so this file also imports the small pieces of
``journal_source`` (a sibling module, not re-exported by ``journal_records``)
that constructing one requires.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import pathlib

import pytest

from grafana_jsm_sandbox import journal_records as jr
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox.forwarder_json import canonical_json, tagged_digest

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent

BOOT_A = "11111111-1111-1111-1111-111111111111"
BOOT_B = "66666666-6666-6666-6666-666666666666"
JOURNAL_UUID = "22222222-2222-2222-2222-222222222222"
WALL_A = "2026-09-23T00:00:00.000000Z"
WALL_B = "2026-09-23T00:01:00.000000Z"
GENESIS_BOUNDS = {
    "max_admissions": 10_000,
    "max_pending_fingerprints": 1_024,
    "ordinary_bytes": 112 * 2**20,
    "total_bytes": 128 * 2**20,
}


# === Shared helpers ==========================================================


def _independent_body(envelope: dict) -> bytes:
    """The plan's independent cross-check encoding, not ``canonical_json``."""
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _independent_record_digest(body: bytes) -> str:
    return hashlib.sha256(b"rj.record.v1\x00" + body).hexdigest()


def _independent_tagged_digest(tag: str, value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(tag.encode("ascii") + b"\x00" + encoded.encode("ascii")).hexdigest()


def _expect(exc_type, code, fn, *args, **kwargs):
    with pytest.raises(exc_type) as info:
        fn(*args, **kwargs)
    error = info.value
    assert error.code == code
    assert error.args == (code,)
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


def expect_record(code, fn, *args, **kwargs):
    return _expect(jr.RecordError, code, fn, *args, **kwargs)


def expect_source(code, fn, *args, **kwargs):
    return _expect(js.SourceError, code, fn, *args, **kwargs)


def stamp(*, boot_id: str = BOOT_A, wall_time: str = WALL_A, mono_us: int = 0) -> jr.Stamp:
    return jr.Stamp(boot_id=boot_id, wall_time=wall_time, mono_us=mono_us)


def position(
    *,
    event_seq: int = 1,
    commit_seq: int = 1,
    commit_index: int = 0,
    commit_size: int = 1,
    prev_record_digest: str = jr.ZERO_DIGEST,
    journal_generation: int = 1,
) -> jr.Position:
    return jr.Position(
        journal_generation=journal_generation, event_seq=event_seq, commit_seq=commit_seq,
        commit_index=commit_index, commit_size=commit_size, prev_record_digest=prev_record_digest,
    )


def genesis_draft(event_id: str = BOOT_A, bounds: dict | None = None) -> jr.Draft:
    return jr.Draft(
        event_id=event_id, event_type="journal_genesis", actor="receiver", ids={},
        data={
            "format": "rj.journal.v1", "journal_uuid": JOURNAL_UUID,
            "bounds": dict(bounds or GENESIS_BOUNDS),
        },
    )


def sample_source() -> js.SourceRecord:
    group_key = '{}:{alertname="Service error rate is elevated", grafana_folder="demo"}'
    alert = js.SourceAlert(
        fingerprint="5e8d72dc87b1ff35", status="firing",
        values=(("A", "1"), ("B", "1")), starts_at=None,
    )
    return js.SourceRecord(
        source_group=js.source_group_digest(group_key), alerts=(alert,),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )


def build_chain() -> tuple[jr.Record, ...]:
    """One record of each of the five in-scope types, chained as a real journal
    would produce them: genesis, then an admission/dedupe_decision commit, then
    a restart_recovery, then a capacity_hold. Used by A1 and A4.
    """
    genesis = jr.seal(genesis_draft(), position(), stamp())

    source = sample_source()
    source_digest = js.source_digest(source)
    dedupe_key = js.dedupe_key(source)
    admission_id = "33333333-3333-3333-3333-333333333333"
    admission = jr.seal(
        jr.Draft(
            event_id=admission_id, event_type="admission", actor="receiver",
            ids={"admission_id": admission_id},
            data={
                "arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
                "source": js.source_to_json(source), "source_digest": source_digest,
            },
        ),
        position(event_seq=2, commit_seq=2, commit_index=0, commit_size=2,
                 prev_record_digest=genesis.record_digest),
        stamp(),
    )
    dedupe_event_id = "44444444-4444-4444-4444-444444444444"
    dedupe_decision = jr.seal(
        jr.Draft(
            event_id=dedupe_event_id, event_type="dedupe_decision", actor="receiver",
            ids={"admission_id": admission_id},
            data={
                "rule": "latest-admitted-v1", "result": "admitted",
                "source_group": source.source_group, "dedupe_key": dedupe_key,
                "baseline_before": None,
                "baseline_after": {
                    "admission_id": admission_id, "complete": True, "dedupe_key": dedupe_key,
                },
                "superseded": (), "pending_count_after": 1,
            },
        ),
        position(event_seq=3, commit_seq=2, commit_index=1, commit_size=2,
                 prev_record_digest=admission.record_digest),
        stamp(),
    )
    restart_id = "55555555-5555-5555-5555-555555555555"
    restart = jr.seal(
        jr.Draft(
            event_id=restart_id, event_type="restart_recovery", actor="receiver", ids={},
            data={
                "previous_boot_id": BOOT_A,
                "recovered": {
                    "commit_seq": 2, "event_seq": 3, "record_digest": dedupe_decision.record_digest,
                },
                "anchor_lag": 0, "wal_found": None,
                "dispatch_hold": "restart_recovery", "prior_leases": "invalid",
            },
        ),
        position(event_seq=4, commit_seq=3, commit_index=0, commit_size=1,
                 prev_record_digest=dedupe_decision.record_digest),
        stamp(boot_id=BOOT_B, wall_time=WALL_B),
    )
    cap_id = "77777777-7777-7777-7777-777777777777"
    capacity_hold = jr.seal(
        jr.Draft(
            event_id=cap_id, event_type="capacity_hold", actor="receiver", ids={},
            data={
                "code": "capacity_admissions", "limit": 5, "observed": 5, "requested": 1,
                "refused_source_digest": source_digest, "action": "set",
            },
        ),
        position(event_seq=5, commit_seq=4, commit_index=0, commit_size=1,
                 prev_record_digest=restart.record_digest),
        stamp(boot_id=BOOT_B, wall_time=WALL_B),
    )
    return genesis, admission, dedupe_decision, restart, capacity_hold


def _envelope_of(record: jr.Record, draft: jr.Draft) -> dict:
    return {
        "schema_version": jr.SCHEMA_VERSION,
        "journal_generation": record.position.journal_generation,
        "event_id": record.event_id,
        "event_seq": record.position.event_seq,
        "commit_seq": record.position.commit_seq,
        "commit_index": record.position.commit_index,
        "commit_size": record.position.commit_size,
        "event_type": record.event_type,
        "actor": record.actor,
        "boot_id": record.stamp.boot_id,
        "wall_time": record.stamp.wall_time,
        "mono_us": record.stamp.mono_us,
        "ids": jr.thaw(draft.ids),
        "data": jr.thaw(draft.data),
        "prev_record_digest": record.position.prev_record_digest,
    }


# === A1: known-answer canonical bytes, record_digest, content_digest =======


def test_a1_known_answer_digests_for_every_event_type():
    genesis_d = genesis_draft()
    records = build_chain()
    drafts = {
        "journal_genesis": genesis_d,
    }
    # Rebuild each draft's exact ids/data alongside its sealed record so the
    # independent encoder sees precisely what `seal` saw.
    source = sample_source()
    source_digest = js.source_digest(source)
    dedupe_key = js.dedupe_key(source)
    admission_id = "33333333-3333-3333-3333-333333333333"
    drafts["admission"] = jr.Draft(
        event_id=admission_id, event_type="admission", actor="receiver",
        ids={"admission_id": admission_id},
        data={
            "arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
            "source": js.source_to_json(source), "source_digest": source_digest,
        },
    )
    drafts["dedupe_decision"] = jr.Draft(
        event_id="44444444-4444-4444-4444-444444444444", event_type="dedupe_decision",
        actor="receiver", ids={"admission_id": admission_id},
        data={
            "rule": "latest-admitted-v1", "result": "admitted",
            "source_group": source.source_group, "dedupe_key": dedupe_key,
            "baseline_before": None,
            "baseline_after": {
                "admission_id": admission_id, "complete": True, "dedupe_key": dedupe_key,
            },
            "superseded": (), "pending_count_after": 1,
        },
    )
    drafts["restart_recovery"] = jr.Draft(
        event_id="55555555-5555-5555-5555-555555555555", event_type="restart_recovery",
        actor="receiver", ids={},
        data={
            "previous_boot_id": BOOT_A,
            "recovered": {
                "commit_seq": 2, "event_seq": 3, "record_digest": records[2].record_digest,
            },
            "anchor_lag": 0, "wal_found": None,
            "dispatch_hold": "restart_recovery", "prior_leases": "invalid",
        },
    )
    drafts["capacity_hold"] = jr.Draft(
        event_id="77777777-7777-7777-7777-777777777777", event_type="capacity_hold",
        actor="receiver", ids={},
        data={
            "code": "capacity_admissions", "limit": 5, "observed": 5, "requested": 1,
            "refused_source_digest": source_digest, "action": "set",
        },
    )

    assert [r.event_type for r in records] == [
        "journal_genesis", "admission", "dedupe_decision", "restart_recovery", "capacity_hold",
    ]
    for record in records:
        draft = drafts[record.event_type]
        envelope = _envelope_of(record, draft)
        independent_body = _independent_body(envelope)
        assert record.body == independent_body
        assert record.record_digest == _independent_record_digest(independent_body)
        # content_digest excludes position/framing/stamp/predecessor.
        content_payload = {
            "schema_version": jr.SCHEMA_VERSION,
            "journal_generation": record.position.journal_generation,
            "event_id": record.event_id,
            "event_type": record.event_type,
            "actor": record.actor,
            "ids": jr.thaw(draft.ids),
            "data": jr.thaw(draft.data),
        }
        expected = _independent_tagged_digest("rj.content.v1", content_payload)
        assert jr.content_digest(record) == expected
        # decoding the sealed body must reproduce the same record.
        assert jr.open_record(record.body) == record


def test_a1_content_digest_uses_tagged_digest_directly():
    record = build_chain()[0]
    assert jr.content_digest(record) == tagged_digest(
        "rj.content.v1",
        {
            "schema_version": 1, "journal_generation": 1, "event_id": record.event_id,
            "event_type": "journal_genesis", "actor": "receiver", "ids": {},
            "data": {
                "format": "rj.journal.v1", "journal_uuid": JOURNAL_UUID, "bounds": GENESIS_BOUNDS,
            },
        },
    )


# === A2: canonical round trip and mutation handling =========================


def test_a2_open_record_round_trips_a_sealed_body():
    record = jr.seal(genesis_draft(), position(), stamp())
    assert jr.open_record(record.body) == record


def test_a2_inserted_space_is_not_canonical():
    record = jr.seal(genesis_draft(), position(), stamp())
    idx = record.body.index(b":")
    mutated = record.body[:idx + 1] + b" " + record.body[idx + 1:]
    assert mutated != record.body
    expect_record("record_not_canonical", jr.open_record, mutated)


def test_a2_reordered_keys_are_not_canonical():
    record = jr.seal(genesis_draft(), position(), stamp())
    envelope = json.loads(record.body)
    reordered = dict(reversed(list(envelope.items())))
    mutated = json.dumps(reordered, separators=(",", ":")).encode("ascii")
    assert mutated != record.body
    expect_record("record_not_canonical", jr.open_record, mutated)


def test_a2_ascii_letter_as_unicode_escape_is_not_canonical():
    record = jr.seal(genesis_draft(), position(), stamp())
    assert b'"journal_genesis"' in record.body
    mutated = record.body.replace(b'"journal_genesis"', b'"\\u006aournal_genesis"')
    assert mutated != record.body
    assert json.loads(mutated)["event_type"] == "journal_genesis"
    expect_record("record_not_canonical", jr.open_record, mutated)


def test_a2_trailing_newline_fails_ascii_only_parsing_before_canonical_check():
    # PLAN DISCREPANCY: the plan's A2 narrative groups a trailing newline with
    # the other three mutations as giving `record_not_canonical`. But the
    # plan also pins `parse_json(body, ..., ascii_only=True)` exactly (L162),
    # and forwarder_json's ascii_only mode rejects any raw byte < 0x20 in the
    # WHOLE document (not just inside strings) -- see forwarder_json.py's
    # `parse_json`, the `any(byte < 0x20 ... for byte in data)` guard. A
    # trailing b"\n" (0x0A) therefore never reaches the canonical-bytes
    # comparison; it is rejected by parse_json itself as `json_unicode`,
    # which `verify_body` maps to `record_json`. Trusting the pinned rule
    # over the narrative, per the task's instruction.
    record = jr.seal(genesis_draft(), position(), stamp())
    mutated = record.body + b"\n"
    expect_record("record_json", jr.open_record, mutated)
    # A trailing plain space (0x20) is not caught by ascii_only and does
    # reach the canonical-bytes comparison, giving `record_not_canonical`.
    expect_record("record_not_canonical", jr.open_record, record.body + b" ")


def test_a2_byte_flip_gives_record_digest_before_any_parse():
    record = jr.seal(genesis_draft(), position(), stamp())
    flipped = bytearray(record.body)
    flipped[10] ^= 0x01
    # The flipped bytes are checked against the ORIGINAL correct digest, so
    # the mismatch is caught before parse_json ever runs -- unlike
    # `open_record`, which would recompute a digest that trivially matches.
    expect_record("record_digest", jr.verify_body, bytes(flipped), record.record_digest)


def test_a2_verify_body_checks_digest_before_syntax():
    record = jr.seal(genesis_draft(), position(), stamp())
    garbage = b"not json at all, but wrong length too"
    expect_record("record_digest", jr.verify_body, garbage, record.record_digest)


# === A3: envelope bounds =====================================================


def _seal_with(**overrides):
    kwargs = {"event_id": BOOT_A, "bounds": None}
    kwargs.update({k: v for k, v in overrides.items() if k in ("event_id", "bounds")})
    draft = genesis_draft(event_id=kwargs["event_id"], bounds=kwargs["bounds"])
    pos = position(**{k: v for k, v in overrides.items() if k in (
        "event_seq", "commit_seq", "commit_index", "commit_size",
        "prev_record_digest", "journal_generation",
    )})
    stmp = stamp(**{k: v for k, v in overrides.items() if k in ("boot_id", "wall_time", "mono_us")})
    draft_keys = ("actor", "event_type", "ids", "data")
    if any(key in overrides for key in draft_keys):
        draft = dataclasses.replace(draft, **{
            k: v for k, v in overrides.items() if k in ("actor", "event_type", "ids", "data")
        })
    return jr.seal(draft, pos, stmp)


def test_a3_id_length_and_charset():
    expect_record("record_id", _seal_with, event_id="x" * 129)
    ok = _seal_with(event_id="x" * 128)
    assert ok.event_id == "x" * 128
    expect_record("record_id", _seal_with, event_id="bad id with spaces")
    expect_record("record_id", _seal_with, event_id="")


def test_a3_sequence_bounds():
    expect_record("record_field", _seal_with, event_seq=0)
    expect_record("record_field", _seal_with, event_seq=2**53)
    expect_record("record_field", _seal_with, commit_seq=0)
    expect_record("record_field", _seal_with, commit_seq=2**53)


def test_a3_commit_framing_bounds():
    expect_record("record_field", _seal_with, commit_index=1, commit_size=1)
    expect_record("record_field", _seal_with, commit_size=0, commit_index=0)
    expect_record("record_field", _seal_with, commit_size=9, commit_index=0)


def test_a3_generation_bounds():
    expect_record("record_field", _seal_with, journal_generation=0)
    expect_record("record_field", _seal_with, journal_generation=2**31)


def test_a3_mono_us_negative():
    expect_record("record_field", _seal_with, mono_us=-1)


@pytest.mark.parametrize("bad_wall_time", [
    "2026-09-23T00:00:00.000000+00:00",  # offset instead of Z
    "2026-09-23t00:00:00.000000Z",  # lowercase t
    "2026-09-23T00:00:00Z",  # no fraction
    "1999-12-31T23:59:59.000000Z",  # year below 2000
    "10000-01-01T00:00:00.000000Z",  # year above 9999
    "2026-02-30T00:00:00.000000Z",  # February 30th: not calendar-valid
])
def test_a3_wall_time_rejections(bad_wall_time):
    expect_record("record_time", _seal_with, wall_time=bad_wall_time)


def test_a3_schema_version_unknown_event_type_and_unknown_rule_are_unsupported():
    genesis = jr.seal(genesis_draft(), position(), stamp())
    envelope = json.loads(genesis.body)
    envelope["schema_version"] = 2
    body = _independent_body(envelope)
    digest = _independent_record_digest(body)
    expect_record("record_unsupported", jr.decode_record, envelope, body, digest)

    envelope2 = json.loads(genesis.body)
    envelope2["event_type"] = "not_a_real_type"
    body2 = _independent_body(envelope2)
    digest2 = _independent_record_digest(body2)
    expect_record("record_unsupported", jr.decode_record, envelope2, body2, digest2)

    # An unknown `rule` on a dedupe_decision.
    source = sample_source()
    dedupe_key = js.dedupe_key(source)
    admission_id = "33333333-3333-3333-3333-333333333333"
    dedupe = jr.seal(
        jr.Draft(
            event_id="44444444-4444-4444-4444-444444444444", event_type="dedupe_decision",
            actor="receiver", ids={"admission_id": admission_id},
            data={
                "rule": "latest-admitted-v1", "result": "admitted",
                "source_group": source.source_group, "dedupe_key": dedupe_key,
                "baseline_before": None,
                "baseline_after": {
                    "admission_id": admission_id, "complete": True, "dedupe_key": dedupe_key,
                },
                "superseded": (), "pending_count_after": 1,
            },
        ),
        position(), stamp(),
    )
    envelope3 = json.loads(dedupe.body)
    envelope3["data"]["rule"] = "latest-admitted-v2"
    body3 = _independent_body(envelope3)
    digest3 = _independent_record_digest(body3)
    expect_record("record_unsupported", jr.decode_record, envelope3, body3, digest3)


def test_a3_unknown_key_gives_record_field():
    expect_record("record_field", _seal_with, data=dict(GENESIS_BOUNDS_DATA(), extra_field="x"))


def GENESIS_BOUNDS_DATA():
    return {"format": "rj.journal.v1", "journal_uuid": JOURNAL_UUID, "bounds": dict(GENESIS_BOUNDS)}


def test_a3_bool_for_int_gives_record_type():
    genesis = jr.seal(genesis_draft(), position(), stamp())
    envelope = json.loads(genesis.body)
    envelope["journal_generation"] = True
    body = _independent_body(envelope)
    digest = _independent_record_digest(body)
    expect_record("record_type", jr.decode_record, envelope, body, digest)


def test_a3_oversized_body_gives_record_too_large():
    genesis = jr.seal(genesis_draft(), position(), stamp())
    padded = genesis.body[:-1] + b" " * (jr.MAX_RECORD_BYTES) + genesis.body[-1:]
    digest = _independent_record_digest(padded)
    expect_record("record_too_large", jr.verify_body, padded, digest)


def test_a3_zero_digest_only_valid_at_event_seq_one():
    genesis = jr.seal(genesis_draft(), position(), stamp())
    # event_seq 1 with a non-zero predecessor.
    expect_record(
        "record_field", _seal_with,
        prev_record_digest="a" * 64,
    )
    # event_seq > 1 with ZERO_DIGEST as predecessor.
    expect_record(
        "record_field", _seal_with,
        event_seq=2, commit_seq=2, prev_record_digest=jr.ZERO_DIGEST,
    )
    assert genesis.position.prev_record_digest == jr.ZERO_DIGEST


# === A4: content_digest scope, record_digest, thaw/freeze ==================


def test_a4_content_digest_ignores_position_framing_stamp_and_predecessor():
    genesis_a = jr.seal(genesis_draft(), position(), stamp())
    genesis_b = jr.seal(
        genesis_draft(),
        position(event_seq=1, commit_seq=1, commit_index=0, commit_size=1,
                 prev_record_digest=jr.ZERO_DIGEST, journal_generation=1),
        stamp(boot_id=BOOT_B, wall_time=WALL_B, mono_us=999),
    )
    # Same event_id/type/actor/ids/data, different stamp -> same content digest.
    assert jr.content_digest(genesis_a) == jr.content_digest(genesis_b)
    assert genesis_a.record_digest != genesis_b.record_digest


def test_a4_content_digest_changes_with_ids_or_data():
    source = sample_source()
    source_digest = js.source_digest(source)
    admission_id = "33333333-3333-3333-3333-333333333333"
    base_data = {
        "arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
        "source": js.source_to_json(source), "source_digest": source_digest,
    }
    rec_1 = jr.seal(
        jr.Draft(event_id=admission_id, event_type="admission", actor="receiver",
                 ids={"admission_id": admission_id}, data=base_data),
        position(event_seq=1), stamp(),
    )
    rec_2 = jr.seal(
        jr.Draft(event_id=admission_id, event_type="admission", actor="receiver",
                 ids={"admission_id": admission_id}, data=dict(base_data, arrival_seq=2)),
        position(event_seq=1), stamp(),
    )
    assert jr.content_digest(rec_1) != jr.content_digest(rec_2)


def test_a4_record_digest_equals_raw_byte_sha256():
    record = jr.seal(genesis_draft(), position(), stamp())
    assert record.record_digest == hashlib.sha256(b"rj.record.v1\x00" + record.body).hexdigest()


def test_a4_thaw_makes_frozen_views_encodable_and_raw_frozen_view_fails():
    record = jr.seal(genesis_draft(), position(), stamp())
    assert type(record.ids) is not dict
    assert type(record.data) is not dict
    thawed_data = jr.thaw(record.data)
    assert type(thawed_data) is dict
    canonical_json(thawed_data, ascii_only=True)  # must not raise
    from grafana_jsm_sandbox.forwarder_json import JSONPolicyError
    with pytest.raises(JSONPolicyError) as info:
        canonical_json(record.data, ascii_only=True)
    assert info.value.code == "json_type"


def test_a4_thaw_is_recursive_over_nested_mappings_and_keeps_tuples():
    nested = jr.thaw({"a": {"b": (1, {"c": 2}, "d")}})
    assert nested == {"a": {"b": (1, {"c": 2}, "d")}}
    assert type(nested["a"]) is dict
    assert type(nested["a"]["b"]) is tuple
    assert type(nested["a"]["b"][1]) is dict


# === A5: per-type validators =================================================


def test_a5_admission_dispatch_holds_sorted_and_unique():
    source = sample_source()
    admission_id = "33333333-3333-3333-3333-333333333333"
    base = {
        "arrival_seq": 1, "decision": "admitted",
        "source": js.source_to_json(source), "source_digest": js.source_digest(source),
    }

    def make(holds):
        return jr.seal(
            jr.Draft(event_id=admission_id, event_type="admission", actor="receiver",
                     ids={"admission_id": admission_id}, data=dict(base, dispatch_holds=holds)),
            position(), stamp(),
        )

    ok = make(("capacity_bytes", "restart_recovery"))
    assert ok.data["dispatch_holds"] == ("capacity_bytes", "restart_recovery")
    expect_record("record_field", make, ("restart_recovery", "capacity_bytes"))  # unsorted
    expect_record("record_field", make, ("restart_recovery", "restart_recovery"))  # duplicate
    expect_record("record_field", make, ("not_a_hold_code",))


def test_a5_admission_with_malformed_embedded_source_propagates_source_error():
    # The embedded sanitized source owns its own closed vocabulary: a bad one
    # raises SourceError straight through `seal`, not a RecordError.
    admission_id = "33333333-3333-3333-3333-333333333333"
    bad_source_json = {
        "alerts": (), "body_digest": "0" * 64, "source_group": "0" * 64,
        "truncated_alerts": 0,
        "provenance": {"kind": "http", "line": None, "path": "/notification"},
    }
    draft = jr.Draft(
        event_id=admission_id, event_type="admission", actor="receiver",
        ids={"admission_id": admission_id},
        data={
            "arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
            "source": bad_source_json, "source_digest": "0" * 64,
        },
    )
    expect_source("source_shape", jr.seal, draft, position(), stamp())


def test_a5_dedupe_decision_superseded_sorted_unique_and_bounded():
    source = sample_source()
    dedupe_key = js.dedupe_key(source)
    admission_id = "33333333-3333-3333-3333-333333333333"

    def make(superseded):
        return jr.seal(
            jr.Draft(
                event_id="44444444-4444-4444-4444-444444444444", event_type="dedupe_decision",
                actor="receiver", ids={"admission_id": admission_id},
                data={
                    "rule": "latest-admitted-v1", "result": "pending_reduced",
                    "source_group": source.source_group, "dedupe_key": dedupe_key,
                    "baseline_before": None,
                    "baseline_after": {
                        "admission_id": admission_id, "complete": True, "dedupe_key": dedupe_key,
                    },
                    "superseded": superseded, "pending_count_after": 1,
                },
            ),
            position(), stamp(),
        )

    def entry(admission_id, fingerprint):
        return {"admission_id": admission_id, "fingerprint": fingerprint}

    ok = make((entry("aa", "fp-a"), entry("bb", "fp-b")))
    assert len(ok.data["superseded"]) == 2
    expect_record("record_field", make, (entry("bb", "fp-b"), entry("aa", "fp-a")))  # unsorted
    expect_record(
        "record_field", make,
        tuple(entry(f"id{i}", f"fp-{i:03d}") for i in range(33)),
    )


def test_a5_baseline_requires_exact_bool_complete():
    source = sample_source()
    dedupe_key = js.dedupe_key(source)
    admission_id = "33333333-3333-3333-3333-333333333333"

    def make(complete_value):
        return jr.seal(
            jr.Draft(
                event_id="44444444-4444-4444-4444-444444444444", event_type="dedupe_decision",
                actor="receiver", ids={"admission_id": admission_id},
                data={
                    "rule": "latest-admitted-v1", "result": "admitted",
                    "source_group": source.source_group, "dedupe_key": dedupe_key,
                    "baseline_before": None,
                    "baseline_after": {
                        "admission_id": admission_id, "complete": complete_value,
                        "dedupe_key": dedupe_key,
                    },
                    "superseded": (), "pending_count_after": 1,
                },
            ),
            position(), stamp(),
        )

    assert make(True).data["baseline_after"]["complete"] is True
    expect_record("record_type", make, 1)
    expect_record("record_type", make, "true")


def test_a5_capacity_hold_requested_at_least_one():
    def make(requested):
        return jr.seal(
            jr.Draft(
                event_id="77777777-7777-7777-7777-777777777777", event_type="capacity_hold",
                actor="receiver", ids={},
                data={
                    "code": "capacity_admissions", "limit": 5, "observed": 5,
                    "requested": requested, "refused_source_digest": "0" * 64, "action": "set",
                },
            ),
            position(), stamp(),
        )

    assert make(1).data["requested"] == 1
    expect_record("record_field", make, 0)


def test_a5_restart_recovery_wal_found_shape():
    def make(wal_found):
        return jr.seal(
            jr.Draft(
                event_id="55555555-5555-5555-5555-555555555555", event_type="restart_recovery",
                actor="receiver", ids={},
                data={
                    "previous_boot_id": BOOT_A,
                    "recovered": {"commit_seq": 1, "event_seq": 1, "record_digest": "a" * 64},
                    "anchor_lag": 0, "wal_found": wal_found,
                    "dispatch_hold": "restart_recovery", "prior_leases": "invalid",
                },
            ),
            position(), stamp(),
        )

    assert make(None).data["wal_found"] is None
    ok = make({"size": 128, "digest": "b" * 64})
    assert ok.data["wal_found"]["size"] == 128
    expect_record("record_field", make, {"size": 128})  # missing "digest"
    expect_record("record_field", make, {"size": 128, "digest": "b" * 64, "extra": 1})


def test_a5_genesis_bounds_against_ceilings():
    ok = _seal_with(bounds=dict(GENESIS_BOUNDS, max_admissions=10_000))
    assert ok.data["bounds"]["max_admissions"] == 10_000
    expect_record("record_field", _seal_with, bounds=dict(GENESIS_BOUNDS, max_admissions=10_001))
    expect_record(
        "record_field", _seal_with,
        bounds=dict(GENESIS_BOUNDS, ordinary_bytes=GENESIS_BOUNDS["total_bytes"] + 1,
                    total_bytes=GENESIS_BOUNDS["total_bytes"]),
    )


@pytest.mark.parametrize("fingerprint", ["bad fp!", "fp/1", "a" * 65, ""])
def test_a5_superseded_fingerprint_uses_the_source_fingerprint_grammar(fingerprint):
    source = sample_source()
    dedupe_key = js.dedupe_key(source)
    admission_id = "33333333-3333-3333-3333-333333333333"
    draft = jr.Draft(
        event_id="44444444-4444-4444-4444-444444444444", event_type="dedupe_decision",
        actor="receiver", ids={"admission_id": admission_id},
        data={
            "rule": "latest-admitted-v1", "result": "pending_reduced",
            "source_group": source.source_group, "dedupe_key": dedupe_key,
            "baseline_before": None,
            "baseline_after": {
                "admission_id": admission_id, "complete": True, "dedupe_key": dedupe_key,
            },
            "superseded": ({"admission_id": "aa", "fingerprint": fingerprint},),
            "pending_count_after": 1,
        },
    )
    expect_record("record_field", jr.seal, draft, position(), stamp())


# Non-ASCII digits (ARABIC-INDIC) in otherwise well-formed times.
NON_ASCII_YEAR = "٢٠٢٦"


def test_a3_wall_time_with_non_ascii_digits_is_record_time():
    expect_record("record_time", _seal_with, wall_time=f"{NON_ASCII_YEAR}-09-23T00:00:00.000000Z")


def test_seal_maps_a_non_ascii_starts_at_to_a_source_error():
    source_json = js.source_to_json(sample_source())
    alert = dict(source_json["alerts"][0], starts_at=f"{NON_ASCII_YEAR}-09-17T21:56:20Z")
    admission_id = "33333333-3333-3333-3333-333333333333"
    draft = jr.Draft(
        event_id=admission_id, event_type="admission", actor="receiver",
        ids={"admission_id": admission_id},
        data={
            "arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
            "source": dict(source_json, alerts=(alert,)), "source_digest": "0" * 64,
        },
    )
    expect_source("source_starts_at", jr.seal, draft, position(), stamp())


def test_thaw_refuses_cycles_and_excessive_depth_with_a_fixed_code():
    cyclic: dict = {}
    cyclic["self"] = cyclic
    expect_record("record_field", jr.thaw, cyclic)
    deep: object = "leaf"
    for _ in range(3_000):
        deep = {"k": deep}
    expect_record("record_field", jr.thaw, deep)
    at_bound: object = "leaf"
    for _ in range(16):  # canonical_json's depth cap: still thawed
        at_bound = {"k": at_bound}
    assert jr.thaw(at_bound) == at_bound


# === A11 (record part): closed error custody ===================================


def test_a11_record_error_codes_are_closed_and_custody_clean():
    for code in jr.RECORD_ERROR_CODES:
        error = jr.RecordError(code)
        assert error.args == (code,)
        assert error.code == code
        assert error.__cause__ is None
        assert error.__context__ is None


def test_a11_every_raised_error_code_is_in_the_closed_set():
    # A sweep of realistic failures across this module's public entry points.
    expect_record("record_id", jr.validate_id, "bad id")
    assert "record_id" in jr.RECORD_ERROR_CODES
    expect_record("record_argument", jr.seal, "not a draft", position(), stamp())
    assert "record_argument" in jr.RECORD_ERROR_CODES
    # RECORD_ERROR_CODES and SOURCE_ERROR_CODES are disjoint closed sets, so a
    # caller can tell which module rejected an input from the code alone.
    assert jr.RECORD_ERROR_CODES.isdisjoint(js.SOURCE_ERROR_CODES)


# === A12: AST checks (imports, except bodies, banned datetime calls) =======

MODULE_PATH = REPOSITORY / "grafana_jsm_sandbox" / "journal_records.py"
ALLOWED_TOP_LEVEL_IMPORTS = frozenset({
    "__future__", "dataclasses", "hashlib", "re", "collections", "types", "datetime",
})


def _module_ast() -> ast.Module:
    source = MODULE_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(MODULE_PATH))


def test_a12_imports_match_the_exact_allowlist():
    tree = _module_ast()
    top_level_names: set[str] = set()
    from_imports: set[tuple[int, str, tuple[str, ...]]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            names = tuple(sorted(alias.name for alias in node.names))
            from_imports.add((node.level, module, names))
            if node.level == 0:
                top_level_names.add((module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            target = node.func
            is_dunder_import = isinstance(target, ast.Name) and target.id == "__import__"
            is_importlib = isinstance(target, ast.Attribute) and target.attr == "import_module"
            assert not is_dunder_import and not is_importlib, "dynamic import call found"

    assert top_level_names == ALLOWED_TOP_LEVEL_IMPORTS
    assert (0, "__future__", ("annotations",)) in from_imports
    assert (0, "collections.abc", ("Mapping",)) in from_imports
    assert (0, "types", ("MappingProxyType",)) in from_imports
    assert (0, "datetime", ("datetime", "timezone")) in from_imports
    assert (1, "forwarder_json", (
        "JSONPolicyError", "canonical_json", "parse_json", "tagged_digest",
    )) in from_imports
    assert (1, "journal_source", ("MAX_FINGERPRINT_BYTES", "source_from_json")) in from_imports
    # Exactly these six `from` imports -- no extra relative or absolute one,
    # and in particular no re-import of anything `journal_source` re-exports.
    assert len(from_imports) == 6


def test_a12_except_bodies_are_only_assign_annassign_or_pass():
    tree = _module_ast()
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) >= 3  # sanity: the module really does have handlers to check
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), (
                f"except body has a {type(statement).__name__} at line {statement.lineno}"
            )
        for inner in ast.walk(handler):
            if isinstance(inner, ast.Raise):
                pytest.fail(f"raise inside except handler at line {inner.lineno}")


def test_a12_no_datetime_now_utcnow_or_today():
    tree = _module_ast()
    banned = {"now", "utcnow", "today"}
    offenders = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in banned
    ]
    assert offenders == []


# === Unit 15a review gaps: envelope and per-type checks left unasserted =====
#
# The following close specific reviewer-found gaps: each isolates exactly one
# comparison (every other envelope/data field stays valid) so the test can
# only pass if that one comparison actually runs.


def test_actor_spawner_is_rejected_even_though_it_is_a_valid_actor():
    # "spawner" is a member of ACTORS, but every v1 type additionally requires
    # `actor == "receiver"` (spec L150-151). A mutant that only checks
    # membership in ACTORS (dropping the `!= "receiver"` comparison) would
    # accept this and must not.
    assert "spawner" in jr.ACTORS
    expect_record("record_field", _seal_with, actor="spawner")


def test_admission_id_in_ids_must_equal_the_record_event_id():
    source = sample_source()
    admission_id = "33333333-3333-3333-3333-333333333333"
    draft = jr.Draft(
        # A well-formed but different event_id from `ids.admission_id`.
        event_id="99999999-9999-9999-9999-999999999999", event_type="admission", actor="receiver",
        ids={"admission_id": admission_id},
        data={
            "arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
            "source": js.source_to_json(source), "source_digest": js.source_digest(source),
        },
    )
    expect_record("record_field", jr.seal, draft, position(), stamp())


def test_genesis_ordinary_bytes_over_total_bytes_while_both_are_under_ceiling():
    # Both fields individually pass their own `V1_BOUND_CEILINGS` check (112
    # MiB and 128 MiB respectively); only the cross-field
    # `ordinary_bytes > total_bytes` comparison can reject this input. A bound
    # that also violated its own ceiling (as in
    # `test_a5_genesis_bounds_against_ceilings`) would not isolate this check.
    expect_record(
        "record_field", _seal_with,
        bounds=dict(GENESIS_BOUNDS, ordinary_bytes=50 * 2**20, total_bytes=10 * 2**20),
    )


def test_dedupe_decision_superseded_rejects_duplicate_fingerprint():
    # Two entries that share a fingerprint are neither strictly sorted nor
    # unique. A mutant that only checks strict ordering between *distinct*
    # values (`<` instead of `<=`) would let a same-fingerprint pair through.
    source = sample_source()
    dedupe_key = js.dedupe_key(source)
    admission_id = "33333333-3333-3333-3333-333333333333"
    draft = jr.Draft(
        event_id="44444444-4444-4444-4444-444444444444", event_type="dedupe_decision",
        actor="receiver", ids={"admission_id": admission_id},
        data={
            "rule": "latest-admitted-v1", "result": "pending_reduced",
            "source_group": source.source_group, "dedupe_key": dedupe_key,
            "baseline_before": None,
            "baseline_after": {
                "admission_id": admission_id, "complete": True, "dedupe_key": dedupe_key,
            },
            "superseded": (
                {"admission_id": "aa", "fingerprint": "fp-1"},
                {"admission_id": "bb", "fingerprint": "fp-1"},
            ),
            "pending_count_after": 1,
        },
    )
    expect_record("record_field", jr.seal, draft, position(), stamp())


_GENESIS_HASHSEED_SCRIPT = """
import sys
sys.path.insert(0, sys.argv[1])
from grafana_jsm_sandbox import journal_records as jr

bounds = {
    "max_admissions": "bad",
    "max_pending_fingerprints": 1024,
    "ordinary_bytes": 999_999_999_999,
    "total_bytes": 128 * 2**20,
}
draft = jr.Draft(
    event_id="x", event_type="journal_genesis", actor="receiver", ids={},
    data={
        "format": "rj.journal.v1",
        "journal_uuid": "22222222-2222-2222-2222-222222222222",
        "bounds": bounds,
    },
)
pos = jr.Position(
    journal_generation=1, event_seq=1, commit_seq=1, commit_index=0,
    commit_size=1, prev_record_digest=jr.ZERO_DIGEST,
)
stamp = jr.Stamp(boot_id="boot-0", wall_time="2026-09-23T00:00:00.000000Z", mono_us=0)
try:
    jr.seal(draft, pos, stamp)
    print("no-error")
except jr.RecordError as error:
    print(error.code)
"""


def test_genesis_bounds_error_code_is_hash_seed_independent(tmp_path):
    # Two bad fields: `max_admissions` is the wrong type (would give
    # `record_type`) and `ordinary_bytes` is out of range (would give
    # `record_field`). `_validate_journal_genesis` iterates
    # `sorted(_BOUNDS_KEYS)`, so `max_admissions` (alphabetically first) is
    # always checked before `ordinary_bytes`, and the result is always
    # `record_type`. A mutant that iterates the bare frozenset instead of the
    # sorted tuple would let `PYTHONHASHSEED` change which field is checked
    # first, and thus which code comes back.
    import os
    import subprocess
    import sys

    script_path = tmp_path / "genesis_hashseed.py"
    script_path.write_text(_GENESIS_HASHSEED_SCRIPT)
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    codes = set()
    for seed in ("0", "1", "2", "42"):
        result = subprocess.run(
            [sys.executable, str(script_path), str(repo_root)],
            capture_output=True, text=True, check=True, timeout=10,
            env=dict(os.environ, PYTHONHASHSEED=seed),
        )
        codes.add(result.stdout.strip())
    assert codes == {"record_type"}
