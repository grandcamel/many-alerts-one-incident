"""Pure tests for the front-door journal extensions in ``journal_records`` and
``journal_reducer`` (ticket 37, unit 17a; Implementer A, cases A1-A12).

Every projection here is built by replaying planned records through
``verify_commit``/``apply_delta``, exactly as the live shell and ``replay``
do; nothing opens a store. ``capture_rows``, ``wire`` and ``grafana_group``
are imported read-only from ``tests.test_journal_ingress_corpus``, and the
unit-16 forgeries and divergence patches from ``tests.test_journal_ingress``,
for A3/A4; everything else is self-contained, in the style of
``tests/test_recovery_journal_adversarial.py``.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import pathlib
import random

import pytest

from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_records as jr
from grafana_jsm_sandbox import journal_reducer as jrd
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox.forwarder_json import (
    MAX_JSON_ARRAY_ITEMS,
    JSONPolicyError,
    canonical_json,
    tagged_digest,
)
from tests.test_journal_ingress import DIVERGENCE_PATCHES, FORGED_REFUSALS, _valid_member_refusal
from tests.test_journal_ingress_corpus import capture_rows, grafana_group, wire

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


def expect_replay(code, fn, *args, **kwargs):
    return _expect(jrd.ReplayError, code, fn, *args, **kwargs)


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


def sample_source(fingerprint: str = "5e8d72dc87b1ff35") -> js.SourceRecord:
    group_key = '{}:{alertname="Service error rate is elevated", grafana_folder="demo"}'
    alert = js.SourceAlert(
        fingerprint=fingerprint, status="firing", values=(("A", "1"),), starts_at=None,
    )
    return js.SourceRecord(
        source_group=js.source_group_digest(group_key), alerts=(alert,),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )


# --- Refusal summary builders (mirroring journal_ingress's own shape) -------


def _member_sort_key(member: tuple[str, str]) -> tuple[bool, str]:
    return (member[1] != "resolved", member[0])


def no_group_summary(code: str, *, body_bytes: int = 8, body_digest: str = "b" * 64) -> dict:
    return {
        "alerts": None, "body_bytes": body_bytes, "body_digest": body_digest, "code": code,
        "members": (), "members_omitted": 0, "refused_group": None, "resolved": None,
        "source_group": None,
    }


def too_large_summary(declared_length: int = 300_000) -> dict:
    return {
        "alerts": None, "body_bytes": declared_length, "body_digest": None,
        "code": "ingress_too_large", "members": (), "members_omitted": 0, "refused_group": None,
        "resolved": None, "source_group": None,
    }


def group_unsupported_summary(
    *, refused_group: str = "c" * 64, body_bytes: int = 40, body_digest: str = "b" * 64,
) -> dict:
    # Phase 1 (member shape) already ran by the time the group key is found
    # unsupported (journal_ingress phase 2), so this carries real members,
    # unlike the no-group codes.
    members = (("m000", "firing"),)
    return {
        "alerts": 1, "body_bytes": body_bytes, "body_digest": body_digest,
        "code": "ingress_group_key_unsupported", "members": members, "members_omitted": 0,
        "refused_group": refused_group, "resolved": 0, "source_group": None,
    }


def member_summary(
    code: str, members: list[tuple[str, str]], *, alerts: int | None = None,
    resolved: int | None = None, source_group: str = "d" * 64, body_bytes: int = 200,
    body_digest: str = "e" * 64, members_omitted: int = 0,
) -> dict:
    ordered = sorted(members, key=_member_sort_key)
    if alerts is None:
        alerts = len(ordered) + members_omitted
    if resolved is None:
        resolved = sum(1 for _fp, status in ordered if status == "resolved")
    return {
        "alerts": alerts, "body_bytes": body_bytes, "body_digest": body_digest, "code": code,
        "members": tuple(ordered), "members_omitted": members_omitted, "refused_group": None,
        "resolved": resolved, "source_group": source_group,
    }


def resolved_group_unsupported_summary(*, refused_group: str, body_bytes: int = 40) -> dict:
    """Like ``group_unsupported_summary``, but with a Resolved member, so it
    counts toward the reserved 64 (not the unreserved 192)."""
    members = (("m000", "resolved"),)
    return {
        "alerts": 1, "body_bytes": body_bytes, "body_digest": "b" * 64,
        "code": "ingress_group_key_unsupported", "members": members, "members_omitted": 0,
        "refused_group": refused_group, "resolved": 1, "source_group": None,
    }


def too_many_alerts_summary(n_firing: int = 32, n_resolved: int = 1) -> dict:
    resolved_members = [(f"r{i:03d}", "resolved") for i in range(n_resolved)]
    firing_members = [(f"a{i:03d}", "firing") for i in range(n_firing)]
    ordered = sorted(resolved_members + firing_members, key=_member_sort_key)
    listed = tuple(ordered[:32])
    return {
        "alerts": len(ordered), "body_bytes": 9_000, "body_digest": "d" * 64,
        "code": "ingress_too_many_alerts", "members": listed,
        "members_omitted": len(ordered) - len(listed), "refused_group": None,
        "resolved": n_resolved, "source_group": "f" * 64,
    }


def operator_action_data(
    *, since_commit_seq: int = 2, inspected_commit_seq: int = 1, inspected_event_seq: int = 1,
    inspected_digest: str = "a" * 64, pending_digest: str = "b" * 64, operator: str = "alice",
    reason: str = "restart-inspected",
) -> dict:
    return {
        "action": "resume", "rule": jr.RESUME_RULE, "hold": "restart_recovery",
        "since_commit_seq": since_commit_seq,
        "inspected": {
            "commit_seq": inspected_commit_seq, "event_seq": inspected_event_seq,
            "record_digest": inspected_digest,
        },
        "pending_digest": pending_digest, "operator": operator, "reason": reason,
    }


def _independent_body(envelope: dict) -> bytes:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _independent_record_digest(body: bytes) -> str:
    return hashlib.sha256(b"rj.record.v1\x00" + body).hexdigest()


def _independent_tagged_digest(tag: str, value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(tag.encode("ascii") + b"\x00" + encoded.encode("ascii")).hexdigest()


# --- A pure commit-history harness (mirrors test_journal_reducer.py's Journal)


class PureJournal:
    """Mints sequential IDs/stamps and always runs the live path's own
    ``verify_commit``/``apply_delta`` pair before mutating the projection --
    exactly what the shell does before it ever writes anything. No store.
    """

    def __init__(self, bounds: jrd.JournalBounds | None = None, *, boot_id: str = BOOT_A) -> None:
        self.projection = jrd.new_projection()
        self.history: list[jr.Record] = []
        self._boot_id = boot_id
        self._wall = WALL_A
        self._mono = 0
        # A per-label counter, not one shared counter: an admission's minted
        # IDs must not shift just because unrelated refusals happened first
        # (a real id_factory mints uncorrelated random UUIDs).
        self._counters: dict[str, int] = {}
        genesis = jrd.plan_genesis(
            journal_uuid=JOURNAL_UUID, bounds=bounds or jrd.DEFAULT_BOUNDS,
            event_id=self._next_id("genesis"), stamp=self._stamp(),
        )
        self._commit(genesis)

    def _next_id(self, label: str) -> str:
        self._counters[label] = self._counters.get(label, 0) + 1
        return f"{label}-{self._counters[label]:04d}"

    def _stamp(self) -> jr.Stamp:
        self._mono += 1
        return stamp(boot_id=self._boot_id, wall_time=self._wall, mono_us=self._mono)

    def _commit(self, plan: jrd.Plan) -> dict:
        delta = jrd.verify_commit(self.projection, plan.records)
        jrd.apply_delta(self.projection, delta)
        self.history.extend(plan.records)
        return dict(plan.outcome)

    def admit(self, src: js.SourceRecord) -> dict:
        admission_id = self._next_id("adm")
        plan = jrd.plan_admission(
            self.projection, src, admission_id=admission_id,
            dedupe_event_id=self._next_id("ded"), stamp=self._stamp(),
        )
        if isinstance(plan, jrd.CapacityRefusal):
            return {"refusal": plan}
        outcome = self._commit(plan)
        outcome["admission_id"] = admission_id
        return outcome

    def hold_capacity(self, refusal: jrd.CapacityRefusal, src: js.SourceRecord) -> dict | None:
        """The shell's own follow-up to a capacity refusal: the first per code
        commits a ``capacity_hold``; later ones (``None`` plan) write nothing."""
        plan = jrd.plan_capacity_hold(
            self.projection, refusal, event_id=self._next_id("cap"), stamp=self._stamp(),
            refused_source_digest=js.source_digest(src),
        )
        if plan is None:
            return None
        assert isinstance(plan, jrd.Plan)
        return self._commit(plan)

    def restart(self, *, boot_id: str, wall_time: str, wal_found=None) -> dict:
        self._boot_id = boot_id
        self._wall = wall_time
        self._mono = 0
        plan = jrd.plan_restart(
            self.projection, event_id=self._next_id("restart"), stamp=self._stamp(),
            anchor_lag=0, wal_found=wal_found,
        )
        assert isinstance(plan, jrd.Plan)
        return self._commit(plan)

    def refuse(self, summary: dict):
        plan = jrd.plan_ingress_refusal(
            self.projection, summary, event_id=self._next_id("refuse"), stamp=self._stamp(),
        )
        if isinstance(plan, jrd.RefusalNotRecorded):
            return plan
        return self._commit(plan)

    def resume(self, *, operator: str = "alice", reason: str = "restart-inspected") -> dict:
        plan = jrd.plan_operator_resume(
            self.projection, event_id=self._next_id("resume"), stamp=self._stamp(),
            operator=operator, reason=reason,
        )
        if isinstance(plan, jrd.CapacityRefusal):
            return {"refusal": plan}
        return self._commit(plan)


# === A1: known-answer digests for ingress_refusal and operator_action ======


def test_a1_known_answer_ingress_refusal_and_operator_action_digests():
    genesis = jr.seal(genesis_draft(), position(), stamp())
    summary = too_many_alerts_summary()
    refusal_key = jrd.refusal_key(summary)
    refusal_draft = jr.Draft(
        event_id="33333333-3333-3333-3333-333333333333", event_type="ingress_refusal",
        actor="receiver", ids={},
        data={
            "rule": jr.REFUSAL_RULE, "summary": summary, "refusal_key": refusal_key,
            "refusal_seq": 1,
        },
    )
    refusal = jr.seal(
        refusal_draft,
        position(event_seq=2, commit_seq=2, prev_record_digest=genesis.record_digest),
        stamp(),
    )
    envelope = {
        "schema_version": jr.SCHEMA_VERSION, "journal_generation": 1,
        "event_id": refusal.event_id, "event_seq": 2, "commit_seq": 2, "commit_index": 0,
        "commit_size": 1, "event_type": "ingress_refusal", "actor": "receiver",
        "boot_id": refusal.stamp.boot_id, "wall_time": refusal.stamp.wall_time,
        "mono_us": refusal.stamp.mono_us, "ids": {}, "data": jr.thaw(refusal_draft.data),
        "prev_record_digest": genesis.record_digest,
    }
    independent_body = _independent_body(envelope)
    assert refusal.body == independent_body
    assert refusal.record_digest == _independent_record_digest(independent_body)
    content_payload = {
        "schema_version": jr.SCHEMA_VERSION, "journal_generation": 1, "event_id": refusal.event_id,
        "event_type": "ingress_refusal", "actor": "receiver", "ids": {},
        "data": jr.thaw(refusal_draft.data),
    }
    expected_content_digest = _independent_tagged_digest("rj.content.v1", content_payload)
    assert jr.content_digest(refusal) == expected_content_digest
    assert jr.open_record(refusal.body) == refusal

    operator_data = operator_action_data(
        since_commit_seq=2, inspected_commit_seq=2, inspected_event_seq=2,
        inspected_digest=refusal.record_digest, pending_digest="0" * 64,
    )
    operator_draft = jr.Draft(
        event_id="44444444-4444-4444-4444-444444444444", event_type="operator_action",
        actor="operator", ids={}, data=operator_data,
    )
    action = jr.seal(
        operator_draft,
        position(event_seq=3, commit_seq=3, prev_record_digest=refusal.record_digest),
        stamp(),
    )
    envelope2 = {
        "schema_version": jr.SCHEMA_VERSION, "journal_generation": 1,
        "event_id": action.event_id, "event_seq": 3, "commit_seq": 3, "commit_index": 0,
        "commit_size": 1, "event_type": "operator_action", "actor": "operator",
        "boot_id": action.stamp.boot_id, "wall_time": action.stamp.wall_time,
        "mono_us": action.stamp.mono_us, "ids": {}, "data": jr.thaw(operator_draft.data),
        "prev_record_digest": refusal.record_digest,
    }
    independent_body2 = _independent_body(envelope2)
    assert action.body == independent_body2
    assert action.record_digest == _independent_record_digest(independent_body2)
    assert jr.open_record(action.body) == action


def test_a1_refusal_key_is_tagged_digest_directly():
    summary = too_many_alerts_summary()
    payload = {
        field: summary[field] for field in (
            "alerts", "code", "members", "members_omitted", "refused_group", "resolved",
            "source_group",
        )
    }
    assert jrd.refusal_key(summary) == tagged_digest("rj.refusal-key.v1", payload)


# === A2: per-(type, actor) table; SCHEMA_VERSIONS; check-position pin ======


_ACTORS_UNDER_TEST = ("receiver", "spawner", "forwarder", "operator")


@pytest.mark.parametrize("event_type", jr.REGISTERED_EVENT_TYPES)
@pytest.mark.parametrize("actor", _ACTORS_UNDER_TEST)
def test_a2_actor_table_accepted_iff_matches_type_actors(event_type, actor):
    accepted = actor == jr.TYPE_ACTORS[(event_type, 1)]
    envelope = _envelope_for(event_type, actor=actor)
    if accepted:
        jr._validate_envelope(dict(envelope))
    else:
        expect_record("record_field", jr._validate_envelope, dict(envelope))


def test_a2_unknown_type_with_actor_operator_is_unsupported():
    envelope = _envelope_for("journal_genesis", actor="operator")
    envelope["event_type"] = "not_a_real_type"
    expect_record("record_unsupported", jr._validate_envelope, dict(envelope))


def test_a2_event_types_record_class_and_registries_are_exact():
    assert jr.EVENT_TYPES == (
        "journal_genesis", "restart_recovery", "capacity_hold", "admission", "dedupe_decision",
    )
    assert set(jr.RECORD_CLASS) == set(jr.REGISTERED_EVENT_TYPES)
    expected_keys = {(t, 1) for t in jr.REGISTERED_EVENT_TYPES}
    assert set(jr.TYPE_ACTORS) == expected_keys
    assert set(jr._TYPE_VALIDATORS) == expected_keys
    assert jr.SCHEMA_VERSIONS == {1}
    assert {t for t, _v in jr.TYPE_ACTORS if jr.TYPE_ACTORS[(t, 1)] == "receiver"} == set(
        jr.EVENT_TYPES + ("ingress_refusal",)
    )
    assert jr.TYPE_ACTORS[("operator_action", 1)] == "operator"


@pytest.mark.parametrize("event_type", jr.REGISTERED_EVENT_TYPES)
@pytest.mark.parametrize("bad_version", [0, 2, 2**53 - 1])
def test_a2_bad_schema_version_is_unsupported_before_generation_check(event_type, bad_version):
    envelope = _envelope_for(event_type, actor=jr.TYPE_ACTORS[(event_type, 1)])
    envelope["schema_version"] = bad_version
    envelope["journal_generation"] = "not-an-int"  # would give record_type if ever reached
    expect_record("record_unsupported", jr._validate_envelope, dict(envelope))


def _envelope_for(event_type: str, *, actor: str) -> dict:
    """A structurally-valid envelope for ``event_type``, ``ids``/``data``
    aside, used only to probe the four registry-driven predicates."""
    ids: dict = {}
    event_id = BOOT_A
    if event_type == "admission":
        ids = {"admission_id": "33333333-3333-3333-3333-333333333333"}
        event_id = ids["admission_id"]  # _validate_admission requires event_id == admission_id
    elif event_type == "dedupe_decision":
        ids = {"admission_id": "33333333-3333-3333-3333-333333333333"}
    data = _data_for(event_type)
    return {
        "schema_version": 1, "journal_generation": 1, "event_id": event_id, "event_seq": 1,
        "commit_seq": 1, "commit_index": 0, "commit_size": 1, "event_type": event_type,
        "actor": actor, "boot_id": BOOT_A, "wall_time": WALL_A, "mono_us": 0, "ids": ids,
        "data": data, "prev_record_digest": jr.ZERO_DIGEST,
    }


def _data_for(event_type: str) -> dict:
    if event_type == "journal_genesis":
        return {"format": "rj.journal.v1", "journal_uuid": JOURNAL_UUID, "bounds": GENESIS_BOUNDS}
    if event_type == "restart_recovery":
        return {
            "previous_boot_id": BOOT_A,
            "recovered": {"commit_seq": 1, "event_seq": 1, "record_digest": jr.ZERO_DIGEST},
            "anchor_lag": 0, "wal_found": None, "dispatch_hold": "restart_recovery",
            "prior_leases": "invalid",
        }
    if event_type == "capacity_hold":
        return {
            "code": "capacity_admissions", "limit": 1, "observed": 1, "requested": 1,
            "refused_source_digest": "a" * 64, "action": "set",
        }
    if event_type == "admission":
        source = sample_source()
        return {
            "arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
            "source": js.source_to_json(source), "source_digest": js.source_digest(source),
        }
    if event_type == "dedupe_decision":
        source = sample_source()
        key = js.dedupe_key(source)
        return {
            "rule": "latest-admitted-v1", "result": "admitted",
            "source_group": source.source_group, "dedupe_key": key, "baseline_before": None,
            "baseline_after": {
                "admission_id": "33333333-3333-3333-3333-333333333333", "complete": True,
                "dedupe_key": key,
            },
            "superseded": (), "pending_count_after": 1,
        }
    if event_type == "ingress_refusal":
        summary = no_group_summary("ingress_json_invalid")
        return {
            "rule": jr.REFUSAL_RULE, "summary": summary, "refusal_key": jrd.refusal_key(summary),
            "refusal_seq": 1,
        }
    return operator_action_data()


# === A3: validator rejections through seal and decode_record ================


def _seal_refusal(**data_overrides):
    summary = data_overrides.pop("summary", None)
    if summary is None:
        summary = no_group_summary("ingress_json_invalid")
    # An overriding refusal_key spares a forged summary the key computation,
    # which could itself refuse to encode it before the validator runs.
    key = data_overrides.pop("refusal_key", None) or jrd.refusal_key(summary)
    data = {"rule": jr.REFUSAL_RULE, "summary": summary, "refusal_key": key, "refusal_seq": 1}
    data.update(data_overrides)
    draft = jr.Draft(
        event_id="33333333-3333-3333-3333-333333333333", event_type="ingress_refusal",
        actor="receiver", ids={}, data=data,
    )
    return jr.seal(draft, position(), stamp())


def _seal_operator_action(**data_overrides):
    data = operator_action_data()
    data.update(data_overrides)
    draft = jr.Draft(
        event_id="44444444-4444-4444-4444-444444444444", event_type="operator_action",
        actor="operator", ids={}, data=data,
    )
    return jr.seal(draft, position(), stamp())


def test_a3_ingress_refusal_missing_key_gives_record_field():
    summary = no_group_summary("ingress_json_invalid")
    data = {
        "rule": jr.REFUSAL_RULE, "summary": summary, "refusal_key": jrd.refusal_key(summary),
        "refusal_seq": 1,
    }
    del data["refusal_seq"]
    draft = jr.Draft(
        event_id="33333333-3333-3333-3333-333333333333", event_type="ingress_refusal",
        actor="receiver", ids={}, data=data,
    )
    expect_record("record_field", jr.seal, draft, position(), stamp())


def test_a3_ingress_refusal_extra_key_gives_record_field():
    summary = no_group_summary("ingress_json_invalid")
    data = {
        "rule": jr.REFUSAL_RULE, "summary": summary, "refusal_key": jrd.refusal_key(summary),
        "refusal_seq": 1, "extra": "x",
    }
    draft = jr.Draft(
        event_id="33333333-3333-3333-3333-333333333333", event_type="ingress_refusal",
        actor="receiver", ids={}, data=data,
    )
    expect_record("record_field", jr.seal, draft, position(), stamp())


def test_a3_ingress_refusal_unknown_rule_is_unsupported_even_with_other_keys_wrong():
    expect_record(
        "record_unsupported", _seal_refusal, rule="first-per-membership-v2", refusal_seq=99999,
    )


def test_a3_ingress_refusal_check_order_rule_before_key_set():
    # M31: the rule literal is checked before the exact key set (plan check
    # order, critic 4/R2), so an extra or missing key never masks a future
    # rule string as merely malformed. The test above only changes a value;
    # this one changes the key set itself, which the check-order swap flips
    # from record_unsupported to record_field.
    expect_record(
        "record_unsupported", _seal_refusal, rule="first-per-membership-v2", note="x",
    )
    data = _data_for("ingress_refusal")
    data["rule"] = "first-per-membership-v2"
    del data["refusal_seq"]
    expect_record("record_unsupported", _seal_data, "ingress_refusal", data)
    expect_record("record_unsupported", _decode_data, "ingress_refusal", data)


@pytest.mark.parametrize("bad_seq", [0, 257])
def test_a3_refusal_seq_bounds_give_record_field(bad_seq):
    expect_record("record_field", _seal_refusal, refusal_seq=bad_seq)


def test_a3_refusal_seq_string_gives_record_type():
    expect_record("record_type", _seal_refusal, refusal_seq="1")


def test_a3_refusal_summary_members_as_lists_is_record_field():
    # The strict checker accepts tuples only; the normalizer is what accepts lists.
    summary = too_many_alerts_summary()
    summary = dict(summary, members=[list(m) for m in summary["members"]])
    expect_record("record_field", _seal_refusal, summary=summary)


def test_a3_refusal_summary_over_the_byte_bound_is_record_field(monkeypatch):
    # A legitimately-shaped summary (32 members at the 64-byte fingerprint
    # ceiling) never reaches 4,096 bytes -- confirmed at about 2.8 KiB. The
    # bound is exercised directly by lowering it, which also pins the check
    # order: group/member shape is checked first, the byte bound last.
    summary = too_many_alerts_summary(n_firing=32, n_resolved=1)
    monkeypatch.setattr(jr, "_MAX_REFUSAL_JSON_BYTES", 10)
    expect_record("record_field", _seal_refusal, summary=summary)


def test_a3_refusal_summary_byte_bound_is_inclusive(monkeypatch):
    summary = too_many_alerts_summary()
    size = len(canonical_json(summary, ascii_only=True))
    monkeypatch.setattr(jr, "_MAX_REFUSAL_JSON_BYTES", size)
    jr._check_refusal_summary(summary)
    _seal_refusal(summary=summary)
    monkeypatch.setattr(jr, "_MAX_REFUSAL_JSON_BYTES", size - 1)
    expect_record("record_field", jr._check_refusal_summary, summary)
    expect_record("record_field", _seal_refusal, summary=summary)


class _PosingInt(int):
    """An int subclass posing as an exact int."""


def _refusal_data(refusal: ji.IngressRefusal) -> dict:
    """``refusal`` as summary data, bypassing ``refusal_to_json``'s own checks."""
    return {field.name: getattr(refusal, field.name) for field in dataclasses.fields(refusal)}


