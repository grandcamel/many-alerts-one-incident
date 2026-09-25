"""Unqualified spawn/release journal claims cannot create launch authority."""

from dataclasses import replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_store, recovery_journal
from tests.test_initial_reservation_intent_journal import JOURNAL, stamp
from tests.test_launch_claim_journal import _intended, _launch

ATTEST_ID = "00000000-0000-0000-0000-000000000041"
INTENT_ID = "00000000-0000-0000-0000-000000000042"
OBSERVED_ID = "00000000-0000-0000-0000-000000000043"


def _ready():
    projection, history, _ = _intended()
    launch = _launch(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, launch.records))
    return projection, history + launch.records


def _attestation(projection, **changes):
    fields = {
        "event_id": ATTEST_ID, "blocked_ack_digest": "a" * 64,
        "anchor_key_digest": "b" * 64, "witness_kind": "stable_witness",
        "verifier_version": "v1", "witness_locator": "opaque_locator",
        "witness_identity_digest": "c" * 64,
        "registry_entry_digest": "d" * 64, "stamp": stamp(9),
    }
    fields.update(changes)
    return reducer.plan_spawn_attestation(projection, **fields)


def _attested():
    projection, history = _ready()
    attestation = _attestation(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, attestation.records))
    return projection, history + attestation.records


def _activations(projection, *, at=10):
    return tuple(
        (name, grant_id, "e" * 64, at)
        for name, _claim_id, _scope, grant_id, _expiry in projection.launch_claim.grants
    )


def _intent(projection, **changes):
    fields = {
        "event_id": INTENT_ID, "activated_grants": _activations(projection),
        "stamp": stamp(11),
    }
    fields.update(changes)
    return reducer.plan_release_intent(projection, **fields)


def _intended_release():
    projection, history = _attested()
    intent = _intent(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, intent.records))
    return projection, history + intent.records


def _observation(projection, **changes):
    fields = {"event_id": OBSERVED_ID, "ack_digest": "f" * 64, "stamp": stamp(12)}
    fields.update(changes)
    return reducer.plan_release_observation(projection, **fields)


def test_three_crash_prefixes_replay_as_unqualified_claims():
    projection, history = _ready()
    prior_run_digest = reducer.run_intent_claim_digest(projection)
    prior_launch_digest = reducer.launch_claim_digest(projection)
    for planned, slot, digest in (
        (_attestation(projection), "spawn_attestation", reducer.spawn_attestation_claim_digest),
        (None, "release_intent", reducer.release_intent_claim_digest),
        (None, "release_observation", reducer.release_observation_claim_digest),
    ):
        if planned is None:
            planned = _intent(projection) if slot == "release_intent" else _observation(projection)
        record = planned.records[0]
        assert records.open_record(record.body) == record
        assert planned.outcome["state"] == "outstanding_unqualified_launch_claim"
        reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
        history += planned.records
        replayed = reducer.replay(history)
        assert getattr(replayed, slot) == getattr(projection, slot)
        assert digest(replayed) == digest(projection)
        assert reducer.run_intent_claim_digest(replayed) == prior_run_digest
        assert reducer.launch_claim_digest(replayed) == prior_launch_digest
    assert records.RUN_EVENT_TYPES_V3 == ("run_intent", "launch_claim")
    assert records.SPAWN_RECORD_CLASS_V3 == {
        "spawn_attestation": "ordinary", "release_intent": "ordinary",
        "release_observation": "recovery",
    }
    assert not hasattr(recovery_journal.RecoveryJournal, "record_spawn_attestation")
    assert not hasattr(recovery_journal.RecoveryJournal, "record_release_intent")
    assert not hasattr(recovery_journal.RecoveryJournal, "record_release_observation")


