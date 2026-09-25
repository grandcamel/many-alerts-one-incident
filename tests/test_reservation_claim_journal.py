"""Versioned journal reservation claims remain descriptive and replayable."""

import hashlib
from dataclasses import asdict, replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_source as source
from grafana_jsm_sandbox import journal_store as store_module
from grafana_jsm_sandbox import recovery_journal
from grafana_jsm_sandbox.forwarder_json import canonical_json, tagged_digest

JOURNAL = '11111111-1111-1111-1111-111111111111'
ADMISSION = '22222222-2222-2222-2222-222222222222'
INTENT = '33333333-3333-3333-3333-333333333333'
ATTEMPT = '44444444-4444-4444-4444-444444444444'
RESERVATION = '55555555-5555-5555-5555-555555555555'
RUN = '66666666-6666-6666-6666-666666666666'
LEASE = '77777777-7777-7777-7777-777777777777'
CONFIRMATION = '88888888-8888-8888-8888-888888888888'
LEDGER = '99999999-9999-9999-9999-999999999999'
LEDGER_EVENT = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
FINGERPRINT = '5e8d72dc87b1ff35'
JOB = '00000000-0000-0000-0000-000000000010'


def stamp():
    return records.Stamp(
        boot_id='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        wall_time='2026-09-25T00:00:00.000000Z', mono_us=3,
    )


def position():
    return records.Position(
        journal_generation=1, event_seq=5, commit_seq=4,
        commit_index=0, commit_size=1, prev_record_digest='a' * 64,
    )


def intent_draft(**overrides):
    ids = {
        'job_id': 'job-1', 'admission_id': ADMISSION, 'intent_id': INTENT,
        'attempt_id': ATTEMPT, 'reservation_id': RESERVATION,
        'run_id': RUN, 'lease_id': LEASE,
    }
    data = {
        'rule': 'reservation-intent-v2', 'based_on_commit_seq': 3,
        'intent_digest': 'c' * 64,
    }
    ids.update(overrides.pop('ids', {}))
    data.update(overrides.pop('data', {}))
    return records.Draft(
        event_id=overrides.pop('event_id', INTENT),
        event_type='reservation_intent', actor='receiver', ids=ids, data=data,
    )


def confirmation_draft(**overrides):
    data = {
        'rule': 'reservation-confirmation-v2', 'intent_digest': 'c' * 64,
        'ledger_uuid': LEDGER, 'ledger_generation': 1,
        'ledger_event_id': LEDGER_EVENT, 'sequence': 7, 'event_digest': 'd' * 64,
    }
    data.update(overrides.pop('data', {}))
    return records.Draft(
        event_id=overrides.pop('event_id', CONFIRMATION),
        event_type='reservation_confirmation', actor='receiver',
        ids={'intent_id': INTENT}, data=data,
    )


def test_two_exact_v2_pairs_round_trip_and_keep_v1_public_registry():
    assert records.SCHEMA_VERSIONS == frozenset({1})
    assert 'reservation_intent' not in records.REGISTERED_EVENT_TYPES
    for draft in (intent_draft(), confirmation_draft()):
        record = records.seal(draft, position(), stamp(), schema_version=2)
        assert record.event_type == draft.event_type
        assert record.schema_version == 2
        assert len(record.body) <= 2048
        assert records.open_record(record.body) == record
        with pytest.raises(records.RecordError, match='^record_unsupported$'):
            records.seal(draft, position(), stamp(), schema_version=1)


@pytest.mark.parametrize('draft', [
    intent_draft(ids={'attempt_id': 'not-a-uuid'}),
    intent_draft(data={'based_on_commit_seq': True}),
    intent_draft(data={'intent_digest': 'secret'}),
    confirmation_draft(data={'ledger_generation': True}),
    confirmation_draft(data={'event_digest': 'secret'}),
])
def test_v2_claim_records_reject_malformed_fields_without_echo(draft):
    with pytest.raises(records.RecordError) as error:
        records.seal(draft, position(), stamp(), schema_version=2)
    assert error.value.code in records.RECORD_ERROR_CODES
    assert 'secret' not in repr(error.value)


