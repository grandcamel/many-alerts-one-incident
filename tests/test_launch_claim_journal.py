"""A v3 launch claim is replayable grant-mapping evidence, never launch authority."""

from dataclasses import asdict, replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_source as source
from grafana_jsm_sandbox import journal_store, recovery_journal
from grafana_jsm_sandbox.forwarder_json import tagged_digest
from tests.test_initial_reservation_intent_journal import ADMISSION, FINGERPRINT, JOURNAL, stamp
from tests.test_run_intent_claim_journal import _confirmed, _run, _services

LAUNCH_ID = "00000000-0000-0000-0000-000000000040"
GENERATION = "generation_synthetic"


def _intended(*, five=False):
    p, history, item = _confirmed()
    services = tuple(sorted((*_services(), (
        "confluence", "00000000-0000-0000-0000-000000000027", "f" * 64,
    )))) if five else _services()
    run = _run(p, services=services)
    reducer.apply_delta(p, reducer.verify_commit(p, run.records))
    return p, history + run.records, item


def _grants(p, *, origin=8):
    return tuple(
        (name, claim_id, scope, f"lease_synthetic_{index}", origin + 200_000_000)
        for index, (name, claim_id, scope) in enumerate(p.run_intent.services)
    )


def _launch(p, **changes):
    fields = {
        "event_id": LAUNCH_ID, "forwarder_generation": GENERATION,
        "barrier_token_digest": "e" * 64, "grants": _grants(p), "stamp": stamp(8),
    }
    fields.update(changes)
    return reducer.plan_launch_claim(p, **fields)


def test_launch_claim_is_private_ordinary_and_replayed_unqualified():
    p, history, _ = _intended()
    old_run_digest = reducer.run_intent_claim_digest(p)
    old_reservation_digest = reducer.initial_intents_digest(p)
    assert records.RUN_EVENT_TYPES_V3 == ("run_intent", "launch_claim")
    assert records.RUN_RECORD_CLASS_V3["launch_claim"] == "ordinary"
    planned = _launch(p)
    record = planned.records[0]
    assert (record.event_type, record.schema_version, record.actor) == (
        "launch_claim", 3, "receiver",
    )
    assert len(record.body) <= records.MAX_LAUNCH_CLAIM_RECORD_BYTES
    assert planned.outcome["state"] == "outstanding_unqualified_launch_claim"
    assert records.open_record(record.body) == record
    assert record.data["launch_claim_digest"] == tagged_digest(
        reducer.LAUNCH_CLAIM_TAG, {
            "event_id": record.event_id, "ids": records.thaw(record.ids),
            "data": {key: records.thaw(value) for key, value in record.data.items()
                     if key != "launch_claim_digest"},
        },
    )
    reducer.apply_delta(p, reducer.verify_commit(p, planned.records))
    replayed = reducer.replay(history + planned.records)
    assert replayed.launch_claim == p.launch_claim
    assert reducer.launch_claim_digest(p) == tagged_digest(
        reducer.LAUNCH_CLAIM_STATE_TAG, asdict(p.launch_claim),
    )
    assert reducer.run_intent_claim_digest(p) == old_run_digest
    assert reducer.initial_intents_digest(p) == old_reservation_digest
    assert not hasattr(recovery_journal.RecoveryJournal, "record_launch_claim")
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(p, event_id="00000000-0000-0000-0000-000000000041")


def test_worst_five_service_shape_fits_type_specific_bound():
    p, _, _ = _intended(five=True)
    assert len(p.run_intent.services) == 5
    record = _launch(p).records[0]
    data = records.thaw(record.data)
    origin = records.MAX_SEQ - 300_000_000
    data.update({
        "based_on_commit_seq": records.MAX_SEQ,
        "run_intent_commit_seq": records.MAX_SEQ - 1,
        "receiver_boot_id": "b" * records.MAX_ID_BYTES,
        "forwarder_generation": "g" * records.MAX_ID_BYTES,
        "origin_us": origin, "work_deadline_us": origin + 270_000_000,
        "flush_deadline_us": origin + 290_000_000,
        "hard_deadline_us": origin + 300_000_000,
    })
    for index, grant in enumerate(data["grants"]):
        grant["grant_id"] = str(index) * records.MAX_ID_BYTES
        grant["grant_expiry_us"] = origin + 270_000_000
    maximal = records.seal(
        records.Draft(record.event_id, record.event_type, record.actor,
                      record.ids, data),
        records.Position(records.MAX_GENERATION, records.MAX_SEQ, records.MAX_SEQ,
                         0, 1, "f" * 64),
        records.Stamp("b" * records.MAX_ID_BYTES,
                      "9999-12-31T23:59:59.999999Z", origin),
        schema_version=3,
    )
    assert len(maximal.body) > records.MAX_RUN_HOLD_RECORD_BYTES
    assert len(maximal.body) <= records.MAX_LAUNCH_CLAIM_RECORD_BYTES
    assert records.open_record(maximal.body) == maximal


