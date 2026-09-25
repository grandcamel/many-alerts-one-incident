"""The first-attempt v3 intent is a replayed claim with no writer or permit."""

from dataclasses import asdict, replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_source as source
from grafana_jsm_sandbox import journal_store, recovery_journal
from grafana_jsm_sandbox.forwarder_json import tagged_digest

JOURNAL = '11111111-1111-1111-1111-111111111111'
ADMISSION = '22222222-2222-2222-2222-222222222222'
JOB = '00000000-0000-0000-0000-000000000010'
INTENT = '33333333-3333-3333-3333-333333333333'
ATTEMPT = '44444444-4444-4444-4444-444444444444'
RESERVATION = '55555555-5555-5555-5555-555555555555'
RUN = '66666666-6666-6666-6666-666666666666'
LEASE = '77777777-7777-7777-7777-777777777777'
FINGERPRINT = '5e8d72dc87b1ff35'


def stamp(mono_us=3):
    return records.Stamp(
        boot_id='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        wall_time='2026-09-25T00:00:00.000000Z', mono_us=mono_us,
    )


def admitted():
    p = reducer.new_projection()
    genesis = reducer.plan_genesis(
        journal_uuid=JOURNAL, bounds=reducer.JournalBounds(),
        event_id='genesis', stamp=stamp(),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, genesis.records))
    item = source.SourceRecord(
        source_group=source.source_group_digest('initial-intent-test'),
        alerts=(source.SourceAlert(FINGERPRINT, 'firing', None, None),),
        truncated_alerts=0, body_digest='a' * 64,
        provenance=source.HTTP_PROVENANCE,
    )
    admission = reducer.plan_admission(
        p, item, admission_id=ADMISSION, dedupe_event_id='dedupe-1',
        stamp=stamp(4),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, admission.records))
    return p, genesis.records + admission.records, item


def plan(p, **overrides):
    fields = {
        'job_id': JOB, 'admission_id': ADMISSION, 'intent_id': INTENT,
        'attempt_id': ATTEMPT, 'reservation_id': RESERVATION,
        'run_id': RUN, 'lease_id': LEASE, 'stamp': stamp(5),
    }
    fields.update(overrides)
    return reducer.plan_initial_reservation_intent(p, **fields)


def test_v3_record_is_private_bounded_and_canonical():
    p, _, _ = admitted()
    record = plan(p).records[0]
    assert record.schema_version == 3
    assert len(record.body) <= 2048
    assert records.open_record(record.body) == record
    assert records.SCHEMA_VERSIONS == frozenset({1})
    assert 'reservation_intent' not in records.REGISTERED_EVENT_TYPES
    assert records.RESERVATION_RECORD_CLASS_V3['reservation_intent'] == 'ordinary'
    with pytest.raises(records.RecordError, match='^record_unsupported$'):
        records.seal(
            records.Draft(record.event_id, record.event_type, record.actor,
                          record.ids, record.data),
            record.position, record.stamp, schema_version=4,
        )


def test_initial_claim_replays_with_a_separate_digest_and_no_authority():
    p, history, _ = admitted()
    old_v1_digest = reducer.state_digest(p)
    old_v2_digest = reducer.reservation_claims_digest(p)
    initial = plan(p)
    member_digest = tagged_digest('rj.initial-intent-members.v3', (FINGERPRINT,))
    assert initial.records[0].data['member_digest'] == member_digest
    assert initial.records[0].data['intent_digest'] == tagged_digest(
        'rj.reservation-intent.v3', {
            'journal_uuid': JOURNAL, 'journal_generation': 1,
            'admission_id': ADMISSION, 'job_id': JOB, 'intent_id': INTENT,
            'attempt_id': ATTEMPT, 'reservation_id': RESERVATION,
            'run_id': RUN, 'lease_id': LEASE,
            'based_on_commit_seq': p.head.commit_seq,
            'member_count': 1, 'member_digest': member_digest,
        },
    )
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    replayed = reducer.replay(history + initial.records)
    assert replayed.initial_intents == p.initial_intents
    assert reducer.initial_intents_digest(replayed) == reducer.initial_intents_digest(p)
    assert reducer.initial_intents_digest(p) == tagged_digest(
        'rj.initial-intents.v3', [asdict(p.initial_intents[INTENT])],
    )
    assert reducer.reservation_claims_digest(p) == old_v2_digest
    assert reducer.state_digest(p) != old_v1_digest  # same formula, new head
    assert 'permit' not in initial.outcome and 'ready' not in initial.outcome


@pytest.mark.parametrize('field,value', [
    ('job_id', 'job-1'), ('attempt_id', JOB), ('intent_id', JOURNAL),
    ('reservation_id', ADMISSION), ('run_id', ATTEMPT), ('lease_id', RUN),
])
def test_bad_or_colliding_identity_refuses_without_a_record(field, value):
    p, _, _ = admitted()
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan(p, **{field: value})


