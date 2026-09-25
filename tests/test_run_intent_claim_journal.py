"""A v3 Run intent is an unqualified replayed claim with no application writer."""

from dataclasses import asdict, replace

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_source as source
from grafana_jsm_sandbox import journal_store, recovery_journal
from grafana_jsm_sandbox.forwarder_json import tagged_digest
from grafana_jsm_sandbox.forwarder_services import SERVICE_PROFILES
from tests.test_initial_reservation_intent_journal import (
    ADMISSION,
    FINGERPRINT,
    INTENT,
    JOURNAL,
    LEASE,
    admitted,
    plan,
    plan_confirmation,
    stamp,
)

RUN_INTENT = '00000000-0000-0000-0000-000000000030'


def _services():
    return tuple(
        (name, LEASE if name == 'anthropic' else f'00000000-0000-0000-0000-{i:012d}', 'a' * 64)
        for i, name in enumerate(('anthropic', 'grafana', 'jira', 'kubernetes'), start=21)
    )


def _confirmed():
    p, history, item = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    confirmation = plan_confirmation(p)
    reducer.apply_delta(p, reducer.verify_commit(p, confirmation.records))
    return p, history + initial.records + confirmation.records, item


def _run(p, **changes):
    fields = {
        'intent_id': INTENT, 'event_id': RUN_INTENT,
        'ledger_head_sequence': 7, 'ledger_head_digest': 'd' * 64,
        'services': _services(), 'stamp': stamp(7),
    }
    fields.update(changes)
    return reducer.plan_run_intent(p, **fields)


def test_run_intent_is_private_ordinary_and_unqualified_with_separate_digest():
    p, history, _ = _confirmed()
    before_v2 = reducer.reservation_claims_digest(p)
    before_v3 = reducer.initial_intents_digest(p)
    assert records.RUN_EVENT_TYPES_V3 == ('run_intent', 'launch_claim')
    assert records.RUN_RECORD_CLASS_V3['run_intent'] == 'ordinary'
    assert records.SCHEMA_VERSIONS == frozenset({1})
    assert {name for name, profile in SERVICE_PROFILES.items() if profile.mandatory} == {
        'anthropic', 'jira', 'grafana', 'kubernetes',
    }
    planned = _run(p)
    record = planned.records[0]
    assert (record.event_type, record.schema_version, record.actor) == (
        'run_intent', 3, 'receiver',
    )
    assert 2_048 < len(record.body) <= records.MAX_RUN_INTENT_RECORD_BYTES
    assert planned.outcome['state'] == 'outstanding_unqualified'
    assert records.open_record(record.body) == record
    assert record.data['run_intent_digest'] == tagged_digest(
        reducer.RUN_INTENT_TAG, {
            'event_id': record.event_id, 'ids': records.thaw(record.ids),
            'data': {k: records.thaw(v) for k, v in record.data.items()
                     if k != 'run_intent_digest'},
        },
    )
    reducer.apply_delta(p, reducer.verify_commit(p, planned.records))
    replayed = reducer.replay(history + planned.records)
    assert replayed.run_intent == p.run_intent
    assert reducer.run_intent_claim_digest(p) == tagged_digest(
        reducer.RUN_INTENT_STATE_TAG, asdict(p.run_intent),
    )
    assert reducer.run_intent_claim_digest(replayed) == reducer.run_intent_claim_digest(p)
    assert reducer.reservation_claims_digest(p) == before_v2
    assert reducer.initial_intents_digest(p) == before_v3
    assert not hasattr(recovery_journal.RecoveryJournal, 'record_run_intent')
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        _run(p, event_id='00000000-0000-0000-0000-000000000031', stamp=stamp(8))


def test_worst_bounded_five_service_record_stays_within_private_ceiling():
    p, _, _ = _confirmed()
    services = tuple(sorted((*_services(), (
        'confluence', '00000000-0000-0000-0000-000000000027', 'f' * 64,
    ))))
    planned = _run(p, services=services)
    original = planned.records[0]
    data = records.thaw(original.data)
    data.update({
        'based_on_commit_seq': records.MAX_SEQ - 1,
        'initial_intent_commit_seq': records.MAX_SEQ - 3,
        'confirmation_commit_seq': records.MAX_SEQ - 2,
        'ledger_generation': records.MAX_GENERATION,
        'sequence': records.MAX_SEQ - 1,
        'ledger_head': {'sequence': records.MAX_SEQ, 'event_digest': 'f' * 64},
    })
    maximal = records.seal(
        records.Draft(original.event_id, original.event_type, original.actor,
                      original.ids, data),
        records.Position(records.MAX_GENERATION, records.MAX_SEQ, records.MAX_SEQ,
                         0, 1, 'f' * 64),
        records.Stamp('b' * records.MAX_ID_BYTES,
                      '9999-12-31T23:59:59.999999Z', records.MAX_SEQ),
        schema_version=3,
    )
    assert len(maximal.body) > records.MAX_RUN_HOLD_RECORD_BYTES
    assert len(maximal.body) <= records.MAX_RUN_INTENT_RECORD_BYTES
    assert records.open_record(maximal.body) == maximal


