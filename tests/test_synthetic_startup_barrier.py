"""Closed synthetic process evidence for the proposed startup barrier."""

from __future__ import annotations

import os
import subprocess

import pytest

from prototype.run_timing.synthetic_barrier import (
    SyntheticBarrierError,
    launch_synthetic_barrier,
)


def test_fixed_child_stays_blocked_until_attested_release():
    with launch_synthetic_barrier() as barrier:
        barrier.attest_blocked()
        assert barrier.process.poll() is None
        assert barrier.observe(timeout=0.05) is None
        barrier.decide(b"R")
        assert barrier.observe(timeout=2.0) == b"A"
        assert barrier.process.wait(timeout=2.0) == 0
        with pytest.raises(SyntheticBarrierError, match="handoff_invalid"):
            barrier.decide(b"R")


def test_parent_release_pipe_closure_is_fail_closed():
    barrier = launch_synthetic_barrier()
    barrier.attest_blocked()
    assert barrier.observe(timeout=0.05) is None
    barrier.close()
    assert barrier.process.returncode == 66


def test_wrong_release_byte_never_runs_the_inert_action():
    with launch_synthetic_barrier() as barrier:
        barrier.attest_blocked()
        barrier.decide(b"X")
        assert barrier.observe(timeout=2.0) == b""
        assert barrier.process.wait(timeout=2.0) == 66


def test_failed_session_attestation_closes_without_release(monkeypatch):
    with launch_synthetic_barrier() as barrier:
        monkeypatch.setattr(os, "getsid", lambda _pid: -1)
        with pytest.raises(SyntheticBarrierError, match="attestation_failed"):
            barrier.attest_blocked()
        assert barrier.process.returncode == 66


def test_unattested_or_malformed_decision_cannot_release():
    with launch_synthetic_barrier() as barrier:
        with pytest.raises(SyntheticBarrierError, match="handoff_invalid"):
            barrier.decide(b"R")
        barrier.attest_blocked()
        for invalid in (b"", b"RR", "R", True):
            with pytest.raises(SyntheticBarrierError, match="handoff_invalid"):
                barrier.decide(invalid)
        assert barrier.observe(timeout=0.05) is None


def test_second_pipe_failure_closes_first_pipe(monkeypatch):
    real_pipe = os.pipe
    acquired = []

    def fail_second_pipe():
        if acquired:
            raise OSError("injected descriptor exhaustion")
        pair = real_pipe()
        acquired.append(pair)
        return pair

    monkeypatch.setattr(os, "pipe", fail_second_pipe)
    with pytest.raises(SyntheticBarrierError, match="pipe_failed"):
        launch_synthetic_barrier()
    for fd in acquired[0]:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_failed_handoff_write_reaps_closed_child(monkeypatch):
    barrier = launch_synthetic_barrier()
    barrier.attest_blocked()
    release_fd = barrier._release_fd
    real_write = os.write

    def fail_release(fd, value):
        if fd == release_fd:
            raise BrokenPipeError("injected release failure")
        return real_write(fd, value)

    monkeypatch.setattr(os, "write", fail_release)
    with pytest.raises(SyntheticBarrierError, match="handoff_failed"):
        barrier.decide(b"R")
    assert barrier.process.returncode == 66
    assert barrier._observe_fd is None


def test_reap_failure_still_closes_observation_pipe(monkeypatch):
    barrier = launch_synthetic_barrier()
    barrier.attest_blocked()
    observe_fd = barrier._observe_fd
    real_wait = barrier.process.wait

    def fail_wait(*, timeout):
        raise subprocess.TimeoutExpired("synthetic", timeout)

    with monkeypatch.context() as patch:
        patch.setattr(barrier.process, "wait", fail_wait)
        with pytest.raises(SyntheticBarrierError, match="reap_failed"):
            barrier.close()
    with pytest.raises(OSError):
        os.fstat(observe_fd)
    real_wait(timeout=2.0)
