"""The first-attempt v3 intent is a replayed claim with no writer or permit."""

from dataclasses import asdict, replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_source as source
from grafana_jsm_sandbox import journal_store, recovery_journal, reservation_scan
from grafana_jsm_sandbox.accounting_events import ZERO, encode_event
from grafana_jsm_sandbox.accounting_store import LedgerStore
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
CONFIRMATION = '88888888-8888-8888-8888-888888888888'
LEDGER = '99999999-9999-9999-9999-999999999999'
LEDGER_EVENT = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'


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


def plan_confirmation(p, **overrides):
    fields = {
        'intent_id': INTENT, 'event_id': CONFIRMATION,
        'ledger_uuid': LEDGER, 'ledger_generation': 1,
        'ledger_event_id': LEDGER_EVENT, 'sequence': 7,
        'event_digest': 'd' * 64, 'stamp': stamp(6),
    }
    fields.update(overrides)
    return reducer.plan_initial_reservation_confirmation(p, **fields)


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


def test_v3_confirmation_is_a_replayed_unverified_claim():
    p, history, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    prior_intent_digest = reducer.initial_intents_digest(p)
    prior_v2_digest = reducer.reservation_claims_digest(p)
    confirmation = plan_confirmation(p)
    record = confirmation.records[0]
    assert (record.schema_version, record.data['rule']) == (
        3, 'reservation-confirmation-v3',
    )
    assert record.data['intent_digest'] == p.initial_intents[INTENT].intent_digest
    assert len(record.body) <= 2048
    assert records.open_record(record.body) == record
    assert records.RESERVATION_RECORD_CLASS_V3['reservation_confirmation'] == 'recovery'
    reducer.apply_delta(p, reducer.verify_commit(p, confirmation.records))
    replayed = reducer.replay(history + initial.records + confirmation.records)
    assert replayed.initial_confirmations == p.initial_confirmations
    assert reducer.initial_confirmations_digest(p) == tagged_digest(
        'rj.initial-confirmations.v3', [asdict(p.initial_confirmations[INTENT])],
    )
    assert reducer.initial_confirmations_digest(replayed) == (
        reducer.initial_confirmations_digest(p)
    )
    assert reducer.initial_intents_digest(p) == prior_intent_digest
    assert reducer.reservation_claims_digest(p) == prior_v2_digest
    assert 'permit' not in confirmation.outcome and 'confirmed' not in confirmation.outcome


