"""Pure active/archive relation over original same-generation event bytes."""

from dataclasses import replace

import pytest

from grafana_jsm_sandbox.accounting_archive_index import encode_index
from grafana_jsm_sandbox.accounting_archive_overlap import (
    ArchiveOverlapError,
    compare_archive_active,
)
from grafana_jsm_sandbox.accounting_archive_segment import encode_segment
from grafana_jsm_sandbox.accounting_events import ZERO, encode_event
from grafana_jsm_sandbox.accounting_store import LedgerStore
from tests.test_accounting_store import (
    EXPERIMENT,
    JOURNAL,
    LEDGER,
    journal_binding,
    profile_configuration,
    receiver_genesis,
)


def _history():
    genesis = receiver_genesis()
    bound = journal_binding(genesis.digest)
    configured = profile_configuration(bound.digest)
    return genesis, bound, configured


def _archive(events):
    segment = encode_segment(events)
    return (segment,), encode_index((segment,))


def _compare(segments, index, events, head=None):
    if head is None:
        head = (events[-1].fields()['sequence'], events[-1].digest)
    return compare_archive_active(segments, index, events, active_head=head)


def test_complete_partial_and_immediate_suffix_replay_one_history():
    events = _history()
    segments, index = _archive(events)
    complete = _compare(segments, index, events)
    assert complete.projection.events == events
    assert (complete.archived_count, complete.active_count,
            complete.overlap_count, complete.suffix_count) == (3, 3, 3, 0)

    segments, index = _archive(events[:2])
    partial = _compare(segments, index, events[1:])
    assert partial.projection.events == events
    assert (partial.archived_count, partial.active_count,
            partial.overlap_count, partial.suffix_count) == (2, 2, 1, 1)
    suffix = _compare(segments, index, events[2:])
    assert suffix.projection.events == events
    assert (suffix.overlap_count, suffix.suffix_count) == (0, 1)

    first = encode_segment(events[:2])
    second = encode_segment(events[2:], previous_projection=first.projection)
    two_segments = (first, second)
    compared = _compare(two_segments, encode_index(two_segments), events[1:])
    assert compared.projection.events == events
    assert (compared.overlap_count, compared.suffix_count) == (2, 0)


def test_stopped_sqlite_rows_match_retained_archive_prefix(tmp_path):
    events = _history()
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, events[0]) as store:
        store.append(events[1], expected_head=events[0].digest)
        store.append(events[2], expected_head=events[1].digest)
    with LedgerStore.open(directory) as store:
        active = store.projection.events
        head = (store.projection.head_sequence, store.projection.head_digest)
    segments, index = _archive(events[:2])
    compared = _compare(segments, index, active, head)
    assert compared.projection.events == active
    assert compared.suffix_count == 1
    assert compared.projection.population == 'unknown'


def test_missing_changed_or_reordered_overlap_holds():
    events = _history()
    segments, index = _archive(events)
    changed = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=2, previous_digest=events[0].digest,
        event_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        recorded_at_utc='2026-09-24T12:01:00.000000Z', actor_kind='receiver',
        event_type='journal_bound',
        data={'journal_uuid': JOURNAL, 'journal_generation': 1},
    )
    with pytest.raises(ArchiveOverlapError, match='archive_overlap_conflict'):
        _compare(segments, index, (events[0], changed, events[2]))
    with pytest.raises(ArchiveOverlapError, match='archive_gap'):
        _compare(segments, index, (events[0], events[2]))
    with pytest.raises(ArchiveOverlapError, match='archive_gap'):
        _compare(segments, index, (events[2], events[1]))
    with pytest.raises(ArchiveOverlapError, match='archive_gap'):
        _compare(segments, index, events[:2])


def test_suffix_chain_generation_and_head_conflicts_hold():
    events = _history()
    segments, index = _archive(events[:2])
    broken = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=3, previous_digest=ZERO,
        event_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        recorded_at_utc='2026-09-24T12:02:00.000000Z', actor_kind='receiver',
        event_type='profile_configured', data=events[2].fields()['data'],
    )
    with pytest.raises(ArchiveOverlapError, match='archive_union_invalid'):
        _compare(segments, index, (broken,))
    alien = encode_event(
        ledger_uuid=LEDGER, ledger_generation=2, experiment_id=EXPERIMENT,
        sequence=3, previous_digest=events[1].digest,
        event_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        recorded_at_utc='2026-09-24T12:02:00.000000Z', actor_kind='receiver',
        event_type='profile_configured', data=events[2].fields()['data'],
    )
    with pytest.raises(ArchiveOverlapError, match='archive_identity_conflict'):
        _compare(segments, index, (alien,))
    with pytest.raises(ArchiveOverlapError, match='archive_head_conflict'):
        _compare(segments, index, events[2:], (3, ZERO))


def test_suffix_semantic_duplicate_is_rejected_by_union_replay():
    events = _history()
    segments, index = _archive(events[:2])
    duplicate_binding = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=4, previous_digest=events[2].digest,
        event_id='dddddddd-dddd-dddd-dddd-dddddddddddd',
        recorded_at_utc='2026-09-24T12:03:00.000000Z', actor_kind='receiver',
        event_type='journal_bound',
        data={'journal_uuid': JOURNAL, 'journal_generation': 1},
    )
    with pytest.raises(ArchiveOverlapError, match='archive_union_invalid'):
        _compare(segments, index, events[2:] + (duplicate_binding,))


def test_index_and_active_object_corruption_hold_without_authority():
    events = _history()
    segments, index = _archive(events[:2])
    with pytest.raises(ArchiveOverlapError, match='archive_index_invalid'):
        _compare(segments, replace(index, digest=ZERO), events[2:])
    with pytest.raises(ArchiveOverlapError, match='archive_active_invalid'):
        _compare(segments, index, (replace(events[2], digest=ZERO),))
    with pytest.raises(ArchiveOverlapError, match='archive_overlap_invalid'):
        compare_archive_active(segments, index, (), active_head=(2, events[1].digest))
    with pytest.raises(ArchiveOverlapError, match='archive_overlap_invalid'):
        compare_archive_active(segments, index, events[2:], active_head=(True, ZERO))