def _forged(code: str, **changes) -> ji.IngressRefusal:
    """A valid one-member refusal of ``code`` with ``changes`` applied."""
    base = ji.IngressRefusal(
        code=code, body_bytes=1_000, body_digest="0" * 64, source_group="a" * 64,
        refused_group=None, alerts=1, resolved=0, members=(("f" * 16, "firing"),),
        members_omitted=0,
    )
    return dataclasses.replace(base, **changes)


_NO_GROUP = {"source_group": None, "alerts": None, "resolved": None, "members": ()}
_THIRTY_TWO_FIRING = tuple((f"{i:064x}", "firing") for i in range(32))

# The unit-16 gap-4 cases (test_journal_ingress.py test_gap4_*), then exact-int
# and cross-field rules no unit-16 row isolates on its own.
_MORE_FORGED_REFUSALS = [
    ("gap4_group_key_unsupported_with_source_group", _forged("ingress_group_key_unsupported")),
    ("gap4_member_status_pending", _forged(
        "ingress_ref_id_unsupported", members=(("f" * 16, "pending"),),
    )),
    ("gap4_oversized_body_bytes_on_a_phase1_code", _forged(
        "ingress_fingerprint", body_bytes=300_000, **dict(_NO_GROUP, source_group="a" * 64),
    )),
    ("gap4_phase1_code_with_no_group", _forged("ingress_fingerprint", **_NO_GROUP)),
    ("gap4_ref_id_unsupported_with_only_refused_group", _forged(
        "ingress_ref_id_unsupported", source_group=None, refused_group="b" * 64,
    )),
    ("gap4_record_too_large_with_only_refused_group", _forged(
        "ingress_record_too_large", source_group=None, refused_group="c" * 64, alerts=10,
        members=_THIRTY_TWO_FIRING[:10],
    )),
    ("gap4_too_many_alerts_with_alerts_of_one", _forged("ingress_too_many_alerts")),
    ("gap4_too_many_values_with_alerts_of_forty", _forged(
        "ingress_too_many_values", alerts=40, members=_THIRTY_TWO_FIRING, members_omitted=8,
    )),
    ("members_omitted_false_without_members", _forged(
        "ingress_json_invalid", members_omitted=False, **_NO_GROUP,
    )),
    ("members_omitted_true_on_33_alerts", dataclasses.replace(
        ji.IngressRefusal(**too_many_alerts_summary()), members_omitted=True,
    )),
    ("members_omitted_int_subclass", dataclasses.replace(
        _valid_member_refusal(), members_omitted=_PosingInt(8),
    )),
    ("alerts_true", _forged("ingress_ref_id_unsupported", alerts=True)),
    ("resolved_false", _forged("ingress_ref_id_unsupported", resolved=False)),
    ("body_bytes_false", _forged("ingress_ref_id_unsupported", body_bytes=False)),
    ("body_bytes_int_subclass", _forged("ingress_ref_id_unsupported", body_bytes=_PosingInt(1))),
    ("one_fingerprint_both_resolved_and_firing", _forged(
        "ingress_ref_id_unsupported", alerts=2, resolved=1,
        members=(("f" * 16, "resolved"), ("f" * 16, "firing")),
    )),
    ("divergence_with_alerts_and_only_refused_group", _forged(
        "ingress_divergence", source_group=None, refused_group="b" * 64,
    )),
    # The numeric boundaries, one past each on the refused side.
    ("too_large_at_the_body_bound", dataclasses.replace(
        ji.oversize_refusal(262_145), body_bytes=262_144,
    )),
    ("json_invalid_past_the_body_bound", _forged(
        "ingress_json_invalid", body_bytes=262_145, **_NO_GROUP,
    )),
    ("too_many_alerts_with_exactly_32", _forged(
        "ingress_too_many_alerts", alerts=32, members=_THIRTY_TWO_FIRING,
    )),
    # Unit-17a gap-agent additions (mutation survivors M07/M09/M13-M15/M18/M19):
    # each isolates one cross-field rule the checker/normalizer port from
    # journal_ingress, using only value changes no earlier row exercises.
    ("group_key_unsupported_with_both_groups", _forged(
        "ingress_group_key_unsupported", refused_group="b" * 64,
    )),
    ("no_group_with_members_omitted_one", _forged(
        "ingress_json_invalid", members_omitted=1, **_NO_GROUP,
    )),
    ("too_many_values_at_alerts_33", _forged(
        "ingress_too_many_values", alerts=33, members=_THIRTY_TWO_FIRING, members_omitted=1,
    )),
    ("record_too_large_at_alerts_33", _forged(
        "ingress_record_too_large", alerts=33, members=_THIRTY_TWO_FIRING, members_omitted=1,
    )),
    ("divergence_at_alerts_33", _forged(
        "ingress_divergence", alerts=33, members=_THIRTY_TWO_FIRING, members_omitted=1,
    )),
    ("resolved_exceeds_alerts_all_listed_resolved", _forged(
        "ingress_ref_id_unsupported", alerts=2, resolved=3,
        members=(("f" * 16, "resolved"), ("g" * 16, "resolved")),
    )),
    ("fewer_members_than_min_alerts_32", _forged(
        "ingress_ref_id_unsupported", alerts=3,
        members=(("f" * 16, "firing"), ("g" * 16, "firing")), members_omitted=1,
    )),
    ("resolved_claimed_but_none_listed", _forged("ingress_ref_id_unsupported", resolved=1)),
    ("fingerprint_with_space_suffix", _forged(
        "ingress_ref_id_unsupported", members=(("ffff x", "firing"),),
    )),
]
_ALL_FORGED_REFUSALS = [
    (name, mutate(_valid_member_refusal())) for name, mutate in FORGED_REFUSALS
] + _MORE_FORGED_REFUSALS