@pytest.mark.parametrize("stage", ["attestation", "intent", "observation"])
def test_recomputed_forged_basis_or_claim_is_rejected(stage):
    projection, _history = {
        "attestation": _ready, "intent": _attested,
        "observation": _intended_release,
    }[stage]()
    planned = {
        "attestation": _attestation, "intent": _intent,
        "observation": _observation,
    }[stage](projection)
    record = planned.records[0]
    data = records.thaw(record.data)
    data["based_on_record_digest"] = "f" * 64
    forged = records.seal(
        records.Draft(record.event_id, record.event_type, record.actor, record.ids, data),
        record.position, record.stamp, schema_version=3,
    )
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (forged,))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        reducer.verify_commit(projection, (replace(record, data=data),))


def test_pre_release_order_identity_hold_boot_and_deadline():
    projection, _ = _ready()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection, event_id=projection.launch_claim.launch_claim_id)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection, stamp=stamp(projection.launch_claim.work_deadline_us))
    projection.dispatch_holds["restart_recovery"] = projection.head.commit_seq
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection)
    projection.dispatch_holds.clear()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection, stamp=records.Stamp("other-boot", stamp(9).wall_time, 9))
    attestation = _attestation(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, attestation.records))
    bad = list(_activations(projection))
    bad[0] = (*bad[0][:3], 8)
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, activated_grants=tuple(bad))
    bad = list(_activations(projection))
    bad[0] = (bad[1][0], *bad[0][1:])
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, activated_grants=tuple(bad))
    projection.dispatch_holds["restart_recovery"] = projection.head.commit_seq
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection)


def test_claim_phase_replay_and_activation_deadline_rejections():
    projection, _ = _ready()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection)
    attestation = _attestation(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, attestation.records))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection, event_id="00000000-0000-0000-0000-000000000045",
                     stamp=stamp(10))
    bad = list(_activations(projection))
    bad[0] = (*bad[0][:3], projection.launch_claim.grants[0][4])
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, activated_grants=tuple(bad), stamp=stamp(bad[0][3]))
    bad = list(_activations(projection, at=12))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, activated_grants=tuple(bad))
    intent = _intent(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, intent.records))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _intent(projection, event_id="00000000-0000-0000-0000-000000000045",
                stamp=stamp(12))
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _observation(projection, stamp=stamp(10))


def test_original_member_supersession_blocks_pre_release():
    projection, _ = _ready()
    projection.pending.clear()
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _attestation(projection)


def test_maximal_legal_opaque_fields_fit_private_record_caps():
    projection, _ = _ready()
    attestation = _attestation(projection)
    record = attestation.records[0]
    data = records.thaw(record.data)
    for key in ("witness_kind", "verifier_version", "witness_locator"):
        data[key] = "a" * records.MAX_ID_BYTES
    maximal = records.seal(
        records.Draft(record.event_id, record.event_type, record.actor, record.ids, data),
        record.position, record.stamp, schema_version=3,
    )
    assert len(maximal.body) <= records.MAX_SPAWN_ATTESTATION_RECORD_BYTES
    reducer.apply_delta(projection, reducer.verify_commit(projection, (record,)))
    intent = _intent(projection).records[0]
    data = records.thaw(intent.data)
    data["forwarder_generation"] = "b" * records.MAX_ID_BYTES
    for index, item in enumerate(data["activated_grants"]):
        item["grant_id"] = str(index) * records.MAX_ID_BYTES
    maximal = records.seal(
        records.Draft(intent.event_id, intent.event_type, intent.actor, intent.ids, data),
        intent.position, intent.stamp, schema_version=3,
    )
    assert len(maximal.body) <= records.MAX_RELEASE_INTENT_RECORD_BYTES
    reducer.apply_delta(projection, reducer.verify_commit(projection, (intent,)))
    observation = _observation(projection).records[0]
    data = records.thaw(observation.data)
    data["receiver_boot_id"] = "d" * records.MAX_ID_BYTES
    maximal = records.seal(
        records.Draft(observation.event_id, observation.event_type,
                      observation.actor, observation.ids, data),
        observation.position, observation.stamp, schema_version=3,
    )
    assert len(maximal.body) <= records.MAX_RELEASE_OBSERVATION_RECORD_BYTES


