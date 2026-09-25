"""Jira OPS reconciliation observations remain replayable, unqualified claims."""

from dataclasses import replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_store, recovery_journal
from tests.test_effect_claim_journal import _intent, _released
from tests.test_initial_reservation_intent_journal import JOURNAL, stamp


def _apply(projection, history, planned):
    assert isinstance(planned, reducer.Plan)
    assert records.open_record(planned.records[0].body) == planned.records[0]
    reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
    return history + planned.records


def _mutation_ready(*, route_id="jira.issue.update"):
    projection, history = _released()
    service = ("anthropic" if route_id == "anthropic.messages" else
               "grafana" if route_id == "metrics_range" else "jira")
    grant = next(row for row in projection.launch_claim.grants if row[0] == service)
    history = _apply(projection, history, _intent(
        projection, route_id=route_id, service=service,
        grant_id=grant[3], scope_digest=grant[2],
    ))
    return projection, history


def _observation(projection, number=0, **changes):
    fields = {
        "event_id": f"00000000-0000-0000-0000-{0x901 + number:012x}",
        "operation_id": next(iter(projection.effect_intents)),
        "reported_state": "unavailable", "source_evidence_digest": "c" * 64,
        "version_digest": None, "stamp": stamp(14 + number),
    }
    fields.update(changes)
    return reducer.plan_reconciliation_observation(projection, **fields)


def test_append_only_conflicting_reports_stay_unqualified():
    projection, history = _mutation_ready()
    prior_effect_digest = reducer.effect_intents_claim_digest(projection)
    for number, state in enumerate(("unavailable", "confirmed", "absent", "conflict")):
        plan = _observation(
            projection, number, reported_state=state,
            version_digest=("d" * 64 if state in ("confirmed", "conflict") else None),
        )
        assert plan.outcome["state"] == "reconciliation_unqualified"
        history = _apply(projection, history, plan)
        replayed = reducer.replay(history)
        assert replayed.reconciliation_observations == projection.reconciliation_observations
        assert reducer.reconciliation_observations_claim_digest(replayed) == (
            reducer.reconciliation_observations_claim_digest(projection)
        )
    claims = next(iter(projection.reconciliation_observations.values()))
    assert [claim.reported_state for claim in claims] == [
        "unavailable", "confirmed", "absent", "conflict",
    ]
    assert reducer.effect_intents_claim_digest(projection) == prior_effect_digest
    assert records.RECONCILIATION_RECORD_CLASS_V3 == {
        "reconciliation_observation": "recovery",
    }
    assert not hasattr(recovery_journal.RecoveryJournal, "record_reconciliation_observation")


@pytest.mark.parametrize("route_id", [
    "jira.issue.get", "anthropic.messages", "metrics_range",
])
def test_non_jira_mutation_routes_cannot_claim_ops_reconciliation(route_id):
    projection, history = _mutation_ready(route_id=route_id)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _observation(projection)
    assert reducer.replay(history).reconciliation_observations == {}


@pytest.mark.parametrize(("route_id", "source_kind"), [
    ("jira.issue.create", "jira_issue_readback"),
    ("jira.issue.update", "jira_issue_readback"),
    ("jira.transition", "jira_issue_readback"),
    ("jira.comment.add", "jira_comment_readback"),
])
def test_closed_route_to_source_mapping(route_id, source_kind):
    projection, history = _mutation_ready(route_id=route_id)
    plan = _observation(projection)
    assert plan.records[0].data["source_kind"] == source_kind
    history = _apply(projection, history, plan)
    assert len(reducer.replay(history).reconciliation_observations) == 1


def test_wrong_version_and_forged_fields_are_rejected():
    projection, _ = _mutation_ready()
    for bad in (
        {"reported_state": "confirmed", "version_digest": None},
        {"reported_state": "absent", "version_digest": "d" * 64},
        {"reported_state": "resolved"},
        {"source_evidence_digest": "not-a-digest"},
    ):
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            _observation(projection, **bad)
    plan = _observation(projection)
    for field, value in (
        ("based_on_record_digest", "f" * 64),
        ("target_digest", "f" * 64),
        ("source_kind", "jira_comment_readback"),
        ("observation_index", 2),
    ):
        data = records.thaw(plan.records[0].data)
        data[field] = value
        forged = records.seal(records.Draft(
            plan.records[0].event_id, "reconciliation_observation", "receiver",
            plan.records[0].ids, data,
        ), plan.records[0].position, plan.records[0].stamp, schema_version=3)
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            reducer.verify_commit(projection, (forged,))
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            reducer.verify_commit(projection, (replace(plan.records[0], data=data),))


def test_count_recovery_byte_cap_late_append_and_restart_refusal():
    projection, history = _mutation_ready()
    first = _observation(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes
    assert isinstance(_observation(projection), reducer.Plan)
    projection.logical_bytes = projection.bounds.total_bytes - first.charge + 1
    assert isinstance(_observation(projection), reducer.CapacityRefusal)
    projection, history = _mutation_ready()
    for number in range(4):
        history = _apply(projection, history, _observation(
            projection, number, stamp=stamp(projection.launch_claim.hard_deadline_us + number + 1),
        ))
    refusal = _observation(projection, 4, stamp=stamp(
        projection.launch_claim.hard_deadline_us + 5,
    ))
    assert isinstance(refusal, reducer.CapacityRefusal)
    assert refusal.code == "capacity_reconciliation_claims"
    assert len(reducer.replay(history).reconciliation_observations[
        next(iter(projection.effect_intents))
    ]) == 4
    restarted = reducer.plan_restart(
        projection, event_id="reconciliation-restart",
        stamp=records.Stamp("new-boot", stamp(40).wall_time, 1),
        anchor_lag=0, wal_found=None,
    )
    _apply(projection, history, restarted)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _observation(projection, 5, stamp=records.Stamp(
            "new-boot", stamp(41).wall_time, 2,
        ))


def test_stopped_live_inspection_and_old_decoder(tmp_path, monkeypatch):
    projection, history = _mutation_ready()
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
    for summary in (stopped.report["journal"]["reconciliation_claims"],
                    live["reconciliation_claims"]):
        assert summary["state"] == "reconciliation_unqualified"
        assert summary["count"] == 1
        assert summary["digest"] == reducer.reconciliation_observations_claim_digest(projection)
        assert summary["operations"][0]["reported_states"] == ["unavailable"]
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, "_V3_TYPE_VALIDATORS", {
            key: value for key, value in records._V3_TYPE_VALIDATORS.items()
            if key[0] not in records.RECONCILIATION_EVENT_TYPES_V3
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == "journal_schema_unsupported"
        finally:
            older.close()