def test_a3_forgery_baselines_are_valid_at_every_layer():
    for refusal in (_valid_member_refusal(), _forged("ingress_ref_id_unsupported")):
        summary = ji.refusal_to_json(refusal)
        jr._check_refusal_summary(jr.refusal_summary_data(summary))
        _seal_refusal(summary=_refusal_data(refusal))


@pytest.mark.parametrize(
    "code", ["ingress_too_many_values", "ingress_record_too_large", "ingress_divergence"],
)
def test_a3_alert_count_boundary_of_32_is_still_accepted(code):
    # Companion control for the 33-alert boundary forgeries above (M13): 32
    # alerts is the legitimate boundary these secondary codes can still carry.
    refusal = _forged(code, alerts=32, members=_THIRTY_TWO_FIRING, members_omitted=0)
    summary = ji.refusal_to_json(refusal)
    jr._check_refusal_summary(jr.refusal_summary_data(summary))


@pytest.mark.parametrize(
    "name,forged", _ALL_FORGED_REFUSALS, ids=[name for name, _f in _ALL_FORGED_REFUSALS],
)
def test_a3_unit16_forgeries_as_data_are_record_field_at_every_layer(name, forged):
    with pytest.raises(ji.IngressError) as info:
        ji.refusal_to_json(forged)
    assert info.value.args == ("ingress_argument",)
    data = _refusal_data(forged)
    expect_record("record_field", jr._check_refusal_summary, data)
    listy = dict(data, members=[list(member) for member in data["members"]])
    expect_record("record_field", jr.refusal_summary_data, listy)
    expect_record("record_field", _seal_refusal, summary=data, refusal_key="0" * 64)
    envelope = _envelope_for("ingress_refusal", actor="receiver")
    envelope["data"] = dict(envelope["data"], summary=data, refusal_key="0" * 64)
    body = None
    try:
        body = canonical_json(envelope, ascii_only=True)
    except JSONPolicyError:
        pass  # the encoder itself refuses it (an int subclass, or past 2^53)
    if body is not None:
        expect_record("record_field", jr.open_record, body)


@pytest.mark.parametrize("label,mutate", [
    ("unknown code", lambda s: dict(s, code="nope")),
    ("members_omitted wrong", lambda s: dict(s, members_omitted=s["members_omitted"] + 1)),
    ("duplicate fingerprint", lambda s: dict(s, members=(s["members"][0], s["members"][0]))),
    ("both groups set", lambda s: dict(s, refused_group="0" * 64)),
    ("bad body_digest length", lambda s: dict(s, body_digest="x" * 10)),
    ("resolved greater than alerts", lambda s: dict(s, resolved=s["alerts"] + 1)),
    ("unsorted members", lambda s: dict(s, members=tuple(reversed(s["members"])))),
])
def test_a3_summary_forgeries_translated_to_data_are_record_field(label, mutate):
    base = too_many_alerts_summary()
    forged = mutate(base)
    expect_record("record_field", _seal_refusal, summary=forged)


def test_a3_operator_action_forgeries():
    expect_record("record_field", _seal_operator_action, action="cancel")
    # operator/reason are data fields in the ID grammar: record_field, as the
    # plan's check order says, not validate_id's record_id.
    expect_record("record_field", _seal_operator_action, operator="a" * 129)
    expect_record("record_field", _seal_operator_action, reason="has space")
    expect_record("record_field", _seal_operator_action, operator=7)
    expect_record("record_field", _seal_operator_action, reason=None)
    expect_record("record_field", _seal_operator_action, since_commit_seq=1)
    expect_record("record_type", _seal_operator_action, since_commit_seq=True)
    base = operator_action_data()
    inspected_extra = dict(base["inspected"], extra="x")
    expect_record("record_field", _seal_operator_action, inspected=inspected_extra)
    inspected_missing = {"commit_seq": 1, "event_seq": 1}
    expect_record("record_field", _seal_operator_action, inspected=inspected_missing)
    inspected_zero = dict(base["inspected"], commit_seq=0)
    expect_record("record_field", _seal_operator_action, inspected=inspected_zero)
    inspected_huge = dict(base["inspected"], commit_seq=2**53)
    expect_record("record_field", _seal_operator_action, inspected=inspected_huge)
    inspected_short_digest = dict(base["inspected"], record_digest="a" * 63)
    expect_record("record_field", _seal_operator_action, inspected=inspected_short_digest)


def test_a3_operator_action_inspected_event_seq_bounds():
    # M37: inspected.event_seq is bounded 1..2^53-1, the same as commit_seq
    # above; the existing forgeries never exercise event_seq's own bounds.
    base = operator_action_data()
    inspected_zero = dict(base["inspected"], event_seq=0)
    expect_record("record_field", _seal_operator_action, inspected=inspected_zero)
    expect_record(
        "record_field", _decode_data, "operator_action",
        dict(operator_action_data(), inspected=inspected_zero),
    )
    inspected_huge = dict(base["inspected"], event_seq=2**53)
    expect_record("record_field", _seal_operator_action, inspected=inspected_huge)


def test_a3_operator_action_unknown_rule_is_unsupported():
    expect_record("record_unsupported", _seal_operator_action, rule="resume-at-open-v2")


def test_a3_operator_action_check_order_rule_before_key_set():
    # M40: mirrors M31 for operator_action's rule/key-set check order.
    expect_record(
        "record_unsupported", _seal_operator_action, rule="resume-at-open-v2", note="x",
    )
    data = operator_action_data()
    data["rule"] = "resume-at-open-v2"
    del data["inspected"]
    expect_record("record_unsupported", _seal_data, "operator_action", data)
    expect_record("record_unsupported", _decode_data, "operator_action", data)


@pytest.mark.parametrize("key,value", [("operator", "a" * 129), ("reason", "has space")])
def test_a3_operator_action_forgeries_through_decode_record(key, value):
    envelope = _envelope_for("operator_action", actor="operator")
    jr.open_record(canonical_json(envelope, ascii_only=True))  # the unmutated control decodes
    envelope["data"] = dict(envelope["data"], **{key: value})
    expect_record("record_field", jr.open_record, canonical_json(envelope, ascii_only=True))


def _seal_data(event_type: str, data: dict) -> jr.Record:
    draft = jr.Draft(
        event_id="44444444-4444-4444-4444-444444444444", event_type=event_type,
        actor=jr.TYPE_ACTORS[(event_type, 1)], ids={}, data=data,
    )
    return jr.seal(draft, position(), stamp())


def _decode_data(event_type: str, data: dict) -> jr.Record:
    envelope = _envelope_for(event_type, actor=jr.TYPE_ACTORS[(event_type, 1)])
    envelope["data"] = data
    return jr.open_record(canonical_json(envelope, ascii_only=True))


_DATA_KEY_CASES = [
    (event_type, key)
    for event_type, keys in (
        ("ingress_refusal", jr._INGRESS_REFUSAL_DATA_KEYS),
        ("operator_action", jr._OPERATOR_ACTION_DATA_KEYS),
    )
    for key in [*sorted(keys), None]  # None: one extra key instead of a missing one
]


@pytest.mark.parametrize("event_type,key", _DATA_KEY_CASES)
def test_a3_each_missing_or_extra_data_key_is_record_field_through_seal_and_decode(
    event_type, key,
):
    data = _data_for(event_type)
    _seal_data(event_type, data)  # the unmutated control passes both layers
    _decode_data(event_type, data)
    if key is None:
        data["note"] = "free text: the caller said anything"
    else:
        del data[key]
    expect_record("record_field", _seal_data, event_type, data)
    expect_record("record_field", _decode_data, event_type, data)


_UNRESUMABLE_HOLDS = sorted(set(jr.DISPATCH_HOLD_CODES) - set(jr.RESUMABLE_HOLDS))


@pytest.mark.parametrize("hold", [*_UNRESUMABLE_HOLDS, "restart_recovery_x"])
def test_a3_operator_action_hold_other_than_restart_recovery_is_record_field(hold):
    assert jr.RESUMABLE_HOLDS == ("restart_recovery",)
    expect_record("record_field", _seal_operator_action, hold=hold)
    data = dict(operator_action_data(), hold=hold)
    expect_record("record_field", _decode_data, "operator_action", data)


@pytest.mark.parametrize("bad", ["0" * 63, "Z" * 64, 7])
def test_a3_refusal_key_must_be_hex64_through_seal_and_decode(bad):
    expect_record("record_field", _seal_refusal, refusal_key=bad)
    data = dict(_data_for("ingress_refusal"), refusal_key=bad)
    expect_record("record_field", _decode_data, "ingress_refusal", data)


