"""Real-process crash tests for the journaled front door (ticket 37, unit
17b; Tester T2b, cases C1-C6).

Every case but C6 runs the actual crash target (the one seam named in the
plan's "Crash windows added by this unit") in a **child process**, started
with ``sys.executable`` and the repository on its own ``sys.path``. The
child installs a monkeypatch on that one seam that runs the real call for
real -- so the durable side effect it names has already happened -- and
then sends itself ``SIGKILL``, which the kernel delivers unconditionally
and which no ``except``, however broad, can intercept: a strictly stronger
guarantee than the in-process ``SimulatedCrash(BaseException)`` images
``test_recovery_journal_crash.py``/``test_recovery_journal_front_door.py``
use for the same windows one layer down, at the shell. The parent process
never touches the crashed child's directory while it might still be
running; it waits for the OS to confirm the kill, then opens or inspects
the state directory itself, exactly as the plan's window table describes.

``journal_spool.py``, ``journaled_receiver.py`` and ``journal_operator.py``
are written in parallel with this file and are not available while it is
drafted.

Real SQLite and real syncs throughout, private 0700 ``tmp_path``
directories, no fixed ports (every child takes ``--port 0`` and is found by
parsing its own "listening on" line), no sleeps for synchronisation --
C6's one real-valued wait is the randomized kill delay itself, bounded and
printed, not a synchronisation sleep.
"""

from __future__ import annotations

import dataclasses
import json
import random
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_operator as jo
from grafana_jsm_sandbox import journal_spool as jsp
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import recovery_journal as rj
from tests.conftest import FIXTURES, post_notification
from tests.test_journal_operator import _wait_for_listening_line

pytestmark = pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE "
    "(Python >= 3.12)",
)

REPOSITORY = Path(__file__).resolve().parent.parent


# === Shared helpers =============================================================


@dataclasses.dataclass
class _URLHolder:
    """The only thing ``post_notification`` needs: a ``.url``."""

    url: str


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)


def _post_and_ignore_disconnect(url: str, body: bytes) -> None:
    """POST once; a connection dropped by the induced crash is the expected
    outcome here, not a test failure -- the child's own exit code is what
    proves the crash happened."""
    try:
        post_notification(_URLHolder(url), body)
    except Exception:  # noqa: BLE001, S110 - any transport failure reads as "the child died".
        pass


def _distinct_body(tag: str) -> bytes:
    payload = {
        "groupKey": f'{{}}:{{alertname="crash", tag="{tag}"}}',
        "alerts": [{"fingerprint": f"fp-{tag}", "status": "firing"}],
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _post_loop(
    url: str, stop_posting: threading.Event, posted_ok: list[str], counter: dict[str, int],
) -> None:
    """C6's client: posts distinct bodies until told to stop, or the
    connection dies under it (the child it is posting to was just killed)."""
    while not stop_posting.is_set():
        counter["n"] += 1
        body = _distinct_body(f"c6-{counter['n']}")
        digest = ji.body_digest(body)
        try:
            response = post_notification(_URLHolder(url), body)
        except Exception:  # noqa: BLE001, S112 - a crashed child drops the connection.
            continue
        if response.status == 202:
            posted_ok.append(digest)


def _spawn_journaled_receiver_main(
    directory: Path, runs_directory: Path, extra_args: tuple[str, ...] = (),
) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable, "-m", "grafana_jsm_sandbox.journaled_receiver",
            "--state-dir", str(directory), "--host", "127.0.0.1", "--port", "0",
            "--runs-directory", str(runs_directory), *extra_args,
        ],
        cwd=REPOSITORY, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


