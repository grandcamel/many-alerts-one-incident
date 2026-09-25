"""Cumulative v1 archive duplicate index over original segment bytes."""

import hashlib
import struct
from dataclasses import replace

import pytest

import grafana_jsm_sandbox.accounting_archive_index as index_module
from grafana_jsm_sandbox.accounting_archive_index import (
    TAG,
    ArchiveIndexError,
    decode_index,
    encode_index,
)
from grafana_jsm_sandbox.accounting_archive_segment import encode_segment
from grafana_jsm_sandbox.accounting_events import encode_event
from grafana_jsm_sandbox.accounting_store import LedgerStore
from grafana_jsm_sandbox.forwarder_json import parse_json
from tests.test_accounting_store import (
    BINDING,
    EXPERIMENT,
    GENESIS,
    JOURNAL,
    LEDGER,
    journal_binding,
    profile_configuration,
    receiver_genesis,
)


def _segments():
    genesis = receiver_genesis()
    bound = journal_binding(genesis.digest)
    configured = profile_configuration(bound.digest)
    first = encode_segment((genesis, bound))
    second = encode_segment((configured,), previous_projection=first.projection)
    return first, second


def _digest(raw):
    return hashlib.sha256(TAG + raw).hexdigest()


def _decode(raw, segments):
    return decode_index(raw, expected_digest=_digest(raw), segments=segments)


def _rows(raw):
    size = struct.unpack('>I', raw[8:12])[0]
    header = parse_json(raw[12:12 + size], max_bytes=65536, numbers='integer',
                        ascii_only=True)
    rows = []
    position = 12 + size
    for _ in range(header['row_count']):
        length = struct.unpack('>H', raw[position:position + 2])[0]
        rows.append(parse_json(raw[position + 2:position + 2 + length],
                               max_bytes=1024, numbers='integer', ascii_only=True))
        position += 2 + length
    assert position == len(raw)
    return header, rows


def test_two_segments_derive_all_event_and_claim_rows_in_canonical_order():
    segments = _segments()
    index = encode_index(segments)
    assert index.raw[:8] == b'MAOIAI01'
    assert index.digest == _digest(index.raw)
    assert index.projection.population == 'unknown'
    assert index.segment_digests == tuple(segment.digest for segment in segments)
    header, rows = _rows(index.raw)
    assert header['format'] == 'accounting-archive-index.v1'
    assert header['segment_digests'] == index.segment_digests
    assert header['row_count'] == index.row_count == 12
    assert len({(row['namespace'], row['key']) for row in rows}) == 12
    assert not any(row['namespace'] == 'provider_line' for row in rows)
    claim = next(row for row in rows if row['namespace'] == 'claimed_id' and
                 row['key'] == (JOURNAL,))
    assert (claim['segment_digest'], claim['sequence'], claim['event_digest']) == (
        segments[0].digest, 2, segments[0].projection.events[1].digest)
    event = next(row for row in rows if row['namespace'] == 'event_id' and
                 row['key'] == (GENESIS,))
    assert event['sequence'] == 1
    assert _decode(index.raw, segments) == index


def test_repeated_claim_keeps_first_event_owner():
    genesis = receiver_genesis()
    first_binding = journal_binding(genesis.digest)
    second_binding = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=3, previous_digest=first_binding.digest,
        event_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        recorded_at_utc='2026-09-24T12:02:00.000000Z', actor_kind='receiver',
        event_type='journal_bound',
        data={'journal_uuid': JOURNAL, 'journal_generation': 2},
    )
    segment = encode_segment((genesis, first_binding, second_binding))
    _header, rows = _rows(encode_index((segment,)).raw)
    owner = next(row for row in rows if row['namespace'] == 'claimed_id' and
                 row['key'] == (JOURNAL,))
    assert owner['sequence'] == 2
    assert sum(row['namespace'] == 'claimed_id' and row['key'] == (JOURNAL,)
               for row in rows) == 1
    assert sum(row['namespace'] == 'event_id' for row in rows) == 3


def test_stopped_sqlite_history_can_be_replayed_into_index(tmp_path):
    genesis = receiver_genesis()
    directory = tmp_path / 'ledger'
    with LedgerStore.create(directory, genesis) as store:
        bound = journal_binding(genesis.digest)
        store.append(bound, expected_head=genesis.digest)
    with LedgerStore.open(directory) as reopened:
        events = reopened.projection.events
        assert reopened.projection.population == 'unknown'
    segment = encode_segment(events)
    index = encode_index((segment,))
    assert _decode(index.raw, (segment,)).projection.events == events
    assert index.row_count == 7


def test_rehashed_changed_omitted_reordered_and_extra_rows_are_rejected():
    segments = _segments()
    index = encode_index(segments)
    size = struct.unpack('>I', index.raw[8:12])[0]
    first = 12 + size
    length1 = struct.unpack('>H', index.raw[first:first + 2])[0]
    second = first + 2 + length1
    length2 = struct.unpack('>H', index.raw[second:second + 2])[0]
    changed = bytearray(index.raw)
    changed[-1] ^= 1
    reordered = (index.raw[:first] + index.raw[second:second + 2 + length2] +
                 index.raw[first:second] + index.raw[second + 2 + length2:])
    omitted = index.raw[:first] + index.raw[second:]
    extra = index.raw + index.raw[first:second]
    for raw in (bytes(changed), reordered, omitted, extra, index.raw[:-1],
                index.raw + b'\x00'):
        with pytest.raises(ArchiveIndexError, match='archive_index_mismatch'):
            _decode(raw, segments)
    with pytest.raises(ArchiveIndexError, match='archive_digest_mismatch'):
        decode_index(index.raw[:-1], expected_digest=index.digest, segments=segments)


def test_missing_or_changed_segment_and_row_capacity_hold(monkeypatch):
    segments = _segments()
    with pytest.raises(ArchiveIndexError, match='archive_segment_invalid'):
        encode_index((segments[1],))
    with pytest.raises(ArchiveIndexError, match='archive_segment_invalid'):
        encode_index((replace(segments[0], digest='0' * 64), segments[1]))
    monkeypatch.setattr(index_module, 'MAX_ROWS', 1)
    with pytest.raises(ArchiveIndexError, match='archive_index_capacity'):
        encode_index(segments)


def test_event_rows_use_original_event_ids():
    segment = _segments()[0]
    _header, rows = _rows(encode_index((segment,)).raw)
    assert {row['key'][0] for row in rows if row['namespace'] == 'event_id'} == {
        GENESIS, BINDING}