@pytest.mark.parametrize("bad", ["a" * 63, "A" * 64, None])
def test_a3_pending_digest_must_be_hex64_through_seal_and_decode(bad):
    expect_record("record_field", _seal_operator_action, pending_digest=bad)
    data = dict(operator_action_data(), pending_digest=bad)
    expect_record("record_field", _decode_data, "operator_action", data)


# Member-less, so neither the member check nor (with one group) the group
# check can reject it: only the closed v1 code set does.
_OUT_OF_SET_CODE_CASES = [
    (code, groups)
    for code in ("ingress_future_code", "capacity_pending")
    for groups in ({"source_group": "a" * 64}, {"refused_group": "b" * 64}, {})
]


@pytest.mark.parametrize("code,groups", _OUT_OF_SET_CODE_CASES)
def test_a3_a_code_outside_the_v1_set_is_record_field_at_every_layer(code, groups):
    assert code not in jr.INGRESS_REFUSAL_CODES_V1
    summary = dict(no_group_summary(code, body_bytes=10, body_digest="c" * 64), **groups)
    expect_record("record_field", jr._check_refusal_summary, summary)
    expect_record("record_field", jr.refusal_summary_data, dict(summary, members=[]))
    expect_record("record_field", _seal_refusal, summary=summary, refusal_key="0" * 64)
    data = dict(_data_for("ingress_refusal"), summary=summary, refusal_key="0" * 64)
    expect_record("record_field", _decode_data, "ingress_refusal", data)


# === F3-2: hex64 grammar for source_group/refused_group (residue gap) ======

# 63 chars, 65 chars, uppercase hex, and a non-hex character: the four
# forgery shapes _hex64_ok must reject. A regression here (for example
# checking only length, or accepting uppercase) would let caller bytes into
# the journal through a field the checker treats as an opaque group digest.
_BAD_HEX64_GROUPS = ["a" * 63, "b" * 65, "C" * 64, "g" * 64]


def _listy(summary: dict) -> dict:
    return dict(summary, members=[list(member) for member in summary["members"]])


@pytest.mark.parametrize("bad", _BAD_HEX64_GROUPS)
def test_f3_2_source_group_must_be_hex64_at_every_layer(bad):
    summary = member_summary("ingress_ref_id_unsupported", [("m000", "firing")], source_group=bad)
    expect_record("record_field", jr._check_refusal_summary, summary)
    expect_record("record_field", jr.refusal_summary_data, _listy(summary))
    expect_record("record_field", _seal_refusal, summary=summary, refusal_key="0" * 64)
    data = dict(_data_for("ingress_refusal"), summary=summary, refusal_key="0" * 64)
    expect_record("record_field", _decode_data, "ingress_refusal", data)


@pytest.mark.parametrize("bad", _BAD_HEX64_GROUPS)
def test_f3_2_refused_group_must_be_hex64_at_every_layer(bad):
    summary = group_unsupported_summary(refused_group=bad)
    expect_record("record_field", jr._check_refusal_summary, summary)
    expect_record("record_field", jr.refusal_summary_data, _listy(summary))
    expect_record("record_field", _seal_refusal, summary=summary, refusal_key="0" * 64)
    data = dict(_data_for("ingress_refusal"), summary=summary, refusal_key="0" * 64)
    expect_record("record_field", _decode_data, "ingress_refusal", data)


# === A4: refusal summary parity with the corpus (imports A4's three helpers) =


CAPTURE_CASES = list(capture_rows())


def _refusals_for_every_code() -> list[ji.IngressRefusal]:
    """Every refusal the corpus and its generators produce. The 115 captures
    all admit, so refusing variants of the first capture, the unit-16 raw
    bodies, both oversize extremes and the unit-16 divergence patches supply
    the rest; together they cover every code."""
    refusals = []
    for _name, _line_no, envelope in CAPTURE_CASES:
        outcome = ji.sanitize_notification(wire(envelope["body"]))
        if outcome.refusal is not None:
            refusals.append(outcome.refusal)
    base = CAPTURE_CASES[0][2]
    alert = base["body"]["alerts"][0]

    def variant(**changes) -> bytes:
        return wire(dict(copy.deepcopy(base["body"]), **changes))

    def alert_variant(**changes) -> bytes:
        return variant(alerts=[dict(copy.deepcopy(alert), **changes)])

    _raw, mixed = grafana_group(base, 40, "firing")
    for member in mixed["alerts"][:3]:
        member["status"] = "resolved"
    raws = [
        b"not json at all", b"5", variant(alerts=5), variant(groupKey=""),
        variant(groupKey="Démo"), variant(truncatedAlerts=-1), variant(message="a\u0000b"),
        variant(alerts=[alert, dict(alert)]), alert_variant(status="pending"),
        alert_variant(fingerprint="bad fingerprint"), alert_variant(values={"A": "not a number"}),
        alert_variant(values={"Query 1": 1}),
        alert_variant(values={f"r{i:02d}": 1 for i in range(65)}),
        variant(alerts=[
            dict(alert, fingerprint=f"{i:064x}", values={"A": 0.123456789012345, "B": 0.2})
            for i in range(24)
        ]),
        grafana_group(base, 33, "firing")[0], grafana_group(base, 40, "resolved")[0], wire(mixed),
    ]
    for raw in raws:
        refusal = ji.sanitize_notification(raw).refusal
        assert refusal is not None
        refusals.append(refusal)
    refusals += [ji.oversize_refusal(262_145), ji.oversize_refusal(2**53 - 1)]
    for target, exception in DIVERGENCE_PATCHES:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                ji, target,
                lambda *a, exception=exception, **k: (_ for _ in ()).throw(exception),
            )
            refusals.append(ji.sanitize_notification(wire(base["body"])).refusal)
    return refusals


def test_a4_every_code_from_the_corpus_and_generators_round_trips():
    refusals = _refusals_for_every_code()
    exercised = set()
    for refusal in refusals:
        summary = ji.refusal_to_json(refusal)
        normalized = jr.refusal_summary_data(summary)
        jr._check_refusal_summary(normalized)  # must not raise
        assert jr.refusal_summary_data(normalized) == normalized
        # The strict checker rejects the raw (list-membered) shape.
        expect_record("record_field", jr._check_refusal_summary, summary)
        exercised.add(refusal.code)
    print(f"\n[A4] summaries={len(refusals)} codes={len(exercised)}")
    assert exercised == set(jr.INGRESS_REFUSAL_CODES_V1)


@pytest.mark.parametrize("n,status", [(33, "firing"), (40, "resolved")])
def test_a4_grafana_group_refusal_summary_round_trips(n, status):
    raw, _body = grafana_group(CAPTURE_CASES[0][2], n, status)
    outcome = ji.sanitize_notification(raw)
    assert outcome.refusal is not None
    summary = ji.refusal_to_json(outcome.refusal)
    normalized = jr.refusal_summary_data(summary)
    jr._check_refusal_summary(normalized)


def _mutated_capture_body(mutate) -> dict:
    base = dict(CAPTURE_CASES[0][2]["body"])
    mutate(base)
    return base


@pytest.mark.parametrize("label,raw", [
    ("malformed json", b"not json at all"),
    ("empty group key", wire(_mutated_capture_body(lambda b: b.update(groupKey="")))),
    ("duplicate fingerprint", wire(_mutated_capture_body(
        lambda b: b.update(alerts=[dict(b["alerts"][0]), dict(b["alerts"][0])]),
    ))),
    ("bad status", wire(_mutated_capture_body(
        lambda b: b.update(alerts=[dict(b["alerts"][0], status="pending")]),
    ))),
])
def test_a4_no_group_and_member_shape_refusals_round_trip(label, raw):
    outcome = ji.sanitize_notification(raw)
    assert outcome.refusal is not None, label
    summary = ji.refusal_to_json(outcome.refusal)
    normalized = jr.refusal_summary_data(summary)
    jr._check_refusal_summary(normalized)  # must not raise
    with pytest.raises(jr.RecordError):
        jr._check_refusal_summary(summary)  # the raw (list-membered) shape


@pytest.mark.parametrize("declared_length", [262_145, 2**53 - 1])
def test_a4_oversize_refusal_summary_round_trips(declared_length):
    refusal = ji.oversize_refusal(declared_length)
    summary = ji.refusal_to_json(refusal)
    normalized = jr.refusal_summary_data(summary)
    jr._check_refusal_summary(normalized)


def test_a4_an_invalid_body_at_exactly_the_body_bound_round_trips():
    refusal = ji.sanitize_notification(b"x" * 262_144).refusal
    assert (refusal.code, refusal.body_bytes) == ("ingress_json_invalid", 262_144)
    normalized = jr.refusal_summary_data(ji.refusal_to_json(refusal))
    jr._check_refusal_summary(normalized)


def test_a4_forged_summaries_fail_both_normalizer_and_checker():
    raw, _body = grafana_group(CAPTURE_CASES[0][2], 33, "firing")
    outcome = ji.sanitize_notification(raw)
    base = outcome.refusal
    forgeries = {
        "unknown code": dataclasses.replace(base, code="nope"),
        "members_omitted wrong": dataclasses.replace(base, members_omitted=0),
        "duplicate fingerprint": dataclasses.replace(
            base, members=(base.members[0], base.members[0]) + base.members[2:],
        ),
        "both groups set": dataclasses.replace(base, refused_group="0" * 64),
        "bad body_digest": dataclasses.replace(base, body_digest="x" * 64),
        "resolved greater than alerts": dataclasses.replace(base, resolved=base.alerts + 1),
        "unsorted members": dataclasses.replace(base, members=tuple(reversed(base.members))),
    }
    for forged in forgeries.values():
        with pytest.raises(ji.IngressError):
            ji.refusal_to_json(forged)  # journal_ingress itself already refuses these
        data = _refusal_data(forged)
        expect_record("record_field", jr._check_refusal_summary, data)
        listy = dict(data, members=[list(member) for member in data["members"]])
        expect_record("record_field", jr.refusal_summary_data, listy)


# === A5: constant parity with journal_ingress and journal_source ===========


def test_a5_ingress_refusal_codes_v1_matches_journal_ingress():
    assert set(jr.INGRESS_REFUSAL_CODES_V1) == ji.INGRESS_REFUSAL_CODES
    assert jr.INGRESS_REFUSAL_CODES_V1 == tuple(sorted(ji.INGRESS_REFUSAL_CODES))


def test_a5_member_and_no_group_codes_match_journal_ingress():
    assert jr._MEMBER_CODES == ji.MEMBER_CODES
    assert jr._NO_GROUP_CODES == ji._NO_GROUP_CODES


def test_a5_statuses_and_bounds_match_journal_source_and_journal_ingress():
    assert jr._ALERT_STATUSES == js.ALERT_STATUSES
    assert jr._MAX_ALERTS == js.MAX_ALERTS
    assert jr._MAX_REFUSAL_MEMBERS == ji.MAX_REFUSAL_MEMBERS
    assert jr._MAX_REFUSAL_JSON_BYTES == ji.MAX_REFUSAL_JSON_BYTES
    assert jr._MAX_INGRESS_BODY_BYTES == ji.MAX_INGRESS_BODY_BYTES


def test_a5_max_json_array_items_is_256():
    assert jr._MAX_JSON_ARRAY_ITEMS == 256
    assert MAX_JSON_ARRAY_ITEMS == 256


# === A6: the normalizer and the checker, tested separately (critic 4) ======


def test_a6_refusal_summary_data_accepts_raw_output_returns_tuples_idempotent():
    raw, _body = grafana_group(CAPTURE_CASES[0][2], 33, "firing")
    outcome = ji.sanitize_notification(raw)
    raw_summary = ji.refusal_to_json(outcome.refusal)
    assert type(raw_summary["members"]) is list
    normalized = jr.refusal_summary_data(raw_summary)
    assert type(normalized["members"]) is tuple
    assert all(type(m) is tuple for m in normalized["members"])
    again = jr.refusal_summary_data(normalized)
    assert again == normalized


def test_a6_refusal_summary_data_raises_wherever_the_checker_does():
    base = too_many_alerts_summary()
    forged = dict(base, code="nope")
    forged_listy = dict(forged, members=[list(m) for m in forged["members"]])
    checker_error = expect_record("record_field", jr._check_refusal_summary, forged)
    normalizer_error = expect_record("record_field", jr.refusal_summary_data, forged_listy)
    assert checker_error.code == normalizer_error.code


