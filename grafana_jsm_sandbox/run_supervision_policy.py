"""Pure deadline schedule for one Run; no process or dispatch authority.

The caller supplies monotonic observations from one boot. The returned actions
are due times, not evidence that revocation, signaling or reaping happened.
"""

import re
from dataclasses import dataclass

_SECOND_US = 1_000_000
_WORK_US = 270 * _SECOND_US
_FLUSH_US = 20 * _SECOND_US
_REAP_US = 30 * _SECOND_US
_MAX_MONO_US = 2**63 - 1
_BOOT_ID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")


class SupervisionError(ValueError):
    """A fixed rejection code that does not echo observation data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SupervisionWindow:
    phase: str
    work_deadline_us: int
    flush_deadline_us: int
    hard_deadline_us: int
    revoke_due: bool
    interrupt_due: bool
    kill_or_reap_due: bool


def _valid_time(value: object) -> bool:
    return type(value) is int and 0 <= value <= _MAX_MONO_US


def assess_supervision(
    *, launch_boot_id: str, observed_boot_id: str, launch_us: int,
    observed_us: int, stop_requested_us: int | None = None,
) -> SupervisionWindow:
    """Describe actions due by ``observed_us`` within one bounded Run window.

    ``stop_requested_us`` represents an already observed cancellation or
    revocation. It cannot extend the original 270/20/10-second schedule.
    A caller must separately verify its provenance and actual process state.
    """
    if (
        type(launch_boot_id) is not str or _BOOT_ID.fullmatch(launch_boot_id) is None
        or type(observed_boot_id) is not str
        or _BOOT_ID.fullmatch(observed_boot_id) is None
    ):
        raise SupervisionError("boot_invalid") from None
    if launch_boot_id != observed_boot_id:
        raise SupervisionError("boot_mismatch") from None
    if not _valid_time(launch_us) or not _valid_time(observed_us):
        raise SupervisionError("time_invalid") from None
    if observed_us < launch_us:
        raise SupervisionError("time_order") from None
    if stop_requested_us is not None and (
        not _valid_time(stop_requested_us)
        or not launch_us <= stop_requested_us <= observed_us
    ):
        raise SupervisionError("stop_invalid") from None
    if launch_us > _MAX_MONO_US - 300 * _SECOND_US:
        raise SupervisionError("deadline_overflow") from None

    work_deadline = launch_us + _WORK_US
    stop = work_deadline if stop_requested_us is None else min(stop_requested_us, work_deadline)
    flush_deadline = min(stop + _FLUSH_US, launch_us + 290 * _SECOND_US)
    hard_deadline = min(stop + _REAP_US, launch_us + 300 * _SECOND_US)
    if observed_us < stop:
        phase = "work"
    elif observed_us < flush_deadline:
        phase = "interrupt_flush"
    elif observed_us < hard_deadline:
        phase = "kill_reap"
    else:
        phase = "hard_deadline_exceeded"
    return SupervisionWindow(
        phase=phase,
        work_deadline_us=work_deadline,
        flush_deadline_us=flush_deadline,
        hard_deadline_us=hard_deadline,
        revoke_due=observed_us >= stop,
        interrupt_due=observed_us >= stop,
        kill_or_reap_due=observed_us >= flush_deadline,
    )


__all__ = ["SupervisionError", "SupervisionWindow", "assess_supervision"]
