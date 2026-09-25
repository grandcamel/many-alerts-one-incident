"""Receiver-facing ledger operations remain non-reserving."""

from datetime import UTC, datetime

import pytest

from grafana_jsm_sandbox.accounting_ledger import AccountingLedger
from grafana_jsm_sandbox.accounting_policy import week_for
from grafana_jsm_sandbox.accounting_store import LedgerError

LEDGER = '11111111-1111-1111-1111-111111111111'
EXPERIMENT = '22222222-2222-2222-2222-222222222222'
GENESIS = '33333333-3333-3333-3333-333333333333'
JOURNAL = '44444444-4444-4444-4444-444444444444'
BINDING = '55555555-5555-5555-5555-555555555555'


def test_receiver_wrapper_records_only_an_event_receipt(tmp_path):
    directory = tmp_path / 'ledger'
    with AccountingLedger.create(
        directory, ledger_uuid=LEDGER, ledger_generation=1,
        experiment_id=EXPERIMENT, event_id=GENESIS,
        recorded_at_utc='2026-09-24T12:00:00.000000Z',
    ) as ledger:
        prior_head = ledger.head[1]
        receipt = ledger.record(
            'journal_bound', {'journal_uuid': JOURNAL, 'journal_generation': 1},
            event_id=BINDING, recorded_at_utc='2026-09-24T12:01:00.000000Z',
            expected_head=prior_head,
        )
        assert receipt.sequence == 2
        assert receipt.read_back is True
        assert not hasattr(receipt, 'launch_permit')
        retry = ledger.record(
            'journal_bound', {'journal_uuid': JOURNAL, 'journal_generation': 1},
            event_id=BINDING, recorded_at_utc='2026-09-24T12:01:00.000000Z',
            expected_head=prior_head,
        )
        assert (retry.sequence, retry.event_digest) == (
            receipt.sequence, receipt.event_digest)
        with pytest.raises(LedgerError, match='reservation_unavailable'):
            ledger.record('reservation_created', {}, event_id=BINDING,
                          recorded_at_utc='2026-09-24T12:02:00.000000Z',
                          expected_head=ledger.head[1])
    with AccountingLedger.open(directory) as reopened:
        assert reopened.head == (2, receipt.event_digest)
        assert reopened.population == 'unknown'


def test_all_nonreserving_business_events_replay_after_open(tmp_path):
    directory = tmp_path / 'ledger'
    profile = {'model_id': '66666666-6666-6666-6666-666666666666',
               'auth_id': '77777777-7777-7777-7777-777777777777',
               'venue_id': '88888888-8888-8888-8888-888888888888'}
    week = week_for(datetime(2026, 9, 24, 12, tzinfo=UTC))
    week_json = {'key': week.key, 'timezone': week.timezone,
                 'start_utc': week.start_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                 'end_utc': week.end_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
    with AccountingLedger.create(
        directory, ledger_uuid=LEDGER, ledger_generation=1,
        experiment_id=EXPERIMENT, event_id=GENESIS,
        recorded_at_utc='2026-09-24T12:00:00.000000Z',
    ) as ledger:
        records = (
            ('journal_bound', {'journal_uuid': JOURNAL, 'journal_generation': 1},
             BINDING),
            ('profile_configured', {'profile': profile},
             'cccccccc-cccc-cccc-cccc-cccccccccccc'),
            ('lifecycle_registered', {
                'lifecycle_id': '99999999-9999-9999-9999-999999999999',
                'slot': 'rehearsal_1', 'week': week_json, 'profile': profile,
                'journal_uuid': JOURNAL, 'journal_generation': 1,
            }, 'dddddddd-dddd-dddd-dddd-dddddddddddd'),
            ('non_model_committed', {
                'cost_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                'kind': 'support', 'upper_bound_usd_micros': 1_000_000,
                'valid_until_utc': '2026-09-25T12:00:00.000000Z',
                'currency': 'USD',
            }, 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'),
            ('hold_set', {'hold_id': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
                          'code': 'billing_unknown'},
             'ffffffff-ffff-ffff-ffff-ffffffffffff'),
        )
        for minute, (kind, data, event_id) in enumerate(records, 1):
            ledger.record(kind, data, event_id=event_id,
                          recorded_at_utc=f'2026-09-24T12:{minute:02d}:00.000000Z',
                          expected_head=ledger.head[1])
    with AccountingLedger.open(directory) as reopened:
        assert reopened.head[0] == 6
        assert reopened.population == 'unknown'