@pytest.mark.parametrize("arity", [1, 3])
@pytest.mark.parametrize("shape", [list, tuple])
def test_a6_refusal_summary_data_refuses_a_member_that_is_not_a_pair(arity, shape):
    # The normalizer rebuilds members as pairs before the checker sees them,
    # so its own arity check is the only guard against silent truncation.
    raw, _body = grafana_group(CAPTURE_CASES[0][2], 33, "firing")
    raw_summary = ji.refusal_to_json(ji.sanitize_notification(raw).refusal)
    members = [shape(member) for member in raw_summary["members"]]
    jr.refusal_summary_data(dict(raw_summary, members=shape(members)))  # the unforged control
    fingerprint, status = members[0]
    members[0] = shape((fingerprint, status, "junk")[:arity])
    expect_record(
        "record_field", jr.refusal_summary_data, dict(raw_summary, members=shape(members)),
    )


class _SubDict(dict):
    """A dict subclass posing as an exact dict."""


class _SubTuple(tuple):
    """A tuple subclass posing as an exact tuple."""


class _SubList(list):
    """A list subclass posing as an exact list."""


def test_a6_refusal_summary_data_refuses_a_dict_subclass_summary():
    # M26: the threat model names dict subclasses in hand-built summaries.
    valid = ji.refusal_to_json(_valid_member_refusal())
    expect_record("record_field", jr.refusal_summary_data, _SubDict(valid))


def test_a6_refusal_summary_data_refuses_a_members_container_subclass():
    # M27: the threat model names tuple subclasses; a list subclass is the
    # same exact-type gap on the other allowed shape.
    valid = ji.refusal_to_json(_valid_member_refusal())
    for wrapped in (_SubTuple(valid["members"]), _SubList(valid["members"])):
        summary = dict(valid, members=wrapped)
        expect_record("record_field", jr.refusal_summary_data, summary)


def test_a6_refusal_summary_data_refuses_a_member_subclass():
    # M28: the per-member exact-type check, same threat as M27 one level down.
    valid = ji.refusal_to_json(_valid_member_refusal())
    first, rest = valid["members"][0], valid["members"][1:]
    for wrapped_first in (_SubTuple(first), _SubList(first)):
        summary = dict(valid, members=[wrapped_first, *rest])
        expect_record("record_field", jr.refusal_summary_data, summary)


def test_a6_checker_accepts_normalized_rejects_raw():
    raw, _body = grafana_group(CAPTURE_CASES[0][2], 33, "firing")
    outcome = ji.sanitize_notification(raw)
    raw_summary = ji.refusal_to_json(outcome.refusal)
    jr._check_refusal_summary(jr.refusal_summary_data(raw_summary))
    expect_record("record_field", jr._check_refusal_summary, raw_summary)


def test_a6_record_refusal_in_memory_data_equals_decoded():
    raw, _body = grafana_group(CAPTURE_CASES[0][2], 33, "firing")
    outcome = ji.sanitize_notification(raw)
    raw_summary = ji.refusal_to_json(outcome.refusal)  # list-shaped, as record_refusal receives it
    normalized = jr.refusal_summary_data(raw_summary)  # what record_refusal seals
    draft = jr.Draft(
        event_id="33333333-3333-3333-3333-333333333333", event_type="ingress_refusal",
        actor="receiver", ids={},
        data={
            "rule": jr.REFUSAL_RULE, "summary": normalized,
            "refusal_key": jrd.refusal_key(normalized), "refusal_seq": 1,
        },
    )
    record = jr.seal(draft, position(), stamp())
    assert record.data == jr.open_record(record.body).data


# === F3-5: refusal_summary_data's exact-type and non-sequence checks =======
# (residue gap: the dict/tuple/list *subclass* cases already exist above --
# M26-M28 -- this covers the exact-type and non-sequence gaps beside them:
# a non-dict summary, a non-sequence ``members``, a non-pair member, and a
# non-str fingerprint/status inside an otherwise pair-shaped member.)


@pytest.mark.parametrize("bad_summary", [[], (), None, "not a summary", 7])
def test_f3_5_refusal_summary_data_refuses_a_non_dict_summary(bad_summary):
    expect_record("record_field", jr.refusal_summary_data, bad_summary)


@pytest.mark.parametrize("bad_members", ["not-a-sequence", {"fingerprint": "x"}, {"a", "b"}])
def test_f3_5_refusal_summary_data_refuses_members_that_is_not_a_sequence(bad_members):
    valid = ji.refusal_to_json(_valid_member_refusal())
    summary = dict(valid, members=bad_members)
    expect_record("record_field", jr.refusal_summary_data, summary)


@pytest.mark.parametrize(
    "bad_member", ["m000-firing", {"fingerprint": f"{0:064x}", "status": "firing"}],
)
def test_f3_5_refusal_summary_data_refuses_a_member_that_is_not_a_list_or_tuple(bad_member):
    valid = ji.refusal_to_json(_valid_member_refusal())
    members = [bad_member, *valid["members"][1:]]
    expect_record("record_field", jr.refusal_summary_data, dict(valid, members=members))


@pytest.mark.parametrize("bad_member", [[123, "firing"], [f"{0:064x}", 456]])
def test_f3_5_refusal_summary_data_refuses_a_non_str_fingerprint_or_status(bad_member):
    # Shape-valid (a pair) so the normalizer's own loop accepts it and hands
    # it to the strict checker, which is what must catch the type violation.
    valid = ji.refusal_to_json(_valid_member_refusal())
    members = [bad_member, *valid["members"][1:]]
    expect_record("record_field", jr.refusal_summary_data, dict(valid, members=members))


# === A7 + A7b: the refusal reducer, and the byte coupling ==================


def test_a7_two_re_renders_give_one_key_membership_change_gives_a_new_key():
    j = PureJournal()
    summary_a = too_many_alerts_summary(n_firing=32, n_resolved=1)
    first = j.refuse(summary_a)
    assert isinstance(first, dict)
    summary_a_rerendered = dict(summary_a, body_digest="9" * 64)  # only message/body_digest changed
    second = j.refuse(summary_a_rerendered)
    assert isinstance(second, jrd.RefusalNotRecorded) and second.reason == "coalesced"

    summary_b = too_many_alerts_summary(n_firing=31, n_resolved=2)  # a member turned Resolved
    third = j.refuse(summary_b)
    assert isinstance(third, dict)
    assert j.projection.refusal_count == 2


def test_a7_limit_at_256_then_coalesced_still_recorded_at_the_limit():
    j = PureJournal()
    # 192 unreserved plus 64 Resolved-bearing (the reserve) = 256 exactly.
    for i in range(192):
        outcome = j.refuse(group_unsupported_summary(refused_group=f"{i:064x}"))
        assert isinstance(outcome, dict), i
    for i in range(64):
        outcome = j.refuse(resolved_group_unsupported_summary(refused_group=f"{192 + i:064x}"))
        assert isinstance(outcome, dict), i
    assert j.projection.refusal_count == 256
    overflow = j.refuse(resolved_group_unsupported_summary(refused_group="f" * 64))
    assert isinstance(overflow, jrd.RefusalNotRecorded) and overflow.reason == "limit"
    # A previously-recorded key is still coalesced even at the limit.
    again = j.refuse(group_unsupported_summary(refused_group=f"{0:064x}"))
    assert isinstance(again, jrd.RefusalNotRecorded) and again.reason == "coalesced"


def test_a7_reserve_192nd_unreserved_is_limit_while_resolved_bearing_still_recorded():
    j = PureJournal()
    for i in range(192):
        outcome = j.refuse(group_unsupported_summary(refused_group=f"{i:064x}"))
        assert isinstance(outcome, dict), i
    assert j.projection.refusal_unreserved_count == 192
    overflow = j.refuse(group_unsupported_summary(refused_group=f"{999:064x}"))
    assert isinstance(overflow, jrd.RefusalNotRecorded) and overflow.reason == "limit"
    # A Resolved-bearing summary still records, using the 64-record reserve.
    resolved_bearing = j.refuse(resolved_group_unsupported_summary(refused_group=f"{1000:064x}"))
    assert isinstance(resolved_bearing, dict)
    assert j.projection.refusal_count == 193


def test_a7_no_room_computed_on_the_sealed_record_against_ordinary_bytes():
    summary = too_many_alerts_summary()
    sealed_probe = jr.seal(
        jr.Draft(
            event_id="probe", event_type="ingress_refusal", actor="receiver", ids={},
            data={
                "rule": jr.REFUSAL_RULE, "summary": summary,
                "refusal_key": jrd.refusal_key(summary), "refusal_seq": 1,
            },
        ),
        position(event_seq=2, commit_seq=2, prev_record_digest="a" * 64), stamp(),
    )
    charge = len(sealed_probe.body) + jrd.RECORD_OVERHEAD_BYTES
    j = PureJournal(jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024,
        ordinary_bytes=1, total_bytes=128 * 2**20,
    ))
    genesis_bytes = j.projection.logical_bytes
    assert genesis_bytes + charge > 1  # tiny budget forces no_room
    result = j.refuse(summary)
    assert isinstance(result, jrd.RefusalNotRecorded) and result.reason == "no_room"


def _genesis_only_bytes(ordinary_bytes: int) -> int:
    bounds = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=ordinary_bytes,
        total_bytes=128 * 2**20,
    )
    return PureJournal(bounds).projection.logical_bytes


def test_a7b_byte_coupling_directed():
    # Measure the refusal and admission charges under a generous bound, where
    # both commit; they are independent of the bounds value (only genesis's
    # own body encodes it). Genesis's own charge varies by the encoded
    # `ordinary_bytes` field's digit width, so the tight target is found by a
    # short fixed-point search over genesis's charge alone.
    summary = too_many_alerts_summary()
    generous = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    probe = PureJournal(generous)
    start_bytes = probe.projection.logical_bytes
    probe.refuse(summary)
    after_refusal_bytes = probe.projection.logical_bytes
    refusal_charge = after_refusal_bytes - start_bytes
    probe.admit(sample_source())
    admission_charge = probe.projection.logical_bytes - after_refusal_bytes

    ordinary_bytes = start_bytes
    for _ in range(5):
        next_bytes = _genesis_only_bytes(ordinary_bytes) + refusal_charge + admission_charge - 1
        if next_bytes == ordinary_bytes:
            break
        ordinary_bytes = next_bytes
    bounds = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=ordinary_bytes,
        total_bytes=128 * 2**20,
    )

    with_refusal = PureJournal(bounds)
    outcome = with_refusal.refuse(summary)
    assert isinstance(outcome, dict)
    admitted = with_refusal.admit(sample_source())
    assert admitted.get("refusal") is not None
    assert admitted["refusal"].code == "capacity_bytes"

    without_refusal = PureJournal(bounds)
    admitted_alone = without_refusal.admit(sample_source())
    assert "refusal" not in admitted_alone

    bounds_plus_one = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=ordinary_bytes + 1,
        total_bytes=128 * 2**20,
    )
    with_both = PureJournal(bounds_plus_one)
    assert isinstance(with_both.refuse(summary), dict)
    assert "refusal" not in with_both.admit(sample_source())

    # The size of a record at the 4,096-byte summary bound, x256 (worst case).
    sealed_at_bound = jr.seal(
        jr.Draft(
            event_id="probe", event_type="ingress_refusal", actor="receiver", ids={},
            data={
                "rule": jr.REFUSAL_RULE, "summary": summary,
                "refusal_key": jrd.refusal_key(summary), "refusal_seq": 1,
            },
        ),
        position(event_seq=2, commit_seq=2, prev_record_digest="a" * 64), stamp(),
    )
    worst_case_record_bytes = len(sealed_at_bound.body) + jrd.RECORD_OVERHEAD_BYTES
    worst_case_total = worst_case_record_bytes * jr.MAX_REFUSAL_RECORDS
    print(
        f"\n[A7b] refusal_charge={refusal_charge} admission_charge={admission_charge} "
        f"worst_case_256_refusals_bytes={worst_case_total}"
    )
    assert worst_case_total < 1_400_000  # under 1.4 MiB, as the plan estimates


def _max_length_members(n: int, *, resolved: int = 1) -> list[tuple[str, str]]:
    """``n`` members at ``MAX_FINGERPRINT_BYTES`` (64), ``resolved`` of them
    Resolved -- the largest legitimate member list at each size."""
    return [
        (f"{i:064x}", "resolved" if i < resolved else "firing") for i in range(n)
    ]


