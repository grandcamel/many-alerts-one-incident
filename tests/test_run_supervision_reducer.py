"""Synthetic action ordering and closeout gaps; no worker is launched."""

from dataclasses import FrozenInstanceError

import pytest

from grafana_jsm_sandbox.run_supervision_policy import SupervisionError
from grafana_jsm_sandbox.run_supervision_reducer import (
    ActionHistory,
    SupervisorReducerError,
    WorkerObservation,
    assess_supervisor_closeout,
    next_supervision_action,
)

S = 1_000_000


def _history(**changes):
    fields = {"revoke_attempted": False, "interrupt_attempted": False,
              "kill_attempted": False, "early_stop_us": None}
    fields.update(changes)
    return ActionHistory(**fields)


def _observation(**changes):
    fields = {"root_state": "running", "group_state": "present",
              "stable_group_identity": True, "stdout_eof": False,
              "stderr_eof": False, "capture_complete": False,
              "revocation_state": "not_attempted", "forwarder_closeout": "open"}
    fields.update(changes)
    return WorkerObservation(**fields)


def _next(history=None, observation=None, *, at=0, stop=None, boot="boot-1"):
    return next_supervision_action(
        _history() if history is None else history,
        _observation() if observation is None else observation,
        launch_boot_id="boot-1", observed_boot_id=boot,
        launch_us=0, observed_us=at, stop_requested_us=stop,
    )


def test_silent_worker_cannot_postpone_the_stop_boundary():
    assert _next(at=269 * S).action is None
    at_boundary = _next(at=270 * S)
    assert (at_boundary.phase, at_boundary.action) == ("interrupt_flush", "revoke_lease")


def test_revocation_attempt_must_precede_interrupt_even_if_it_failed():
    attempted = _history(revoke_attempted=True)
    failed = _observation(revocation_state="failed")
    assert _next(attempted, failed, at=270 * S).action == "signal_interrupt"
    assert assess_supervisor_closeout(attempted, failed).state == "held"
    assert "revocation_unconfirmed" in assess_supervisor_closeout(attempted, failed).gaps


def test_stop_request_brings_the_boundary_forward_without_sliding_it():
    assert _next(at=12 * S, stop=12 * S).action == "revoke_lease"
    history = _history(revoke_attempted=True)
    obs = _observation(revocation_state="acknowledged")
    assert _next(history, obs, at=12 * S, stop=12 * S).action == "signal_interrupt"
    history = _history(revoke_attempted=True, interrupt_attempted=True)
    assert _next(history, obs, at=32 * S, stop=12 * S).action == "signal_kill"
    assert _next(history, obs, at=42 * S, stop=12 * S).action is None


def test_early_root_exit_or_failed_start_retires_installed_lease():
    assert _next(observation=_observation(
        root_state="exited", group_state="absent",
    ), at=5 * S).action == "revoke_lease"
    assert _next(observation=_observation(
        root_state="failed_before_process", group_state="absent",
    ), at=5 * S).action == "revoke_lease"


def test_early_parent_exit_pins_stop_time_before_descendant_cleanup():
    exited = _observation(root_state="exited", group_state="present")
    first = _next(observation=exited, at=5 * S)
    assert (first.action, first.early_stop_to_record_us) == ("revoke_lease", 5 * S)
    attempted = _history(revoke_attempted=True)
    acknowledged = _observation(root_state="reaped", group_state="present",
                                revocation_state="acknowledged")
    with pytest.raises(SupervisorReducerError) as exc:
        _next(attempted, acknowledged, at=6 * S)
    assert str(exc.value) == "early_stop_required"
    pinned = _history(revoke_attempted=True, early_stop_us=5 * S)
    assert _next(pinned, acknowledged, at=6 * S).action == "signal_interrupt"
    interrupted = _history(revoke_attempted=True, interrupt_attempted=True,
                           early_stop_us=5 * S)
    assert _next(interrupted, acknowledged, at=25 * S).action == "signal_kill"
    assert _next(interrupted, acknowledged, at=35 * S).action is None


def test_parent_exit_with_descendants_and_open_pipes_is_not_closeout():
    history = _history(revoke_attempted=True)
    obs = _observation(root_state="reaped", revocation_state="acknowledged",
                       forwarder_closeout="closed")
    result = assess_supervisor_closeout(history, obs)
    assert result.state == "held"
    assert result.gaps == (
        "capture_incomplete", "group_not_confirmed_absent", "stderr_eof_missing",
        "stdout_eof_missing",
    )


