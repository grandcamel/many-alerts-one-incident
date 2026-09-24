"""Public accounting event codec, with independent known byte/digest answers."""

import hashlib
import json

import pytest

from grafana_jsm_sandbox.accounting_events import (
    AccountingEventError,
    decode_event,
    encode_event,
)

L = '11111111-1111-1111-1111-111111111111'
E = '22222222-2222-2222-2222-222222222222'
V = '33333333-3333-3333-3333-333333333333'
ZERO = '0' * 64


def genesis(**changes):
    values = {
        'ledger_uuid': L, 'ledger_generation': 1, 'experiment_id': E,
        'sequence': 1, 'previous_digest': ZERO, 'event_id': V,
        'recorded_at_utc': '2026-09-21T12:00:00.000000Z',
        'actor_kind': 'fixture', 'event_type': 'genesis',
        'data': {'policy_revision': 'accounting-v1',
              'population': 'synthetic_complete'},
    }
    values.update(changes)
    return values


def test_genesis_has_canonical_external_digest():
    event = encode_event(**genesis())
    expected = (b'{"actor_kind":"fixture","data":{"policy_revision":"accounting-v1",'
                b'"population":"synthetic_complete"},"event_id":"33333333-3333-3333-'
                b'3333-333333333333","event_type":"genesis","experiment_id":"22222222-'
                b'2222-2222-2222-222222222222","ledger_generation":1,"ledger_uuid":'
                b'"11111111-1111-1111-1111-111111111111","previous_digest":"' +
                ZERO.encode() + b'","recorded_at_utc":"2026-09-21T12:00:00.000000Z",'
                b'"schema_version":1,"sequence":1}')
    assert event.raw == expected
    assert event.digest == hashlib.sha256(b'acct.event.v1\0' + expected).hexdigest()
    assert decode_event(event.raw, expected_digest=event.digest) == event


@pytest.mark.parametrize('change', [
    {'ledger_generation': True},
    {'ledger_uuid': 'AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA'},
    {'recorded_at_utc': '2026-09-21T12:00:00Z'},
    {'actor_kind': 'receiver'},
    {'data': {'policy_revision': 'accounting-v1', 'population': 'unknown'}},
])
def test_invalid_genesis_refuses(change):
    with pytest.raises(AccountingEventError):
        encode_event(**genesis(**change))


def test_codec_rejects_mismatched_digest_and_noncanonical_bytes():
    event = encode_event(**genesis())
    with pytest.raises(AccountingEventError):
        decode_event(event.raw, expected_digest=ZERO)
    with pytest.raises(AccountingEventError):
        decode_event(event.raw.replace(b'"sequence":1', b'"sequence": 1'),
                     expected_digest=event.digest)


def test_invalid_time_error_retains_no_caller_data_in_context():
    with pytest.raises(AccountingEventError) as error:
        encode_event(**genesis(recorded_at_utc='2026-99-21T12:00:00.000000Z'))
    assert str(error.value) == 'event_invalid'
    assert error.value.__context__ is None


def _reservation_data():
    from datetime import UTC, datetime

    from grafana_jsm_sandbox.accounting_policy import week_for

    week = week_for(datetime(2026, 9, 21, 12, tzinfo=UTC))
    return {
        'journal_uuid': '44444444-4444-4444-4444-444444444444',
        'journal_generation': 1,
        'admission_id': '55555555-5555-5555-5555-555555555555',
        'intent_id': '66666666-6666-6666-6666-666666666666',
        'intent_digest': 'a' * 64,
        'attempt_id': '77777777-7777-7777-7777-777777777777',
        'reservation_id': '88888888-8888-8888-8888-888888888888',
        'run_id': '99999999-9999-9999-9999-999999999999',
        'lease_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        'kind': 'initial', 'lifecycle_id': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'predecessor_id': None, 'effects_reconciled': False,
        'profile': {'model_id': 'cccccccc-cccc-cccc-cccc-cccccccccccc',
                    'auth_id': 'dddddddd-dddd-dddd-dddd-dddddddddddd',
                    'venue_id': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'},
        'week': {'key': week.key,
                 'start_utc': week.start_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                 'end_utc': week.end_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                 'timezone': week.timezone},
        'reservation_usd_micros': 3_000_000,
        'liability_usd_micros': 3_000_000, 'currency': 'USD',
        'valid_until_utc': '2026-09-21T14:00:00.000000Z',
        'policy_revision': 'accounting-v1',
    }


@pytest.mark.parametrize(('field', 'value'), [
    ('liability_usd_micros', True),
    ('liability_usd_micros', -1),
    ('liability_usd_micros', 2**63),
    ('reservation_usd_micros', 2_999_999),
    ('currency', 'EUR'),
])
def test_reservation_money_shape_refuses(field, value):
    data = _reservation_data()
    data[field] = value
    with pytest.raises(AccountingEventError):
        encode_event(**genesis(event_type='reservation_created', data=data))


def test_decoder_rejects_unknown_version_extra_field_and_byte_bound():
    event = encode_event(**genesis())
    for change in ({'schema_version': 2}, {'event_type': 'unregistered'},
                   {'extra': 1}):
        value = json.loads(event.raw)
        value.update(change)
        raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        digest = hashlib.sha256(b'acct.event.v1\0' + raw).hexdigest()
        with pytest.raises(AccountingEventError):
            decode_event(raw, expected_digest=digest)
    missing = json.loads(event.raw)
    del missing['data']['population']
    raw = json.dumps(missing, sort_keys=True, separators=(',', ':')).encode()
    digest = hashlib.sha256(b'acct.event.v1\0' + raw).hexdigest()
    with pytest.raises(AccountingEventError):
        decode_event(raw, expected_digest=digest)
    with pytest.raises(AccountingEventError):
        decode_event(event.raw + b' ' * 16_384, expected_digest=event.digest)