def test_f3_6_a7b_worst_case_uses_the_true_maximum_length_summary(monkeypatch):
    """A7b's own print uses short fingerprints. The largest v1 summary is the
    longest member code with 32 listed members at the 64-byte Fingerprint
    limit, 256 alerts, all Resolved; it stays under the 4,096-byte bound, so
    the bound itself can only be exercised by lowering it."""
    largest = dict(
        member_summary(
            "ingress_group_key_unsupported", _max_length_members(32, resolved=32),
            body_bytes=262_144, body_digest="e" * 64, members_omitted=224, alerts=256,
            resolved=256,
        ),
        source_group=None, refused_group="f" * 64,
    )
    jr._check_refusal_summary(largest)
    largest_record = _seal_refusal(summary=largest)
    largest_size = len(canonical_json(largest, ascii_only=True))
    assert largest_size == 2_866
    assert largest_size < jr._MAX_REFUSAL_JSON_BYTES

    # ``ingress_ref_id_unsupported`` (not one of the alert-count-bounded
    # codes) lets ``members`` sit at any size up to the 32 cap, so a
    # 31-member and a 32-member summary can otherwise be shaped identically.
    summary_31 = member_summary(
        "ingress_ref_id_unsupported", _max_length_members(31), source_group="d" * 64,
        body_bytes=262_143, body_digest="e" * 64, members_omitted=0, alerts=31, resolved=1,
    )
    summary_32 = member_summary(  # one member larger than summary_31
        "ingress_ref_id_unsupported", _max_length_members(32), source_group="d" * 64,
        body_bytes=262_143, body_digest="e" * 64, members_omitted=0, alerts=32, resolved=1,
    )
    size_31 = len(canonical_json(summary_31, ascii_only=True))
    size_32 = len(canonical_json(summary_32, ascii_only=True))
    assert size_31 < size_32
    assert size_32 < jr._MAX_REFUSAL_JSON_BYTES  # the real 4,096-byte bound is never reached

    monkeypatch.setattr(jr, "_MAX_REFUSAL_JSON_BYTES", size_31)
    jr._check_refusal_summary(summary_31)  # at the (lowered) bound, inclusive: seals
    record = _seal_refusal(summary=summary_31, refusal_key="0" * 64)
    # One member larger, over that same bound: refused.
    expect_record("record_field", jr._check_refusal_summary, summary_32)
    expect_record("record_field", _seal_refusal, summary=summary_32, refusal_key="0" * 64)

    assert len(record.body) < len(largest_record.body)

    worst_case_record_bytes = len(largest_record.body) + jrd.RECORD_OVERHEAD_BYTES
    worst_case_total = worst_case_record_bytes * jr.MAX_REFUSAL_RECORDS
    print(
        f"\n[F3-6] largest_summary_bytes={largest_size} "
        f"record_bytes={len(largest_record.body)} "
        f"worst_case_record_bytes={worst_case_record_bytes} "
        f"worst_case_256_refusals_bytes={worst_case_total}"
    )
    assert worst_case_total < 2**20  # under 1 MiB per generation


# --- A7: replay's own checks, probed with hand-sealed records ---------------


def _hand_sealed_refusal(p, summary, *, refusal_key=None, refusal_seq=None, boot_id=None):
    """An ``ingress_refusal`` sealed directly at ``p``'s head, not through
    ``plan_ingress_refusal`` (which applies every rule before it seals), so
    replay's own checks can be probed one at a time."""
    data = {
        "rule": jr.REFUSAL_RULE, "summary": summary,
        "refusal_key": jrd.refusal_key(summary) if refusal_key is None else refusal_key,
        "refusal_seq": p.refusal_count + 1 if refusal_seq is None else refusal_seq,
    }
    draft = jr.Draft(
        event_id="hand-built-refusal", event_type="ingress_refusal", actor="receiver", ids={},
        data=data,
    )
    pos = jr.Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    boot = p.boot_id if boot_id is None else boot_id
    return jr.seal(draft, pos, stamp(boot_id=boot, wall_time=WALL_B, mono_us=p.last_mono_us + 1))


def test_a7_replay_rejects_a_wrong_key():
    j = PureJournal()
    summary = too_many_alerts_summary()
    jrd.verify_commit(j.projection, (_hand_sealed_refusal(j.projection, summary),))
    wrong = _hand_sealed_refusal(j.projection, summary, refusal_key="0" * 64)
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (wrong,))


def test_a7_replay_rejects_a_repeated_key():
    j = PureJournal()
    summary = too_many_alerts_summary()
    j.refuse(summary)
    # A re-render: the key it recomputes is the recorded one; its seq is the next.
    repeated = _hand_sealed_refusal(j.projection, dict(summary, body_digest="9" * 64))
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (repeated,))
    novel = too_many_alerts_summary(n_firing=31, n_resolved=2)
    jrd.verify_commit(j.projection, (_hand_sealed_refusal(j.projection, novel),))


@pytest.mark.parametrize("recorded,seq", [(0, 2), (1, 1), (1, 3)])
def test_a7_replay_rejects_a_refusal_seq_other_than_the_next(recorded, seq):
    j = PureJournal()
    for i in range(recorded):
        j.refuse(group_unsupported_summary(refused_group=f"{i:064x}"))
    record = _hand_sealed_refusal(j.projection, too_many_alerts_summary(), refusal_seq=seq)
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (record,))


def test_a7_replay_rejects_a_record_over_the_limit(monkeypatch):
    # The validator bounds refusal_seq by the same 256, so replay's own limit
    # check is reachable only under a lower limit: lower the reducer's copy.
    monkeypatch.setattr(jrd, "MAX_REFUSAL_RECORDS", 2)
    monkeypatch.setattr(jrd, "REFUSAL_RESOLVED_RESERVE", 0)
    j = PureJournal()
    summaries = [resolved_group_unsupported_summary(refused_group=f"{i:064x}") for i in range(3)]
    for summary in summaries[:2]:
        assert isinstance(j.refuse(summary), dict)
    assert j.refuse(summaries[2]) == jrd.RefusalNotRecorded("limit")
    third = _hand_sealed_refusal(j.projection, summaries[2])
    assert third.data["refusal_seq"] == 3
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (third,))


def test_a7_replay_rejects_an_unreserved_record_past_192():
    j = PureJournal()
    for i in range(192):
        j.refuse(group_unsupported_summary(refused_group=f"{i:064x}"))
    unreserved = _hand_sealed_refusal(
        j.projection, group_unsupported_summary(refused_group=f"{999:064x}"),
    )
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (unreserved,))
    reserved = _hand_sealed_refusal(
        j.projection, resolved_group_unsupported_summary(refused_group=f"{1000:064x}"),
    )
    jrd.verify_commit(j.projection, (reserved,))


def test_a7_replay_rejects_a_foreign_boot():
    j = PureJournal()
    record = _hand_sealed_refusal(j.projection, too_many_alerts_summary(), boot_id=BOOT_B)
    expect_replay("replay_boot", jrd.verify_commit, j.projection, (record,))


def _refusal_bounds(ordinary_bytes: int) -> jrd.JournalBounds:
    return jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=ordinary_bytes,
        total_bytes=128 * 2**20,
    )


def _exact_ordinary_bytes(charge: int) -> int:
    """The ``ordinary_bytes`` that genesis plus ``charge`` fills exactly: a
    fixed point, since genesis's own charge varies with the bound's digits."""
    ordinary_bytes = charge
    for _ in range(5):
        next_bytes = _genesis_only_bytes(ordinary_bytes) + charge
        if next_bytes == ordinary_bytes:
            break
        ordinary_bytes = next_bytes
    assert _genesis_only_bytes(ordinary_bytes - 1) == _genesis_only_bytes(ordinary_bytes)
    return ordinary_bytes


def test_a7_the_ordinary_budget_is_exact_in_plan_and_in_replay():
    summary = too_many_alerts_summary()
    # Replay, on a hand-sealed record: at ordinary_bytes exactly it verifies,
    # one byte less is a mismatch, though total_bytes has room for both.
    probe_record = _hand_sealed_refusal(PureJournal().projection, summary)
    exact = _exact_ordinary_bytes(len(probe_record.body) + jrd.RECORD_OVERHEAD_BYTES)
    fits = PureJournal(_refusal_bounds(exact))
    record = _hand_sealed_refusal(fits.projection, summary)
    assert fits.projection.logical_bytes + len(record.body) + jrd.RECORD_OVERHEAD_BYTES == exact
    jrd.verify_commit(fits.projection, (record,))
    short = PureJournal(_refusal_bounds(exact - 1))
    expect_replay(
        "replay_mismatch", jrd.verify_commit, short.projection,
        (_hand_sealed_refusal(short.projection, summary),),
    )
    # Plan, on its own sealed record: recorded at the bound, no_room one below.
    probe = PureJournal()
    start_bytes = probe.projection.logical_bytes
    probe.refuse(summary)
    exact = _exact_ordinary_bytes(probe.projection.logical_bytes - start_bytes)
    assert isinstance(PureJournal(_refusal_bounds(exact)).refuse(summary), dict)
    no_room = PureJournal(_refusal_bounds(exact - 1)).refuse(summary)
    assert no_room == jrd.RefusalNotRecorded("no_room")


_A7_SUBSTITUTES = (None, True, 0, -1, 2**53, "x" * 300, [], {})  # F1's own set
# Type-valid replacements, tried on summary leaves as well.
_A7_SUMMARY_SUBSTITUTES = (
    "0" * 64, 1, 33, "firing", "resolved", "zz-fp", "ingress_too_many_values",
)
_A7_SURVIVORS = {("data", "summary", "body_bytes"), ("data", "summary", "body_digest")}


def _leaf_paths(node, path=()):
    if type(node) is dict:
        items = node.items()
    elif type(node) is list:
        items = enumerate(node)
    else:
        return
    for key, value in items:
        yield path + (key,)
        yield from _leaf_paths(value, path + (key,))


def _node_at(root, path):
    for step in path:
        root = root[step]
    return root


def _replays_cleanly(envelope: dict, p_before) -> bool:
    try:
        body = canonical_json(envelope, ascii_only=True)
        jrd.verify_commit(copy.deepcopy(p_before), (jr.open_record(body),))
    except (JSONPolicyError, jr.RecordError, jrd.ReplayError):
        return False
    return True


def test_a7_leaf_mutation_matrix_survivors_are_body_bytes_and_body_digest_only():
    j = PureJournal()
    j.admit(sample_source())  # a later mono_us, so an earlier one cannot pass as non-decreasing
    p_before = copy.deepcopy(j.projection)
    plan = jrd.plan_ingress_refusal(
        j.projection, too_many_alerts_summary(), event_id="a7-matrix", stamp=j._stamp(),
    )
    envelope = json.loads(plan.records[0].body)
    assert _replays_cleanly(envelope, p_before)
    paths = list(_leaf_paths(envelope))
    survivors, tried = set(), 0
    for path in paths:
        parent, current = _node_at(envelope, path[:-1]), _node_at(envelope, path)
        substitutes = _A7_SUBSTITUTES
        if path[:2] == ("data", "summary"):
            substitutes += _A7_SUMMARY_SUBSTITUTES
        mutations = [("delete", None)] if type(parent) is dict else []
        mutations += [
            ("substitute", value) for value in substitutes
            if not (type(value) is type(current) and value == current)
        ]
        for op, value in mutations:
            mutated = copy.deepcopy(envelope)
            target = _node_at(mutated, path[:-1])
            if op == "delete":
                del target[path[-1]]
            else:
                target[path[-1]] = copy.deepcopy(value)
            tried += 1
            if _replays_cleanly(mutated, p_before):
                survivors.add((path, op, repr(value)))
    for path in [()] + [path for path in paths if type(_node_at(envelope, path)) is dict]:
        mutated = copy.deepcopy(envelope)
        _node_at(mutated, path)["zz_sibling"] = "x"
        tried += 1
        if _replays_cleanly(mutated, p_before):
            survivors.add((path, "add_sibling", "'x'"))
    print(f"\n[A7] leaf mutations tried={tried} survivors={sorted(survivors)}")
    assert {path for path, _op, _value in survivors} == _A7_SURVIVORS


# === A8: the resume reducer ==================================================


def test_a8_resume_accepted_right_after_a_restart_clears_only_that_hold():
    j = PureJournal()
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    assert j.projection.dispatch_holds == {"restart_recovery": 2}
    outcome = j.resume()
    assert "refusal" not in outcome
    assert j.projection.dispatch_holds == {}
    assert j.projection.resume_count == 1
    assert j.projection.last_resume_commit_seq == j.projection.head.commit_seq


