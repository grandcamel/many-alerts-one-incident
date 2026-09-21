"""Real offline logic under virtual time; no shells, model calls or native processes."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from prototype.run_timing.executor import (
    LENGTHS,
    Capture,
    Charge,
    Frame,
    LengthProbe,
    Lifecycle,
    Receipt,
    admission,
    command_for,
    replay,
)
from tests.test_timing_outcomes import assistant, terminal


def test_deadlines_and_repeated_output_cannot_extend_work():
    lifecycle = Lifecycle()
    for at in (0, 1, 120, 269.999):
        assert lifecycle.advance(at) == ()
        assert lifecycle.work_allowed
    assert lifecycle.advance(270) == ("revoke", "interrupt")
    assert not lifecycle.work_allowed
    assert lifecycle.advance(289.999) == ()
    assert lifecycle.advance(290) == ("kill_and_reap",)
    assert lifecycle.advance(300) == ("hold",)
    assert lifecycle.reasons == {"timeout", "containment_failure"}


@pytest.mark.parametrize("cancel_at", [0, 40, 269.999])
def test_cancel_deadlines_are_anchored_once(cancel_at):
    life = Lifecycle()
    assert life.advance(cancel_at, cancel=True) == ("revoke", "interrupt")
    assert life.kill_at == cancel_at + 20
    assert life.end_at == cancel_at + 30
    life.advance(cancel_at + 5, cancel=True)
    assert life.end_at == cancel_at + 30


def test_parent_exit_does_not_prove_descendant_reaping_or_closed_pipes():
    life = Lifecycle()
    assert life.advance(1, parent_exited=True) == ("revoke", "interrupt")
    assert not life.finished
    life.advance(21, parent_exited=True, reaped=True, pipes_closed=False)
    assert life.killed
    life.advance(31, parent_exited=True, reaped=True, pipes_closed=False)
    assert "containment_failure" in life.reasons


def test_confirmed_reaping_at_bound_is_allowed_but_late_is_not():
    life = Lifecycle()
    life.advance(270)
    assert life.advance(300, parent_exited=True, reaped=True, pipes_closed=True)[-1] == "closed"
    assert "containment_failure" not in life.reasons
    life = Lifecycle()
    life.advance(270)
    life.advance(300.001, parent_exited=True, reaped=True, pipes_closed=True)
    assert "containment_failure" in life.reasons


@pytest.mark.parametrize("at", [-1, float("nan"), float("inf"), True])
def test_bad_clock_rejected(at):
    with pytest.raises((TypeError, ValueError)):
        Lifecycle().advance(at)


def test_backwards_clock_rejected():
    life = Lifecycle()
    life.advance(2)
    with pytest.raises(ValueError):
        life.advance(1)


def test_fixed_commands_match_preparation_fixtures_exactly():
    path = Path(__file__).parents[1] / (
        '.scratch/many-alerts-one-incident/reviews/ticket-23/fixtures/length-cases.json')
    fixtures = json.loads(path.read_text())['cases']
    for case, length in zip(fixtures, LENGTHS, strict=True):
        command = command_for(length)
        assert len(command) == length
        assert command == case['command_data_do_not_execute'].encode('ascii')
        assert hashlib.sha256(command).hexdigest() == case['command_sha256']


def test_complete_fixed_grid_produces_observed_bracket_not_universal_threshold():
    probe = LengthProbe(Lifecycle())
    for i, length in enumerate(LENGTHS):
        command = command_for(length)
        if i < 2:
            receipt = probe.dispatch(command, f'tool-{i}', stub_exit=1)
            assert probe.observe(command, receipt=receipt) == 'dispatched'
        else:
            probe.begin(command, f'tool-{i}')
            assert probe.observe(command, native_decision='permission_denied_before_dispatch',
                                 coverage_complete=True) == 'permission_denied_no_dispatch'
    assert probe.bracket() == {'status': 'observed_bracket', 'largest_dispatched': 11000,
                               'smallest_denied': 12000,
                               'scope': 'synthetic fixed-shape replay only'}
    with pytest.raises(ValueError):
        probe.dispatch(command_for(9500), 'extra')


@pytest.mark.parametrize('pattern,status', [
    ([True] * 5, 'all_dispatched'), ([False] * 5, 'all_denied'),
    ([True, False, True, False, False], 'nonmonotonic'),
])
def test_bracket_refuses_false_thresholds(pattern, status):
    probe = LengthProbe(Lifecycle())
    for i, (length, dispatch) in enumerate(zip(LENGTHS, pattern)):
        command = command_for(length)
        if dispatch:
            receipt = probe.dispatch(command, str(i))
            probe.observe(command, receipt=receipt)
        else:
            probe.begin(command, str(i))
            probe.observe(command, native_decision='permission_denied_before_dispatch',
                          coverage_complete=True)
    assert probe.bracket()['status'] == status


def test_forged_or_other_attempt_receipt_does_not_prove_dispatch():
    command = command_for(9500)
    other = LengthProbe(Lifecycle())
    issued = other.dispatch(command, 'tool')
    for receipt in (issued, Receipt(0, 'tool', issued.command_sha256, 0)):
        probe = LengthProbe(Lifecycle())
        probe.begin(command, 'tool')
        assert probe.observe(command, receipt=receipt) == 'dispatch_unknown'
        assert probe.hold


def test_stale_receipt_cannot_confirm_a_different_case():
    probe = LengthProbe(Lifecycle())
    receipt = probe.dispatch(command_for(9500), 'tool')
    probe.observe(command_for(9500), receipt=receipt)
    probe.begin(command_for(11000), 'second')
    assert probe.observe(command_for(11000), receipt=receipt) == 'dispatch_unknown'


@pytest.mark.parametrize('covered', [True, False])
def test_proven_dispatch_conflicts_with_denial_even_if_receipt_omitted(covered):
    probe = LengthProbe(Lifecycle())
    probe.dispatch(command_for(9500), 'tool')
    assert probe.observe(command_for(9500), native_decision='permission_denied_before_dispatch',
                         coverage_complete=covered) == 'dispatch_unknown'


def test_missing_receipt_and_textual_denial_are_not_no_dispatch_proof():
    for decision in (None, 'the model says permission denied'):
        probe = LengthProbe(Lifecycle())
        probe.begin(command_for(9500), 'tool')
        assert probe.observe(command_for(9500), native_decision=decision) == 'dispatch_unknown'
    probe = LengthProbe(Lifecycle())
    probe.begin(command_for(9500), 'tool')
    assert probe.observe(command_for(9500), native_decision='permission_denied_before_dispatch',
                         coverage_complete=False) == 'dispatch_unknown'


def test_edited_command_and_provider_refusal_stop_instead_of_retry():
    for command, decision, expected in [
        (b'echo changed', None, 'invalid_case'),
        (command_for(9500), 'provider_refusal', 'not_length_evidence'),
        (command_for(9500), 'fallback', 'not_length_evidence'),
    ]:
        probe = LengthProbe(Lifecycle())
        probe.begin(command, 'tool')
        assert probe.observe(command, native_decision=decision) == expected
        assert probe.bracket() == {'status': 'inconclusive'}
        with pytest.raises(ValueError):
            probe.dispatch(command_for(11000), 'retry')


def test_duplicate_out_of_order_and_after_revoke_dispatch_rejected():
    life = Lifecycle()
    probe = LengthProbe(life)
    with pytest.raises(ValueError):
        probe.dispatch(command_for(11000), 'wrong-first')
    probe = LengthProbe(life)
    probe.dispatch(command_for(9500), 'first')
    with pytest.raises(ValueError):
        probe.dispatch(command_for(9500), 'second')
    probe = LengthProbe(life)
    life.advance(270)
    with pytest.raises(ValueError):
        probe.dispatch(command_for(9500), 'late')


NOW = datetime(2026, 9, 21, 12, tzinfo=UTC)


def test_budget_missing_unknown_and_stale_evidence_close_admission():
    assert 'missing_ledger' in admission(None, NOW, billing_current=True)
    assert 'billing_not_current' in admission((), NOW, billing_current=False)
    charges = (Charge('2026-09-14', None),)
    assert 'unknown_exposure' in admission(charges, NOW, billing_current=True)


def test_budget_actuals_replace_reservations_without_double_counting():
    charges = tuple(Charge('2026-09-21', Decimal('0.10')) for _ in range(9))
    assert admission(charges, NOW, billing_current=True) == ()
    assert 'diagnostic_attempts' in admission(charges + charges[:1], NOW, billing_current=True)


def test_budget_limits_use_exact_decimal_and_include_other_allocations():
    assert admission((Charge('2026-09-21', Decimal(27)),), NOW, billing_current=True) == ()
    assert 'diagnostic_budget' in admission((Charge('2026-09-21', Decimal('27.001')),),
                                           NOW, billing_current=True)
    charges = (Charge('2026-09-21', Decimal('147.001'), diagnostic=False),)
    assert 'weekly_budget' in admission(charges, NOW, billing_current=True)


def test_budget_week_is_new_york_and_old_unknowns_survive_rollover():
    # Monday UTC, still Sunday in New York.
    now = datetime(2026, 9, 21, 1, tzinfo=UTC)
    charges = tuple(Charge('2026-09-14', Decimal('0.1')) for _ in range(10))
    assert 'diagnostic_attempts' in admission(charges, now, billing_current=True)
    assert admission(charges, NOW, billing_current=True) == ()
    assert 'invalid_week' in admission((Charge('2026-09-22', Decimal(0)),),
                                      NOW, billing_current=True)


def test_capture_caps_never_overwrite_or_evict_earlier_evidence():
    capture = Capture(limit=10, total_remaining=5)
    assert capture.append(b'12345')
    assert not capture.append(b'6')
    assert not capture.append(b'')
    assert capture.data == b'12345'
    assert not capture.complete


def test_replay_success_is_labelled_and_never_opens_native_launch():
    result = replay((Frame(0, assistant()), Frame(2, terminal()),
                     Frame(3, exit_code=0, reaped=True, pipes_closed=True)), 'candidate')
    assert result.outcome.execution == 'completed'
    assert result.scope == 'OFFLINE_REPLAY_ONLY'
    assert result.native_launch == 'CLOSED'
    assert result.actions == ((3, ('revoke', 'interrupt', 'closed')),)


def test_replay_eof_does_not_invent_containment_or_exit():
    result = replay((Frame(1, assistant()), Frame(2, terminal())), 'candidate')
    assert result.outcome.execution == 'containment_failed'
    assert {'timeout', 'missing_exit'} <= set(result.outcome.reasons)


def test_replay_fallback_live_and_retrospective_are_distinct():
    live = replay((Frame(0, assistant('fallback')), Frame(1, terminal()),
                   Frame(2, exit_code=0, reaped=True, pipes_closed=True)), 'candidate')
    assert live.outcome.execution == 'cancelled'
    assert live.outcome.comparison == 'invalid'
    after = replay((Frame(0, terminal()),
                    Frame(1, assistant('fallback'), exit_code=0, reaped=True,
                          pipes_closed=True)), 'candidate')
    assert after.outcome.execution == 'completed'
    assert after.outcome.comparison == 'invalid'


def test_replay_timeout_retains_success_terminal_but_overrides_execution():
    result = replay((Frame(1, assistant()), Frame(271, terminal()),
                     Frame(280, exit_code=0, reaped=True, pipes_closed=True)), 'candidate')
    assert result.outcome.execution == 'timed_out'
    assert result.actions[0] == (270, ('revoke', 'interrupt'))


def test_replay_capture_exhaustion_stops_and_marks_gap():
    result = replay((Frame(1, assistant()),
                     Frame(2, exit_code=0, reaped=True, pipes_closed=True)),
                    'candidate', capture_limit=2)
    assert result.outcome.execution == 'cancelled'
    assert 'capture_limit' in result.outcome.reasons
    assert not result.audit_complete


def test_replay_spawn_failure_and_duplicate_finalization():
    result = replay((Frame(0, spawn_failure=True),), 'candidate')
    assert result.outcome.execution == 'spawn_failed'
    with pytest.raises(ValueError):
        replay((Frame(0, exit_code=0, reaped=True, pipes_closed=True), Frame(1)), 'candidate')


def test_replay_reaping_exactly_at_deadline_does_not_claim_containment_failure():
    result = replay((Frame(1, assistant()), Frame(2, terminal()), Frame(270),
                     Frame(300, exit_code=0, reaped=True, pipes_closed=True)), 'candidate')
    assert result.outcome.execution == 'timed_out'
    assert 'containment_failure' not in result.outcome.reasons


@pytest.mark.parametrize('value', ['false', 0, 1, None])
@pytest.mark.parametrize('field', ['reaped', 'pipes_closed', 'cancel', 'spawn_failure'])
def test_frame_boolean_evidence_is_not_truthiness(field, value):
    with pytest.raises(TypeError):
        Frame(1, **{field: value})


@pytest.mark.parametrize('field', ['cancel', 'parent_exited', 'reaped', 'pipes_closed'])
def test_lifecycle_rejects_malformed_observation_before_changing_state(field):
    life = Lifecycle()
    with pytest.raises(TypeError):
        life.advance(1, **{field: 'false'})
    assert life.now == 0 and not life.finished and not life.revoked


@pytest.mark.parametrize('value', ['false', 0, 1, None])
def test_coverage_must_be_an_explicit_boolean(value):
    probe = LengthProbe(Lifecycle())
    probe.begin(command_for(9500), 'tool')
    with pytest.raises(TypeError):
        probe.observe(command_for(9500), native_decision='permission_denied_before_dispatch',
                      coverage_complete=value)
    assert probe.results == []


def test_cleanup_retains_receipt_for_dispatched_case_and_cannot_start_another():
    life = Lifecycle()
    probe = LengthProbe(life)
    receipt = probe.dispatch(command_for(9500), 'tool', stub_exit=1)
    life.advance(270)
    assert probe.observe(command_for(9500), receipt=receipt) == 'dispatched'
    assert probe.results == ['dispatched']
    with pytest.raises(ValueError):
        probe.begin(command_for(11000), 'next')


def test_cleanup_retains_denial_for_pending_case_without_creating_new_work():
    life = Lifecycle()
    probe = LengthProbe(life)
    probe.begin(command_for(9500), 'tool')
    life.advance(270)
    assert probe.observe(command_for(9500), native_decision='permission_denied_before_dispatch',
                         coverage_complete=True) == 'permission_denied_no_dispatch'
    other = LengthProbe(life)
    with pytest.raises(ValueError):
        other.observe(command_for(9500), native_decision='permission_denied_before_dispatch',
                      coverage_complete=True)


@pytest.mark.parametrize('decision', ['fallback', 'provider_refusal', 'model_unavailable'])
def test_length_probe_refusal_revokes_lifecycle_and_emits_cleanup_actions(decision):
    life = Lifecycle()
    life.advance(10)
    probe = LengthProbe(life)
    probe.begin(command_for(9500), 'tool')
    assert probe.observe(command_for(9500), native_decision=decision) == 'not_length_evidence'
    assert not life.work_allowed and life.revoked and 'cancelled' in life.reasons
    assert probe.cleanup_actions == ('revoke', 'interrupt')
    assert life.end_at == 40


def test_cancel_at_timeout_keeps_both_reasons():
    life = Lifecycle()
    life.advance(270, cancel=True)
    assert life.reasons == {'cancelled', 'timeout'}


def test_silent_replay_emits_transitions_at_deadlines_not_late_observation_time():
    result = replay((Frame(1, assistant()), Frame(400, terminal(), exit_code=0,
                                                reaped=True, pipes_closed=True)), 'candidate')
    assert result.actions == ((270, ('revoke', 'interrupt')), (290, ('kill_and_reap',)),
                              (300, ('hold',)))
    assert result.outcome.execution == 'containment_failed'
    assert 'missing_terminal' in result.outcome.reasons
