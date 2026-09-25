"""Pure cumulative duplicate index for verified v1 accounting segments.

The index describes one same-generation history but carries no storage,
continuity or admission authority. Current v1 has no authenticated provider
charge-line event, so a provider-line row cannot be derived or accepted.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

from .accounting_archive_segment import (
    ArchiveSegment,
    ArchiveSegmentError,
    decode_segment,
)
from .accounting_transition import Projection, _body_ids
from .forwarder_json import JSONPolicyError, canonical_json

MAGIC = b'MAOIAI01'
TAG = b'maoi.accounting.index.v1\0'
FORMAT = 'accounting-archive-index.v1'
MAX_SEGMENTS = 256
MAX_ROWS = 65_536
MAX_HEADER = 65_536
MAX_ROW = 1024
MAX_INDEX = 16 * 2**20


class ArchiveIndexError(ValueError):
    """Fixed rejection code without caller data or filesystem path."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ArchiveIndex:
    raw: bytes
    digest: str
    projection: Projection
    row_count: int
    segment_digests: tuple[str, ...]


def _check(condition: bool, code: str = 'archive_index_invalid') -> None:
    if not condition:
        raise ArchiveIndexError(code)


def _segments(segments: tuple[ArchiveSegment, ...]) -> tuple[tuple[ArchiveSegment, ...], Projection]:
    _check(type(segments) is tuple and 1 <= len(segments) <= MAX_SEGMENTS)
    verified: list[ArchiveSegment] = []
    prior = None
    for segment in segments:
        _check(type(segment) is ArchiveSegment)
        invalid = False
        try:
            checked = decode_segment(segment.raw, expected_digest=segment.digest,
                                     previous_projection=prior)
        except ArchiveSegmentError:
            invalid = True
        if invalid:
            raise ArchiveIndexError('archive_segment_invalid') from None
        verified.append(checked)
        prior = checked.projection
    return tuple(verified), prior


def _rows(segments: tuple[ArchiveSegment, ...], projection: Projection) -> tuple[bytes, ...]:
    owners: dict[str, tuple[str, int, str]] = {}
    rows: list[tuple[bytes, bytes]] = []
    segment_by_sequence = {
        sequence: segment.digest
        for segment in segments
        for sequence in range(segment.first_sequence, segment.last_sequence + 1)
    }
    _check(len(segment_by_sequence) == len(projection.events),
           'archive_index_history_conflict')
    for sequence, event in enumerate(projection.events, 1):
        fields = event.fields()
        event_id = fields['event_id']
        owner = (segment_by_sequence[sequence], sequence, event.digest)
        rows.append(_row('event_id', (event_id,), owner))
        if sequence == 1:
            claims = (fields['ledger_uuid'], fields['experiment_id'], event_id)
        else:
            claims = (event_id, *_body_ids(fields['event_type'], fields['data']))
        for claim in claims:
            if claim not in owners:
                owners[claim] = owner
                rows.append(_row('claimed_id', (claim,), owner))
    _check(frozenset(owners) == projection.claimed_ids,
           'archive_index_claim_conflict')
    _check(len(rows) <= MAX_ROWS, 'archive_index_capacity')
    rows.sort(key=lambda item: item[0])
    _check(len({key for key, _ in rows}) == len(rows),
           'archive_index_claim_conflict')
    return tuple(body for _, body in rows)


def _row(namespace: str, key: tuple[str, ...], owner: tuple[str, int, str]) -> tuple[bytes, bytes]:
    segment_digest, sequence, event_digest = owner
    row = {
        'namespace': namespace, 'key': key, 'segment_digest': segment_digest,
        'sequence': sequence, 'event_digest': event_digest,
    }
    invalid = False
    try:
        sort_key = canonical_json((namespace, key), ascii_only=True)
        body = canonical_json(row, ascii_only=True)
    except JSONPolicyError:
        invalid = True
    if invalid:
        raise ArchiveIndexError('archive_index_invalid') from None
    _check(1 <= len(body) <= MAX_ROW, 'archive_index_capacity')
    return sort_key, body


def _build(segments: tuple[ArchiveSegment, ...]) -> ArchiveIndex:
    checked, projection = _segments(segments)
    rows = _rows(checked, projection)
    digests = tuple(segment.digest for segment in checked)
    header = {
        'format': FORMAT,
        'ledger_uuid': projection.ledger_uuid,
        'ledger_generation': projection.ledger_generation,
        'experiment_id': projection.experiment_id,
        'segment_digests': digests,
        'row_count': len(rows),
    }
    invalid = False
    try:
        header_raw = canonical_json(header, ascii_only=True)
    except JSONPolicyError:
        invalid = True
    if invalid:
        raise ArchiveIndexError('archive_index_invalid') from None
    _check(1 <= len(header_raw) <= MAX_HEADER, 'archive_index_capacity')
    raw = bytearray(MAGIC + struct.pack('>I', len(header_raw)) + header_raw)
    for row in rows:
        raw.extend(struct.pack('>H', len(row)))
        raw.extend(row)
        _check(len(raw) <= MAX_INDEX, 'archive_index_capacity')
    result = bytes(raw)
    return ArchiveIndex(result, hashlib.sha256(TAG + result).hexdigest(),
                        projection, len(rows), digests)


def encode_index(segments: tuple[ArchiveSegment, ...]) -> ArchiveIndex:
    """Derive a canonical index from complete, reverified v1 segments."""
    return _build(segments)


def decode_index(raw: bytes, *, expected_digest: str,
                 segments: tuple[ArchiveSegment, ...]) -> ArchiveIndex:
    """Require the complete index to match replay-derived canonical bytes."""
    _check(type(raw) is bytes and 13 <= len(raw) <= MAX_INDEX)
    _check(type(expected_digest) is str and len(expected_digest) == 64 and
           all(character in '0123456789abcdef' for character in expected_digest),
           'archive_digest_invalid')
    _check(hashlib.sha256(TAG + raw).hexdigest() == expected_digest,
           'archive_digest_mismatch')
    derived = _build(segments)
    _check(raw == derived.raw and expected_digest == derived.digest,
           'archive_index_mismatch')
    return derived


__all__ = ['ArchiveIndex', 'ArchiveIndexError', 'decode_index', 'encode_index']