def _hand_built_operator_action_record(
    p, *, since_commit_seq, inspected, pending_digest_value, hold="restart_recovery",
    boot_id=None, mono_us=999,
):
    """A structurally-valid ``operator_action`` record built directly (not
    through ``plan_operator_resume``, which assumes its precondition -- the
    hold's presence -- already holds), so replay's own checks can be probed
    in isolation."""
    inspected_json = {
        "commit_seq": 1, "event_seq": 1, "record_digest": jr.ZERO_DIGEST,
    } if inspected is None else {
        "commit_seq": inspected.commit_seq, "event_seq": inspected.event_seq,
        "record_digest": inspected.record_digest,
    }
    data = {
        "action": "resume", "rule": jr.RESUME_RULE, "hold": hold,
        "since_commit_seq": since_commit_seq, "inspected": inspected_json,
        "pending_digest": pending_digest_value, "operator": "alice",
        "reason": "restart-inspected",
    }
    draft = jr.Draft(
        event_id="hand-built-resume", event_type="operator_action", actor="operator", ids={},
        data=data,
    )
    pos = jr.Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    boot = p.boot_id if boot_id is None else boot_id
    return jr.seal(draft, pos, stamp(boot_id=boot, wall_time=WALL_B, mono_us=mono_us))


def test_a8_resume_with_no_hold_is_replay_mismatch():
    j = PureJournal()  # fresh, genesis boot: no restart_recovery hold
    record = _hand_built_operator_action_record(
        j.projection, since_commit_seq=2, inspected=None,
        pending_digest_value=jrd.pending_digest(j.projection),
    )
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (record,))


def test_a8_second_resume_in_one_boot_is_replay_mismatch():
    j = PureJournal()
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    hold_since = j.projection.dispatch_holds["restart_recovery"]
    boot_recovered = j.projection.boot_recovered
    j.resume()  # clears the hold
    record = _hand_built_operator_action_record(
        j.projection, since_commit_seq=hold_since, inspected=boot_recovered,
        pending_digest_value=jrd.pending_digest(j.projection),
    )
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (record,))


def test_a8_replay_rejects_wrong_since_inspected_and_pending_digest():
    j = PureJournal()
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    plan = jrd.plan_operator_resume(
        j.projection, event_id="resume-y", stamp=j._stamp(), operator="alice",
        reason="restart-inspected",
    )
    assert isinstance(plan, jrd.Plan)
    good_record = plan.records[0]

    def reseal(**data_overrides):
        data = dict(good_record.data)
        data.update(data_overrides)
        data["inspected"] = dict(data["inspected"])
        draft = jr.Draft(
            event_id=good_record.event_id, event_type="operator_action", actor="operator",
            ids={}, data=data,
        )
        return jr.seal(draft, good_record.position, good_record.stamp)

    wrong_since = reseal(since_commit_seq=good_record.data["since_commit_seq"] + 1)
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (wrong_since,))

    wrong_pending = reseal(pending_digest="0" * 64)
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (wrong_pending,))

    # accepted as planned:
    delta = jrd.verify_commit(j.projection, (good_record,))
    jrd.apply_delta(j.projection, delta)
    assert j.projection.dispatch_holds == {}


def test_a8_admission_between_restart_and_resume_breaks_immediacy():
    j = PureJournal()
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    j.admit(sample_source("aaaaaaaaaaaaaaaa"))
    plan = jrd.plan_operator_resume(
        j.projection, event_id="resume-z", stamp=j._stamp(), operator="alice",
        reason="restart-inspected",
    )
    # since_commit_seq is now stale relative to boot_start_commit_seq, but the
    # plan function itself still builds a record: replay is what catches it.
    assert isinstance(plan, jrd.Plan)
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, plan.records)


def test_a8_resume_accepted_with_ordinary_region_exhausted_but_not_total():
    j = PureJournal(jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=1,
        total_bytes=128 * 2**20,
    ))
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    outcome = j.resume()
    assert "refusal" not in outcome


def test_a8_next_restart_re_adds_the_hold_with_its_own_since():
    j = PureJournal()
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    j.resume()
    assert j.projection.dispatch_holds == {}
    j.restart(boot_id="77777777-7777-7777-7777-777777777777", wall_time=WALL_B)
    assert "restart_recovery" in j.projection.dispatch_holds
    assert j.projection.dispatch_holds["restart_recovery"] == j.projection.head.commit_seq


@pytest.mark.parametrize("leaf", ["commit_seq", "event_seq", "record_digest"])
def test_a8_replay_rejects_a_wrong_inspected_leaf(leaf):
    j = PureJournal()
    j.admit(sample_source())
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    plan = jrd.plan_operator_resume(
        j.projection, event_id="resume-w", stamp=j._stamp(), operator="alice",
        reason="restart-inspected",
    )
    good = plan.records[0]
    data = jr.thaw(good.data)
    data["inspected"][leaf] = "0" * 64 if leaf == "record_digest" else data["inspected"][leaf] + 1
    forged = jr.seal(
        jr.Draft(
            event_id=good.event_id, event_type="operator_action", actor="operator", ids={},
            data=data,
        ),
        good.position, good.stamp,
    )
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (forged,))
    jrd.verify_commit(j.projection, (good,))


def _restarted(total_bytes: int) -> PureJournal:
    j = PureJournal(jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=1,
        total_bytes=total_bytes,
    ))
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    return j


def _exact_total_bytes(charge: int) -> int:
    """The ``total_bytes`` that genesis, a restart and ``charge`` fill
    exactly: a fixed point over genesis's own digit-dependent charge,
    starting from a guess large enough for the restart itself."""
    total_bytes = _restarted(128 * 2**20).projection.logical_bytes + charge
    for _ in range(5):
        next_total = _restarted(total_bytes).projection.logical_bytes + charge
        if next_total == total_bytes:
            break
        total_bytes = next_total
    after_restart = _restarted(total_bytes).projection.logical_bytes
    assert _restarted(total_bytes - 1).projection.logical_bytes == after_restart
    return total_bytes


def test_a8_resume_over_the_total_region_is_refused_in_plan_and_replay():
    def hand_built(p):
        return _hand_built_operator_action_record(
            p, since_commit_seq=p.dispatch_holds["restart_recovery"], inspected=p.boot_recovered,
            pending_digest_value=jrd.pending_digest(p),
        )

    # Replay, on a hand-built resume: it verifies at total_bytes exactly and is
    # a mismatch one byte below (the ordinary region is exhausted throughout).
    charge = len(hand_built(_restarted(128 * 2**20).projection).body)
    exact = _exact_total_bytes(charge + jrd.RECORD_OVERHEAD_BYTES)
    fits = _restarted(exact)
    jrd.verify_commit(fits.projection, (hand_built(fits.projection),))
    over = _restarted(exact - 1)
    expect_replay(
        "replay_mismatch", jrd.verify_commit, over.projection, (hand_built(over.projection),),
    )
    # Plan, on its own sealed record: a CapacityRefusal against total_bytes.
    probe = _restarted(128 * 2**20)
    start_bytes = probe.projection.logical_bytes
    probe.resume()
    exact = _exact_total_bytes(probe.projection.logical_bytes - start_bytes)
    assert "refusal" not in _restarted(exact).resume()
    refusal = _restarted(exact - 1).resume()["refusal"]
    assert (refusal.code, refusal.limit) == ("capacity_bytes", exact - 1)


def test_a8_resume_clears_restart_recovery_and_keeps_a_capacity_hold():
    j = PureJournal(jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    ))
    j.admit(sample_source("aaaa000000000001"))
    second = sample_source("aaaa000000000002")
    refused = j.admit(second)
    assert refused["refusal"].code == "capacity_admissions"
    j.hold_capacity(refused["refusal"], second)
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    held = dict(j.projection.dispatch_holds)
    assert set(held) == {"capacity_admissions", "restart_recovery"}
    j.resume()
    assert j.projection.dispatch_holds == {"capacity_admissions": held["capacity_admissions"]}


def test_a8_replay_refuses_a_resume_of_a_capacity_hold_even_past_the_validator(monkeypatch):
    j = PureJournal(jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    ))
    j.admit(sample_source("aaaa000000000001"))
    second = sample_source("aaaa000000000002")
    j.hold_capacity(j.admit(second)["refusal"], second)
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    held = dict(j.projection.dispatch_holds)
    # A validator that no longer limits the hold must not be the only guard:
    # the reducer keeps its own copy of RESUMABLE_HOLDS, so this widens seal's.
    monkeypatch.setattr(jr, "RESUMABLE_HOLDS", ("capacity_admissions", "restart_recovery"))
    record = _hand_built_operator_action_record(
        j.projection, since_commit_seq=held["capacity_admissions"],
        inspected=j.projection.boot_recovered,
        pending_digest_value=jrd.pending_digest(j.projection), hold="capacity_admissions",
    )
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (record,))
    assert j.projection.dispatch_holds == held


def test_a8_replay_rejects_a_foreign_boot_and_a_regressed_clock():
    j = PureJournal()
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    p = j.projection

    def built(**stamp_fields):
        return _hand_built_operator_action_record(
            p, since_commit_seq=p.dispatch_holds["restart_recovery"], inspected=p.boot_recovered,
            pending_digest_value=jrd.pending_digest(p), **stamp_fields,
        )

    jrd.verify_commit(p, (built(),))  # the correctly stamped control
    jrd.verify_commit(p, (built(mono_us=p.last_mono_us),))  # equal is not a regression
    expect_replay("replay_boot", jrd.verify_commit, p, (built(boot_id=BOOT_A),))
    expect_replay("replay_clock", jrd.verify_commit, p, (built(mono_us=p.last_mono_us - 1),))


# === A9: a seeded property over admissions, restarts, refusals and resumes =


_A9_SEED = 20260924


def _independent_list_digest(tag: str, items: list) -> str:
    canonical_items = sorted(
        json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        for item in items
    )
    leaves = b"".join(hashlib.sha256(item).digest() for item in canonical_items)
    header = tag.encode("ascii") + b"\x00" + len(canonical_items).to_bytes(4, "big")
    return hashlib.sha256(header + leaves).hexdigest()


def _independent_pending_digest(p) -> str:
    items = [
        [e.fingerprint, e.admission_id, e.arrival_seq, e.source_group, e.status,
         (dict(e.values) if e.values is not None else None)]
        for e in p.pending.values()
    ]
    return _independent_list_digest("rj.pending-set.v1", items)


def _independent_state_digest(p) -> str:
    """A frozen, independent copy of ``b931610``'s ``state_digest`` formula
    (R1: unchanged by this unit), computed without calling the module under
    test's own ``tagged_digest``/``_list_digest``."""
    head = None
    if p.head is not None:
        head = {
            "commit_seq": p.head.commit_seq, "event_seq": p.head.event_seq,
            "generation": p.head.generation, "record_digest": p.head.record_digest,
        }
    baseline_items = [
        [group, baseline.admission_id, baseline.complete, baseline.dedupe_key]
        for group, baseline in p.baselines.items()
    ]
    hold_items = sorted([code, commit_seq] for code, commit_seq in p.dispatch_holds.items())
    payload = {
        "journal_uuid": p.journal_uuid, "generation": p.generation, "head": head,
        "admission_count": p.admission_count, "last_arrival_seq": p.last_arrival_seq,
        "logical_bytes": p.logical_bytes, "dispatch_holds": hold_items,
        "pending_digest": _independent_pending_digest(p),
        "baseline_digest": _independent_list_digest("rj.baseline-set.v1", baseline_items),
    }
    return _independent_tagged_digest("rj.state.v1", payload)


def test_a9_boot_fields_and_digests_hold_over_200_seeded_histories():
    print(f"\n[A9] seed={_A9_SEED}")
    rng = random.Random(_A9_SEED)
    bounds = jrd.JournalBounds(
        max_admissions=jr.V1_BOUND_CEILINGS["max_admissions"],
        max_pending_fingerprints=jr.V1_BOUND_CEILINGS["max_pending_fingerprints"],
        ordinary_bytes=jr.V1_BOUND_CEILINGS["ordinary_bytes"],
        total_bytes=jr.V1_BOUND_CEILINGS["total_bytes"],
    )
    for trial in range(200):
        j = PureJournal(bounds)
        expected_recovered = None
        expected_boot_start = 1
        boot_counter = 0
        steps = rng.randint(1, 12)
        for step in range(steps):
            choice = rng.random()
            if choice < 0.4:
                fp = f"{trial:04d}{step:04d}".rjust(16, "0")
                j.admit(sample_source(fp))
            elif choice < 0.6:
                boot_counter += 1
                boot_id = f"{boot_counter:08x}-0000-0000-0000-{trial:012d}"
                expected_recovered = j.projection.head
                expected_boot_start = j.projection.head.commit_seq + 1
                j.restart(boot_id=boot_id, wall_time=WALL_B)
            elif choice < 0.8:
                summary = group_unsupported_summary(
                    refused_group=f"{trial:04d}{step:04d}".zfill(64),
                )
                j.refuse(summary)
            elif (
                "restart_recovery" in j.projection.dispatch_holds
                and j.projection.head.commit_seq == j.projection.boot_start_commit_seq
            ):
                # Resume is only valid immediately after the restart that
                # started this boot; a refusal in between (like any commit)
                # breaks immediacy, so this branch must skip it too.
                j.resume()

            assert j.projection.boot_recovered == expected_recovered, (trial, step)
            assert j.projection.boot_start_commit_seq == expected_boot_start, (trial, step)
            assert jrd.state_digest(j.projection) == _independent_state_digest(j.projection)
            assert jrd.pending_digest(j.projection) == _independent_pending_digest(j.projection)


