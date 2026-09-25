"""Cleanup claims are replayable but never evidence of a real callback."""

from dataclasses import replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_store, recovery_journal
from tests.test_initial_reservation_intent_journal import JOURNAL, stamp
from tests.test_launch_claim_journal import _intended as _run_intended
from tests.test_launch_claim_journal import _launch
from tests.test_spawn_release_claim_journal import (
    _attestation,
    _attested,
    _intended_release,
    _intent,
    _observation,
    _ready,
)


def _action(projection, number=0, *, kind="revoke_grant", grant=None, **changes):
    grant = grant or projection.launch_claim.grants[0]
    fields = {
        "event_id": f"00000000-0000-0000-0000-{0x400 + number:012x}",
        "action_id": f"00000000-0000-0000-0000-{0x500 + number:012x}",
        "action_kind": kind,
        "service": grant[0] if kind == "revoke_grant" else None,
        "grant_id": grant[3] if kind == "revoke_grant" else None,
        "stamp": stamp(12 + number),
    }
    fields.update(changes)
    return reducer.plan_supervision_action_intent(projection, **fields)


def _result(projection, number=0, **changes):
    fields = {
        "event_id": f"00000000-0000-0000-0000-{0x600 + number:012x}",
        "action_id": f"00000000-0000-0000-0000-{0x500 + number:012x}",
        "claimed_outcome": "acknowledged", "stamp": stamp(13 + number),
    }
    fields.update(changes)
    return reducer.plan_supervision_action_result(projection, **fields)


def _apply(projection, history, planned):
    assert isinstance(planned, reducer.Plan)
    assert records.open_record(planned.records[0].body) == planned.records[0]
    reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
    return history + planned.records


def test_revoke_and_result_replay_are_unqualified_and_have_no_writer():
    projection, history = _ready()
    intent = _action(projection)
    assert intent.outcome["state"] == "supervision_actions_unqualified"
    history = _apply(projection, history, intent)
    assert reducer.replay(history).supervision_action_intents == projection.supervision_action_intents
    result = _result(projection)
    history = _apply(projection, history, result)
    replayed = reducer.replay(history)
    assert replayed.supervision_action_results == projection.supervision_action_results
    assert records.SUPERVISION_ACTION_RECORD_CLASS_V3 == {
        "supervision_action_intent": "recovery",
        "supervision_action_result": "recovery",
    }
    assert not hasattr(recovery_journal.RecoveryJournal, "record_supervision_action_intent")
    assert not hasattr(recovery_journal.RecoveryJournal, "record_supervision_action_result")


def test_pre_release_cleanup_blocks_new_release_intent():
    projection, history = _attested()
    history = _apply(projection, history, _action(projection))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, stamp=stamp(14))
    assert reducer.replay(history).release_intent is None


def test_release_unknown_cleanup_allows_historical_observation_but_blocks_effect():
    projection, history = _intended_release()
    for number, grant in enumerate(projection.launch_claim.grants):
        history = _apply(projection, history, _action(projection, number, grant=grant))
    signal = _action(projection, 5, kind="signal_interrupt")
    assert signal.records[0].data["phase"] == "release_unknown"
    assert len(signal.records[0].data["prior_revoke_action_ids"]) == len(
        projection.launch_claim.grants
    )
    history = _apply(projection, history, signal)
    history = _apply(projection, history, _observation(projection, stamp=stamp(18)))
    from tests.test_effect_claim_journal import _intent as effect_intent
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        effect_intent(projection, stamp=stamp(19))
    replayed = reducer.replay(history)
    assert replayed.release_observation is not None
    assert replayed.supervision_action_intents == projection.supervision_action_intents


def test_signal_claims_require_attestation_and_all_revoke_intents():
    projection, _ = _ready()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _action(projection, kind="signal_interrupt")
    projection, history = _attested()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _action(projection, kind="signal_interrupt")
    for number, grant in enumerate(projection.launch_claim.grants):
        history = _apply(projection, history, _action(projection, number, grant=grant))
    signal = _action(projection, 5, kind="signal_kill")
    assert signal.records[0].data["phase"] == "blocked_pre_release"
    history = _apply(projection, history, signal)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _action(projection, 6, kind="signal_interrupt")
    assert len(reducer.replay(history).supervision_action_intents) == (
        len(projection.launch_claim.grants) + 1
    )


def test_hold_and_late_result_do_not_clear_cleanup_stop():
    projection, history = _ready()
    refusal = reducer.CapacityRefusal(
        "capacity_bytes", projection.bounds.ordinary_bytes, projection.logical_bytes,
        projection.bounds.ordinary_bytes - projection.logical_bytes + 1,
    )
    held = reducer.plan_capacity_hold(
        projection, refusal, event_id="action-held", stamp=stamp(10),
        refused_source_digest="d" * 64,
    )
    history = _apply(projection, history, held)
    planned = _action(projection)
    assert planned.outcome["state"] == "supervision_actions_unqualified"
    history = _apply(projection, history, planned)
    result = _result(
        projection, stamp=stamp(projection.launch_claim.hard_deadline_us + 1),
    )
    history = _apply(projection, history, result)
    replayed = reducer.replay(history)
    assert "capacity_bytes" in replayed.dispatch_holds
    assert len(replayed.supervision_action_results) == 1