def test_v2_claim_record_rejects_nonreceiver_actor_and_extra_field():
    with pytest.raises(records.RecordError, match='^record_field$'):
        records.seal(replace(intent_draft(), actor='spawner'), position(), stamp(),
                     schema_version=2)
    with pytest.raises(records.RecordError, match='^record_field$'):
        records.seal(intent_draft(data={'permit': True}), position(), stamp(),
                     schema_version=2)


def admitted_and_held(admission_id=ADMISSION, job_id='job-1', two_members=False):
    p = reducer.new_projection()
    genesis = reducer.plan_genesis(
        journal_uuid=JOURNAL, bounds=reducer.JournalBounds(),
        event_id='genesis', stamp=stamp(),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, genesis.records))
    alerts = (source.SourceAlert(FINGERPRINT, 'firing', None, None),)
    if two_members:
        alerts += (source.SourceAlert('6e8d72dc87b1ff36', 'firing', None, None),)
    item = source.SourceRecord(
        source_group=source.source_group_digest('reservation-test'),
        alerts=alerts,
        truncated_alerts=0, body_digest='a' * 64,
        provenance=source.HTTP_PROVENANCE,
    )
    admission = reducer.plan_admission(
        p, item, admission_id=admission_id, dedupe_event_id='dedupe-1',
        stamp=replace(stamp(), mono_us=4),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, admission.records))
    held = reducer.plan_run_hold(
        p, job_id=job_id, admission_id=admission_id, event_id='hold-1',
        reason='accounting_unavailable', stamp=replace(stamp(), mono_us=5),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, held.records))
    return p, genesis.records + admission.records + held.records, item


def plan_intent(p, **overrides):
    fields = {
        'job_id': 'job-1', 'admission_id': ADMISSION, 'intent_id': INTENT,
        'attempt_id': ATTEMPT, 'reservation_id': RESERVATION,
        'run_id': RUN, 'lease_id': LEASE,
        'stamp': replace(stamp(), mono_us=6),
    }
    fields.update(overrides)
    return reducer.plan_reservation_intent(p, **fields)


def plan_confirmation(p, **overrides):
    fields = {
        'intent_id': INTENT, 'event_id': CONFIRMATION,
        'ledger_uuid': LEDGER, 'ledger_generation': 1,
        'ledger_event_id': LEDGER_EVENT, 'sequence': 7,
        'event_digest': 'd' * 64, 'stamp': replace(stamp(), mono_us=7),
    }
    fields.update(overrides)
    return reducer.plan_reservation_confirmation(p, **fields)


def test_intent_and_confirmation_replay_as_claims_with_stable_digest():
    p, history, _ = admitted_and_held()
    hold_digest = reducer.run_holds_digest(p)
    intent = plan_intent(p)
    assert intent.records[0].data['intent_digest'] == tagged_digest(
        'rj.reservation-intent.v2', {
            'journal_uuid': JOURNAL, 'journal_generation': 1,
            'admission_id': ADMISSION, 'job_id': 'job-1', 'intent_id': INTENT,
            'attempt_id': ATTEMPT, 'reservation_id': RESERVATION,
            'run_id': RUN, 'lease_id': LEASE,
            'based_on_commit_seq': p.head.commit_seq,
        },
    )
    reducer.apply_delta(p, reducer.verify_commit(p, intent.records))
    confirmation = plan_confirmation(p)
    reducer.apply_delta(p, reducer.verify_commit(p, confirmation.records))
    replayed = reducer.replay(history + intent.records + confirmation.records)
    assert replayed.intents == p.intents
    assert replayed.confirmations == p.confirmations
    assert reducer.reservation_claims_digest(replayed) == (
        reducer.reservation_claims_digest(p)
    )
    assert reducer.reservation_claims_digest(p) == tagged_digest(
        'rj.reservation-claims.v2', {
            'intents': [asdict(p.intents[INTENT])],
            'confirmations': [asdict(p.confirmations[INTENT])],
        },
    )
    assert reducer.run_holds_digest(p) == hold_digest
    assert p.run_holds['job-1'].reason == 'accounting_unavailable'
    assert 'permit' not in intent.outcome and 'permit' not in confirmation.outcome