def test_v3_validator_rejects_actor_shape_and_body_cap(monkeypatch):
    p, _, _ = admitted()
    record = plan(p).records[0]
    draft = records.Draft(record.event_id, record.event_type, record.actor,
                          record.ids, record.data)
    with pytest.raises(records.RecordError, match='^record_field$'):
        records.seal(replace(draft, actor='spawner'), record.position,
                     record.stamp, schema_version=3)
    with pytest.raises(records.RecordError, match='^record_field$'):
        records.seal(replace(draft, data=dict(record.data, permit=True)),
                     record.position, record.stamp, schema_version=3)
    envelope = records.verify_body(record.body, record.record_digest)
    monkeypatch.setattr(records, 'MAX_RUN_HOLD_RECORD_BYTES', len(record.body) - 1)
    with pytest.raises(records.RecordError, match='^record_too_large$'):
        records.decode_record(envelope, record.body, record.record_digest)


@pytest.mark.parametrize('change', [
    {'intent_digest': 'f' * 64}, {'member_digest': 'f' * 64},
    {'member_count': 2}, {'based_on_commit_seq': 1},
])
def test_resigned_computed_field_is_rejected_by_replay(change):
    p, _, _ = admitted()
    original = plan(p).records[0]
    forged = records.seal(
        records.Draft(original.event_id, original.event_type, original.actor,
                      original.ids, dict(original.data, **change)),
        original.position, original.stamp, schema_version=3,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(p, (forged,))


def test_global_holds_and_a_prior_initial_claim_refuse_another_job():
    p, _, _ = admitted()
    p.dispatch_holds['restart_recovery'] = 1
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan(p)
    p.dispatch_holds.clear()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan(p, job_id='88888888-8888-8888-8888-888888888888',
             intent_id='99999999-9999-9999-9999-999999999999', stamp=stamp(6))


def test_v2_hold_then_v3_claim_is_refused_and_v3_then_v2_intent_is_refused():
    p, _, _ = admitted()
    held = reducer.plan_run_hold(
        p, job_id=JOB, admission_id=ADMISSION, event_id='hold-1',
        reason='accounting_unavailable', stamp=stamp(5),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, held.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan(p, stamp=stamp(6))

    fresh, _, _ = admitted()
    initial = plan(fresh)
    reducer.apply_delta(fresh, reducer.verify_commit(fresh, initial.records))
    recovery_hold = reducer.plan_run_hold(
        fresh, job_id=JOB, admission_id=ADMISSION, event_id='hold-2',
        reason='restart_recovery', stamp=stamp(6),
    )
    reducer.apply_delta(fresh, reducer.verify_commit(fresh, recovery_hold.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.plan_reservation_intent(
            fresh, job_id=JOB, admission_id=ADMISSION,
            intent_id='99999999-9999-9999-9999-999999999999',
            attempt_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            reservation_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
            run_id='dddddddd-dddd-dddd-dddd-dddddddddddd',
            lease_id='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', stamp=stamp(7),
        )


def test_recovery_hold_cannot_claim_v3_admission_under_another_job():
    p, _, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.plan_run_hold(
            p, job_id='88888888-8888-8888-8888-888888888888',
            admission_id=ADMISSION, event_id='hold-other',
            reason='restart_recovery', stamp=stamp(6),
        )
    exact = reducer.plan_run_hold(
        p, job_id=JOB, admission_id=ADMISSION, event_id='hold-exact',
        reason='restart_recovery', stamp=stamp(6),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, exact.records))
    assert p.run_holds[JOB].admission_id == ADMISSION


def test_initial_claim_cannot_spend_recovery_reserve():
    p, _, _ = admitted()
    charge = plan(p).charge
    p.logical_bytes = p.bounds.ordinary_bytes - charge + 1
    held = plan(p)
    assert isinstance(held, reducer.CapacityRefusal)
    assert (held.code, held.limit) == ('capacity_bytes', p.bounds.ordinary_bytes)
    assert p.logical_bytes < p.bounds.total_bytes


def test_mixed_history_reopens_and_older_decoder_refuses_v3(tmp_path, monkeypatch):
    p, history, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    hold = reducer.plan_run_hold(
        p, job_id=JOB, admission_id=ADMISSION, event_id='hold-1',
        reason='restart_recovery', stamp=stamp(6),
    )
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        stored.append(history[1:], sync_directory=False)
        stored.append(initial.records, sync_directory=False)
        stored.append(hold.records, sync_directory=False)
    finally:
        stored.close()
    opened = journal_store.JournalStore.open(directory)
    try:
        assert opened.finding is None
        assert reducer.replay(opened.rows()).initial_intents == p.initial_intents
    finally:
        opened.close()
    inspection = recovery_journal.inspect_recovery_journal(directory)
    initial_summary = inspection.report['journal']['initial_reservation_intents']
    assert initial_summary == {
        'count': 1, 'digest': reducer.initial_intents_digest(p), 'outstanding': True,
    }
    claim_view = recovery_journal.inspect_reservation_claim_view(directory)
    assert (claim_view.state, claim_view.intents, claim_view.confirmations) == (
        'ready', (), (),
    )
    assert claim_view.initial_intents == (p.initial_intents[INTENT],)
    assert claim_view.initial_digest == initial_summary['digest']
    journal = recovery_journal.open_recovery_journal(directory)
    try:
        assert journal.snapshot()['initial_reservation_intents'] == initial_summary
    finally:
        journal.close()
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, '_V3_TYPE_VALIDATORS', {})
        refused = journal_store.JournalStore.open(directory)
        try:
            tuple(refused.rows())
            assert refused.finding.code == 'journal_schema_unsupported'
            assert refused.finding.scope == 'process'
        finally:
            refused.close()
