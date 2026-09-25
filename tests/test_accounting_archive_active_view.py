"""Stopped query-only active ledger image for local archive comparison."""

from dataclasses import replace

import pytest

import grafana_jsm_sandbox.accounting_store as storage
from grafana_jsm_sandbox.accounting_archive_index import encode_index
from grafana_jsm_sandbox.accounting_archive_overlap import (
    ArchiveOverlapError,
    compare_archive_to_ledger,
)
from grafana_jsm_sandbox.accounting_archive_segment import encode_segment
from grafana_jsm_sandbox.accounting_events import ZERO, encode_event
from grafana_jsm_sandbox.accounting_store import LedgerError, LedgerStore
from tests.test_accounting_store import (
    BINDING,
    EXPERIMENT,
    GENESIS,
    LEDGER,
    journal_binding,
    profile_configuration,
    receiver_genesis,
)


def _stopped_ledger(tmp_path):
    genesis = receiver_genesis()
    bound = journal_binding(genesis.digest)
    configured = profile_configuration(bound.digest)
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, genesis) as store:
        store.append(bound, expected_head=genesis.digest)
        store.append(configured, expected_head=bound.digest)
    return directory, (genesis, bound, configured)


def _archive(events):
    segment = encode_segment(events)
    return (segment,), encode_index((segment,))


def test_ready_view_releases_original_rows_after_read_only_verification(tmp_path):
    directory, events = _stopped_ledger(tmp_path)
    names = ('ledger.sqlite3', 'ledger.sqlite3-wal', 'anchor')
    before = {name: (directory / name).read_bytes() for name in names}
    view = LedgerStore.inspect_archive_active_view(directory)
    assert (view.state, view.code, view.head, view.population, view.events) == (
        'ready', None, (3, events[-1].digest), 'unknown', events)
    segments, index = _archive(events[:2])
    result = compare_archive_to_ledger(directory, segments, index)
    assert result.projection.events == events
    assert (result.overlap_count, result.suffix_count) == (2, 1)
    assert {name: (directory / name).read_bytes() for name in names} == before
    assert not (directory / 'ledger.sqlite3-shm').exists()


def test_missing_or_damaged_active_image_releases_no_history(tmp_path):
    directory, events = _stopped_ledger(tmp_path)
    segments, index = _archive(events[:2])
    missing = LedgerStore.inspect_archive_active_view(tmp_path / 'absent')
    assert missing.state != 'ready' and missing.head is None and missing.events == ()
    with pytest.raises(ArchiveOverlapError, match='archive_active_unverified'):
        compare_archive_to_ledger(tmp_path / 'absent', segments, index)
    anchor = directory / 'anchor'
    damaged = bytearray(anchor.read_bytes())
    damaged[0] ^= 1
    anchor.write_bytes(damaged)
    view = LedgerStore.inspect_archive_active_view(directory)
    assert view.state != 'ready' and view.head is None and view.events == ()
    with pytest.raises(ArchiveOverlapError, match='archive_active_unverified'):
        compare_archive_to_ledger(directory, segments, index)


def test_persisted_held_image_releases_no_history(tmp_path):
    directory, events = _stopped_ledger(tmp_path)
    segments, index = _archive(events[:2])
    changed = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=2, previous_digest=events[0].digest, event_id=BINDING,
        recorded_at_utc='2026-09-24T12:01:00.000000Z', actor_kind='receiver',
        event_type='journal_bound',
        data={'journal_uuid': '66666666-6666-6666-6666-666666666666',
              'journal_generation': 1},
    )
    with LedgerStore.open(directory) as store, \
            pytest.raises(LedgerError, match='event_conflict'):
        store.append(changed, expected_head=events[0].digest)
    view = LedgerStore.inspect_archive_active_view(directory)
    assert (view.state, view.code, view.head, view.events) == (
        'held', 'event_conflict', None, ())
    with pytest.raises(ArchiveOverlapError, match='archive_active_unverified'):
        compare_archive_to_ledger(directory, segments, index)


def test_close_failure_releases_no_history_or_stuck_lock(tmp_path, monkeypatch):
    directory, events = _stopped_ledger(tmp_path)
    segments, index = _archive(events[:2])
    real_connect = storage._connect

    class FailedClose:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def close(self):
            self.connection.close()
            raise RuntimeError('injected close failure')

    with monkeypatch.context() as patcher:
        patcher.setattr(storage, '_connect', lambda path: FailedClose(real_connect(path)))
        view = LedgerStore.inspect_archive_active_view(directory)
        with pytest.raises(ArchiveOverlapError, match='archive_active_unverified'):
            compare_archive_to_ledger(directory, segments, index)
    assert (view.state, view.code, view.head, view.events) == (
        'unverified', 'ledger_close_failed', None, ())
    with LedgerStore.open(directory):
        pass


def test_comparison_still_rejects_invalid_archive(tmp_path):
    directory, events = _stopped_ledger(tmp_path)
    segments, index = _archive(events[:2])
    with pytest.raises(ArchiveOverlapError, match='archive_index_invalid'):
        compare_archive_to_ledger(directory, segments, replace(index, digest=ZERO))


def test_fixture_origin_cannot_supply_a_receiver_active_view(tmp_path):
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
    view = LedgerStore.inspect_archive_active_view(directory)
    assert view.state != 'ready' and view.head is None and view.events == ()