def test_a9_removing_refusals_leaves_admissions_byte_identical():
    # Precondition: ordinary_bytes chosen so capacity_bytes is unreachable
    # across the whole history, with or without the refusal records.
    bounds = jrd.JournalBounds(
        max_admissions=1_000, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    rng = random.Random(_A9_SEED + 1)
    print(f"\n[A9] removal-clause seed={_A9_SEED + 1}")

    full = PureJournal(bounds)
    without_refusals = PureJournal(bounds)
    for step in range(20):
        if rng.random() < 0.6:
            fp = f"{step:016x}"
            full.admit(sample_source(fp))
            without_refusals.admit(sample_source(fp))
        else:
            full.refuse(group_unsupported_summary(refused_group=f"{step:064x}"))

    full_admissions = [r for r in full.history if r.event_type in ("admission", "dedupe_decision")]
    bare_admissions = [
        r for r in without_refusals.history if r.event_type in ("admission", "dedupe_decision")
    ]
    assert len(full_admissions) == len(bare_admissions)
    for full_record, bare_record in zip(full_admissions, bare_admissions):
        assert full_record.ids == bare_record.ids
        assert full_record.data == bare_record.data


def test_a9_removing_resumes_changes_only_decision_and_dispatch_holds():
    bounds = jrd.JournalBounds(
        max_admissions=1_000, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    with_resume = PureJournal(bounds)
    with_resume.admit(sample_source("aaaa000000000001"))
    with_resume.restart(boot_id=BOOT_B, wall_time=WALL_B)
    with_resume.resume()
    with_resume.admit(sample_source("aaaa000000000002"))

    without_resume = PureJournal(bounds)
    without_resume.admit(sample_source("aaaa000000000001"))
    without_resume.restart(boot_id=BOOT_B, wall_time=WALL_B)
    without_resume.admit(sample_source("aaaa000000000002"))

    with_admissions = [r for r in with_resume.history if r.event_type == "admission"]
    without_admissions = [r for r in without_resume.history if r.event_type == "admission"]
    assert len(with_admissions) == len(without_admissions) == 2
    # Before any restart: identical either way.
    assert with_admissions[0].data == without_admissions[0].data
    # After: with resume it is admitted, holds cleared; without, still held.
    with_second, without_second = dict(with_admissions[1].data), dict(without_admissions[1].data)
    assert with_second["decision"] == "admitted"
    assert with_second["dispatch_holds"] == ()
    assert without_second["decision"] == "held"
    assert without_second["dispatch_holds"] == ("restart_recovery",)
    for key, value in with_second.items():
        if key in ("decision", "dispatch_holds"):
            continue
        assert value == without_second[key], key


def _a9_source(fingerprint: str, group: int, status: str) -> js.SourceRecord:
    group_key = f'{{}}:{{alertname="a9-{group}", grafana_folder="demo"}}'
    alert = js.SourceAlert(
        fingerprint=fingerprint, status=status, values=(("A", "1"),), starts_at=None,
    )
    return js.SourceRecord(
        source_group=js.source_group_digest(group_key), alerts=(alert,), truncated_alerts=0,
        body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )


def _a9_admit(j: PureJournal, op: tuple) -> dict:
    src = _a9_source(*op[1:])
    outcome = j.admit(src)
    if "refusal" in outcome:
        j.hold_capacity(outcome["refusal"], src)
    return outcome


def _a9_play(ops: list, bounds: jrd.JournalBounds) -> PureJournal:
    j = PureJournal(bounds)
    for op in ops:
        if op[0] == "admit":
            _a9_admit(j, op)
        elif op[0] == "restart":
            j.restart(boot_id=op[1], wall_time=WALL_B)
        elif op[0] == "refuse":
            j.refuse(group_unsupported_summary(refused_group=op[1]))
        else:
            j.resume()
    return j


def _a9_pair_records(j: PureJournal, *, mask: tuple[str, ...] = ()) -> list:
    return [
        (r.event_type, r.ids, {k: v for k, v in r.data.items() if k not in mask})
        if r.event_type == "admission" else (r.event_type, r.ids, dict(r.data))
        for r in j.history if r.event_type in ("admission", "dedupe_decision")
    ]


def test_a9_property_over_200_seeded_histories_with_capacity_refusals():
    """The plan's whole A9 over one generator: capacity_admissions and
    capacity_pending refusals (small count bounds), refusals and resumes; the
    capacity_bytes precondition asserted on every history, and both removal
    clauses checked on each."""
    print(f"\n[A9] property seed={_A9_SEED + 2}")
    rng = random.Random(_A9_SEED + 2)
    seen = {"capacity_admissions": 0, "capacity_pending": 0, "refusal": 0, "resume": 0}
    for trial in range(200):
        bounds = jrd.JournalBounds(
            max_admissions=rng.choice((3, 6, 10_000)),
            max_pending_fingerprints=rng.choice((2, 4, 1_024)),
            ordinary_bytes=jr.V1_BOUND_CEILINGS["ordinary_bytes"],
            total_bytes=jr.V1_BOUND_CEILINGS["total_bytes"],
        )
        j = PureJournal(bounds)
        ops: list = []
        expected_recovered, expected_boot_start, largest_admission = None, 1, 0
        for step in range(rng.randint(1, 20)):
            choice = rng.random()
            if choice < 0.5:
                op = (
                    "admit", f"{rng.randrange(6):016x}", rng.randrange(2),
                    rng.choice(js.ALERT_STATUSES),
                )
                before_bytes = j.projection.logical_bytes
                outcome = _a9_admit(j, op)
                if "refusal" in outcome:
                    assert outcome["refusal"].code != "capacity_bytes", (trial, step)
                    seen[outcome["refusal"].code] += 1
                else:
                    charge = j.projection.logical_bytes - before_bytes
                    largest_admission = max(largest_admission, charge)
            elif choice < 0.65:
                restarts = sum(1 for earlier in ops if earlier[0] == "restart")
                op = ("restart", f"{restarts + 1:08x}-0000-0000-0000-{trial:012d}")
                expected_recovered = j.projection.head
                expected_boot_start = j.projection.head.commit_seq + 1
                j.restart(boot_id=op[1], wall_time=WALL_B)
            elif choice < 0.85:
                op = ("refuse", f"{rng.randrange(8):064x}")
                recorded = j.refuse(group_unsupported_summary(refused_group=op[1]))
                seen["refusal"] += isinstance(recorded, dict)
            elif (
                "restart_recovery" in j.projection.dispatch_holds
                and j.projection.head.commit_seq == j.projection.boot_start_commit_seq
            ):
                op = ("resume",)
                capacity_holds = {
                    code: since for code, since in j.projection.dispatch_holds.items()
                    if code != "restart_recovery"
                }
                j.resume()
                seen["resume"] += 1
                assert j.projection.dispatch_holds == capacity_holds, (trial, step)
            else:
                continue
            ops.append(op)
            assert j.projection.boot_recovered == expected_recovered, (trial, step)
            assert j.projection.boot_start_commit_seq == expected_boot_start, (trial, step)
            assert jrd.state_digest(j.projection) == _independent_state_digest(j.projection)
            assert jrd.pending_digest(j.projection) == _independent_pending_digest(j.projection)

        # capacity_bytes is unreachable with or without the refusals and resumes.
        assert j.projection.logical_bytes < bounds.ordinary_bytes - largest_admission, trial
        without_refusals = _a9_play([op for op in ops if op[0] != "refuse"], bounds)
        assert _a9_pair_records(without_refusals) == _a9_pair_records(j), trial
        without_resumes = _a9_play([op for op in ops if op[0] != "resume"], bounds)
        mask = ("decision", "dispatch_holds")
        assert _a9_pair_records(without_resumes, mask=mask) == _a9_pair_records(j, mask=mask)
    print(f"[A9] occurrences={seen}")
    assert all(seen.values()), seen


# === A10: front_door_digest known answers ===================================


def test_a10_front_door_digest_changes_with_refusal_and_resume():
    j = PureJournal()
    before = jrd.front_door_digest(j.projection)
    j.admit(sample_source())
    after_admission = jrd.front_door_digest(j.projection)
    assert after_admission == before  # admission-only: unchanged

    j.refuse(too_many_alerts_summary())
    after_refusal = jrd.front_door_digest(j.projection)
    assert after_refusal != before

    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    after_restart = jrd.front_door_digest(j.projection)
    assert after_restart == after_refusal  # restart alone doesn't touch front-door state

    j.resume()
    after_resume = jrd.front_door_digest(j.projection)
    assert after_resume != after_refusal


def test_a10_front_door_digest_known_answer():
    p = jrd.new_projection()
    payload = {
        "refusal_count": 0, "refusal_unreserved_count": 0,
        "refusal_keys_digest": _independent_list_digest("rj.refusal-key-set.v1", []),
        "resume_count": 0, "last_resume_commit_seq": None,
    }
    expected = _independent_tagged_digest("rj.front-door-state.v1", payload)
    assert jrd.front_door_digest(p) == expected


# === A11: plan -> seal -> verify_commit -> apply_delta round trips =========


def test_a11_ingress_refusal_round_trip_equals_live_projection():
    j = PureJournal()
    summary = too_many_alerts_summary()
    plan = jrd.plan_ingress_refusal(
        j.projection, summary, event_id="probe-refusal", stamp=j._stamp(),
    )
    assert isinstance(plan, jrd.Plan)
    replayed = jrd.replay(j.history)  # an independent projection, built from the flat history
    delta_live = jrd.verify_commit(j.projection, plan.records)
    jrd.apply_delta(j.projection, delta_live)
    delta_replay = jrd.verify_commit(replayed, plan.records)
    jrd.apply_delta(replayed, delta_replay)
    assert jrd.state_digest(j.projection) == jrd.state_digest(replayed)
    assert jrd.front_door_digest(j.projection) == jrd.front_door_digest(replayed)
    assert j.projection.refusal_keys == replayed.refusal_keys


def test_a11_operator_action_round_trip_equals_live_projection():
    j = PureJournal()
    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    plan = jrd.plan_operator_resume(
        j.projection, event_id="probe-resume", stamp=j._stamp(), operator="alice",
        reason="restart-inspected",
    )
    assert isinstance(plan, jrd.Plan)
    replayed = jrd.replay(j.history)
    jrd.apply_delta(j.projection, jrd.verify_commit(j.projection, plan.records))
    jrd.apply_delta(replayed, jrd.verify_commit(replayed, plan.records))
    assert jrd.state_digest(j.projection) == jrd.state_digest(replayed)
    assert jrd.front_door_digest(j.projection) == jrd.front_door_digest(replayed)
    assert j.projection.dispatch_holds == replayed.dispatch_holds == {}
    assert (j.projection.resume_count, j.projection.last_resume_commit_seq) == (
        replayed.resume_count, replayed.last_resume_commit_seq,
    ) == (1, plan.records[0].position.commit_seq)
    assert j.projection.boot_start_commit_seq == replayed.boot_start_commit_seq
    assert j.projection.boot_recovered == replayed.boot_recovered


# === A12: AST checks =========================================================


def _module_ast(name: str) -> ast.Module:
    path = REPOSITORY / "grafana_jsm_sandbox" / f"{name}.py"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_a12_reducer_still_has_no_try():
    tree = _module_ast("journal_reducer")
    tries = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
    assert tries == []


@pytest.mark.parametrize("module_name", ["journal_records", "journal_reducer", "recovery_journal"])
def test_a12_new_except_bodies_only_assign_or_pass(module_name):
    tree = _module_ast(module_name)
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), (
                module_name, handler.lineno, type(statement).__name__,
            )
        for inner in ast.walk(handler):
            assert not isinstance(inner, ast.Raise), (module_name, inner.lineno)
