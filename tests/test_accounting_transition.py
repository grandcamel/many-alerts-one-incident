"""Behavior through the pure replay and transition interfaces."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from grafana_jsm_sandbox.accounting_events import ZERO, encode_event
from grafana_jsm_sandbox.accounting_policy import (
    Candidate,
    Exposure,
    HypotheticalProposal,
    Snapshot,
    evaluate_reservation,
    week_for,
)
from grafana_jsm_sandbox.accounting_transition import (
    AccountingTransitionError,
    apply_event,
    replay_accounting,
)


def uid(number):
    return str(UUID(int=number))


PROFILE = {'model_id': uid(10), 'auth_id': uid(11), 'venue_id': uid(12)}
LEDGER, EXPERIMENT, JOURNAL = uid(1), uid(2), uid(3)


def stamp(minute):
    return f'2026-09-21T12:{minute:02d}:00.000000Z'


def week(day=21):
    value = week_for(datetime(2026, 9, day, 12, tzinfo=UTC))
    return {'key': value.key,
                'start_utc': value.start_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'end_utc': value.end_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'timezone': value.timezone}


def append(events, kind, data, *, minute=None, at=None, actor='fixture'):
    count = len(events) + 1
    event = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=count, previous_digest=events[-1].digest if events else ZERO,
        event_id=uid(100 + count),
        recorded_at_utc=at or stamp(count if minute is None else minute),
        actor_kind=actor, event_type=kind, data=data,
    )
    return (*events, event)


def configured():
    events = append((), 'genesis',
                    {'policy_revision': 'accounting-v1', 'population': 'synthetic_complete'})
    events = append(events, 'journal_bound',
                    {'journal_uuid': JOURNAL, 'journal_generation': 1})
    events = append(events, 'profile_configured', {'profile': PROFILE})
    events = append(events, 'lifecycle_registered',
                    {'lifecycle_id': uid(20), 'slot': 'rehearsal_1', 'week': week(),
                         'profile': PROFILE, 'journal_uuid': JOURNAL, 'journal_generation': 1})
    return events


def reservation(*, liability=3_000_000, attempt=30, journal=JOURNAL,
                generation=1, lifecycle=20):
    return {
        'journal_uuid': journal, 'journal_generation': generation,
        'admission_id': uid(attempt + 10), 'intent_id': uid(attempt + 20),
        'intent_digest': 'a' * 64, 'attempt_id': uid(attempt),
        'reservation_id': uid(attempt + 100), 'run_id': uid(attempt + 200),
        'lease_id': uid(attempt + 300), 'kind': 'initial',
        'lifecycle_id': uid(lifecycle), 'predecessor_id': None,
        'effects_reconciled': False, 'profile': PROFILE, 'week': week(),
        'reservation_usd_micros': 3_000_000, 'liability_usd_micros': liability,
        'currency': 'USD', 'valid_until_utc': '2026-09-21T14:00:00.000000Z',
        'policy_revision': 'accounting-v1',
    }


def test_replay_reconstructs_one_conservative_reservation():
    events = append(configured(), 'reservation_created', reservation())
    left = replay_accounting(events)
    right = replay_accounting(events)
    assert left == right
    assert left.head_sequence == 5
    assert left.head_digest == events[-1].digest
    assert len(left.attempts) == 1
    assert left.attempts[0].attempt.exposure.upper_bound == 3_000_000
    assert left.attempts[0].journal_origin == (JOURNAL, 1)
    assert left.population == 'synthetic_complete'


def test_projection_facts_yield_independent_known_policy_totals():
    state = replay_accounting(append(configured(), 'reservation_created',
                                     reservation(liability=4_000_000)))
    at = datetime(2026, 9, 21, 12, 6, tzinfo=UTC)
    snapshot = Snapshot(
        EXPERIMENT, 1, at, 'hypothetical_complete', state.profiles,
        tuple(item.lifecycle for item in state.lifecycles),
        tuple(item.attempt for item in state.attempts), state.costs, (),
    )
    candidate = Candidate(
        EXPERIMENT, 1, uid(31), uid(131), uid(231), uid(331),
        state.profiles[0], 'initial', uid(20), None, False,
        Exposure('bounded', 3_000_000,
                 datetime(2026, 9, 21, 14, tzinfo=UTC), None),
    )
    result = evaluate_reservation(snapshot, candidate, at=at)
    assert isinstance(result, HypotheticalProposal)
    assert result.totals.week_model == 7_000_000
    assert result.totals.experiment == 7_000_000
    assert result.totals.lifecycle == 7_000_000
    assert result.totals.lifecycle_attempts == 2
    assert result.totals.diagnostic == result.totals.diagnostic_attempts == 0


def test_unknown_population_and_stale_head_refuse_without_change():
    events = append((), 'genesis',
                    {'policy_revision': 'accounting-v1', 'population': 'unknown'},
                    actor='receiver')
    state = replay_accounting(events)
    with pytest.raises(AccountingTransitionError):
        apply_event(state, append(events, 'reservation_created', reservation())[-1],
                    expected_head=state.head_digest)
    assert state.head_sequence == 1
    with pytest.raises(AccountingTransitionError) as error:
        apply_event(state, append(events, 'journal_bound',
                                  {'journal_uuid': JOURNAL, 'journal_generation': 1})[-1],
                    expected_head=ZERO)
    assert error.value.code == 'stale_head'


def test_exact_duplicate_apply_is_idempotent_but_stream_duplicate_refuses():
    events = configured()
    state = replay_accounting(events)
    event = append(events, 'reservation_created', reservation())[-1]
    advanced = apply_event(state, event, expected_head=state.head_digest)
    assert apply_event(advanced, event, expected_head=advanced.head_digest) == advanced
    with pytest.raises(AccountingTransitionError):
        replay_accounting((*events, event, event))


def test_changed_duplicate_event_and_reservation_identities_refuse():
    events = append(configured(), 'reservation_created', reservation())
    state = replay_accounting(events)
    changed = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=5, previous_digest=events[-2].digest, event_id=uid(105),
        recorded_at_utc=stamp(5), actor_kind='fixture',
        event_type='reservation_created', data=reservation(liability=4_000_000),
    )
    with pytest.raises(AccountingTransitionError) as error:
        apply_event(state, changed, expected_head=state.head_digest)
    assert error.value.code == 'event_conflict'
    for field in ('intent_id', 'attempt_id', 'reservation_id'):
        duplicate = reservation(attempt=31)
        duplicate[field] = reservation()[field]
        with pytest.raises(AccountingTransitionError) as error:
            replay_accounting(append(events, 'reservation_created', duplicate))
        assert error.value.code == 'identity_conflict'


def test_missing_configuration_refuses_reservation():
    genesis = append((), 'genesis',
                     {'policy_revision': 'accounting-v1',
                      'population': 'synthetic_complete'})
    bound = append(genesis, 'journal_bound',
                   {'journal_uuid': JOURNAL, 'journal_generation': 1})
    with pytest.raises(AccountingTransitionError):
        replay_accounting(append(bound, 'reservation_created', reservation()))
    diagnostic = reservation()
    diagnostic.update(kind='diagnostic', lifecycle_id=None)
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(bound, 'reservation_created', diagnostic))
    assert error.value.code == 'configuration_conflict'


def test_rebinding_cannot_reuse_old_lifecycle():
    events = configured()
    events = append(events, 'journal_bound',
                    {'journal_uuid': uid(4), 'journal_generation': 2})
    with pytest.raises(AccountingTransitionError):
        replay_accounting(append(events, 'reservation_created',
                                 reservation(journal=uid(4), generation=2)))


def test_new_generation_with_same_journal_uuid_retains_prior_liability():
    events = append(configured(), 'reservation_created', reservation(liability=4_000_000))
    events = append(events, 'journal_bound',
                    {'journal_uuid': JOURNAL, 'journal_generation': 2})
    events = append(events, 'lifecycle_registered',
                    {'lifecycle_id': uid(21), 'slot': 'rehearsal_2', 'week': week(),
                     'profile': PROFILE, 'journal_uuid': JOURNAL,
                     'journal_generation': 2})
    events = append(events, 'reservation_created',
                    reservation(attempt=31, journal=JOURNAL,
                                generation=2, lifecycle=21, liability=5_000_000))
    state = replay_accounting(events)
    assert len(state.attempts) == 2
    assert [row.attempt.exposure.upper_bound for row in state.attempts] == [
        4_000_000, 5_000_000]
    assert [row.journal_origin for row in state.attempts] == [
        (JOURNAL, 1), (JOURNAL, 2)]


def test_same_admission_new_intent_counts_two_reservations():
    events = append(configured(), 'reservation_created', reservation())
    second = reservation(attempt=31)
    second['admission_id'] = uid(40)
    state = replay_accounting(append(events, 'reservation_created', second))
    assert len(state.attempts) == 2
    assert state.attempts[0].admission_id == state.attempts[1].admission_id


def test_nonmodel_liability_and_hold_refuse_new_reservation():
    events = append(configured(), 'non_model_committed',
                    {'cost_id': uid(400), 'kind': 'venue',
                     'upper_bound_usd_micros': 47_000_000,
                     'valid_until_utc': '2026-09-21T14:00:00.000000Z',
                     'currency': 'USD'})
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'reservation_created', reservation()))
    assert error.value.code == 'experiment_limit'
    held = append(configured(), 'hold_set',
                  {'hold_id': uid(401), 'code': 'billing_unknown'})
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(held, 'reservation_created', reservation()))
    assert error.value.code == 'held'


def test_gaps_forks_and_unbound_lifecycle_refuse():
    events = configured()
    broken = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=6, previous_digest=events[-1].digest, event_id=uid(106),
        recorded_at_utc=stamp(6), actor_kind='fixture',
        event_type='hold_set', data={'hold_id': uid(500), 'code': 'billing_unknown'},
    )
    with pytest.raises(AccountingTransitionError):
        replay_accounting((*events, broken))
    forked = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=5, previous_digest=ZERO, event_id=uid(105),
        recorded_at_utc=stamp(5), actor_kind='fixture',
        event_type='hold_set', data={'hold_id': uid(500), 'code': 'billing_unknown'},
    )
    with pytest.raises(AccountingTransitionError):
        replay_accounting((*events, forked))


def test_empty_history_and_cross_role_identity_conflicts_refuse():
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(())
    assert error.value.code == 'history_unavailable'
    genesis = append((), 'genesis',
                     {'policy_revision': 'accounting-v1',
                      'population': 'synthetic_complete'})
    bad_profile = {'model_id': LEDGER, 'auth_id': uid(11), 'venue_id': uid(12)}
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(genesis, 'profile_configured',
                                 {'profile': bad_profile}))
    assert error.value.code == 'identity_conflict'
    repeated = {'model_id': uid(10), 'auth_id': uid(10), 'venue_id': uid(12)}
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(genesis, 'profile_configured',
                                 {'profile': repeated}))
    assert error.value.code == 'identity_conflict'


def test_public_apply_rejects_projection_forged_against_its_event_history():
    events = append(configured(), 'reservation_created', reservation())
    state = replay_accounting(events)
    forged = replace(state, attempts=())
    next_event = append(events, 'reservation_created', reservation(attempt=31))[-1]
    with pytest.raises(AccountingTransitionError) as error:
        apply_event(forged, next_event, expected_head=state.head_digest)
    assert error.value.code == 'projection_conflict'


def test_current_event_id_cannot_reuse_new_body_identity():
    genesis = append((), 'genesis',
                     {'policy_revision': 'accounting-v1',
                      'population': 'synthetic_complete'})
    collision = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=2, previous_digest=genesis[-1].digest, event_id=JOURNAL,
        recorded_at_utc=stamp(2), actor_kind='fixture',
        event_type='journal_bound',
        data={'journal_uuid': JOURNAL, 'journal_generation': 1},
    )
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting((*genesis, collision))
    assert error.value.code == 'identity_conflict'


def test_profile_id_may_repeat_in_its_role_but_not_switch_roles():
    events = append((), 'genesis',
                    {'policy_revision': 'accounting-v1',
                     'population': 'synthetic_complete'})
    events = append(events, 'profile_configured', {'profile': PROFILE})
    switched = {'model_id': PROFILE['auth_id'],
                'auth_id': uid(13), 'venue_id': uid(14)}
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'profile_configured',
                                 {'profile': switched}))
    assert error.value.code == 'identity_conflict'
    allowed = {'model_id': PROFILE['model_id'],
               'auth_id': uid(13), 'venue_id': uid(14)}
    assert len(replay_accounting(append(events, 'profile_configured',
                                        {'profile': allowed})).profiles) == 2


def test_admission_reference_cannot_move_to_new_journal_origin():
    events = append(configured(), 'reservation_created', reservation())
    events = append(events, 'journal_bound',
                    {'journal_uuid': JOURNAL, 'journal_generation': 2})
    events = append(events, 'lifecycle_registered',
                    {'lifecycle_id': uid(21), 'slot': 'rehearsal_2', 'week': week(),
                     'profile': PROFILE, 'journal_uuid': JOURNAL,
                     'journal_generation': 2})
    second = reservation(attempt=31, generation=2, lifecycle=21)
    second['admission_id'] = uid(40)
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'reservation_created', second))
    assert error.value.code == 'origin_conflict'


def test_reservation_outside_policy_year_returns_closed_transition_error():
    events = configured()
    data = reservation()
    data['valid_until_utc'] = '9999-01-06T00:00:00.000000Z'
    future = encode_event(
        ledger_uuid=LEDGER, ledger_generation=1, experiment_id=EXPERIMENT,
        sequence=5, previous_digest=events[-1].digest, event_id=uid(105),
        recorded_at_utc='9999-01-05T12:00:00.000000Z',
        actor_kind='fixture', event_type='reservation_created', data=data,
    )
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting((*events, future))
    assert error.value.code == 'invalid_time'


def test_stale_u_wrong_week_and_missing_binding_refuse():
    events = configured()
    stale = reservation()
    stale['valid_until_utc'] = '2026-09-21T12:04:00.000000Z'
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'reservation_created', stale))
    assert error.value.code == 'exposure_stale'
    wrong_week = reservation()
    wrong_week['week'] = week(14)
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'reservation_created', wrong_week))
    assert error.value.code == 'invalid_week'
    incomplete = events[:1]
    with pytest.raises(AccountingTransitionError):
        replay_accounting(append(incomplete, 'reservation_created', reservation()))


def test_inactive_journal_cannot_register_a_lifecycle():
    events = append(configured(), 'journal_bound',
                    {'journal_uuid': uid(4), 'journal_generation': 1})
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'lifecycle_registered',
                                 {'lifecycle_id': uid(21), 'slot': 'rehearsal_2',
                                  'week': week(), 'profile': PROFILE,
                                  'journal_uuid': JOURNAL,
                                  'journal_generation': 1}))
    assert error.value.code == 'origin_conflict'


def test_old_week_liability_remains_in_strict_lifetime_cap():
    prior = reservation(liability=30_000_000)
    prior['valid_until_utc'] = '2026-09-29T14:00:00.000000Z'
    events = append(configured(), 'reservation_created', prior)
    events = append(events, 'lifecycle_registered',
                    {'lifecycle_id': uid(21), 'slot': 'rehearsal_1',
                     'week': week(28), 'profile': PROFILE,
                     'journal_uuid': JOURNAL, 'journal_generation': 1},
                    at='2026-09-28T12:06:00.000000Z')
    candidate = reservation(attempt=31, lifecycle=21, liability=20_000_000)
    candidate['week'] = week(28)
    candidate['valid_until_utc'] = '2026-09-28T14:00:00.000000Z'
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'reservation_created', candidate,
                                 at='2026-09-28T12:07:00.000000Z'))
    assert error.value.code == 'experiment_limit'


def test_old_generation_liability_remains_in_strict_lifetime_cap():
    events = append(configured(), 'reservation_created',
                    reservation(liability=30_000_000))
    events = append(events, 'journal_bound',
                    {'journal_uuid': JOURNAL, 'journal_generation': 2})
    events = append(events, 'lifecycle_registered',
                    {'lifecycle_id': uid(21), 'slot': 'rehearsal_2',
                     'week': week(), 'profile': PROFILE,
                     'journal_uuid': JOURNAL, 'journal_generation': 2})
    events = append(events, 'non_model_committed',
                    {'cost_id': uid(400), 'kind': 'venue',
                     'upper_bound_usd_micros': 17_000_000,
                     'valid_until_utc': '2026-09-21T14:00:00.000000Z',
                     'currency': 'USD'})
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(events, 'reservation_created',
                                 reservation(attempt=31, generation=2,
                                             lifecycle=21)))
    assert error.value.code == 'experiment_limit'


def test_cross_week_retry_refuses_without_reassigning_old_week():
    prior = reservation()
    prior['valid_until_utc'] = '2026-09-29T14:00:00.000000Z'
    events = append(configured(), 'reservation_created', prior)
    retry = reservation(attempt=31)
    retry.update(kind='retry', predecessor_id=uid(30),
                 effects_reconciled=True, week=week(28),
                 valid_until_utc='2026-09-28T14:00:00.000000Z')
    with pytest.raises(AccountingTransitionError):
        replay_accounting(append(events, 'reservation_created', retry,
                                 at='2026-09-28T12:06:00.000000Z'))


def test_retry_consumes_diagnostics_but_counts_once_in_lifetime():
    events = append(configured(), 'non_model_committed',
                    {'cost_id': uid(400), 'kind': 'venue',
                     'upper_bound_usd_micros': 17_000_000,
                     'valid_until_utc': '2026-09-21T14:00:00.000000Z',
                     'currency': 'USD'})
    events = append(events, 'reservation_created', reservation())
    diagnostic = reservation(attempt=31, liability=26_000_000)
    diagnostic.update(kind='diagnostic', lifecycle_id=None)
    events = append(events, 'reservation_created', diagnostic)
    retry = reservation(attempt=32)
    retry.update(kind='retry', predecessor_id=uid(30), effects_reconciled=True)
    accepted = replay_accounting(append(events, 'reservation_created', retry))
    assert [entry.attempt.kind for entry in accepted.attempts] == [
        'initial', 'diagnostic', 'retry']
    separate = append(configured(), 'reservation_created', reservation())
    full_diagnostics = reservation(attempt=31, liability=30_000_000)
    full_diagnostics.update(kind='diagnostic', lifecycle_id=None)
    separate = append(separate, 'reservation_created', full_diagnostics)
    over_diagnostics = reservation(attempt=32)
    over_diagnostics.update(kind='retry', predecessor_id=uid(30),
                            effects_reconciled=True)
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting(append(separate, 'reservation_created',
                                 over_diagnostics))
    assert error.value.code == 'diagnostic_limit'


def test_replay_input_bound_refuses_before_partial_application():
    genesis = append((), 'genesis',
                     {'policy_revision': 'accounting-v1',
                      'population': 'synthetic_complete'})[0]
    with pytest.raises(AccountingTransitionError) as error:
        replay_accounting((genesis,) * 8193)
    assert error.value.code == 'history_limit'