@pytest.mark.parametrize("change", [
    {"event_id": ADMISSION},
    {"event_id": "00000000-0000-0000-0000-000000000030"},
    {"forwarder_generation": "bad generation"},
    {"forwarder_generation": "x" * (records.MAX_ID_BYTES + 1)},
    {"barrier_token_digest": "unknown"},
    {"grants": ()},
    {"grants": (("jira", "x", "a" * 64, "lease_x", 200_000_008),)},
])
def test_planner_refuses_bad_identity_or_shape(change):
    p, _, _ = _intended()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(p, **change)


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.__setitem__(0, (rows[0][0], rows[1][1], *rows[0][2:])),
    lambda rows: rows.__setitem__(0, ("jira", *rows[0][1:])),
    lambda rows: rows.__setitem__(0, (*rows[0][:3], rows[1][3], rows[0][4])),
    lambda rows: rows.__setitem__(0, (*rows[0][:4], 8)),
    lambda rows: rows.__setitem__(0, (*rows[0][:4], 270_000_009)),
    lambda rows: rows.__setitem__(0, (*rows[0][:4], True)),
])
def test_planner_refuses_wrong_grant_mapping_or_deadline(mutate):
    p, _, _ = _intended()
    rows = list(_grants(p))
    mutate(rows)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(p, grants=tuple(rows))


def test_forged_recomputed_field_is_rejected_by_replay():
    p, _, _ = _intended()
    record = _launch(p).records[0]
    data = records.thaw(record.data)
    data["based_on_record_digest"] = "f" * 64
    forged = records.seal(
        records.Draft(record.event_id, record.event_type, record.actor,
                      record.ids, data),
        record.position, record.stamp, schema_version=3,
    )
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(p, (forged,))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(p, (replace(record, data=data),))


def test_superseded_original_member_and_new_holds_block_launch():
    p, _, original = _intended()
    newer = source.SourceRecord(
        source_group=original.source_group,
        alerts=(source.SourceAlert(FINGERPRINT, "resolved", None, None),),
        truncated_alerts=0, body_digest="f" * 64,
        provenance=source.HTTP_PROVENANCE,
    )
    admission = reducer.plan_admission(
        p, newer, admission_id="00000000-0000-0000-0000-000000000042",
        dedupe_event_id="dedupe-3", stamp=stamp(8),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, admission.records))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(p, stamp=stamp(9), grants=_grants(p, origin=9))
    fresh, _, _ = _intended()
    fresh.dispatch_holds["restart_recovery"] = fresh.head.commit_seq
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(fresh)
    fresh.dispatch_holds.clear()
    fresh.run_holds["held"] = object()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(fresh)


def test_stale_boot_and_ordinary_capacity_hold():
    p, _, _ = _intended()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(p, stamp=records.Stamp("other-boot", stamp(8).wall_time, 8))
    p.boot_start_commit_seq = p.run_intent.committed_at_seq + 1
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(p)
    p.boot_start_commit_seq = 1
    planned = _launch(p)
    p.logical_bytes = p.bounds.ordinary_bytes - planned.charge + 1
    held = _launch(p)
    assert isinstance(held, reducer.CapacityRefusal)
    assert held.code == "capacity_bytes"
    assert p.logical_bytes < p.bounds.total_bytes


def test_restart_before_or_after_claim_never_makes_launch_authority():
    p, _history, _ = _intended()
    restart = reducer.plan_restart(
        p, event_id="restart-after-intent",
        stamp=records.Stamp("new-boot", stamp(8).wall_time, 0),
        anchor_lag=0, wal_found=None,
    )
    reducer.apply_delta(p, reducer.verify_commit(p, restart.records))
    assert p.run_intent is not None
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _launch(p, stamp=records.Stamp("new-boot", stamp(8).wall_time, 8))

    prior, prior_history, _ = _intended()
    claim = _launch(prior)
    reducer.apply_delta(prior, reducer.verify_commit(prior, claim.records))
    after = reducer.plan_restart(
        prior, event_id="restart-after-claim",
        stamp=records.Stamp("new-boot", stamp(8).wall_time, 0),
        anchor_lag=0, wal_found=None,
    )
    reducer.apply_delta(prior, reducer.verify_commit(prior, after.records))
    replayed = reducer.replay(prior_history + claim.records + after.records)
    assert replayed.launch_claim == prior.launch_claim
    assert "restart_recovery" in replayed.dispatch_holds


def test_stopped_store_and_live_snapshot_show_only_unqualified_claim(tmp_path, monkeypatch):
    p, history, _ = _intended()
    planned = _launch(p)
    reducer.apply_delta(p, reducer.verify_commit(p, planned.records))
    directory = tmp_path / "journal"
    directory.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        stored.append(history[1:3], sync_directory=False)
        for record in history[3:]:
            stored.append((record,), sync_directory=False)
        stored.append(planned.records, sync_directory=False)
    finally:
        stored.close()
    inspection = recovery_journal.inspect_recovery_journal(directory)
    expected = {
        "count": 1, "digest": reducer.launch_claim_digest(p),
        "state": "outstanding_unqualified_launch_claim",
    }
    assert inspection.report["journal"]["launch_claim"] == expected
    opened = recovery_journal.open_recovery_journal(directory)
    try:
        assert opened.snapshot()["launch_claim"] == expected
    finally:
        opened.close()
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, "_V3_TYPE_VALIDATORS", {
            ("reservation_intent", 3): records._validate_reservation_intent_v3,
            ("reservation_confirmation", 3): records._validate_reservation_confirmation_v3,
            ("run_intent", 3): records._validate_run_intent_v3,
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == "journal_schema_unsupported"
            assert older.finding.scope == "process"
        finally:
            older.close()
