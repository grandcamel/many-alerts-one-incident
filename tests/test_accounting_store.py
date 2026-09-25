"""Durable accounting store behavior at its public interface."""

import hashlib
import json
import os
import sqlite3
import struct

import pytest

import grafana_jsm_sandbox.accounting_store as storage
from grafana_jsm_sandbox.accounting_events import ZERO, encode_event
from grafana_jsm_sandbox.accounting_store import LedgerError, LedgerStore

LEDGER = '11111111-1111-1111-1111-111111111111'
EXPERIMENT = '22222222-2222-2222-2222-222222222222'
GENESIS = '33333333-3333-3333-3333-333333333333'
JOURNAL = '44444444-4444-4444-4444-444444444444'
BINDING = '55555555-5555-5555-5555-555555555555'


def receiver_genesis():
    return encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=1, previous_digest=ZERO, event_id=GENESIS,
        recorded_at_utc='2026-09-24T12:00:00.000000Z', actor_kind='receiver',
        event_type='genesis', data={'policy_revision': 'accounting-v1',
                                    'population': 'unknown'},
    )


def journal_binding(previous):
    return encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=2, previous_digest=previous, event_id=BINDING,
        recorded_at_utc='2026-09-24T12:01:00.000000Z', actor_kind='receiver',
        event_type='journal_bound',
        data={'journal_uuid': JOURNAL, 'journal_generation': 1},
    )


