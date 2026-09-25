"""Private execution claims replay without capture or Run authority."""

from dataclasses import replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_store, recovery_journal
from grafana_jsm_sandbox.run_outcome import ProcessFacts
from tests.test_effect_claim_journal import _intent as _effect_intent
from tests.test_effect_claim_journal import _receipt as _effect_receipt
from tests.test_effect_claim_journal import _released, _with_intent
from tests.test_initial_reservation_intent_journal import JOURNAL, stamp
from tests.test_spawn_release_claim_journal import (
    _attestation,
    _attested,
    _ready,
)
from tests.test_spawn_release_claim_journal import (
    _intent as _release_intent,
)

PROCESS_ID = "00000000-0000-0000-0000-000000000801"
TERMINAL_ID = "00000000-0000-0000-0000-000000000802"
ASSESSMENT_ID = "00000000-0000-0000-0000-000000000803"


def _apply(projection, history, plan):
    assert isinstance(plan, reducer.Plan)
    assert records.open_record(plan.records[0].body) == plan.records[0]
    reducer.apply_delta(projection, reducer.verify_commit(projection, plan.records))
    return history + plan.records


def _process(projection, **changes):
    fields = {
        "event_id": PROCESS_ID,
        "facts": ProcessFacts("accepted", True, 0, None, False, False, "confirmed"),
        "source_digest": "a" * 64, "stamp": stamp(30),
    }
    fields.update(changes)
    return reducer.plan_process_observation(projection, **fields)


def _terminal(projection, **changes):
    fields = {
        "event_id": TERMINAL_ID, "count_class": "one", "quality": "recognized",
        "subtype": "success", "is_error": False, "reason_code": None,
        "usage_state": "known", "source_digest": "b" * 64, "stamp": stamp(31),
    }
    fields.update(changes)
    return reducer.plan_terminal_observation(projection, **fields)


def _assessment(projection, **changes):
    fields = {"event_id": ASSESSMENT_ID, "stamp": stamp(32)}
    fields.update(changes)
    return reducer.plan_execution_assessment(projection, **fields)


def test_three_claims_replay_success_only_as_unqualified():
    projection, history = _ready()
    for plan, slot, digest in (
        (_process(projection), "process_observation",
         reducer.process_observation_claim_digest),
        (None, "terminal_observation", reducer.terminal_observation_claim_digest),
        (None, "execution_assessment", reducer.execution_assessment_claim_digest),
    ):
        if plan is None:
            plan = _terminal(projection) if slot == "terminal_observation" else _assessment(projection)
        assert plan.outcome["state"] == "execution_unqualified"
        history = _apply(projection, history, plan)
        replayed = reducer.replay(history)
        assert getattr(replayed, slot) == getattr(projection, slot)
        assert digest(replayed) == digest(projection)
    assert projection.execution_assessment.assessment.state == "succeeded"
    assert projection.execution_assessment.assessment.usage == "known"
    assert projection.launch_claim is not None
    assert records.EXECUTION_RECORD_CLASS_V3 == {
        "process_observation": "recovery", "terminal_observation": "recovery",
        "execution_assessment": "recovery",
    }
    for method in ("record_process_observation", "record_terminal_observation",
                   "record_execution_assessment"):
        assert not hasattr(recovery_journal.RecoveryJournal, method)


@pytest.mark.parametrize(
    ("terminal", "state", "reason"),
    [
        ({"count_class": "none", "quality": None, "subtype": None,
          "is_error": None, "usage_state": None, "source_digest": None},
         "incomplete", "missing_terminal"),
        ({"count_class": "multiple", "quality": None, "subtype": None,
          "is_error": None, "usage_state": None},
         "incomplete", "duplicate_terminal"),
        ({"quality": "invalid", "invalidity_code": "field_invalid",
          "subtype": None, "is_error": None, "usage_state": None},
         "incomplete", "terminal_invalid"),
        ({"subtype": "error", "is_error": True, "reason_code": "runtime_error"},
         "failed", "result_error"),
    ],
)
def test_terminal_classes_preserve_classifier_precedence(terminal, state, reason):
    projection, history = _ready()
    history = _apply(projection, history, _process(projection))
    history = _apply(projection, history, _terminal(projection, **terminal))
    history = _apply(projection, history, _assessment(projection))
    assessment = projection.execution_assessment.assessment
    assert assessment.state == state
    assert reason in assessment.reasons
    assert reducer.replay(history).execution_assessment.assessment == assessment