def test_run_intent_requires_confirmation_claim():
    p, _, _ = admitted()
    initial = plan(p)
    reducer.apply_delta(p, reducer.verify_commit(p, initial.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        _run(p)


def test_duplicate_service_name_is_rejected_by_planner_codec_and_replay():
    p, _, _ = _confirmed()
    duplicate = tuple(sorted((*_services(), (
        'jira', '00000000-0000-0000-0000-000000000027', 'f' * 64,
    ))))
    assert tuple(name for name, _, _ in duplicate) == (
        'anthropic', 'grafana', 'jira', 'jira', 'kubernetes',
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        _run(p, services=duplicate)
    record = _run(p).records[0]
    data = records.thaw(record.data)
    data['services'] = [
        {'service': name, 'lease_claim_id': lease_claim, 'scope_digest': digest}
        for name, lease_claim, digest in duplicate
    ]
    with pytest.raises(records.RecordError, match='^record_field$'):
        records.seal(
            records.Draft(record.event_id, record.event_type, record.actor,
                          record.ids, data),
            record.position, record.stamp, schema_version=3,
        )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(p, (replace(record, data=data),))


@pytest.mark.parametrize('change', [
    {'ledger_head_sequence': 6},
    {'ledger_head_sequence': 7, 'ledger_head_digest': 'e' * 64},
    {'ledger_head_sequence': True},
    {'event_id': ADMISSION},
    {'services': _services()[1:]},
    {'services': _services() + (('confluence', _services()[1][1], 'a' * 64),)},
    {'services': tuple((name, ADMISSION if name == 'jira' else lease, digest)
                       for name, lease, digest in _services())},
])
def test_run_intent_rejects_wrong_claim_or_service_identity(change):
    p, _, _ = _confirmed()
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        _run(p, **change)


def test_run_intent_holds_superseded_original_member():
    p, _, original = _confirmed()
    newer = source.SourceRecord(
        source_group=original.source_group,
        alerts=(source.SourceAlert(FINGERPRINT, 'resolved', None, None),),
        truncated_alerts=0, body_digest='e' * 64,
        provenance=source.HTTP_PROVENANCE,
    )
    admission = reducer.plan_admission(
        p, newer, admission_id='00000000-0000-0000-0000-000000000032',
        dedupe_event_id='dedupe-2', stamp=stamp(7),
    )
    reducer.apply_delta(p, reducer.verify_commit(p, admission.records))
    assert p.pending[FINGERPRINT].admission_id != ADMISSION
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        _run(p, stamp=stamp(8))


def test_run_intent_replay_rejects_forged_recomputed_fields():
    p, _, _ = _confirmed()
    record = _run(p).records[0]
    data = records.thaw(record.data)
    data['member_digest'] = 'e' * 64
    forged = records.seal(
        records.Draft(record.event_id, record.event_type, record.actor,
                      record.ids, data),
        record.position, record.stamp, schema_version=3,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(p, (forged,))


def test_run_intent_uses_ordinary_capacity_and_five_service_shape_fits():
    p, _, _ = _confirmed()
    services = tuple(sorted((*_services(), (
        'confluence', '00000000-0000-0000-0000-000000000027', 'a' * 64,
    ))))
    planned = _run(p, services=services)
    assert len(planned.records[0].body) < records.MAX_RUN_INTENT_RECORD_BYTES
    p.logical_bytes = p.bounds.ordinary_bytes - planned.charge + 1
    held = _run(p, services=services)
    assert isinstance(held, reducer.CapacityRefusal)
    assert (held.code, held.limit) == ('capacity_bytes', p.bounds.ordinary_bytes)
    assert p.logical_bytes < p.bounds.total_bytes


def test_run_intent_mixed_store_reopens_and_older_decoder_holds(tmp_path, monkeypatch):
    p, history, _ = _confirmed()
    planned = _run(p)
    reducer.apply_delta(p, reducer.verify_commit(p, planned.records))
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    stored = journal_store.JournalStore.create(directory, history[0], journal_uuid=JOURNAL)
    try:
        stored.append(history[1:3], sync_directory=False)
        for record in history[3:]:
            stored.append((record,), sync_directory=False)
        stored.append(planned.records, sync_directory=False)
    finally:
        stored.close()
    inspection = recovery_journal.inspect_recovery_journal(directory)
    assert inspection.report['verdict'] == 'ready'
    assert inspection.report['journal']['run_intent'] == {
        'count': 1, 'digest': reducer.run_intent_claim_digest(p),
        'state': 'outstanding_unqualified',
    }
    opened = recovery_journal.open_recovery_journal(directory)
    try:
        assert opened.snapshot()['run_intent'] == inspection.report['journal']['run_intent']
    finally:
        opened.close()
    with monkeypatch.context() as old_binary:
        old_binary.setattr(records, '_V3_TYPE_VALIDATORS', {
            ('reservation_intent', 3): records._validate_reservation_intent_v3,
            ('reservation_confirmation', 3): records._validate_reservation_confirmation_v3,
        })
        older = journal_store.JournalStore.open(directory)
        try:
            tuple(older.rows())
            assert older.finding.code == 'journal_schema_unsupported'
            assert older.finding.scope == 'process'
        finally:
            older.close()
