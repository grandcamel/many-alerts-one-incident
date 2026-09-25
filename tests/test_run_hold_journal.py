"""Versioned, no-dispatch Run holds on a mixed journal history."""

import dataclasses
import hashlib

import pytest

from grafana_jsm_sandbox import journal_records as records
from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journal_source as source
from grafana_jsm_sandbox import journal_store as store_module
from grafana_jsm_sandbox import recovery_journal
from grafana_jsm_sandbox.forwarder_json import canonical_json, tagged_digest

BOOT = '11111111-1111-1111-1111-111111111111'
WALL = '2026-09-24T00:00:00.000000Z'
FINGERPRINT = '5e8d72dc87b1ff35'


def stamp(mono_us=1):
    return records.Stamp(boot_id=BOOT, wall_time=WALL, mono_us=mono_us)


def admitted():
    projection = reducer.new_projection()
    genesis = reducer.plan_genesis(
        journal_uuid='22222222-2222-2222-2222-222222222222',
        bounds=reducer.JournalBounds(), event_id='genesis', stamp=stamp(),
    )
    reducer.apply_delta(projection, reducer.verify_commit(projection, genesis.records))
    item = source.SourceRecord(
        source_group=source.source_group_digest('test-group'),
        alerts=(source.SourceAlert(FINGERPRINT, 'firing', None, None),),
        truncated_alerts=0, body_digest='a' * 64,
        provenance=source.HTTP_PROVENANCE,
    )
    admission = reducer.plan_admission(
        projection, item, admission_id='admission-1',
        dedupe_event_id='dedupe-1', stamp=stamp(2),
    )
    reducer.apply_delta(projection, reducer.verify_commit(projection, admission.records))
    return projection, genesis.records + admission.records, item


def hold(projection, **overrides):
    fields = {'job_id': 'job-1', 'admission_id': 'admission-1',
              'event_id': 'hold-1', 'reason': 'accounting_unavailable',
              'stamp': stamp(3)}
    fields.update(overrides)
    return reducer.plan_run_hold(projection, **fields)


def test_v1_default_seal_bytes_remain_identical_with_explicit_version():
    projection, history, _ = admitted()
    original = history[0]
    explicit = records.seal(
        records.Draft(original.event_id, original.event_type, original.actor,
                      original.ids, original.data), original.position,
        original.stamp, schema_version=1,
    )
    assert explicit.body == original.body
    assert explicit.record_digest == original.record_digest
    assert explicit.schema_version == 1
    assert projection.head.event_seq == 3


def test_v2_hold_replays_without_erasing_v1_pending_and_has_separate_digest():
    projection, history, _ = admitted()
    old_state_digest = reducer.state_digest(projection)
    plan = hold(projection)
    record = plan.records[0]
    assert record.schema_version == 2
    assert record.event_type == 'run_hold'
    assert len(record.body) <= 2048
    assert records.open_record(record.body) == record
    content = {
        'schema_version': 2, 'journal_generation': record.position.journal_generation,
        'event_id': record.event_id, 'event_type': record.event_type,
        'actor': record.actor, 'ids': dict(record.ids), 'data': dict(record.data),
    }
    assert records.content_digest(record) == tagged_digest(records.CONTENT_TAG, content)
    assert records.content_digest(record) != tagged_digest(
        records.CONTENT_TAG, dict(content, schema_version=1),
    )
    reducer.apply_delta(projection, reducer.verify_commit(projection, plan.records))
    replayed = reducer.replay(history + plan.records)
    assert reducer.run_holds_digest(replayed) == reducer.run_holds_digest(projection)
    assert replayed.run_holds['job-1'].admission_id == 'admission-1'
    assert replayed.pending[FINGERPRINT].admission_id == 'admission-1'
    assert reducer.state_digest(projection) != old_state_digest


