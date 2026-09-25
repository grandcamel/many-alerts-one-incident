"""A replayed effect claim is never a Forwarder permit or trusted receipt."""

from dataclasses import replace

import pytest

from grafana_jsm_sandbox import (
    forwarder_receipts,
    forwarder_routes,
    journal_store,
    recovery_journal,
)
from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from tests.test_initial_reservation_intent_journal import JOURNAL, stamp
from tests.test_spawn_release_claim_journal import _intended_release


def _released():
    projection, history = _intended_release()
    observation = reducer.plan_release_observation(
        projection, event_id="00000000-0000-0000-0000-000000000043",
        ack_digest="f" * 64, stamp=stamp(12),
    )
    reducer.apply_delta(projection, reducer.verify_commit(projection, observation.records))
    return projection, history + observation.records


def _intent(projection, number=0, **changes):
    grant = next(row for row in projection.launch_claim.grants if row[0] == "jira")
    fields = {
        "event_id": f"00000000-0000-0000-0000-{100 + number:012x}",
        "operation_id": f"00000000-0000-0000-0000-{200 + number:012x}",
        "service": "jira", "route_id": "jira.issue.get", "grant_id": grant[3],
        "scope_digest": grant[2], "flight_id": f"flight{number}",
        "forwarder_receipt_id": f"receipt{number}",
        "request_digest": "a" * 64, "target_digest": "b" * 64,
        "expires_us": 1_000_000, "stamp": stamp(13 + number),
    }
    fields.update(changes)
    return reducer.plan_effect_intent(projection, **fields)


def _with_intent():
    projection, history = _released()
    planned = _intent(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
    return projection, history + planned.records


def _receipt(projection, **changes):
    fields = {
        "event_id": "00000000-0000-0000-0000-000000000300",
        "operation_id": "00000000-0000-0000-0000-0000000000c8",
        "claimed_dispatch_state": "NOT_DISPATCHED",
        "claimed_reason": "permit_denied",
        "finalized_receipt_digest": "c" * 64,
        "stamp": stamp(14),
    }
    fields.update(changes)
    return reducer.plan_effect_receipt(projection, **fields)


def test_route_and_receipt_vocabulary_are_pinned_without_reducer_imports():
    assert dict(reducer.EFFECT_ROUTE_SERVICE_V3) == {
        route_id: status.service for route_id, status in forwarder_routes.ROUTE_CATALOG.items()
    }
    assert dict(records.EFFECT_CLAIM_REASONS) == {
        state: frozenset(reasons) for state, reasons in
        forwarder_receipts._REASON_LOCAL_RESPONSE.items()
    }
    assert records.EFFECT_RECORD_CLASS_V3 == {
        "effect_intent": "ordinary", "effect_receipt": "recovery",
    }
    assert forwarder_routes.ROUTE_CATALOG["jira.issue.create"].state == "unavailable"
    assert not hasattr(recovery_journal.RecoveryJournal, "record_effect_intent")
    assert not hasattr(recovery_journal.RecoveryJournal, "record_effect_receipt")


def test_exact_intent_and_receipt_replay_stay_unqualified():
    projection, history = _released()
    intent = _intent(projection)
    assert intent.outcome["state"] == "effects_unqualified"
    assert records.open_record(intent.records[0].body) == intent.records[0]
    reducer.apply_delta(projection, reducer.verify_commit(projection, intent.records))
    history += intent.records
    replayed = reducer.replay(history)
    assert replayed.effect_intents == projection.effect_intents
    assert len(replayed.effect_receipts) == 0
    receipt = _receipt(projection)
    assert receipt.outcome["state"] == "effects_unqualified"
    assert records.open_record(receipt.records[0].body) == receipt.records[0]
    reducer.apply_delta(projection, reducer.verify_commit(projection, receipt.records))
    replayed = reducer.replay(history + receipt.records)
    assert replayed.effect_receipts == projection.effect_receipts
    assert len(replayed.effect_intents) == 1
    assert len(replayed.effect_receipts) == 1
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _receipt(projection, event_id="00000000-0000-0000-0000-000000000301",
                 stamp=stamp(15))


@pytest.mark.parametrize("stage", ["intent", "receipt"])
def test_forged_recomputed_predecessor_is_rejected(stage):
    projection, _history = _released() if stage == "intent" else _with_intent()
    planned = _intent(projection) if stage == "intent" else _receipt(projection)
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


def test_wrong_route_grant_operation_target_and_duplicate_hold():
    projection, _ = _released()
    invalid = (
        {"route_id": "jira.issue.unknown"},
        {"service": "grafana"},
        {"grant_id": "different"},
        {"scope_digest": "f" * 64},
        {"operation_id": projection.launch_claim.run_id},
        {"request_digest": "bad"},
        {"target_digest": "bad"},
        {"flight_id": "bad flight"},
        {"expires_us": 13},
    )
    for changed in invalid:
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            _intent(projection, **changed)
    planned = _intent(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, number=1,
                operation_id="00000000-0000-0000-0000-0000000000c8",
                target_digest="f" * 64, stamp=stamp(14))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, number=1, flight_id="flight0", stamp=stamp(14))