# One seam, named by (module, class, method); the wrapper calls the real
# implementation for real -- so the durable side effect it names has
# happened -- and only then, on its `crash_at`-th call, sends itself
# SIGKILL. Never caught: the process ends there, mid-call, exactly like a
# real crash at that instruction.
_CRASH_CHILD_SCRIPT = """
import sys
sys.path.insert(0, {repo!r})
import os
import signal
from grafana_jsm_sandbox import {patch_module} as _target_module
from grafana_jsm_sandbox import journaled_receiver

_real = getattr(_target_module.{patch_class}, {patch_method!r})
_state = {{"n": 0}}
_crash_at = {crash_at!r}


def _wrapper(*args, **kwargs):
    result = _real(*args, **kwargs)
    _state["n"] += 1
    if _state["n"] == _crash_at:
        sys.stdout.flush()
        os.kill(os.getpid(), signal.SIGKILL)
    return result


setattr(_target_module.{patch_class}, {patch_method!r}, _wrapper)

sys.exit(journaled_receiver.main([
    "--state-dir", {state_dir!r}, "--host", "127.0.0.1", "--port", "0",
    "--runs-directory", {runs_dir!r}, {extra_args}
]))
"""


def _run_crash_child(
    *, patch_module: str, patch_class: str, patch_method: str, crash_at: int,
    state_dir: Path, runs_dir: Path, extra_args: tuple[str, ...] = (),
) -> subprocess.Popen:
    script = _CRASH_CHILD_SCRIPT.format(
        repo=str(REPOSITORY), patch_module=patch_module, patch_class=patch_class,
        patch_method=patch_method, crash_at=crash_at, state_dir=str(state_dir),
        runs_dir=str(runs_dir),
        extra_args="".join(f"{arg!r}, " for arg in extra_args),
    )
    return subprocess.Popen(
        [sys.executable, "-c", script], cwd=REPOSITORY,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _run_http_crash_case(
    *, patch_module: str, patch_class: str, patch_method: str, crash_at: int, state_dir: Path,
    runs_dir: Path, body: bytes,
) -> None:
    """C1-C3: the crash fires while handling one real POST.

    ``crash_at`` is the seam's call count at the moment of the crash, and it
    is *not* always 1: every ``start()`` already commits one
    ``restart_recovery`` through ``JournalStore.append`` before any POST is
    possible (confirmed against the actual listener: the append seam's first
    call happens at open, never at a POST), so a case that shares that seam
    with the restart commit -- C2 and C3, both on ``JournalStore.append`` --
    must crash on the *second* call, not the first. C1's seam
    (``JournalSpool.store``) is never touched during open, so its crash is
    still the first and only call.
    """
    proc = _run_crash_child(
        patch_module=patch_module, patch_class=patch_class, patch_method=patch_method,
        crash_at=crash_at, state_dir=state_dir, runs_dir=runs_dir,
    )
    try:
        _lines, listening = _wait_for_listening_line(proc, time.monotonic() + 10)
        assert listening is not None, "child never printed its listening line"
        url = listening.removeprefix("listening on ")
        _post_and_ignore_disconnect(url, body)
        proc.wait(timeout=10)
    finally:
        _stop(proc)
    assert proc.returncode == -signal.SIGKILL, proc.returncode


# === C1: after spool.store, before admit =======================================


def test_c1_crash_after_spool_store_before_admit_leaves_an_orphan(tmp_path):
    directory = tmp_path / "S"
    runs_dir = tmp_path / "runs"
    jo.create_state(directory)
    body = (FIXTURES / "notification-firing.json").read_bytes()
    digest = ji.body_digest(body)

    _run_http_crash_case(
        patch_module="journal_spool", patch_class="JournalSpool", patch_method="store",
        crash_at=1, state_dir=directory, runs_dir=runs_dir, body=body,
    )

    inspection = rj.inspect_recovery_journal(directory / "journal")
    assert inspection.report["verdict"] == "ready"
    assert inspection.report["journal"]["counts"]["admissions"] == 0
    assert digest not in inspection.references
    survey = jsp.survey_spool(directory / "spool", inspection.references)
    assert digest in survey["orphans"]

    # A re-POST reuses the spooled entry and is admitted.
    outcome = ji.sanitize_notification(body)
    assert outcome.source is not None
    journal = rj.open_recovery_journal(directory / "journal")
    try:
        receipt = journal.admit(outcome.source)
    finally:
        journal.close()
    assert receipt.result == "admitted"
    spool = jsp.JournalSpool.open(directory / "spool")
    assert spool.store(body, digest) == "present"


# === C2: after append, before the 202 ===========================================


def test_c2_crash_after_append_before_the_202_leaves_the_admission_durable(tmp_path):
    directory = tmp_path / "S"
    runs_dir = tmp_path / "runs"
    jo.create_state(directory)
    body = (FIXTURES / "notification-firing.json").read_bytes()
    digest = ji.body_digest(body)

    _run_http_crash_case(
        patch_module="journal_store", patch_class="JournalStore", patch_method="append",
        crash_at=2, state_dir=directory, runs_dir=runs_dir, body=body,
    )

    inspection = rj.inspect_recovery_journal(directory / "journal")
    assert inspection.report["verdict"] == "ready"
    assert inspection.report["journal"]["counts"]["admissions"] == 1
    assert digest in inspection.references
    survey = jsp.survey_spool(directory / "spool", inspection.references)
    assert survey["entries"] == 1
    assert survey["orphans_total"] == 0

    # A re-POST (replayed here as a direct `admit`) is suppressed: the
    # journal already holds this admission, and it is still held for
    # dispatch, because the crashed boot's own restart was never resumed.
    outcome = ji.sanitize_notification(body)
    journal = rj.open_recovery_journal(directory / "journal")
    try:
        assert "restart_recovery" in journal.dispatch_holds
        receipt = journal.admit(outcome.source)
    finally:
        journal.close()
    assert receipt.result == "suppressed"
    assert receipt.decision == "held"


# === C3: after the refusal commit, before the 4xx ================================


def test_c3_crash_after_the_refusal_commit_before_the_4xx_leaves_one_record(tmp_path):
    directory = tmp_path / "S"
    runs_dir = tmp_path / "runs"
    jo.create_state(directory)
    body = b"not json"  # ingress_json_invalid: refused before any admission is possible

    _run_http_crash_case(
        patch_module="journal_store", patch_class="JournalStore", patch_method="append",
        crash_at=2, state_dir=directory, runs_dir=runs_dir, body=body,
    )

    inspection = rj.inspect_recovery_journal(directory / "journal")
    assert inspection.report["verdict"] == "ready"
    assert inspection.report["refusals"]["recorded"] == 1

    # A re-send of the identical body is coalesced under the same key.
    outcome = ji.sanitize_notification(body)
    assert outcome.refusal is not None
    summary = ji.refusal_to_json(outcome.refusal)
    journal = rj.open_recovery_journal(directory / "journal")
    try:
        result = journal.record_refusal(summary)
    finally:
        journal.close()
    assert result == "coalesced"


# === C4: after the start's restart, before the resume ============================


def test_c4_crash_after_the_starts_restart_before_the_resume(tmp_path):
    directory = tmp_path / "S"
    runs_dir = tmp_path / "runs"
    jo.create_state(directory)
    stale_token = rj.inspect_recovery_journal(directory / "journal").report["resume"]["token"]

    proc = _run_crash_child(
        patch_module="journal_store", patch_class="JournalStore", patch_method="append",
        crash_at=1, state_dir=directory, runs_dir=runs_dir,
        extra_args=("--resume-token", stale_token, "--operator", "c4-tester"),
    )
    try:
        proc.wait(timeout=10)
    finally:
        _stop(proc)
    assert proc.returncode == -signal.SIGKILL, proc.returncode

    inspection = rj.inspect_recovery_journal(directory / "journal")
    assert inspection.report["verdict"] == "ready"
    assert inspection.report["resumes"]["count"] == 0  # no operator_action was ever committed

    with pytest.raises(rj.JournalError) as info:
        rj.open_recovery_journal(
            directory / "journal",
            resume=rj.ResumeRequest(token=stale_token, operator="c4-tester-retry"),
        )
    assert info.value.code == "resume_stale"


# === C5: after the resume commit, before serving =================================


def test_c5_crash_after_the_resume_commit_before_serving(tmp_path):
    directory = tmp_path / "S"
    runs_dir = tmp_path / "runs"
    jo.create_state(directory)
    token = rj.inspect_recovery_journal(directory / "journal").report["resume"]["token"]

    proc = _run_crash_child(
        patch_module="journal_store", patch_class="JournalStore", patch_method="append",
        crash_at=2, state_dir=directory, runs_dir=runs_dir,
        extra_args=("--resume-token", token, "--operator", "c5-tester"),
    )
    try:
        proc.wait(timeout=10)
    finally:
        _stop(proc)
    assert proc.returncode == -signal.SIGKILL, proc.returncode

    inspection = rj.inspect_recovery_journal(directory / "journal")
    assert inspection.report["verdict"] == "ready"
    assert inspection.report["resumes"]["count"] == 1  # the resume itself committed cleanly

    # The next real open re-holds: nothing served long enough to be resumed.
    journal = rj.open_recovery_journal(directory / "journal")
    try:
        assert "restart_recovery" in journal.dispatch_holds
    finally:
        journal.close()

    store = journal_store.JournalStore.open(directory / "journal")
    try:
        record_types = [record.event_type for record in store.rows()]
    finally:
        store.close()
    # ..., restart_recovery (the crashed boot), operator_action (the resume
    # that committed), restart_recovery (this open, immediately re-holding).
    assert record_types[-3:] == ["restart_recovery", "operator_action", "restart_recovery"]


# === C6: a SIGKILL loop, 5 iterations, a randomized kill delay ===================


def _run_c6(tmp_path: Path, *, seed: int = 20260924) -> None:
    print(f"\n[c6] seed={seed}")
    rng = random.Random(seed)
    directory = tmp_path / "S"
    runs_dir = tmp_path / "runs"
    jo.create_state(directory)

    acknowledged: set[str] = set()
    counter = {"n": 0}
    resume_token: str | None = None

    for iteration in range(5):
        extra_args = () if resume_token is None else (
            "--resume-token", resume_token, "--operator", "c6-tester",
        )
        proc = _spawn_journaled_receiver_main(directory, runs_dir, extra_args)
        posted_ok: list[str] = []
        try:
            _lines, listening = _wait_for_listening_line(proc, time.monotonic() + 10)
            assert listening is not None, f"iteration {iteration}: child never listened"
            url = listening.removeprefix("listening on ")

            stop_posting = threading.Event()
            thread = threading.Thread(
                target=_post_loop, args=(url, stop_posting, posted_ok, counter),
            )
            thread.start()

            delay = rng.uniform(0.05, 0.4)
            time.sleep(delay)
            print(f"[c6] iteration={iteration} kill_delay={delay:.3f}s")

            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=10)
            stop_posting.set()
            thread.join(timeout=10)
            assert not thread.is_alive(), f"iteration {iteration}: client thread never stopped"
        finally:
            _stop(proc)

        acknowledged.update(posted_ok)
        resume_token = rj.inspect_recovery_journal(directory / "journal").report["resume"]["token"]

    inspection = rj.inspect_recovery_journal(directory / "journal")
    survey = jsp.survey_spool(directory / "spool", inspection.references)
    assert survey["missing_total"] == 0
    for digest in acknowledged:
        assert digest in inspection.references
        assert digest not in survey["orphans"]
        assert digest not in survey["missing"]


def test_c6_sigkill_loop_five_iterations(tmp_path):
    _run_c6(tmp_path)
