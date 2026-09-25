"""V1 resume cannot release a restart hold over later private claims."""

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_store, recovery_journal
from tests.test_initial_reservation_intent_journal import JOURNAL, admitted, plan, stamp
from tests.test_reconciliation_claim_journal import _apply, _mutation_ready


def _restart(projection, history):
    planned = reducer.plan_restart(
        projection, event_id="00000000-0000-0000-0000-000000000901",
        stamp=records.Stamp("recovery-boot", stamp(30).wall_time, 1),
        anchor_lag=0, wal_found=None,
    )
    return _apply(projection, history, planned)


def _resume_record(projection):
    return records.seal(
        records.Draft(
            event_id="00000000-0000-0000-0000-000000000902",
            event_type="operator_action", actor="operator", ids={},
            data={
                "action": "resume", "rule": records.RESUME_RULE,
                "hold": "restart_recovery",
                "since_commit_seq": projection.dispatch_holds["restart_recovery"],
                "inspected": {
                    "commit_seq": projection.boot_recovered.commit_seq,
                    "event_seq": projection.boot_recovered.event_seq,
                    "record_digest": projection.boot_recovered.record_digest,
                },
                "pending_digest": reducer.pending_digest(projection),
                "operator": "operator-a", "reason": "reviewed",
            },
        ),
        records.Position(
            journal_generation=projection.generation,
            event_seq=projection.head.event_seq + 1,
            commit_seq=projection.head.commit_seq + 1,
            commit_index=0, commit_size=1,
            prev_record_digest=projection.head.record_digest,
        ),
        records.Stamp("recovery-boot", stamp(31).wall_time, 2),
    )


def test_effect_intent_blocks_planning_and_a_forged_v1_resume_on_replay():
    projection, history = _mutation_ready()
    history = _restart(projection, history)
    assert len(projection.effect_intents) == 1
    assert reducer.private_claims_outstanding(projection)
    assert projection.dispatch_holds == {"restart_recovery": projection.head.commit_seq}
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.plan_operator_resume(
            projection, event_id="resume", stamp=records.Stamp(
                "recovery-boot", stamp(31).wall_time, 2,
            ), operator="operator-a", reason="reviewed",
        )
    forged = _resume_record(projection)
    assert records.open_record(forged.body) == forged
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (forged,))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.replay(history + (forged,))


def test_initial_reservation_claim_alone_blocks_v1_resume():
    projection, history, _ = admitted()
    history = _apply(projection, history, plan(projection))
    history = _restart(projection, history)
    assert projection.initial_intents
    assert not projection.effect_intents
    assert reducer.private_claims_outstanding(projection)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (_resume_record(projection),))


def test_live_open_preserves_restart_hold_and_no_resume_receipt(tmp_path):
    _projection, history = _mutation_ready()
    directory = tmp_path / "journal"
    directory.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        stored.append(history[1:3], sync_directory=False)
        for record in history[3:]:
            stored.append((record,), sync_directory=False)
    finally:
        stored.close()
    token = recovery_journal.inspect_recovery_journal(directory).report["journal"]["head"]["record_digest"]
    opened = recovery_journal.open_recovery_journal(
        directory, resume=recovery_journal.ResumeRequest(token=token, operator="operator-a"),
    )
    try:
        assert opened.state == "ready"
        assert opened.dispatch_holds == ("restart_recovery",)
        assert opened.resumed_this_boot is None
        assert [record.event_type for record in opened._store.rows()][-1] == "restart_recovery"
        assert opened.snapshot()["effect_claims"]["intents"] == 1
    finally:
        opened.close()


def test_persisted_unsafe_resume_fails_verified_open(tmp_path):
    projection, history = _mutation_ready()
    history = _restart(projection, history)
    forged = _resume_record(projection)
    directory = tmp_path / "journal"
    directory.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        stored.append(history[1:3], sync_directory=False)
        for record in history[3:] + (forged,):
            stored.append((record,), sync_directory=False)
    finally:
        stored.close()
    opened = recovery_journal.open_recovery_journal(directory)
    try:
        assert opened.hold == ("journal_replay_mismatch", "recovery")
        assert opened.resumed_this_boot is None
    finally:
        opened.close()
