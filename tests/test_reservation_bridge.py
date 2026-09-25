"""No-launch structural join across proposed journal and accounting records."""

from dataclasses import FrozenInstanceError, asdict, replace

import pytest

from grafana_jsm_sandbox.reservation_bridge import (
    BridgeError,
    JournalConfirmation,
    JournalIntent,
    LedgerReservation,
    assess_bridge,
)

JOURNAL = '11111111-1111-1111-1111-111111111111'
ADMISSION = '22222222-2222-2222-2222-222222222222'
INTENT = '33333333-3333-3333-3333-333333333333'
ATTEMPT = '44444444-4444-4444-4444-444444444444'
RESERVATION = '55555555-5555-5555-5555-555555555555'
RUN = '66666666-6666-6666-6666-666666666666'
LEASE = '77777777-7777-7777-7777-777777777777'
LEDGER = '88888888-8888-8888-8888-888888888888'
EVENT = '99999999-9999-9999-9999-999999999999'
OTHER = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'


def intent(**overrides):
    values = {
        'journal_uuid': JOURNAL, 'journal_generation': 1,
        'admission_id': ADMISSION, 'intent_id': INTENT, 'attempt_id': ATTEMPT,
        'reservation_id': RESERVATION, 'run_id': RUN, 'lease_id': LEASE,
        'intent_digest': 'a' * 64,
    }
    values.update(overrides)
    return JournalIntent(**values)


def ledger(**overrides):
    values = asdict(intent())
    values.update(ledger_uuid=LEDGER, ledger_generation=1, event_id=EVENT,
                  sequence=7, event_digest='b' * 64, read_back=True)
    values.update(overrides)
    return LedgerReservation(**values)


def confirmation(**overrides):
    values = {
        'intent_id': INTENT, 'ledger_uuid': LEDGER, 'ledger_generation': 1,
        'event_id': EVENT, 'sequence': 7, 'event_digest': 'b' * 64,
    }
    values.update(overrides)
    return JournalConfirmation(**values)


def assess(intents=None, reservations=None, confirmations=None):
    return assess_bridge(
        INTENT, (intent(),) if intents is None else intents,
        (ledger(),) if reservations is None else reservations,
        (confirmation(),) if confirmations is None else confirmations,
    )


@pytest.mark.parametrize('values,reason', [
    (((), (), ()), 'missing_intent'),
    (((), (ledger(),), ()), 'orphan_ledger'),
    (((intent(),), (), ()), 'missing_ledger'),
    (((intent(),), (ledger(read_back=False),), (confirmation(),)), 'ledger_unverified'),
    (((intent(),), (ledger(),), ()), 'missing_confirmation'),
])
def test_missing_or_unverified_counterpart_is_a_hold(values, reason):
    result = assess(*values)
    assert result.hold is True
    assert result.reason == reason


def test_exact_triple_is_still_unqualified_and_has_no_permit():
    result = assess()
    assert result.hold is True
    assert result.reason == 'matching_unqualified'
    with pytest.raises(FrozenInstanceError):
        result.hold = False
    for name in ('permit', 'launch', 'spend_available', 'amount'):
        assert not hasattr(result, name)


@pytest.mark.parametrize('field,value', [
    ('journal_uuid', OTHER), ('journal_generation', 2),
    ('admission_id', OTHER), ('attempt_id', OTHER),
    ('reservation_id', OTHER), ('run_id', OTHER), ('lease_id', OTHER),
    ('intent_digest', 'c' * 64),
])
def test_ledger_link_mismatch_is_a_conflict_hold(field, value):
    result = assess(reservations=(ledger(**{field: value}),))
    assert (result.hold, result.reason) == (True, 'identity_conflict')


@pytest.mark.parametrize('field,value', [
    ('ledger_uuid', OTHER), ('ledger_generation', 2),
    ('event_id', OTHER), ('sequence', 8), ('event_digest', 'c' * 64),
])
def test_confirmation_mismatch_is_a_conflict_hold(field, value):
    result = assess(confirmations=(confirmation(**{field: value}),))
    assert (result.hold, result.reason) == (True, 'identity_conflict')


def test_counterpart_conflict_outweighs_missing_readback():
    result = assess(
        reservations=(ledger(read_back=False),),
        confirmations=(confirmation(event_digest='c' * 64),),
    )
    assert result.reason == 'identity_conflict'


def test_exact_duplicate_is_idempotent_but_conflicting_duplicate_holds():
    assert assess(intents=(intent(), intent()),
                  reservations=(ledger(), ledger()),
                  confirmations=(confirmation(), confirmation())).reason == (
                      'matching_unqualified')
    assert assess(intents=(intent(), replace(intent(), run_id=OTHER))).reason == (
        'identity_conflict')
    assert assess(reservations=(ledger(), replace(ledger(), event_id=OTHER))).reason == (
        'identity_conflict')
    assert assess(confirmations=(confirmation(), replace(confirmation(), sequence=8))).reason == (
        'identity_conflict')
    assert assess(intents=(), reservations=(ledger(), replace(
        ledger(), event_id=OTHER,
    )), confirmations=()).reason == 'identity_conflict'


def test_reused_cross_intent_identity_is_conflict_not_a_second_reservation():
    second = intent(intent_id=OTHER)
    result = assess(intents=(intent(), second))
    assert result.reason == 'identity_conflict'


def test_ledger_event_cannot_be_claimed_by_another_intent():
    unrelated = ledger(
        admission_id='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', intent_id=OTHER,
        attempt_id='cccccccc-cccc-cccc-cccc-cccccccccccc',
        reservation_id='dddddddd-dddd-dddd-dddd-dddddddddddd',
        run_id='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
        lease_id='ffffffff-ffff-ffff-ffff-ffffffffffff',
    )
    assert assess(reservations=(ledger(), unrelated)).reason == 'identity_conflict'
    assert assess(confirmations=(confirmation(), replace(
        confirmation(), intent_id=OTHER,
    ))).reason == 'identity_conflict'


@pytest.mark.parametrize('overrides', [
    {'journal_generation': True}, {'intent_digest': 'secret'},
    {'attempt_id': 'private\nbody'}, {'lease_id': 'ABC'},
    {'attempt_id': RESERVATION},
])
def test_malformed_facts_have_only_a_sanitized_code(overrides):
    with pytest.raises(BridgeError, match='^bridge_invalid$') as error:
        assess(intents=(intent(**overrides),))
    assert error.value.code == 'bridge_invalid'
    assert 'private' not in repr(error.value)


def test_wrong_tuple_or_unbounded_family_is_rejected():
    with pytest.raises(BridgeError, match='^bridge_invalid$'):
        assess_bridge(INTENT, [intent()], (ledger(),), (confirmation(),))
    with pytest.raises(BridgeError, match='^bridge_invalid$'):
        assess(intents=(intent(),) * 1025)
