"""Pure archive segment framing and full-history replay, without archive authority."""

import hashlib
import struct

import pytest

from grafana_jsm_sandbox.accounting_archive_segment import (
    TAG,
    ArchiveSegmentError,
    decode_segment,
    encode_segment,
)
from grafana_jsm_sandbox.accounting_events import encode_event
from grafana_jsm_sandbox.forwarder_json import canonical_json, parse_json
from tests.test_accounting_store import (
    EXPERIMENT,
    LEDGER,
    journal_binding,
    profile_configuration,
    receiver_genesis,
)


def _digest(raw):
    return hashlib.sha256(TAG + raw).hexdigest()


def _decode(raw, *, previous_projection=None):
    return decode_segment(raw, expected_digest=_digest(raw),
                          previous_projection=previous_projection)


def _rewrite_header(raw, change):
    size = struct.unpack('>I', raw[8:12])[0]
    header = parse_json(raw[12:12 + size], max_bytes=4096, numbers='integer',
                        ascii_only=True)
    change(header)
    revised = canonical_json(header, ascii_only=True)
    return raw[:8] + struct.pack('>I', len(revised)) + revised + raw[12 + size:]


def _events():
    genesis = receiver_genesis()
    bound = journal_binding(genesis.digest)
    configured = profile_configuration(bound.digest)
    return genesis, bound, configured


def test_first_segment_preserves_original_bytes_and_unknown_population():
    events = _events()
    segment = encode_segment(events)
    assert segment.raw[:8] == b'MAOIAR01'
    assert segment.digest == _digest(segment.raw)
    assert (segment.first_sequence, segment.last_sequence) == (1, 3)
    assert segment.projection.events == events
    assert segment.projection.population == 'unknown'
    assert _decode(segment.raw).projection == segment.projection


def test_second_segment_requires_exact_prior_head_and_replays_once():
    genesis, bound, configured = _events()
    first = encode_segment((genesis, bound))
    second = encode_segment((configured,), previous_projection=first.projection)
    assert (second.first_sequence, second.last_sequence) == (3, 3)
    assert second.projection.events == (genesis, bound, configured)
    assert _decode(second.raw, previous_projection=first.projection).projection == (
        second.projection)
    with pytest.raises(ArchiveSegmentError, match='archive_sequence_conflict'):
        _decode(second.raw)
    with pytest.raises(ArchiveSegmentError, match='archive_sequence_conflict'):
        _decode(first.raw, previous_projection=first.projection)


def test_content_digest_and_exact_framing_reject_changed_truncated_and_trailing_bytes():
    segment = encode_segment((_events()[0],))
    changed = bytearray(segment.raw)
    changed[-1] ^= 1
    with pytest.raises(ArchiveSegmentError, match='archive_digest_mismatch'):
        decode_segment(bytes(changed), expected_digest=segment.digest)
    for raw in (segment.raw[:-1], segment.raw + b'\x00'):
        with pytest.raises(ArchiveSegmentError, match='archive_segment_invalid'):
            _decode(raw)


def test_rehashed_header_and_entry_conflicts_fail_closed():
    segment = encode_segment(_events()[:2])
    wrong_owner = _rewrite_header(segment.raw, lambda header: header.update(
        experiment_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'))
    with pytest.raises(ArchiveSegmentError, match='archive_identity_conflict'):
        _decode(wrong_owner)
    wrong_end = _rewrite_header(segment.raw, lambda header: header.update(
        end_event_digest='a' * 64))
    with pytest.raises(ArchiveSegmentError, match='archive_segment_invalid'):
        _decode(wrong_end)
    header_size = struct.unpack('>I', segment.raw[8:12])[0]
    first_frame = 12 + header_size
    duplicate = bytearray(segment.raw)
    second_frame = first_frame + 44 + len(_events()[0].raw)
    duplicate[second_frame:second_frame + 8] = struct.pack('>Q', 1)
    with pytest.raises(ArchiveSegmentError, match='archive_sequence_conflict'):
        _decode(bytes(duplicate))


def test_semantically_invalid_but_validly_hashed_event_is_rejected():
    genesis, bound, _ = _events()
    # A second journal binding to the same origin is syntactically valid.
    duplicate_binding = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=3, previous_digest=bound.digest,
        event_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        recorded_at_utc='2026-09-24T12:02:00.000000Z', actor_kind='receiver',
        event_type='journal_bound', data=bound.fields()['data'],
    )
    segment = encode_segment((genesis, bound))
    frame = (struct.pack('>QI', 3, len(duplicate_binding.raw)) +
             bytes.fromhex(duplicate_binding.digest) + duplicate_binding.raw)
    augmented = segment.raw + frame
    modified = _rewrite_header(augmented, lambda header: header.update(
        last_sequence=3, event_count=3, payload_bytes=header['payload_bytes'] + len(frame),
        end_event_digest=duplicate_binding.digest))
    with pytest.raises(ArchiveSegmentError, match='archive_replay_invalid'):
        _decode(modified)


def test_noncanonical_header_and_unsupported_format_refused():
    segment = encode_segment((_events()[0],))
    unsupported = _rewrite_header(segment.raw, lambda header: header.update(
        format='accounting-archive-segment.v2'))
    with pytest.raises(ArchiveSegmentError, match='archive_segment_unsupported'):
        _decode(unsupported)
    size = struct.unpack('>I', segment.raw[8:12])[0]
    header = segment.raw[12:12 + size]
    noncanonical = (segment.raw[:8] + struct.pack('>I', size + 1) + b' ' + header +
                    segment.raw[12 + size:])
    with pytest.raises(ArchiveSegmentError, match='archive_segment_invalid'):
        _decode(noncanonical)
