"""Pure Run deadline boundaries; no native process is started."""

from dataclasses import FrozenInstanceError

import pytest

from grafana_jsm_sandbox.run_supervision_policy import (
    SupervisionError,
    assess_supervision,
)

S = 1_000_000


def window(at: int, *, stop: int | None = None):
    return assess_supervision(
        launch_boot_id="boot-1", observed_boot_id="boot-1",
        launch_us=7 * S, observed_us=(7 + at) * S,
        stop_requested_us=None if stop is None else (7 + stop) * S,
    )


@pytest.mark.parametrize(
    ("at", "phase", "revoke", "kill"),
    [
        (0, "work", False, False),
        (269, "work", False, False),
        (270, "interrupt_flush", True, False),
        (289, "interrupt_flush", True, False),
        (290, "kill_reap", True, True),
        (299, "kill_reap", True, True),
        (300, "hard_deadline_exceeded", True, True),
    ],
)
def test_nominal_boundaries(at, phase, revoke, kill):
    result = window(at)
    assert (result.phase, result.revoke_due, result.interrupt_due,
            result.kill_or_reap_due) == (phase, revoke, revoke, kill)
    assert (result.work_deadline_us, result.flush_deadline_us,
            result.hard_deadline_us) == (277 * S, 297 * S, 307 * S)


def test_early_stop_shortens_both_cleanup_windows():
    assert window(10, stop=10).phase == "interrupt_flush"
    assert window(29, stop=10).phase == "interrupt_flush"
    at_grace = window(30, stop=10)
    assert at_grace.phase == "kill_reap"
    assert (at_grace.flush_deadline_us, at_grace.hard_deadline_us) == (37 * S, 47 * S)
    assert window(40, stop=10).phase == "hard_deadline_exceeded"


def test_late_stop_cannot_extend_original_deadlines():
    result = window(295, stop=295)
    assert result.phase == "kill_reap"
    assert (result.flush_deadline_us, result.hard_deadline_us) == (297 * S, 307 * S)
    assert window(300, stop=300).phase == "hard_deadline_exceeded"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"launch_boot_id": "bad boot"}, "boot_invalid"),
        ({"observed_boot_id": "boot-2"}, "boot_mismatch"),
        ({"launch_us": True}, "time_invalid"),
        ({"observed_us": 6 * S}, "time_order"),
        ({"stop_requested_us": True}, "stop_invalid"),
        ({"stop_requested_us": 8 * S}, "stop_invalid"),
        ({"launch_us": 2**63 - 1}, "time_order"),
    ],
)
def test_invalid_observations_hold_by_fixed_code(change, code):
    args = {
        "launch_boot_id": "boot-1", "observed_boot_id": "boot-1",
        "launch_us": 7 * S, "observed_us": 7 * S,
    }
    args.update(change)
    with pytest.raises(SupervisionError) as error:
        assess_supervision(**args)
    assert error.value.code == code
    assert str(error.value) == code


def test_deadline_overflow_and_immutable_result():
    late = 2**63 - 1 - 299 * S
    with pytest.raises(SupervisionError, match="^deadline_overflow$"):
        assess_supervision(
            launch_boot_id="b", observed_boot_id="b", launch_us=late,
            observed_us=late,
        )
    with pytest.raises(FrozenInstanceError):
        window(0).phase = "complete"