def test_create_and_open_preserve_verified_unknown_head(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    with LedgerStore.create(directory, genesis) as store:
        assert store.head == (1, genesis.digest)
        assert store.projection.population == 'unknown'
    with LedgerStore.open(directory) as reopened:
        assert reopened.head == (1, genesis.digest)
        assert reopened.projection.population == 'unknown'


def test_append_returns_read_back_event_receipt_and_reopens(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    with LedgerStore.create(directory, genesis) as store:
        binding = journal_binding(genesis.digest)
        receipt = store.append(binding, expected_head=genesis.digest)
        assert (receipt.sequence, receipt.event_id, receipt.event_digest) == (
            2, BINDING, binding.digest)
        assert receipt.anchor_counter == 2
        assert receipt.read_back is True
    with LedgerStore.open(directory) as reopened:
        assert reopened.head == (2, binding.digest)
        assert reopened.projection.bindings == ((JOURNAL, 1),)


def test_fixture_genesis_cannot_create_receiver_store(tmp_path):
    fixture = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=1, previous_digest=ZERO, event_id=GENESIS,
        recorded_at_utc='2026-09-24T12:00:00.000000Z', actor_kind='fixture',
        event_type='genesis', data={'policy_revision': 'accounting-v1',
                                    'population': 'synthetic_complete'},
    )
    directory = tmp_path / 'ledger'
    with pytest.raises(LedgerError, match='ledger_event_invalid'):
        LedgerStore.create(directory, fixture)
    assert not directory.exists()


def test_exact_historical_event_retry_is_read_back_without_a_second_row(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    binding = journal_binding(genesis.digest)
    with LedgerStore.create(directory, genesis) as store:
        first = store.append(binding, expected_head=genesis.digest)
        retry = store.append(binding, expected_head=genesis.digest)
        assert (retry.sequence, retry.event_digest) == (first.sequence, first.event_digest)
        assert store.head == (2, binding.digest)


def test_new_event_with_stale_head_refuses_without_mutation(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    binding = journal_binding(genesis.digest)
    with LedgerStore.create(directory, genesis) as store:
        with pytest.raises(LedgerError, match='stale_head'):
            store.append(binding, expected_head=ZERO)
        assert store.head == (1, genesis.digest)


def test_committed_unanchored_tail_becomes_durable_hold(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    binding = journal_binding(genesis.digest)
    with LedgerStore.create(directory, genesis):
        pass
    connection = sqlite3.connect(directory / 'ledger.sqlite3', isolation_level=None)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    connection.execute(
        'INSERT INTO ledger_events '
        '(sequence, event_id, event_type, body, event_digest) VALUES (?, ?, ?, ?, ?)',
        (2, BINDING, 'journal_bound', binding.raw, binding.digest),
    )
    connection.close()
    with pytest.raises(LedgerError, match='ledger_held'):
        LedgerStore.open(directory)
    with pytest.raises(LedgerError, match='ledger_held'):
        LedgerStore.open(directory)


def test_inspect_reports_verified_head_without_changing_store_files(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    with LedgerStore.create(directory, genesis):
        pass
    names = ('ledger.sqlite3', 'ledger.sqlite3-wal', 'anchor')
    before = {name: (directory / name).read_bytes() for name in names}
    report = LedgerStore.inspect(directory)
    assert (report.state, report.code, report.head) == (
        'ready', None, (1, genesis.digest))
    assert {name: (directory / name).read_bytes() for name in names} == before
    assert not (directory / 'ledger.sqlite3-shm').exists()


def test_schema_change_persists_a_recovery_hold(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()):
        pass
    connection = sqlite3.connect(directory / 'ledger.sqlite3', isolation_level=None)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    connection.execute('CREATE TABLE unexpected (id INTEGER)')
    connection.close()
    with pytest.raises(LedgerError, match='ledger_schema_invalid'):
        LedgerStore.open(directory)
    with pytest.raises(LedgerError, match='ledger_held'):
        LedgerStore.open(directory)
    report = LedgerStore.inspect(directory)
    assert (report.state, report.code) == ('held', 'ledger_schema_invalid')


def test_missing_wal_is_unverified_without_recreation(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()):
        pass
    wal = directory / 'ledger.sqlite3-wal'
    wal.unlink()
    anchor = (directory / 'anchor').read_bytes()
    report = LedgerStore.inspect(directory)
    assert (report.state, report.code) == ('unverified', 'ledger_wal_absent')
    with pytest.raises(LedgerError, match='ledger_wal_absent'):
        LedgerStore.open(directory)
    assert not wal.exists()
    assert (directory / 'anchor').read_bytes() == anchor


def test_second_writer_and_symlinked_store_are_refused(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()), pytest.raises(
        LedgerError, match='ledger_locked'
    ):
        LedgerStore.open(directory)
    alias = tmp_path / 'alias'
    alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(LedgerError, match='ledger_path_invalid'):
        LedgerStore.open(alias)


def test_changed_event_id_is_conflict_and_holds_store(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    binding = journal_binding(genesis.digest)
    changed = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=2, previous_digest=genesis.digest, event_id=BINDING,
        recorded_at_utc='2026-09-24T12:01:00.000000Z', actor_kind='receiver',
        event_type='journal_bound',
        data={'journal_uuid': '66666666-6666-6666-6666-666666666666',
              'journal_generation': 1},
    )
    with LedgerStore.create(directory, genesis) as store:
        store.append(binding, expected_head=genesis.digest)
        with pytest.raises(LedgerError, match='event_conflict'):
            store.append(changed, expected_head=genesis.digest)
        with pytest.raises(LedgerError, match='ledger_held'):
            store.append(binding, expected_head=genesis.digest)
    assert LedgerStore.inspect(directory).code == 'event_conflict'


def test_older_valid_anchor_must_match_its_historical_event(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    with LedgerStore.create(directory, genesis) as store:
        store.append(journal_binding(genesis.digest), expected_head=genesis.digest)
    anchor_path = directory / 'anchor'
    raw = bytearray(anchor_path.read_bytes())
    length = struct.unpack('>I', raw[8:12])[0]
    body = json.loads(raw[12:12 + length])
    body['head']['event_digest'] = 'f' * 64
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True).encode('ascii')
    header = b'ACANCHOR' + struct.pack('>I', len(payload))
    checksum = hashlib.sha256(b'acct.anchor.v1\0' + header + payload).digest()
    raw[:4096] = (header + payload + checksum).ljust(4096, b'\0')
    anchor_path.write_bytes(raw)
    with pytest.raises(LedgerError, match='ledger_anchor_conflict'):
        LedgerStore.open(directory)


def test_stored_event_digest_mismatch_persists_hold(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    binding = journal_binding(genesis.digest)
    with LedgerStore.create(directory, genesis):
        pass
    connection = sqlite3.connect(directory / 'ledger.sqlite3', isolation_level=None)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    connection.execute(
        'INSERT INTO ledger_events '
        '(sequence, event_id, event_type, body, event_digest) VALUES (?, ?, ?, ?, ?)',
        (2, BINDING, 'journal_bound', binding.raw, 'f' * 64),
    )
    connection.close()
    with pytest.raises(LedgerError, match='ledger_event_invalid'):
        LedgerStore.open(directory)
    assert LedgerStore.inspect(directory).code == 'ledger_event_invalid'


def test_anchor_write_failure_after_sql_commit_returns_no_receipt_and_holds(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    anchor = directory / 'anchor'
    with LedgerStore.create(directory, genesis) as store:
        anchor.chmod(0o400)
        try:
            with pytest.raises(LedgerError, match='ledger_write_failed'):
                store.append(journal_binding(genesis.digest),
                             expected_head=genesis.digest)
            with pytest.raises(LedgerError, match='ledger_closed'):
                store.append(journal_binding(genesis.digest),
                             expected_head=genesis.digest)
        finally:
            anchor.chmod(0o600)
    with pytest.raises(LedgerError, match='ledger_held'):
        LedgerStore.open(directory)
    assert LedgerStore.inspect(directory).code == 'tail_adopted_unreconciled'


def test_corrupt_database_header_is_a_recovery_hold(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()):
        pass
    db = directory / 'ledger.sqlite3'
    with db.open('r+b') as stream:
        stream.write(b'not a sqlite db!')
        stream.flush()
    with pytest.raises(LedgerError, match='ledger_corrupt'):
        LedgerStore.open(directory)
    assert LedgerStore.inspect(directory).code == 'ledger_corrupt'


def test_corrupt_wal_header_is_held_before_sqlite_can_ignore_it(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()):
        pass
    wal = directory / 'ledger.sqlite3-wal'
    with wal.open('r+b') as stream:
        stream.write(b'BAD!')
        stream.flush()
    with pytest.raises(LedgerError, match='ledger_corrupt'):
        LedgerStore.open(directory)
    assert LedgerStore.inspect(directory).code == 'ledger_corrupt'


def test_readback_failure_after_anchor_sync_returns_no_receipt(tmp_path, monkeypatch):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    binding = journal_binding(genesis.digest)
    with LedgerStore.create(directory, genesis) as store:
        real_read = storage._read_anchor
        calls = 0

        def fail_receipt_read(path):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('injected read failure')
            return real_read(path)

        with monkeypatch.context() as patcher:
            patcher.setattr(storage, '_read_anchor', fail_receipt_read)
            with pytest.raises(LedgerError, match='ledger_write_failed'):
                store.append(binding, expected_head=genesis.digest)
        with pytest.raises(LedgerError, match='ledger_closed'):
            store.append(binding, expected_head=genesis.digest)
    with LedgerStore.open(directory) as reopened:
        assert reopened.head == (2, binding.digest)


def test_hard_linked_anchor_and_newer_schema_refuse_without_repair(tmp_path):
    linked_dir = tmp_path / 'linked-ledger'
    with LedgerStore.create(linked_dir, receiver_genesis()):
        pass
    os.link(linked_dir / 'anchor', tmp_path / 'extra-link')
    with pytest.raises(LedgerError, match='ledger_permissions'):
        LedgerStore.open(linked_dir)

    newer_dir = tmp_path / 'newer-ledger'
    with LedgerStore.create(newer_dir, receiver_genesis()):
        pass
    connection = sqlite3.connect(newer_dir / 'ledger.sqlite3', isolation_level=None)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    connection.execute('PRAGMA user_version=2')
    connection.close()
    before = (newer_dir / 'anchor').read_bytes()
    with pytest.raises(LedgerError, match='ledger_schema_unsupported'):
        LedgerStore.open(newer_dir)
    assert (newer_dir / 'anchor').read_bytes() == before


def test_returned_projection_cannot_replace_verified_store_state(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()) as store:
        with pytest.raises(AttributeError):
            store.projection = object()
        assert store.projection.population == 'unknown'


def test_two_committed_events_beyond_anchor_refuse_adoption(tmp_path):
    directory = tmp_path / 'ledger'
    genesis = receiver_genesis()
    binding = journal_binding(genesis.digest)
    profile = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=3, previous_digest=binding.digest,
        event_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        recorded_at_utc='2026-09-24T12:02:00.000000Z', actor_kind='receiver',
        event_type='profile_configured',
        data={'profile': {
            'model_id': '66666666-6666-6666-6666-666666666666',
            'auth_id': '77777777-7777-7777-7777-777777777777',
            'venue_id': '88888888-8888-8888-8888-888888888888',
        }},
    )
    with LedgerStore.create(directory, genesis):
        pass
    connection = sqlite3.connect(directory / 'ledger.sqlite3', isolation_level=None)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    for sequence, event_id, kind, event in (
        (2, BINDING, 'journal_bound', binding),
        (3, 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'profile_configured', profile),
    ):
        connection.execute(
            'INSERT INTO ledger_events '
            '(sequence, event_id, event_type, body, event_digest) '
            'VALUES (?, ?, ?, ?, ?)',
            (sequence, event_id, kind, event.raw, event.digest),
        )
    connection.close()
    with pytest.raises(LedgerError, match='ledger_anchor_conflict'):
        LedgerStore.open(directory)
    assert LedgerStore.inspect(directory).code == 'ledger_anchor_conflict'


def test_fixture_genesis_copied_into_physical_store_is_refused_on_open(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()):
        pass
    fixture = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=1, previous_digest=ZERO, event_id=GENESIS,
        recorded_at_utc='2026-09-24T12:00:00.000000Z', actor_kind='fixture',
        event_type='genesis', data={'policy_revision': 'accounting-v1',
                                    'population': 'synthetic_complete'},
    )
    connection = sqlite3.connect(directory / 'ledger.sqlite3', isolation_level=None)
    connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    trigger = connection.execute(
        "SELECT sql FROM sqlite_schema WHERE name='ledger_events_no_update'"
    ).fetchone()[0]
    connection.execute('DROP TRIGGER ledger_events_no_update')
    connection.execute('UPDATE ledger_events SET body=?, event_digest=? WHERE sequence=1',
                       (fixture.raw, fixture.digest))
    connection.execute(trigger)
    connection.close()
    anchor_path = directory / 'anchor'
    raw = bytearray(anchor_path.read_bytes())
    length = struct.unpack('>I', raw[8:12])[0]
    body = json.loads(raw[12:12 + length])
    body['head']['event_digest'] = fixture.digest
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True).encode('ascii')
    header = b'ACANCHOR' + struct.pack('>I', len(payload))
    checksum = hashlib.sha256(b'acct.anchor.v1\0' + header + payload).digest()
    raw[:4096] = (header + payload + checksum).ljust(4096, b'\0')
    anchor_path.write_bytes(raw)
    with pytest.raises(LedgerError, match='ledger_event_invalid'):
        LedgerStore.open(directory)


def test_physical_schema_and_format_identity_match_reviewed_v1(tmp_path):
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, receiver_genesis()):
        pass
    connection = sqlite3.connect(directory / 'ledger.sqlite3')
    assert connection.execute('PRAGMA application_id').fetchone() == (0x41434C47,)
    assert connection.execute('PRAGMA user_version').fetchone() == (1,)
    assert connection.execute('PRAGMA page_size').fetchone() == (4096,)
    assert connection.execute('PRAGMA journal_mode').fetchone() == ('wal',)
    assert connection.execute('PRAGMA table_xinfo(ledger_events)').fetchall() == [
        (0, 'sequence', 'INTEGER', 0, None, 1, 0),
        (1, 'event_id', 'TEXT', 1, None, 0, 0),
        (2, 'event_type', 'TEXT', 1, None, 0, 0),
        (3, 'body', 'BLOB', 1, None, 0, 0),
        (4, 'event_digest', 'TEXT', 1, None, 0, 0),
    ]
    triggers = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='trigger'"
    )}
    assert triggers == {'ledger_events_no_update', 'ledger_events_no_delete',
                        'ledger_events_contiguous'}
    connection.close()