def test_effect_intent_rejects_non_scalar_grant_values_before_comparison():
    class HostileEquality:
        def __eq__(self, other):
            raise AssertionError("untrusted equality ran")

    projection, _ = _released()
    for field in ("grant_id", "scope_digest"):
        with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
            _intent(projection, **{field: HostileEquality()})


def test_64_operation_cap_and_ordinary_capacity():
    projection, _ = _released()
    first = _intent(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes - first.charge + 1
    assert isinstance(_intent(projection), reducer.CapacityRefusal)
    projection, _ = _released()
    for index in range(reducer.MAX_EFFECT_CLAIMS):
        planned = _intent(projection, number=index)
        reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
    assert len(projection.effect_intents) == reducer.MAX_EFFECT_CLAIMS
    held = _intent(projection, number=reducer.MAX_EFFECT_CLAIMS)
    assert held == reducer.CapacityRefusal(
        "capacity_effect_claims", reducer.MAX_EFFECT_CLAIMS,
        reducer.MAX_EFFECT_CLAIMS, 1,
    )


def test_maximal_opaque_fields_fit_private_record_ceilings():
    projection, _ = _released()
    intent = _intent(projection).records[0]
    data = records.thaw(intent.data)
    for key in (
        "receiver_boot_id", "forwarder_generation", "route_id", "grant_id",
        "flight_id", "forwarder_receipt_id",
    ):
        data[key] = "a" * records.MAX_ID_BYTES
    maximal = records.seal(
        records.Draft(intent.event_id, intent.event_type, intent.actor,
                      intent.ids, data), intent.position, intent.stamp,
        schema_version=3,
    )
    assert len(maximal.body) <= records.MAX_EFFECT_INTENT_RECORD_BYTES
    reducer.apply_delta(projection, reducer.verify_commit(projection, (intent,)))
    receipt = _receipt(projection).records[0]
    data = records.thaw(receipt.data)
    for key in ("receiver_boot_id", "grant_id", "flight_id", "forwarder_receipt_id"):
        data[key] = "b" * records.MAX_ID_BYTES
    maximal = records.seal(
        records.Draft(receipt.event_id, receipt.event_type, receipt.actor,
                      receipt.ids, data), receipt.position, receipt.stamp,
        schema_version=3,
    )
    assert len(maximal.body) <= records.MAX_EFFECT_RECEIPT_RECORD_BYTES


def test_late_receipt_after_hold_is_historical_only_and_uses_recovery_capacity():
    projection, history = _with_intent()
    refusal = reducer.CapacityRefusal(
        "capacity_bytes", projection.bounds.ordinary_bytes, projection.logical_bytes,
        projection.bounds.ordinary_bytes - projection.logical_bytes + 1,
    )
    held = reducer.plan_capacity_hold(
        projection, refusal, event_id="effect-held", stamp=stamp(14),
        refused_source_digest="d" * 64,
    )
    reducer.apply_delta(projection, reducer.verify_commit(projection, held.records))
    history += held.records
    late = _receipt(projection, stamp=stamp(projection.launch_claim.hard_deadline_us + 1))
    assert late.outcome["state"] == "effects_unqualified"
    reducer.apply_delta(projection, reducer.verify_commit(projection, late.records))
    replayed = reducer.replay(history + late.records)
    assert "capacity_bytes" in replayed.dispatch_holds
    assert replayed.effect_receipts == projection.effect_receipts
    projection, _ = _with_intent()
    receipt = _receipt(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes
    assert not isinstance(_receipt(projection), reducer.CapacityRefusal)
    projection.logical_bytes = projection.bounds.total_bytes - receipt.charge + 1
    assert isinstance(_receipt(projection), reducer.CapacityRefusal)


@pytest.mark.parametrize("state,reason", [
    ("NOT_DISPATCHED", "connect_failed"),
    ("FAILED", "permit_denied"),
    ("TRANSPORT_CONFIRMED", "write_failed"),
])
def test_receipt_claim_state_reason_pair_must_match_closed_vocabulary(state, reason):
    projection, _ = _with_intent()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _receipt(projection, claimed_dispatch_state=state, claimed_reason=reason)


@pytest.mark.parametrize("with_receipt", [False, True])
def test_stopped_live_and_old_binary_boundaries(tmp_path, monkeypatch, with_receipt):
    projection, history = _with_intent()
    if with_receipt:
        receipt = _receipt(projection)
        reducer.apply_delta(projection, reducer.verify_commit(projection, receipt.records))
        history += receipt.records
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
        "intents": 1, "receipts": int(with_receipt),
        "unmatched_intents": int(not with_receipt),
        "intents_digest": reducer.effect_intents_claim_digest(projection),
        "receipts_digest": reducer.effect_receipts_claim_digest(projection),
        "state": "effects_unqualified",
    }
    assert stopped.report["journal"]["effect_claims"] == expected
    assert live["effect_claims"] == expected
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, "_V3_TYPE_VALIDATORS", {
            key: value for key, value in records._V3_TYPE_VALIDATORS.items()
            if key[0] not in records.EFFECT_EVENT_TYPES_V3
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == "journal_schema_unsupported"
        finally:
            older.close()
