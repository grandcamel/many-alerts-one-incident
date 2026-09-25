"""ADR 0012 execution classification from sanitized, local observations."""

from dataclasses import FrozenInstanceError

import pytest

from grafana_jsm_sandbox.run_outcome import (
    OutcomeError,
    ProcessFacts,
    TerminalFacts,
    assess_execution,
)

DIGEST = 'a' * 64


def process(**overrides):
    fields = {'spawn_state': 'accepted', 'exit_observed': True, 'exit_code': 0,
              'exit_signal': None, 'timed_out': False, 'cancelled': False,
              'containment': 'confirmed'}
    fields.update(overrides)
    return ProcessFacts(**fields)


def terminal(**overrides):
    fields = {'subtype': 'success', 'is_error': False, 'reason': None,
              'usage_state': 'known', 'evidence_digest': DIGEST}
    fields.update(overrides)
    return TerminalFacts(**fields)


def test_only_clean_exit_one_valid_success_and_confirmed_containment_succeeds():
    result = assess_execution(process(), (terminal(),))
    assert (result.state, result.reasons, result.usage, result.never_started) == (
        'succeeded', (), 'known', False)
    with pytest.raises(FrozenInstanceError):
        result.state = 'failed'
    assert not hasattr(result, 'permit')
    assert not hasattr(result, 'effect')


@pytest.mark.parametrize('containment', ['failed', 'unknown'])
def test_unconfirmed_containment_overrides_success_and_timeout(containment):
    result = assess_execution(process(containment=containment, timed_out=True),
                              (terminal(),))
    assert result.state == 'containment_failed'
    assert 'timeout' in result.reasons
    assert any(reason.startswith('containment_') for reason in result.reasons)


@pytest.mark.parametrize('flag,reason', [('timed_out', 'timeout'),
                                        ('cancelled', 'cancelled')])
def test_receiver_deadline_or_cancel_overrides_clean_terminal(flag, reason):
    result = assess_execution(process(**{flag: True}), (terminal(),))
    assert result.state == 'cancelled'
    assert reason in result.reasons


def test_trusted_preprocess_spawn_failure_is_failed_and_never_started():
    facts = process(spawn_state='failed_before_process', exit_observed=False,
                    exit_code=None, containment='unknown')
    result = assess_execution(facts, ())
    assert result.state == 'failed'
    assert result.never_started is True
    assert 'spawn_failed' in result.reasons


@pytest.mark.parametrize('facts,terminals,reason', [
    (process(exit_code=7), (terminal(),), 'nonzero_exit'),
    (process(exit_code=None, exit_signal=9), (terminal(),), 'signaled_exit'),
    (process(), (terminal(subtype='error', is_error=True),), 'result_error'),
])
def test_process_or_terminal_error_prevents_success(facts, terminals, reason):
    result = assess_execution(facts, terminals)
    assert result.state == 'failed'
    assert reason in result.reasons


@pytest.mark.parametrize('terminals,reason', [
    ((), 'missing_terminal'),
    ((terminal(), terminal()), 'duplicate_terminal'),
    ((terminal(is_error=1),), 'terminal_invalid'),
    ((terminal(subtype='success', is_error=True),), 'terminal_invalid'),
    ((terminal(subtype='error', is_error=False),), 'terminal_invalid'),
    ((terminal(reason='error: denied'),), 'terminal_invalid'),
    ((terminal(reason='private\nbody'),), 'terminal_invalid'),
    ((terminal(evidence_digest='bad'),), 'terminal_invalid'),
])
def test_missing_duplicate_or_malformed_terminal_is_incomplete(terminals, reason):
    result = assess_execution(process(), terminals)
    assert result.state == 'incomplete'
    assert reason in result.reasons
    assert result.usage == 'unknown'
    assert 'private' not in repr(result)


def test_missing_exit_and_unknown_spawn_do_not_prove_never_started():
    missing_exit = assess_execution(
        process(exit_observed=False, exit_code=None), (terminal(),))
    assert missing_exit.state == 'incomplete'
    assert 'exit_missing' in missing_exit.reasons
    unknown_spawn = assess_execution(
        process(spawn_state='unknown', exit_observed=False, exit_code=None,
                containment='unknown'), (terminal(),))
    assert unknown_spawn.state == 'containment_failed'
    assert unknown_spawn.never_started is False


@pytest.mark.parametrize('usage_state', ['absent', 'malformed'])
def test_missing_or_malformed_usage_is_unknown_not_zero(usage_state):
    result = assess_execution(process(), (terminal(usage_state=usage_state),))
    assert result.usage == 'unknown'
    assert result.state == ('succeeded' if usage_state == 'absent' else 'incomplete')


@pytest.mark.parametrize('changes', [
    {'exit_observed': 1}, {'exit_code': True}, {'exit_code': 2**31},
    {'exit_code': None}, {'exit_signal': 0, 'exit_code': None},
    {'exit_signal': 9}, {'timed_out': 1}, {'containment': 'maybe'},
    {'spawn_state': 'not_attempted'},
])
def test_invalid_process_facts_have_one_sanitized_code(changes):
    with pytest.raises(OutcomeError, match='^process_invalid$') as error:
        assess_execution(process(**changes), (terminal(),))
    assert error.value.code == 'process_invalid'
