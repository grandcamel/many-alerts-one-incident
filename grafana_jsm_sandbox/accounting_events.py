"""Pure, closed synthetic accounting event codec. No storage authority."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .forwarder_json import JSONPolicyError, canonical_json, parse_json

TAG = b'acct.event.v1\0'
ZERO = '0' * 64
MAX_BODY = 16_384
_UUID = re.compile(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_TIME = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:'
                   r'[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z')
_TOP = frozenset({'schema_version', 'ledger_uuid', 'ledger_generation',
                  'experiment_id', 'sequence', 'previous_digest', 'event_id',
                  'recorded_at_utc', 'actor_kind', 'event_type', 'data'})
_DATA = {
    'genesis': frozenset({'policy_revision', 'population'}),
    'journal_bound': frozenset({'journal_uuid', 'journal_generation'}),
    'profile_configured': frozenset({'profile'}),
    'lifecycle_registered': frozenset({'lifecycle_id', 'slot', 'week',
                                       'profile', 'journal_uuid', 'journal_generation'}),
    'non_model_committed': frozenset({'cost_id', 'kind', 'upper_bound_usd_micros',
                                      'valid_until_utc', 'currency'}),
    'reservation_created': frozenset({
        'journal_uuid', 'journal_generation', 'admission_id', 'intent_id',
        'intent_digest', 'attempt_id', 'reservation_id', 'run_id', 'lease_id',
        'kind', 'lifecycle_id', 'predecessor_id', 'effects_reconciled',
        'profile', 'week', 'reservation_usd_micros', 'liability_usd_micros',
        'currency', 'valid_until_utc', 'policy_revision',
    }),
    'hold_set': frozenset({'hold_id', 'code'}),
}
_PROFILE = frozenset({'model_id', 'auth_id', 'venue_id'})
_WEEK = frozenset({'key', 'start_utc', 'end_utc', 'timezone'})


class AccountingEventError(ValueError):
    """Closed validation error without caller data."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _check(ok, code='event_invalid'):
    if not ok:
        raise AccountingEventError(code)


def _uuid(value):
    _check(type(value) is str and _UUID.fullmatch(value) is not None)


def _digest(value):
    _check(type(value) is str and _HEX.fullmatch(value) is not None)


def _integer(value, lower, upper):
    _check(type(value) is int and lower <= value <= upper)