def test_v3_confirmation_needs_intent_and_rejects_duplicate_and_forgery():
    p, _, _ = admitted()
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_confirmation(p)
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    record = plan_confirmation(p).records[0]
    forged = records.seal(
        records.Draft(record.event_id, record.event_type, record.actor,
                      record.ids, dict(record.data, intent_digest='f' * 64)),
        record.position, record.stamp, schema_version=3,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(p, (forged,))
    with pytest.raises(records.RecordError, match='^record_field$'):
        records.seal(
            records.Draft(record.event_id, record.event_type, record.actor,
                          record.ids, dict(record.data, ledger_event_id=LEDGER)),
            record.position, record.stamp, schema_version=3,
        )
    reducer.apply_delta(p, reducer.verify_commit(p, (record,)))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_confirmation(p, event_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
                          stamp=stamp(7))


def _other_v2_intent(p):
    claim = p.initial_intents[INTENT]
    return reducer.ReservationIntentClaim(
        journal_uuid=claim.journal_uuid, journal_generation=claim.journal_generation,
        admission_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        job_id='job-v2', intent_id='dddddddd-dddd-dddd-dddd-dddddddddddd',
        attempt_id='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
        reservation_id='ffffffff-ffff-ffff-ffff-ffffffffffff',
        run_id='00000000-0000-0000-0000-000000000020',
        lease_id='00000000-0000-0000-0000-000000000021',
        intent_digest='c' * 64, based_on_commit_seq=claim.based_on_commit_seq,
        committed_at_seq=claim.committed_at_seq,
    )


@pytest.mark.parametrize('collision', ['event', 'sequence'])
def test_cross_version_ledger_identity_reuse_is_refused_in_both_orders(collision):
    p, _, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    first = plan_confirmation(p)
    reducer.apply_delta(p, reducer.verify_commit(p, first.records))
    other = _other_v2_intent(p)
    p.intents[other.intent_id] = other  # Future mixed history after a disposition transition.
    reuse = {'ledger_event_id': LEDGER_EVENT} if collision == 'event' else {'sequence': 7}
    alternatives = {
        'ledger_event_id': '00000000-0000-0000-0000-000000000022', 'sequence': 8,
    }
    alternatives.update(reuse)
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.plan_reservation_confirmation(
            p, intent_id=other.intent_id,
            event_id='00000000-0000-0000-0000-000000000023',
            ledger_uuid=LEDGER, ledger_generation=1,
            event_digest='d' * 64, stamp=stamp(7), **alternatives,
        )

    reverse, _, _ = admitted()
    reverse_initial = plan(reverse)
    reducer.apply_delta(reverse, reducer.verify_commit(reverse, reverse_initial.records))
    reverse.confirmations[other.intent_id] = reducer.ReservationConfirmationClaim(
        intent_id=other.intent_id,
        confirmation_event_id='00000000-0000-0000-0000-000000000023',
        intent_digest=other.intent_digest, ledger_uuid=LEDGER, ledger_generation=1,
        ledger_event_id=LEDGER_EVENT, sequence=7, event_digest='d' * 64,
        committed_at_seq=reverse.head.commit_seq,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_confirmation(reverse, **alternatives)


def test_v3_confirmation_can_use_recovery_bytes_but_respects_total_cap():
    p, _, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    charge = plan_confirmation(p).charge
    p.logical_bytes = p.bounds.ordinary_bytes + 1
    assert isinstance(plan_confirmation(p), reducer.Plan)
    p.logical_bytes = p.bounds.total_bytes - charge + 1
    refused = plan_confirmation(p)
    assert isinstance(refused, reducer.CapacityRefusal)
    assert (refused.code, refused.limit) == ('capacity_bytes', p.bounds.total_bytes)
    p.logical_bytes = 0
    p.confirmations = {f'prior-{index}': None for index in range(256)}
    refused = plan_confirmation(p)
    assert isinstance(refused, reducer.CapacityRefusal)
    assert refused.code == 'capacity_reservation_confirmations'


def test_v3_confirmation_reopens_and_is_visible_without_ledger_authority(tmp_path, monkeypatch):
    p, history, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    confirmation = plan_confirmation(p)
    reducer.apply_delta(p, reducer.verify_commit(p, confirmation.records))
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        stored.append(history[1:], sync_directory=False)
        stored.append(initial.records, sync_directory=False)
        stored.append(confirmation.records, sync_directory=False)
    finally:
        stored.close()
    inspection = recovery_journal.inspect_recovery_journal(directory)
    summary = inspection.report['journal']['initial_reservation_confirmations']
    assert summary == {
        'count': 1, 'digest': reducer.initial_confirmations_digest(p),
        'outstanding': True,
    }
    view = recovery_journal.inspect_reservation_claim_view(directory)
    assert view.state == 'ready' and view.confirmations == ()
    assert view.initial_confirmations == (p.initial_confirmations[INTENT],)
    assert view.initial_confirmations_digest == summary['digest']
    opened = recovery_journal.open_recovery_journal(directory)
    try:
        assert opened.snapshot()['initial_reservation_confirmations'] == summary
    finally:
        opened.close()
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, '_V3_TYPE_VALIDATORS', {
            ('reservation_intent', 3): records._validate_reservation_intent_v3,
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == 'journal_schema_unsupported'
            assert older.finding.scope == 'process'
        finally:
            older.close()


@pytest.mark.parametrize('with_confirmation', [False, True])
def test_stopped_negative_scanner_reads_v3_claim_and_still_holds_missing_ledger(
    tmp_path, with_confirmation,
):
    p, history, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    confirmation = plan_confirmation(p) if with_confirmation else None
    journal_dir = tmp_path / 'journal'
    journal_dir.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(
        journal_dir, history[0], journal_uuid=JOURNAL,
    )
    try:
        stored.append(history[1:], sync_directory=False)
        stored.append(initial.records, sync_directory=False)
        if confirmation is not None:
            stored.append(confirmation.records, sync_directory=False)
    finally:
        stored.close()
    ledger_dir = tmp_path / 'ledger'
    genesis = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1,
        experiment_id='00000000-0000-0000-0000-000000000012',
        sequence=1, previous_digest=ZERO,
        event_id='00000000-0000-0000-0000-000000000013',
        recorded_at_utc='2026-09-25T00:00:00.000000Z', actor_kind='receiver',
        event_type='genesis',
        data={'policy_revision': 'accounting-v1', 'population': 'unknown'},
    )
    with LedgerStore.create(ledger_dir, genesis):
        pass
    before = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in (*journal_dir.iterdir(), *ledger_dir.iterdir()) if path.is_file()
    }
    result = reservation_scan.scan_reservation(journal_dir, ledger_dir, INTENT)
    assert (result.hold, result.reason) == (True, 'missing_ledger')
    assert {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in (*journal_dir.iterdir(), *ledger_dir.iterdir()) if path.is_file()
    } == before