def test_forged_recomputed_intent_digest_is_rejected_by_replay():
    p, _, _ = admitted_and_held()
    original = plan_intent(p).records[0]
    forged = records.seal(
        replace(intent_draft(), data=dict(original.data, intent_digest='f' * 64)),
        original.position, original.stamp, schema_version=2,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(p, (forged,))
    forged_prior = records.seal(
        replace(intent_draft(), data=dict(original.data, based_on_commit_seq=2)),
        original.position, original.stamp, schema_version=2,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(p, (forged_prior,))


def test_non_uuid_legacy_admission_replays_but_cannot_start_intent():
    p, history, _ = admitted_and_held(admission_id='admission-1')
    assert reducer.replay(history).run_holds['job-1'].admission_id == 'admission-1'
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_intent(p, admission_id='admission-1')


@pytest.mark.parametrize('field,value', [
    ('intent_id', JOURNAL), ('attempt_id', ADMISSION),
    ('reservation_id', INTENT), ('run_id', ATTEMPT), ('lease_id', RESERVATION),
])
def test_intent_identity_collisions_are_rejected(field, value):
    p, _, _ = admitted_and_held()
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_intent(p, **{field: value})


def test_unhashable_identity_has_a_fixed_replay_rejection():
    p, _, _ = admitted_and_held()
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_intent(p, attempt_id=[])


def test_all_intent_identity_pairs_are_distinct():
    p, _, _ = admitted_and_held(job_id=JOB)
    values = {
        'journal_uuid': JOURNAL, 'admission_id': ADMISSION, 'job_id': JOB,
        'intent_id': INTENT, 'attempt_id': ATTEMPT,
        'reservation_id': RESERVATION, 'run_id': RUN, 'lease_id': LEASE,
    }
    keys = tuple(values)
    for index, left in enumerate(keys):
        for right in keys[index + 1:]:
            with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
                plan_intent(p, **({'job_id': JOB} | {right: values[left]}))


def test_claim_capacity_refusal_keeps_the_head_and_hold():
    p, _, _ = admitted_and_held()
    original_head = p.head
    p.intents = {f'prior-{index}': None for index in range(256)}
    result = plan_intent(p)
    assert isinstance(result, reducer.CapacityRefusal)
    assert result.code == 'capacity_reservation_intents'
    assert p.head == original_head
    assert 'job-1' in p.run_holds


def test_second_intent_cannot_reuse_an_attempt_identity():
    p, _, _ = admitted_and_held()
    first = plan_intent(p)
    reducer.apply_delta(p, reducer.verify_commit(p, first.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_intent(
            p, intent_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
            attempt_id=ATTEMPT,
            reservation_id='dddddddd-dddd-dddd-dddd-dddddddddddd',
            run_id='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
            lease_id='ffffffff-ffff-ffff-ffff-ffffffffffff',
            stamp=replace(stamp(), mono_us=7),
        )


def test_confirmation_claim_reuse_and_duplicate_are_rejected():
    p, _, _ = admitted_and_held()
    intent = plan_intent(p)
    reducer.apply_delta(p, reducer.verify_commit(p, intent.records))
    confirmation = plan_confirmation(p)
    reducer.apply_delta(p, reducer.verify_commit(p, confirmation.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_confirmation(p, event_id='cccccccc-cccc-cccc-cccc-cccccccccccc')


def test_confirmation_requires_intent_and_cross_intent_ledger_identity_is_unique():
    p, _, _ = admitted_and_held()
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_confirmation(p)
    first = plan_intent(p)
    reducer.apply_delta(p, reducer.verify_commit(p, first.records))
    first_confirmation = plan_confirmation(p)
    reducer.apply_delta(p, reducer.verify_commit(p, first_confirmation.records))
    second = plan_intent(
        p, intent_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        attempt_id='dddddddd-dddd-dddd-dddd-dddddddddddd',
        reservation_id='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
        run_id='ffffffff-ffff-ffff-ffff-ffffffffffff',
        lease_id='00000000-0000-0000-0000-000000000001',
        stamp=replace(stamp(), mono_us=8),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, second.records))
    second_id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_confirmation(
            p, intent_id=second_id,
            event_id='00000000-0000-0000-0000-000000000002',
            ledger_event_id=LEDGER_EVENT, stamp=replace(stamp(), mono_us=9),
        )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_confirmation(
            p, intent_id=second_id,
            event_id='00000000-0000-0000-0000-000000000002',
            ledger_event_id='00000000-0000-0000-0000-000000000003',
            sequence=7, stamp=replace(stamp(), mono_us=9),
        )


def test_confirmation_capacity_is_a_no_write_refusal():
    p, _, _ = admitted_and_held()
    intent = plan_intent(p)
    reducer.apply_delta(p, reducer.verify_commit(p, intent.records))
    original_head = p.head
    p.confirmations = {f'prior-{index}': None for index in range(256)}
    refused = plan_confirmation(p)
    assert isinstance(refused, reducer.CapacityRefusal)
    assert refused.code == 'capacity_reservation_confirmations'
    assert p.head == original_head


def test_confirmation_and_claimed_ledger_ids_cannot_collide_with_intent():
    p, _, _ = admitted_and_held(job_id=JOB)
    intent = plan_intent(p, job_id=JOB)
    reducer.apply_delta(p, reducer.verify_commit(p, intent.records))
    identifiers = (JOURNAL, ADMISSION, JOB, INTENT, ATTEMPT,
                   RESERVATION, RUN, LEASE)
    for identity in identifiers:
        for field in ('event_id', 'ledger_uuid', 'ledger_event_id'):
            with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
                plan_confirmation(p, **{field: identity})
    for collision in (
        {'event_id': LEDGER}, {'event_id': LEDGER_EVENT},
        {'ledger_uuid': LEDGER_EVENT},
    ):
        with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
            plan_confirmation(p, **collision)


def test_claim_decoder_enforces_v2_body_cap_after_validation(monkeypatch):
    record = records.seal(intent_draft(), position(), stamp(), schema_version=2)
    envelope = records.verify_body(record.body, record.record_digest)
    monkeypatch.setattr(records, 'MAX_RUN_HOLD_RECORD_BYTES', len(record.body) - 1)
    with pytest.raises(records.RecordError, match='^record_too_large$'):
        records.decode_record(envelope, record.body, record.record_digest)


def test_resigned_confirmation_intent_digest_mismatch_is_rejected():
    p, _, _ = admitted_and_held()
    intent = plan_intent(p)
    reducer.apply_delta(p, reducer.verify_commit(p, intent.records))
    original = plan_confirmation(p).records[0]
    forged = records.seal(
        replace(confirmation_draft(), data=dict(original.data, intent_digest='f' * 64)),
        original.position, original.stamp, schema_version=2,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(p, (forged,))


def test_superseded_held_job_cannot_attach_intent_to_new_admission():
    p, history, item = admitted_and_held()
    newer = replace(item, alerts=(replace(item.alerts[0], status='resolved'),),
                    body_digest='b' * 64)
    admission = reducer.plan_admission(
        p, newer, admission_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        dedupe_event_id='dedupe-2', stamp=replace(stamp(), mono_us=6),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, admission.records))
    assert reducer.replay(history + admission.records).run_holds['job-1'] == p.run_holds['job-1']
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_intent(p, stamp=replace(stamp(), mono_us=7))


def test_partial_supersession_does_not_requalify_the_old_hold():
    p, history, item = admitted_and_held(two_members=True)
    newer = replace(item, alerts=(replace(item.alerts[0], status='resolved'),),
                    body_digest='b' * 64)
    admission = reducer.plan_admission(
        p, newer, admission_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        dedupe_event_id='dedupe-2', stamp=replace(stamp(), mono_us=6),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, admission.records))
    assert sum(entry.admission_id == ADMISSION for entry in p.pending.values()) == 1
    assert reducer.replay(history + admission.records).run_holds['job-1'] == p.run_holds['job-1']
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        plan_intent(p, stamp=replace(stamp(), mono_us=7))


def test_committed_claim_history_reopens_and_inspects_without_permit(tmp_path):
    p, history, _ = admitted_and_held()
    intent = plan_intent(p)
    reducer.apply_delta(p, reducer.verify_commit(p, intent.records))
    confirmation = plan_confirmation(p)
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    store = store_module.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        store.append(history[1:], sync_directory=False)
        store.append(intent.records, sync_directory=False)
        store.append(confirmation.records, sync_directory=False)
    finally:
        store.close()
    inspected = recovery_journal.inspect_recovery_journal(directory)
    assert inspected.report['verdict'] == 'ready'
    claims = inspected.report['journal']['reservation_claims']
    assert claims['intents'] == 1
    assert claims['confirmations'] == 1
    assert claims['digest'] != '0' * 64
    assert 'permit' not in claims and 'ready' not in claims
    opened = recovery_journal.open_recovery_journal(directory)
    try:
        assert opened.snapshot()['reservation_claims'] == claims
        assert opened.snapshot()['run_holds']['count'] == 1
    finally:
        opened.close()


def test_intent_only_crash_image_reopens_as_unconfirmed_claim(tmp_path):
    p, history, _ = admitted_and_held()
    intent = plan_intent(p)
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    store = store_module.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        store.append(history[1:], sync_directory=False)
        store.append(intent.records, sync_directory=False)
    finally:
        store.close()
    inspected = recovery_journal.inspect_recovery_journal(directory)
    assert inspected.report['verdict'] == 'ready'
    assert inspected.report['journal']['reservation_claims']['intents'] == 1
    assert inspected.report['journal']['reservation_claims']['confirmations'] == 0
    opened = recovery_journal.open_recovery_journal(directory)
    try:
        assert opened.snapshot()['reservation_claims']['confirmations'] == 0
        assert opened.snapshot()['run_holds']['count'] == 1
    finally:
        opened.close()


def test_pre_intent_crash_image_has_no_claim(tmp_path):
    _, history, _ = admitted_and_held()
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    store = store_module.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        store.append(history[1:], sync_directory=False)
    finally:
        store.close()
    inspected = recovery_journal.inspect_recovery_journal(directory)
    assert inspected.report['verdict'] == 'ready'
    assert 'reservation_claims' not in inspected.report['journal']
    assert inspected.report['journal']['run_holds']['count'] == 1


def test_restart_between_intent_and_confirmation_keeps_claim_held():
    p, history, _ = admitted_and_held()
    intent = plan_intent(p)
    reducer.apply_delta(p, reducer.verify_commit(p, intent.records))
    new_boot = '00000000-0000-0000-0000-000000000011'
    restarted = reducer.plan_restart(
        p, event_id='restart-1',
        stamp=replace(stamp(), boot_id=new_boot, mono_us=1),
        anchor_lag=0, wal_found=None,
    )
    reducer.apply_delta(p, reducer.verify_commit(p, restarted.records))
    assert len(p.intents) == 1 and not p.confirmations
    assert p.run_holds['job-1'].reason == 'accounting_unavailable'
    confirmation = plan_confirmation(
        p, stamp=replace(stamp(), boot_id=new_boot, mono_us=2),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, confirmation.records))
    replayed = reducer.replay(
        history + intent.records + restarted.records + confirmation.records
    )
    assert replayed.confirmations == p.confirmations
    assert replayed.run_holds == p.run_holds


def test_resigned_false_intent_in_store_is_not_ready(tmp_path):
    p, history, _ = admitted_and_held()
    original = plan_intent(p).records[0]
    forged = records.seal(
        replace(intent_draft(), data=dict(original.data, intent_digest='f' * 64)),
        original.position, original.stamp, schema_version=2,
    )
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    store = store_module.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        store.append(history[1:], sync_directory=False)
        store.append((forged,), sync_directory=False)
    finally:
        store.close()
    inspected = recovery_journal.inspect_recovery_journal(directory)
    assert inspected.report['verdict'] != 'ready'
    assert inspected.report['journal'] is None


def test_future_claim_pair_is_a_nonpersisted_process_hold():
    p, history, _ = admitted_and_held()
    record = plan_intent(p).records[0]
    envelope = records.verify_body(record.body, record.record_digest)
    envelope['schema_version'] = 3
    body = canonical_json(envelope, ascii_only=True)
    digest = hashlib.sha256(b'rj.record.v1\x00' + body).hexdigest()
    row = (record.position.event_seq, record.event_id, record.event_type, body, digest)
    decoded, finding = store_module._verify_row(
        row, history[-1], {entry.event_id for entry in history},
    )
    assert decoded is None
    assert (finding.code, finding.scope) == ('journal_schema_unsupported', 'process')