def _time(value):
    _check(type(value) is str and _TIME.fullmatch(value) is not None)
    invalid = False
    try:
        stamp = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC)
    except ValueError:
        invalid = True
    if invalid:
        raise AccountingEventError('event_invalid') from None
    _check(stamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ') == value)
    return stamp


def _profile(value):
    _check(type(value) is dict and value.keys() == _PROFILE)
    for item in value.values():
        _uuid(item)


def _week(value):
    _check(type(value) is dict and value.keys() == _WEEK)
    _check(value['timezone'] == 'America/New_York')
    start, end = _time(value['start_utc']), _time(value['end_utc'])
    _check(type(value['key']) is str and start.date().isoformat() == value['key'])
    _check(start.weekday() == 0 and end.date() - start.date() == timedelta(days=7))
    _check(end - start in tuple(timedelta(hours=h) for h in (167, 168, 169)))
    for item in (start, end):
        _check(item.hour in (4, 5) and item.minute == item.second == item.microsecond == 0)


def _money(value, *, minimum=0):
    _integer(value, minimum, 2**63 - 1)


def _validate(value):
    _check(type(value) is dict and value.keys() == _TOP)
    _check(type(value['schema_version']) is int and value['schema_version'] == 1,
           'event_unsupported')
    for field in ('ledger_uuid', 'experiment_id', 'event_id'):
        _uuid(value[field])
    _integer(value['ledger_generation'], 1, 2**31 - 1)
    _integer(value['sequence'], 1, 2**53 - 1)
    _digest(value['previous_digest'])
    _time(value['recorded_at_utc'])
    _check(type(value['actor_kind']) is str and value['actor_kind'] in
           ('receiver', 'fixture'))
    kind, data = value['event_type'], value['data']
    _check(type(kind) is str and kind in _DATA, 'event_unsupported')
    _check(type(data) is dict and data.keys() == _DATA[kind])
    if kind == 'genesis':
        _check(data['policy_revision'] == 'accounting-v1')
        _check((value['actor_kind'], data['population']) in
               (('receiver', 'unknown'), ('fixture', 'synthetic_complete')))
        _check(value['sequence'] == 1 and value['previous_digest'] == ZERO)
    elif kind == 'journal_bound':
        _uuid(data['journal_uuid'])
        _integer(data['journal_generation'], 1, 2**31 - 1)
    elif kind == 'profile_configured':
        _profile(data['profile'])
    elif kind == 'lifecycle_registered':
        _uuid(data['lifecycle_id'])
        _check(type(data['slot']) is str and data['slot'] in
               ('rehearsal_1', 'rehearsal_2', 'rehearsal_3', 'presentation'))
        _week(data['week'])
        _profile(data['profile'])
        _uuid(data['journal_uuid'])
        _integer(data['journal_generation'], 1, 2**31 - 1)
    elif kind == 'non_model_committed':
        _uuid(data['cost_id'])
        _check(type(data['kind']) is str and data['kind'] in ('support', 'review', 'venue'))
        _money(data['upper_bound_usd_micros'])
        _time(data['valid_until_utc'])
        _check(type(data['currency']) is str and data['currency'] == 'USD')
    elif kind == 'reservation_created':
        for field in ('journal_uuid', 'admission_id', 'intent_id', 'attempt_id',
                      'reservation_id', 'run_id', 'lease_id'):
            _uuid(data[field])
        _integer(data['journal_generation'], 1, 2**31 - 1)
        _digest(data['intent_digest'])
        _check(type(data['kind']) is str and data['kind'] in
               ('initial', 'retry', 'diagnostic'))
        for field in ('lifecycle_id', 'predecessor_id'):
            if data[field] is not None:
                _uuid(data[field])
        _check(type(data['effects_reconciled']) is bool)
        _profile(data['profile'])
        _week(data['week'])
        _check(type(data['reservation_usd_micros']) is int and
               data['reservation_usd_micros'] == 3_000_000)
        _money(data['liability_usd_micros'], minimum=3_000_000)
        _check(type(data['currency']) is str and data['currency'] == 'USD')
        _time(data['valid_until_utc'])
        _check(data['policy_revision'] == 'accounting-v1')
    else:
        _uuid(data['hold_id'])
        from .accounting_policy import HOLDS
        _check(type(data['code']) is str and data['code'] in HOLDS)


@dataclass(frozen=True, slots=True)
class AccountingEvent:
    raw: bytes
    digest: str

    def fields(self):
        """Return a fresh decoded tree; no mutable value escapes the event."""
        return parse_json(self.raw, max_bytes=MAX_BODY, ascii_only=True)


def decode_event(raw, *, expected_digest):
    _digest(expected_digest)
    _check(type(raw) is bytes and len(raw) <= MAX_BODY)
    invalid = False
    try:
        value = parse_json(raw, max_bytes=MAX_BODY, ascii_only=True)
        canonical = canonical_json(value, ascii_only=True)
    except JSONPolicyError:
        invalid = True
    if invalid:
        raise AccountingEventError('event_invalid') from None
    _check(canonical == raw, 'event_not_canonical')
    _validate(value)
    digest = hashlib.sha256(TAG + raw).hexdigest()
    _check(digest == expected_digest, 'event_digest')
    return AccountingEvent(raw, digest)


def encode_event(*, ledger_uuid, ledger_generation, experiment_id, sequence,
                 previous_digest, event_id, recorded_at_utc, actor_kind,
                 event_type, data):
    value = {'schema_version': 1, 'ledger_uuid': ledger_uuid,
                 'ledger_generation': ledger_generation, 'experiment_id': experiment_id,
                 'sequence': sequence, 'previous_digest': previous_digest,
                 'event_id': event_id, 'recorded_at_utc': recorded_at_utc,
                 'actor_kind': actor_kind, 'event_type': event_type, 'data': data}
    _validate(value)
    invalid = False
    try:
        raw = canonical_json(value, ascii_only=True)
    except JSONPolicyError:
        invalid = True
    if invalid:
        raise AccountingEventError('event_invalid') from None
    _check(len(raw) <= MAX_BODY, 'event_too_large')
    return AccountingEvent(raw, hashlib.sha256(TAG + raw).hexdigest())


__all__ = ['AccountingEvent', 'AccountingEventError', 'decode_event', 'encode_event']