def test_replay_rejects_resigned_hold_with_false_pending_digest():
    projection, _, _ = admitted()
    plan = hold(projection)
    original = plan.records[0]
    data = dict(original.data, pending_digest='0' * 64)
    forged = records.seal(
        records.Draft(original.event_id, original.event_type, original.actor,
                      original.ids, data), original.position, original.stamp,
        schema_version=2,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(projection, (forged,))
    forged_count = records.seal(
        records.Draft(original.event_id, original.event_type, original.actor,
                      original.ids, dict(original.data, member_count=2)),
        original.position, original.stamp, schema_version=2,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(projection, (forged_count,))
    forged_members = records.seal(
        records.Draft(original.event_id, original.event_type, original.actor,
                      original.ids, dict(original.data, member_digest='0' * 64)),
        original.position, original.stamp, schema_version=2,
    )
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        reducer.verify_commit(projection, (forged_members,))


def test_v2_decoding_enforces_its_bound_after_typed_validation(monkeypatch):
    projection, _, _ = admitted()
    record = hold(projection).records[0]
    envelope = records.verify_body(record.body, record.record_digest)
    monkeypatch.setattr(records, 'MAX_RUN_HOLD_RECORD_BYTES', len(record.body) - 1)
    with pytest.raises(records.RecordError, match='^record_too_large$'):
        records.decode_record(envelope, record.body, record.record_digest)


def test_hold_rejects_noncurrent_admission_and_duplicate_identity():
    projection, _, _ = admitted()
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        hold(projection, admission_id='missing')
    plan = hold(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, plan.records))
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        hold(projection, job_id='job-1', event_id='hold-2')
    with pytest.raises(reducer.ReplayError, match='^replay_mismatch$'):
        hold(projection, job_id='job-2', event_id='hold-3')


def test_run_hold_family_limit_is_a_no_write_refusal():
    projection, _, _ = admitted()
    for index in range(reducer.MAX_RUN_HOLDS):
        projection.run_holds[f'prior-{index}'] = reducer.RunHold(
            admission_id=f'prior-admission-{index}', reason='operator_review',
            since_commit_seq=2, member_digest='0' * 64,
        )
    prior_head = projection.head
    refused = hold(projection)
    assert isinstance(refused, reducer.CapacityRefusal)
    assert (refused.code, refused.limit, refused.observed, refused.requested) == (
        'capacity_run_holds', 1024, 1024, 1,
    )
    assert projection.head == prior_head


def test_hold_projection_survives_newer_admission_and_is_immutable_in_digest():
    projection, history, item = admitted()
    plan = hold(projection)
    reducer.apply_delta(projection, reducer.verify_commit(projection, plan.records))
    saved_digest = reducer.run_holds_digest(projection)
    newer = dataclasses.replace(
        item, alerts=(dataclasses.replace(item.alerts[0], status='resolved'),),
        body_digest='b' * 64,
    )
    admission = reducer.plan_admission(
        projection, newer, admission_id='admission-2',
        dedupe_event_id='dedupe-2', stamp=stamp(4),
    )
    reducer.apply_delta(projection, reducer.verify_commit(projection, admission.records))
    replayed = reducer.replay(history + plan.records + admission.records)
    assert reducer.run_holds_digest(projection) == saved_digest
    assert reducer.run_holds_digest(replayed) == saved_digest
    assert projection.pending[FINGERPRINT].admission_id == 'admission-2'
    assert projection.run_holds['job-1'].admission_id == 'admission-1'


def test_committed_mixed_history_is_inspectable_and_reopens_held(tmp_path):
    projection, history, _ = admitted()
    plan = hold(projection)
    directory = tmp_path / 'journal'
    directory.mkdir(mode=0o700)
    store = store_module.JournalStore.create(
        directory, history[0], journal_uuid='22222222-2222-2222-2222-222222222222',
    )
    try:
        store.append(history[1:], sync_directory=False)
        store.append(plan.records, sync_directory=False)
        assert store.find_duplicate(plan.records).event_seqs == (4,)
    finally:
        store.close()

    inspection = recovery_journal.inspect_recovery_journal(directory)
    assert inspection.report['verdict'] == 'ready'
    assert inspection.report['journal']['run_holds']['count'] == 1
    assert inspection.report['journal']['run_holds']['digest'] != '0' * 64

    reopened = recovery_journal.open_recovery_journal(directory)
    try:
        snapshot = reopened.snapshot()
        assert snapshot['run_holds'] == inspection.report['journal']['run_holds']
        assert 'restart_recovery' in snapshot['dispatch_holds'][0]['code']
    finally:
        reopened.close()


def test_future_schema_and_v2_field_conflict_fail_closed():
    projection, _, _ = admitted()
    plan = hold(projection)
    record = plan.records[0]
    with pytest.raises(records.RecordError, match='^record_unsupported$'):
        records.seal(
            records.Draft(record.event_id, record.event_type, record.actor,
                          record.ids, record.data), record.position, record.stamp,
            schema_version=3,
        )
    with pytest.raises(records.RecordError, match='^record_field$'):
        records.seal(
            records.Draft(record.event_id, record.event_type, record.actor,
                          record.ids, dict(record.data, member_count=0)),
            record.position, record.stamp, schema_version=2,
        )


def test_unknown_future_pair_is_a_process_hold_at_storage_decode():
    projection, history, _ = admitted()
    record = hold(projection).records[0]
    envelope = records.verify_body(record.body, record.record_digest)
    envelope['schema_version'] = 3
    body = canonical_json(envelope, ascii_only=True)
    digest = hashlib.sha256(b'rj.record.v1\x00' + body).hexdigest()
    row = (record.position.event_seq, record.event_id, record.event_type, body, digest)
    decoded, finding = store_module._verify_row(
        row, history[-1], {entry.event_id for entry in history},
    )
    assert decoded is None
    assert finding.code == 'journal_schema_unsupported'
    assert finding.scope == 'process'
