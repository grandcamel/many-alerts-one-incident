"""Post-restart Jira read-back claims never settle an old effect."""

from dataclasses import replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_store, recovery_journal
from tests.test_initial_reservation_intent_journal import JOURNAL, stamp
from tests.test_reconciliation_claim_journal import _apply, _mutation_ready


def _restart(projection, history, number=1):
    boot = f"recovery-boot-{number}"
    planned = reducer.plan_restart(
        projection, event_id=f"restart-19u-{number}",
        stamp=records.Stamp(boot, stamp(40 + number).wall_time, 1),
        anchor_lag=0, wal_found=None,
    )
    return _apply(projection, history, planned), boot


def _observation(projection, number=0, **changes):
    fields = {
        "event_id": f"00000000-0000-0000-0000-{0xa01 + number:012x}",
        "operation_id": next(iter(projection.effect_intents)),
        "reported_state": "unavailable", "source_evidence_digest": "c" * 64,
        "version_digest": None,
        "stamp": records.Stamp(projection.boot_id, stamp(50 + number).wall_time,
                               projection.last_mono_us + 1),
    }
    fields.update(changes)
    return reducer.plan_restart_reconciliation_observation(projection, **fields)


def test_new_boot_claim_replays_without_effect_or_hold_change():
    projection, history = _mutation_ready()
    old_state = reducer.state_digest(projection)
    history, boot = _restart(projection, history)
    assert projection.boot_start_record_digest == projection.head.record_digest
    assert projection.boot_recovered.commit_seq + 1 == projection.boot_start_commit_seq
    before_holds = dict(projection.dispatch_holds)
    before_effects = dict(projection.effect_intents)
    planned = _observation(projection)
    assert planned.outcome["state"] == "reconciliation_unqualified"
    record = planned.records[0]
    assert record.data["receiver_boot_id"] == boot
    assert record.data["restart_record_digest"] == projection.boot_start_record_digest
    assert record.data["recovered_record_digest"] == projection.boot_recovered.record_digest
    history = _apply(projection, history, planned)
    assert reducer.replay(history).restart_reconciliations == projection.restart_reconciliations
    assert projection.dispatch_holds == before_holds
    assert projection.effect_intents == before_effects
    assert reducer.state_digest(projection) != old_state  # only the ordinary head moved
    assert records.RESTART_RECONCILIATION_RECORD_CLASS_V3 == {
        "restart_reconciliation_observation": "recovery",
    }
    assert not hasattr(recovery_journal.RecoveryJournal,
                       "record_restart_reconciliation_observation")


def test_prior_boot_and_active_restart_hold_are_required():
    projection, _ = _mutation_ready()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _observation(projection)
    history, _ = _restart(projection, ())
    projection.dispatch_holds.pop("restart_recovery")
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _observation(projection)
    # A read-only Jira intent is still ineligible after restart.
    read_only, history = _mutation_ready(route_id="jira.issue.get")
    history, _ = _restart(read_only, history)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _observation(read_only)


def test_second_restart_binds_latest_record_while_hold_origin_stays_old():
    projection, history = _mutation_ready()
    history, first_boot = _restart(projection, history, 1)
    first_hold_origin = projection.dispatch_holds["restart_recovery"]
    history = _apply(projection, history, _observation(projection))
    first_restart_digest = projection.boot_start_record_digest
    history, second_boot = _restart(projection, history, 2)
    assert first_boot != second_boot
    assert projection.dispatch_holds["restart_recovery"] == first_hold_origin
    assert projection.boot_start_commit_seq > first_hold_origin
    assert projection.boot_start_record_digest != first_restart_digest
    planned = _observation(projection, 1, reported_state="confirmed",
                           version_digest="d" * 64)
    assert planned.records[0].data["observation_index"] == 2
    assert planned.records[0].data["restart_commit_seq"] == projection.boot_start_commit_seq
    history = _apply(projection, history, planned)
    claims = next(iter(reducer.replay(history).restart_reconciliations.values()))
    assert [(claim.receiver_boot_id, claim.reported_state) for claim in claims] == [
        (first_boot, "unavailable"), (second_boot, "confirmed"),
    ]


def test_forged_restart_binding_and_version_matrix_are_rejected():
    projection, history = _mutation_ready()
    history, _ = _restart(projection, history)
    for bad in (
        {"reported_state": "confirmed", "version_digest": None},
        {"reported_state": "absent", "version_digest": "d" * 64},
        {"reported_state": "settled"},
    ):
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            _observation(projection, **bad)
    plan = _observation(projection)
    for field, value in (
        ("restart_record_digest", "f" * 64),
        ("recovered_record_digest", "f" * 64),
        ("based_on_record_digest", "f" * 64),
        ("target_digest", "f" * 64),
        ("source_kind", "jira_comment_readback"),
        ("observation_index", 2),
    ):
        data = records.thaw(plan.records[0].data)
        data[field] = value
        forged = records.seal(records.Draft(
            plan.records[0].event_id, "restart_reconciliation_observation",
            "receiver", plan.records[0].ids, data,
        ), plan.records[0].position, plan.records[0].stamp, schema_version=3)
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            reducer.verify_commit(projection, (forged,))
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            reducer.verify_commit(projection, (replace(plan.records[0], data=data),))


def test_lifetime_count_and_recovery_bytes():
    projection, history = _mutation_ready()
    history, _ = _restart(projection, history)
    first = _observation(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes
    assert isinstance(_observation(projection), reducer.Plan)
    projection.logical_bytes = projection.bounds.total_bytes - first.charge + 1
    assert isinstance(_observation(projection), reducer.CapacityRefusal)
    projection, history = _mutation_ready()
    history, _ = _restart(projection, history)
    for number in range(4):
        history = _apply(projection, history, _observation(projection, number))
    refusal = _observation(projection, 4)
    assert isinstance(refusal, reducer.CapacityRefusal)
    assert refusal.code == "capacity_restart_reconciliation_claims"
    assert len(next(iter(reducer.replay(history).restart_reconciliations.values()))) == 4


def test_live_stopped_inspection_and_old_decoder(tmp_path, monkeypatch):
    projection, history = _mutation_ready()
    history, _ = _restart(projection, history)
    history = _apply(projection, history, _observation(projection))
    directory = tmp_path / "journal"
    directory.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        stored.append(history[1:3], sync_directory=False)
        for record in history[3:]:
            stored.append((record,), sync_directory=False)
    finally:
        stored.close()
    stopped = recovery_journal.inspect_recovery_journal(directory)
    opened = recovery_journal.open_recovery_journal(directory)
    try:
        live = opened.snapshot()
    finally:
        opened.close()
    for summary in (stopped.report["journal"]["restart_reconciliation_claims"],
                    live["restart_reconciliation_claims"]):
        assert summary["state"] == "reconciliation_unqualified"
        assert summary["count"] == 1
        assert summary["digest"] == reducer.restart_reconciliations_claim_digest(projection)
        assert summary["operations"][0]["reports"][0]["reported_state"] == "unavailable"
        assert summary["operations"][0]["reports"][0]["prior_effect_boot_id"] == (
            projection.effect_intents[next(iter(projection.effect_intents))].receiver_boot_id
        )
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, "_V3_TYPE_VALIDATORS", {
            key: value for key, value in records._V3_TYPE_VALIDATORS.items()
            if key[0] not in records.RESTART_RECONCILIATION_EVENT_TYPES_V3
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == "journal_schema_unsupported"
        finally:
            older.close()