def test_recomputed_predecessor_and_invalid_outcome_are_rejected():
    projection, _ = _ready()
    planned = _action(projection)
    record = planned.records[0]
    data = records.thaw(record.data)
    data["based_on_record_digest"] = "f" * 64
    forged = records.seal(
        records.Draft(record.event_id, record.event_type, record.actor,
                      record.ids, data), record.position, record.stamp,
        schema_version=3,
    )
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (forged,))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (replace(record, data=data),))
    _apply(projection, (), planned)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _result(projection, claimed_outcome="requested")


def test_restart_does_not_adopt_prior_boot_action_result():
    projection, history = _ready()
    history = _apply(projection, history, _action(projection))
    restarted = reducer.plan_restart(
        projection, event_id="action-restart",
        stamp=records.Stamp("new-boot", stamp(20).wall_time, 1),
        anchor_lag=0, wal_found=None,
    )
    history = _apply(projection, history, restarted)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _result(
            projection,
            stamp=records.Stamp("new-boot", stamp(21).wall_time, 2),
        )
    assert len(reducer.replay(history).supervision_action_intents) == 1


def test_count_capacity_and_recovery_bytes():
    projection, history = _attested()
    first = _action(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes
    assert not isinstance(_action(projection), reducer.CapacityRefusal)
    projection.logical_bytes = projection.bounds.total_bytes - first.charge + 1
    assert isinstance(_action(projection), reducer.CapacityRefusal)
    projection, history = _attested()
    for number, grant in enumerate(projection.launch_claim.grants):
        history = _apply(projection, history, _action(projection, number, grant=grant))
    history = _apply(projection, history, _action(projection, 5, kind="signal_interrupt"))
    history = _apply(projection, history, _action(projection, 6, kind="signal_kill"))
    limit = len(projection.launch_claim.grants) + 2
    assert len(projection.supervision_action_intents) == limit
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _action(projection, 7)
    assert len(reducer.replay(history).supervision_action_intents) == limit


def test_maximal_opaque_fields_fit_record_ceiling():
    projection, _, _ = _run_intended(five=True)
    _apply(projection, (), _launch(projection))
    _apply(projection, (), _attestation(projection))
    for number, grant in enumerate(projection.launch_claim.grants):
        _apply(projection, (), _action(projection, number, grant=grant))
    intent = _action(projection, 5, kind="signal_interrupt").records[0]
    data = records.thaw(intent.data)
    for key in ("receiver_boot_id", "forwarder_generation",
                "witness_locator"):
        data[key] = "a" * records.MAX_ID_BYTES
    maximal = records.seal(
        records.Draft(intent.event_id, intent.event_type, intent.actor,
                      intent.ids, data),
        records.Position(records.MAX_GENERATION, records.MAX_SEQ, records.MAX_SEQ,
                         0, 1, "f" * 64),
        records.Stamp("b" * records.MAX_ID_BYTES,
                      "9999-12-31T23:59:59.999999Z", records.MAX_SEQ - 1),
        schema_version=3,
    )
    assert len(data["prior_revoke_action_ids"]) == 5
    assert len(maximal.body) <= records.MAX_SUPERVISION_ACTION_INTENT_RECORD_BYTES
    _apply(projection, (), _action(projection, 5, kind="signal_interrupt"))
    result = _result(projection, 5, claimed_outcome="requested").records[0]
    result_data = records.thaw(result.data)
    result_data["receiver_boot_id"] = "b" * records.MAX_ID_BYTES
    maximal_result = records.seal(
        records.Draft(result.event_id, result.event_type, result.actor,
                      result.ids, result_data),
        records.Position(records.MAX_GENERATION, records.MAX_SEQ, records.MAX_SEQ,
                         0, 1, "f" * 64),
        records.Stamp("b" * records.MAX_ID_BYTES,
                      "9999-12-31T23:59:59.999999Z", records.MAX_SEQ - 1),
        schema_version=3,
    )
    assert len(maximal_result.body) <= records.MAX_SUPERVISION_ACTION_RESULT_RECORD_BYTES


def test_stopped_live_inspection_and_old_decoder(tmp_path, monkeypatch):
    projection, history = _ready()
    history = _apply(projection, history, _action(projection))
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
    expected = {
        "intents": 1, "results": 0, "unmatched_intents": 1,
        "intents_digest": reducer.supervision_action_intents_claim_digest(projection),
        "results_digest": reducer.supervision_action_results_claim_digest(projection),
        "state": "supervision_actions_unqualified",
        "trigger_and_due_time": "unqualified",
    }
    assert stopped.report["journal"]["supervision_action_claims"] == expected
    assert live["supervision_action_claims"] == expected
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, "_V3_TYPE_VALIDATORS", {
            key: value for key, value in records._V3_TYPE_VALIDATORS.items()
            if key[0] not in records.SUPERVISION_ACTION_EVENT_TYPES_V3
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == "journal_schema_unsupported"
        finally:
            older.close()
