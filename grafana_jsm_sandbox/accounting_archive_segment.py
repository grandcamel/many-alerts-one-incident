"""Pure codec for one same-generation accounting archive segment.

This validates bytes and replay; it does not export, witness, register, compact,
or authorize an accounting history. A caller must bind the returned digest to
an independently trusted archive manifest and continuity witness.
"""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass

from .accounting_events import ZERO, AccountingEvent, AccountingEventError, decode_event
from .accounting_transition import AccountingTransitionError, Projection, replay_accounting
from .forwarder_json import JSONPolicyError, canonical_json, parse_json

MAGIC = b'MAOIAR01'
TAG = b'maoi.accounting.segment.v1\0'
FORMAT = 'accounting-archive-segment.v1'
MAX_HEADER = 4096
MAX_SEGMENT = 160 * 2**20
MAX_EVENTS = 8192
MAX_BODY = 16_384
_UUID = re.compile(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_KEYS = frozenset({
    'format', 'ledger_uuid', 'ledger_generation', 'experiment_id',
    'first_sequence', 'last_sequence', 'event_count', 'payload_bytes',
    'start_previous_digest', 'end_event_digest',
})


class ArchiveSegmentError(ValueError):
    """Fixed rejection code without event bytes or filesystem paths."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ArchiveSegment:
    raw: bytes
    digest: str
    projection: Projection
    first_sequence: int
    last_sequence: int


def _check(condition: bool, code: str = 'archive_segment_invalid') -> None:
    if not condition:
        raise ArchiveSegmentError(code)


def _identity(value: object) -> bool:
    return type(value) is str and _UUID.fullmatch(value) is not None


def _digest(value: object) -> bool:
    return type(value) is str and _HEX.fullmatch(value) is not None


def _integer(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _prior(previous_projection: Projection | None) -> tuple[AccountingEvent, ...]:
    if previous_projection is None:
        return ()
    _check(type(previous_projection) is Projection, 'archive_prior_invalid')
    invalid = False
    try:
        _check(replay_accounting(previous_projection.events) == previous_projection,
               'archive_prior_invalid')
    except AccountingTransitionError:
        invalid = True
    if invalid:
        raise ArchiveSegmentError('archive_prior_invalid') from None
    return previous_projection.events


def _validate_header(header: object) -> dict:
    _check(type(header) is dict and header.keys() == _KEYS)
    _check(header['format'] == FORMAT, 'archive_segment_unsupported')
    _check(_identity(header['ledger_uuid']) and _identity(header['experiment_id']))
    _check(_integer(header['ledger_generation'], 1, 2**31 - 1))
    _check(_integer(header['first_sequence'], 1, MAX_EVENTS))
    _check(_integer(header['last_sequence'], header['first_sequence'], MAX_EVENTS))
    _check(_integer(header['event_count'], 1, MAX_EVENTS) and
           header['event_count'] == header['last_sequence'] - header['first_sequence'] + 1)
    _check(_integer(header['payload_bytes'], 38, MAX_SEGMENT))
    _check(_digest(header['start_previous_digest']) and
           _digest(header['end_event_digest']))
    return header


def decode_segment(raw: bytes, *, expected_digest: str,
                   previous_projection: Projection | None = None) -> ArchiveSegment:
    """Verify one complete segment and replay it after a verified prior prefix."""
    _check(type(raw) is bytes and 13 <= len(raw) <= MAX_SEGMENT)
    _check(_digest(expected_digest), 'archive_digest_invalid')
    _check(hashlib.sha256(TAG + raw).hexdigest() == expected_digest,
           'archive_digest_mismatch')
    _check(raw[:8] == MAGIC)
    header_length = struct.unpack('>I', raw[8:12])[0]
    _check(1 <= header_length <= MAX_HEADER and 12 + header_length <= len(raw))
    header_raw = raw[12:12 + header_length]
    invalid = False
    try:
        header = parse_json(header_raw, max_bytes=MAX_HEADER, numbers='integer',
                            ascii_only=True)
        _check(canonical_json(header, ascii_only=True) == header_raw)
    except JSONPolicyError:
        invalid = True
    if invalid:
        raise ArchiveSegmentError('archive_segment_invalid') from None
    header = _validate_header(header)
    prefix = _prior(previous_projection)
    _check(header['first_sequence'] == len(prefix) + 1, 'archive_sequence_conflict')
    predecessor = prefix[-1].digest if prefix else ZERO
    _check(header['start_previous_digest'] == predecessor,
           'archive_chain_conflict')
    _check(header['last_sequence'] <= MAX_EVENTS)
    position = 12 + header_length
    _check(len(raw) - position == header['payload_bytes'])
    events: list[AccountingEvent] = []
    for sequence in range(header['first_sequence'], header['last_sequence'] + 1):
        _check(len(raw) - position >= 44)
        stored_sequence, body_length = struct.unpack('>QI', raw[position:position + 12])
        _check(stored_sequence == sequence, 'archive_sequence_conflict')
        _check(2 <= body_length <= MAX_BODY and len(raw) - position >= 44 + body_length)
        digest = raw[position + 12:position + 44].hex()
        body = raw[position + 44:position + 44 + body_length]
        invalid = False
        try:
            event = decode_event(body, expected_digest=digest)
        except AccountingEventError:
            invalid = True
        if invalid:
            raise ArchiveSegmentError('archive_event_invalid') from None
        fields = event.fields()
        _check(fields['sequence'] == sequence, 'archive_sequence_conflict')
        _check(fields['previous_digest'] == predecessor, 'archive_chain_conflict')
        _check((fields['ledger_uuid'], fields['ledger_generation'],
                fields['experiment_id']) ==
               (header['ledger_uuid'], header['ledger_generation'],
                header['experiment_id']), 'archive_identity_conflict')
        predecessor = digest
        events.append(event)
        position += 44 + body_length
    _check(position == len(raw) and predecessor == header['end_event_digest'])
    invalid = False
    try:
        projection = replay_accounting(prefix + tuple(events))
    except AccountingTransitionError:
        invalid = True
    if invalid:
        raise ArchiveSegmentError('archive_replay_invalid') from None
    _check((projection.ledger_uuid, projection.ledger_generation,
            projection.experiment_id) ==
           (header['ledger_uuid'], header['ledger_generation'],
            header['experiment_id']), 'archive_identity_conflict')
    return ArchiveSegment(raw, expected_digest, projection,
                          header['first_sequence'], header['last_sequence'])


def encode_segment(events: tuple[AccountingEvent, ...], *,
                   previous_projection: Projection | None = None) -> ArchiveSegment:
    """Encode original event bodies; validate the finished bytes by decoding."""
    _check(type(events) is tuple and 1 <= len(events) <= MAX_EVENTS)
    prefix = _prior(previous_projection)
    _check(len(prefix) + len(events) <= MAX_EVENTS)
    payload = bytearray()
    for index, event in enumerate(events, len(prefix) + 1):
        _check(type(event) is AccountingEvent and 2 <= len(event.raw) <= MAX_BODY and
               _digest(event.digest))
        invalid = False
        try:
            decode_event(event.raw, expected_digest=event.digest)
        except AccountingEventError:
            invalid = True
        if invalid:
            raise ArchiveSegmentError('archive_event_invalid') from None
        payload.extend(struct.pack('>QI', index, len(event.raw)))
        payload.extend(bytes.fromhex(event.digest))
        payload.extend(event.raw)
    first = events[0].fields()
    header = {
        'format': FORMAT,
        'ledger_uuid': first['ledger_uuid'],
        'ledger_generation': first['ledger_generation'],
        'experiment_id': first['experiment_id'],
        'first_sequence': len(prefix) + 1,
        'last_sequence': len(prefix) + len(events),
        'event_count': len(events),
        'payload_bytes': len(payload),
        'start_previous_digest': prefix[-1].digest if prefix else ZERO,
        'end_event_digest': events[-1].digest,
    }
    invalid = False
    try:
        header_raw = canonical_json(header, ascii_only=True)
    except JSONPolicyError:
        invalid = True
    if invalid:
        raise ArchiveSegmentError('archive_segment_invalid') from None
    _check(1 <= len(header_raw) <= MAX_HEADER)
    raw = MAGIC + struct.pack('>I', len(header_raw)) + header_raw + payload
    _check(len(raw) <= MAX_SEGMENT)
    digest = hashlib.sha256(TAG + raw).hexdigest()
    return decode_segment(bytes(raw), expected_digest=digest,
                          previous_projection=previous_projection)


__all__ = ['ArchiveSegment', 'ArchiveSegmentError', 'decode_segment',
           'encode_segment']
