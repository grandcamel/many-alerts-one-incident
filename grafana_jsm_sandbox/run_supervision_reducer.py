"""Pure worker-supervision actions and closeout gaps over unverified claims.

Only a future guarded launcher can execute these actions. This module has no
process, Forwarder, journal or dispatch authority and cannot release a Run hold.
"""

from __future__ import annotations

from dataclasses import dataclass

from .run_supervision_policy import assess_supervision

_ROOT = frozenset({"running", "exited", "reaped", "failed_before_process", "unknown"})
_GROUP = frozenset({"present", "absent", "unknown"})
_REVOCATION = frozenset({"not_attempted", "acknowledged", "failed", "unknown"})
_CLOSEOUT = frozenset({"open", "draining", "closed", "overdue", "unknown"})


class SupervisorReducerError(ValueError):
    """Fixed rejection code with no caller content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ActionHistory:
    revoke_attempted: bool
    interrupt_attempted: bool
    kill_attempted: bool
    early_stop_us: int | None


@dataclass(frozen=True, slots=True)
class WorkerObservation:
    root_state: str
    group_state: str
    stable_group_identity: bool
    stdout_eof: bool
    stderr_eof: bool
    capture_complete: bool
    revocation_state: str
    forwarder_closeout: str


@dataclass(frozen=True, slots=True)
class ActionDecision:
    phase: str
    action: str | None
    hard_deadline_reached: bool
    early_stop_to_record_us: int | None


@dataclass(frozen=True, slots=True)
class CloseoutAssessment:
    state: str
    gaps: tuple[str, ...]


def _valid_history(history: object) -> bool:
    return (type(history) is ActionHistory and
            all(type(value) is bool for value in (
                history.revoke_attempted, history.interrupt_attempted,
                history.kill_attempted,
            )) and
            (history.revoke_attempted or
             not (history.interrupt_attempted or history.kill_attempted)) and
            (history.early_stop_us is None or
             (type(history.early_stop_us) is int and
              0 <= history.early_stop_us <= 2**63 - 1)))


def _valid_observation(observation: object) -> bool:
    if type(observation) is not WorkerObservation:
        return False
    if (type(observation.root_state) is not str or observation.root_state not in _ROOT or
            type(observation.group_state) is not str or observation.group_state not in _GROUP or
            type(observation.revocation_state) is not str or
            observation.revocation_state not in _REVOCATION or
            type(observation.forwarder_closeout) is not str or
            observation.forwarder_closeout not in _CLOSEOUT):
        return False
    if not all(type(value) is bool for value in (
        observation.stable_group_identity, observation.stdout_eof,
        observation.stderr_eof, observation.capture_complete,
    )):
        return False
    return not (observation.root_state == "failed_before_process" and
                observation.group_state != "absent")


def _check(history: ActionHistory, observation: WorkerObservation) -> None:
    if not _valid_history(history) or not _valid_observation(observation):
        raise SupervisorReducerError("supervision_argument") from None
    if ((not history.revoke_attempted and
         observation.revocation_state != "not_attempted") or
            (history.revoke_attempted and
             observation.revocation_state == "not_attempted")):
        raise SupervisorReducerError("supervision_order") from None


def next_supervision_action(
    history: ActionHistory, observation: WorkerObservation, *,
    launch_boot_id: str, observed_boot_id: str,
    launch_us: int, observed_us: int, stop_requested_us: int | None = None,
) -> ActionDecision:
    """Choose at most one action; a caller records each attempted action.

    Revocation is due at the ordinary stop boundary or on early root exit.
    SIGINT follows an attempted revocation even if acknowledgment failed; that
    signal is containment work, never proof that dispatch was fenced.
    """
    _check(history, observation)
    window = assess_supervision(
        launch_boot_id=launch_boot_id, observed_boot_id=observed_boot_id,
        launch_us=launch_us, observed_us=observed_us,
        stop_requested_us=stop_requested_us,
    )
    if history.early_stop_us is not None:
        assess_supervision(
            launch_boot_id=launch_boot_id, observed_boot_id=observed_boot_id,
            launch_us=launch_us, observed_us=observed_us,
            stop_requested_us=history.early_stop_us,
        )
        effective_stop = min(
            stop_requested_us if stop_requested_us is not None else window.work_deadline_us,
            history.early_stop_us,
        )
        window = assess_supervision(
            launch_boot_id=launch_boot_id, observed_boot_id=observed_boot_id,
            launch_us=launch_us, observed_us=observed_us,
            stop_requested_us=effective_stop,
        )
    early_end = observation.root_state in {"exited", "reaped", "failed_before_process"}
    early_descendants = (observation.root_state in {"exited", "reaped"} and
                         observation.group_state != "absent")
    if early_descendants and history.early_stop_us is None and history.revoke_attempted:
        raise SupervisorReducerError("early_stop_required") from None
    if window.phase == "hard_deadline_exceeded":
        return ActionDecision(window.phase, None, True, None)
    if (window.revoke_due or early_end) and not history.revoke_attempted:
        return ActionDecision(
            window.phase, "revoke_lease", False,
            observed_us if early_descendants and history.early_stop_us is None else None,
        )
    can_signal = (history.revoke_attempted and
                  observation.stable_group_identity and
                  observation.group_state == "present")
    if can_signal and window.kill_or_reap_due and not history.kill_attempted:
        return ActionDecision(window.phase, "signal_kill", False, None)
    if can_signal and window.interrupt_due and not history.interrupt_attempted:
        return ActionDecision(window.phase, "signal_interrupt", False, None)
    return ActionDecision(window.phase, None, False, None)


def assess_supervisor_closeout(
    history: ActionHistory, observation: WorkerObservation,
) -> CloseoutAssessment:
    """Describe gaps without declaring durable Run or effect success."""
    _check(history, observation)
    gaps: set[str] = set()
    if observation.root_state not in {"reaped", "failed_before_process"}:
        gaps.add("root_not_reaped")
    if observation.root_state != "failed_before_process":
        if not observation.stable_group_identity:
            gaps.add("group_identity_unverified")
        if observation.group_state != "absent":
            gaps.add("group_not_confirmed_absent")
        if not observation.stdout_eof:
            gaps.add("stdout_eof_missing")
        if not observation.stderr_eof:
            gaps.add("stderr_eof_missing")
        if not observation.capture_complete:
            gaps.add("capture_incomplete")
    if not history.revoke_attempted or observation.revocation_state != "acknowledged":
        gaps.add("revocation_unconfirmed")
    if observation.forwarder_closeout != "closed":
        gaps.add("forwarder_closeout_" + observation.forwarder_closeout)
    return CloseoutAssessment(
        "claimed_complete" if not gaps else "held", tuple(sorted(gaps)),
    )


__all__ = [
    "ActionDecision", "ActionHistory", "CloseoutAssessment", "SupervisorReducerError",
    "WorkerObservation", "assess_supervisor_closeout", "next_supervision_action",
]