def test_process_failure_precedence_and_attestation_conflict():
    projection, history = _ready()
    failed = ProcessFacts("failed_before_process", False, None, None,
                          False, False, "unknown")
    history = _apply(projection, history, _process(projection, facts=failed))
    history = _apply(projection, history, _terminal(projection))
    history = _apply(projection, history, _assessment(projection))
    assert projection.execution_assessment.assessment.never_started is True
    assert projection.execution_assessment.assessment.state == "failed"
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection, stamp=stamp(33))
    attested, _ = _attested()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _process(attested, facts=failed)
    contained, _ = _ready()
    facts = ProcessFacts("accepted", True, 0, None, True, False, "failed")
    _apply(contained, (), _process(contained, facts=facts))
    _apply(contained, (), _terminal(contained))
    _apply(contained, (), _assessment(contained))
    assert contained.execution_assessment.assessment.state == "containment_failed"


def test_process_closeout_stops_new_positive_claims_but_keeps_receipts():
    projection, history = _ready()
    history = _apply(projection, history, _process(projection))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection, stamp=stamp(31))
    attested, history = _attested()
    history = _apply(attested, history, _process(attested))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _release_intent(attested, stamp=stamp(31))
    released, history = _released()
    history = _apply(released, history, _process(released))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _effect_intent(released, stamp=stamp(31))
    with_intent, history = _with_intent()
    history = _apply(with_intent, history, _process(with_intent))
    history = _apply(with_intent, history, _effect_receipt(with_intent, stamp=stamp(31)))
    assert len(reducer.replay(history).effect_receipts) == 1


def test_duplicate_order_fields_and_recomputed_forgery_rejected():
    projection, history = _ready()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _terminal(projection)
    history = _apply(projection, history, _process(projection))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _process(projection)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _terminal(projection, reason_code="freeform native output")
    terminal = _terminal(projection)
    data = records.thaw(terminal.records[0].data)
    data["process_digest"] = "f" * 64
    forged = records.seal(records.Draft(
        TERMINAL_ID, "terminal_observation", "receiver", terminal.records[0].ids, data,
    ), terminal.records[0].position, terminal.records[0].stamp, schema_version=3)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (forged,))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (replace(terminal.records[0], data=data),))
    history = _apply(projection, history, terminal)
    assessment = _assessment(projection)
    data = records.thaw(assessment.records[0].data)
    data["state"] = "failed"
    forged = records.seal(records.Draft(
        ASSESSMENT_ID, "execution_assessment", "receiver",
        assessment.records[0].ids, data,
    ), assessment.records[0].position, assessment.records[0].stamp, schema_version=3)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (forged,))
    history = _apply(projection, history, assessment)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _assessment(projection)
    assert reducer.replay(history).execution_assessment.assessment.state == "succeeded"


def test_recovery_capacity_late_history_and_restart_refusal():
    projection, history = _ready()
    first = _process(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes
    assert isinstance(_process(projection), reducer.Plan)
    projection.logical_bytes = projection.bounds.total_bytes - first.charge + 1
    assert isinstance(_process(projection), reducer.CapacityRefusal)
    projection, history = _ready()
    history = _apply(projection, history, _process(
        projection, stamp=stamp(projection.launch_claim.hard_deadline_us + 1),
    ))
    history = _apply(projection, history, _terminal(
        projection, stamp=stamp(projection.launch_claim.hard_deadline_us + 2),
    ))
    history = _apply(projection, history, _assessment(
        projection, stamp=stamp(projection.launch_claim.hard_deadline_us + 3),
    ))
    assert reducer.replay(history).execution_assessment is not None
    restarted = reducer.plan_restart(
        projection, event_id="execution-restart",
        stamp=records.Stamp("new-boot", stamp(40).wall_time, 1),
        anchor_lag=0, wal_found=None,
    )
    _apply(projection, history, restarted)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _assessment(projection, event_id="00000000-0000-0000-0000-000000000804",
                    stamp=records.Stamp("new-boot", stamp(41).wall_time, 2))


def test_live_stopped_inspection_and_old_decoder(tmp_path, monkeypatch):
    projection, history = _ready()
    history = _apply(projection, history, _process(projection))
    history = _apply(projection, history, _terminal(projection))
    history = _apply(projection, history, _assessment(projection))
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
    for summary in (stopped.report["journal"]["execution_claims"],
                    live["execution_claims"]):
        assert summary["state"] == "execution_unqualified"
        assert summary["terminal"]["count_class"] == "one"
        assert summary["assessment"]["derived_state"] == "succeeded"
        assert summary["assessment"]["digest"] == (
            reducer.execution_assessment_claim_digest(projection)
        )
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, "_V3_TYPE_VALIDATORS", {
            key: value for key, value in records._V3_TYPE_VALIDATORS.items()
            if key[0] not in records.EXECUTION_EVENT_TYPES_V3
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == "journal_schema_unsupported"
        finally:
            older.close()