def test_group_identity_is_required_for_signals_and_clean_closeout():
    history = _history(revoke_attempted=True)
    obs = _observation(stable_group_identity=False, revocation_state="acknowledged")
    assert _next(history, obs, at=270 * S).action is None
    close = assess_supervisor_closeout(history, _observation(
        root_state="reaped", group_state="absent", stable_group_identity=False,
        stdout_eof=True, stderr_eof=True, capture_complete=True,
        revocation_state="acknowledged", forwarder_closeout="closed",
    ))
    assert close.gaps == ("group_identity_unverified",)


def test_signal_actions_do_not_repeat_and_kill_only_targets_a_present_group():
    obs = _observation(revocation_state="acknowledged")
    history = _history(revoke_attempted=True, interrupt_attempted=True)
    assert _next(history, obs, at=280 * S).action is None
    assert _next(history, obs, at=290 * S).action == "signal_kill"
    history = _history(revoke_attempted=True, interrupt_attempted=True,
                       kill_attempted=True)
    assert _next(history, obs, at=291 * S).action is None
    assert _next(_history(revoke_attempted=True), _observation(
        group_state="absent", revocation_state="acknowledged",
    ), at=290 * S).action is None


def test_hard_deadline_emits_no_new_action_even_if_prior_steps_were_missed():
    decision = _next(at=300 * S)
    assert (decision.phase, decision.action, decision.hard_deadline_reached) == (
        "hard_deadline_exceeded", None, True,
    )


@pytest.mark.parametrize(("state", "reason"), [
    ("open", "forwarder_closeout_open"),
    ("draining", "forwarder_closeout_draining"),
    ("overdue", "forwarder_closeout_overdue"),
    ("unknown", "forwarder_closeout_unknown"),
])
def test_forwarder_closeout_is_distinct_from_revocation(state, reason):
    result = assess_supervisor_closeout(_history(revoke_attempted=True), _observation(
        root_state="reaped", group_state="absent", stdout_eof=True,
        stderr_eof=True, capture_complete=True, revocation_state="acknowledged",
        forwarder_closeout=state,
    ))
    assert result.gaps == (reason,)


def test_all_claimed_closeout_facts_still_have_no_durable_authority():
    result = assess_supervisor_closeout(_history(revoke_attempted=True), _observation(
        root_state="reaped", group_state="absent", stdout_eof=True,
        stderr_eof=True, capture_complete=True, revocation_state="acknowledged",
        forwarder_closeout="closed",
    ))
    assert (result.state, result.gaps) == ("claimed_complete", ())
    with pytest.raises(FrozenInstanceError):
        result.state = "held"


def test_failed_before_process_still_requires_revocation_and_closeout():
    obs = _observation(root_state="failed_before_process", group_state="absent",
                       revocation_state="acknowledged", forwarder_closeout="closed")
    assert assess_supervisor_closeout(_history(revoke_attempted=True), obs).state == (
        "claimed_complete"
    )
    assert "revocation_unconfirmed" in assess_supervisor_closeout(
        _history(), _observation(root_state="failed_before_process",
                                 group_state="absent"),
    ).gaps


@pytest.mark.parametrize(("history", "observation", "code"), [
    (_history(interrupt_attempted=True), _observation(), "supervision_argument"),
    (_history(revoke_attempted=1), _observation(), "supervision_argument"),
    (_history(), _observation(group_state="gone"), "supervision_argument"),
    (_history(), _observation(stdout_eof=1), "supervision_argument"),
    (_history(), _observation(root_state="failed_before_process"), "supervision_argument"),
    (_history(), _observation(root_state="failed_before_process",
                              group_state="unknown"), "supervision_argument"),
    (_history(), _observation(revocation_state="acknowledged"), "supervision_order"),
    (_history(revoke_attempted=True), _observation(), "supervision_order"),
])
def test_invalid_observation_or_action_history_is_closed(history, observation, code):
    with pytest.raises(SupervisorReducerError) as exc:
        _next(history, observation)
    assert str(exc.value) == code


def test_clock_boot_mismatch_is_rejected_by_the_single_timing_source():
    with pytest.raises(SupervisionError) as exc:
        _next(at=10 * S, boot="boot-2")
    assert str(exc.value) == "boot_mismatch"