def test_historical_observation_survives_new_hold_and_elapsed_deadline():
    projection, history = _intended_release()
    refusal = reducer.CapacityRefusal(
        "capacity_bytes", projection.bounds.ordinary_bytes, projection.logical_bytes,
        projection.bounds.ordinary_bytes - projection.logical_bytes + 1,
    )
    held = reducer.plan_capacity_hold(
        projection, refusal, event_id="held-after-release", stamp=stamp(12),
        refused_source_digest="a" * 64,
    )
    reducer.apply_delta(projection, reducer.verify_commit(projection, held.records))
    history += held.records
    late = _observation(
        projection, stamp=stamp(projection.launch_claim.hard_deadline_us + 1),
    )
    assert late.outcome["state"] == "outstanding_unqualified_launch_claim"
    reducer.apply_delta(projection, reducer.verify_commit(projection, late.records))
    replayed = reducer.replay(history + late.records)
    assert replayed.release_observation == projection.release_observation
    assert "capacity_bytes" in replayed.dispatch_holds
    with pytest.raises(reducer.ReplayError, match="^replay_mismatch$"):
        _observation(projection, event_id="00000000-0000-0000-0000-000000000044")


def test_ordinary_and_recovery_capacity_are_separate():
    projection, _ = _ready()
    attestation = _attestation(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes - attestation.charge + 1
    assert isinstance(_attestation(projection), reducer.CapacityRefusal)
    projection, _ = _intended_release()
    observation = _observation(projection)
    projection.logical_bytes = projection.bounds.ordinary_bytes
    assert not isinstance(_observation(projection), reducer.CapacityRefusal)
    projection.logical_bytes = projection.bounds.total_bytes - observation.charge + 1
    assert isinstance(_observation(projection), reducer.CapacityRefusal)


def test_stopped_and_live_inspection_keep_claims_unqualified(tmp_path, monkeypatch):
    projection, history = _intended_release()
    observation = _observation(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, observation.records))
    history += observation.records
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
    for name, digest in (
        ("spawn_attestation_claim", reducer.spawn_attestation_claim_digest(projection)),
        ("release_intent_claim", reducer.release_intent_claim_digest(projection)),
        ("release_observation_claim", reducer.release_observation_claim_digest(projection)),
    ):
        expected = {"count": 1, "digest": digest,
                    "state": "outstanding_unqualified_launch_claim"}
        assert stopped.report["journal"][name] == expected
        assert live[name] == expected
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, "_V3_TYPE_VALIDATORS", {
            key: value for key, value in records._V3_TYPE_VALIDATORS.items()
            if key[0] not in records.SPAWN_EVENT_TYPES_V3
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == "journal_schema_unsupported"
        finally:
            older.close()


@pytest.mark.parametrize("phase", [
    "launch_claimed", "attested", "release_intended", "release_observed",
])
def test_inspection_states_each_crash_prefix_explicitly(tmp_path, phase):
    projection, history = _ready()
    if phase in ("attested", "release_intended", "release_observed"):
        planned = _attestation(projection)
        reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
        history += planned.records
    if phase in ("release_intended", "release_observed"):
        planned = _intent(projection)
        reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
        history += planned.records
    if phase == "release_observed":
        planned = _observation(projection)
        reducer.apply_delta(projection, reducer.verify_commit(projection, planned.records))
        history += planned.records
    directory = tmp_path / phase
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
        "claimed_phase": phase,
        "state": "outstanding_unqualified_launch_claim",
        "digest": {
            "launch_claimed": reducer.launch_claim_digest,
            "attested": reducer.spawn_attestation_claim_digest,
            "release_intended": reducer.release_intent_claim_digest,
            "release_observed": reducer.release_observation_claim_digest,
        }[phase](projection),
    }
    assert stopped.report["journal"]["spawn_release_claims"] == expected
    assert live["spawn_release_claims"] == expected
