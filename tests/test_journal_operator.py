"""CLI tests for the operator entry point (ticket 37, unit 17b; Tester T2b,
cases O1-O8).

``journal_operator.py`` and ``journaled_receiver.py`` are written in parallel
with this file and are not available while it is drafted: every signature
below follows ``reviews/receiver-journal/implementation-plan.md`` exactly
("Operator entry points"), so the finalizer reconciles names against the
real modules rather than this file inventing its own.

Real SQLite and real syncs throughout, private 0700 ``tmp_path``
directories, no fixed ports (every server binds ``127.0.0.1:0``; every
child process takes ``--port 0`` and is found by parsing its own "listening
on" line), no sleeps. ``SeqIds``/``SeqClock``/``CG1_KEY``/``PF``/``source``
and the WAL crash-image helpers are reused by read-only import from
``test_recovery_journal.py`` and ``test_recovery_journal_crash.py`` rather
than redefined.
"""

from __future__ import annotations

import json
import os
import select
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_operator as jo
from grafana_jsm_sandbox import journal_spool as jsp
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import journaled_receiver as jreceiver
from grafana_jsm_sandbox import recovery_journal as rj
from tests.conftest import FIXTURES, http_request
from tests.test_recovery_journal import CG1_KEY, PF, source
from tests.test_recovery_journal_crash import commit_groups, flip_byte_in_group, wal_frames

pytestmark = pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE "
    "(Python >= 3.12)",
)

REPOSITORY = Path(__file__).resolve().parent.parent


# === Shared helpers ===========================================================


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _tree_snapshot(directory: Path) -> dict[str, bytes]:
    """Every regular file's bytes under ``directory``, keyed by relative path."""
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _run_main(argv: list[str], capsys) -> tuple[int, dict, str]:
    code = jo.main(argv)
    captured = capsys.readouterr()
    report = json.loads(captured.out) if captured.out.strip() else {}
    return code, report, captured.err


def _distinct_notification_body(tag: str) -> bytes:
    payload = {
        "groupKey": f'{{}}:{{alertname="o5", tag="{tag}"}}',
        "alerts": [{"fingerprint": f"fp-{tag}", "status": "firing"}],
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _build_held_image(tmp_path: Path, name: str) -> Path:
    """A state directory whose journal carries a recovery finding baked into
    its WAL, never opened -- and so never persisted -- since the corruption
    (mirrors ``test_recovery_journal_crash.py``'s e8a/e8b images)."""
    directory = tmp_path / name
    jo.create_state(directory)
    journal = rj.open_recovery_journal(directory / "journal")
    try:
        journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    finally:
        journal.close()
    wal_path = directory / "journal" / journal_store.WAL_FILENAME
    wal_bytes = wal_path.read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path.write_bytes(flip_byte_in_group(wal_bytes, groups[-1]))
    return directory


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def _spawn_journaled_receiver(
    directory: Path, runs_directory: Path, *extra_args: str, env: dict[str, str] | None = None,
) -> subprocess.Popen:
    if env is None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPOSITORY) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        [
            sys.executable, "-m", "grafana_jsm_sandbox.journaled_receiver",
            "--state-dir", str(directory), "--host", "127.0.0.1", "--port", "0",
            "--runs-directory", str(runs_directory), *extra_args,
        ],
        cwd=REPOSITORY, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _readline_before(stream, deadline: float) -> str | None:
    """One line from ``stream``, never blocking past ``deadline`` (a quiet,
    hung child must never hang this test, or the suite run behind it)."""
    line = bytearray()
    while time.monotonic() < deadline:
        ready, _write, _err = select.select([stream], [], [], deadline - time.monotonic())
        if not ready:
            return None
        byte = os.read(stream.fileno(), 1)
        if not byte:
            return line.decode() or None
        line.extend(byte)
        if byte == b"\n":
            return line.decode()
    return None


def _wait_for_listening_line(
    proc: subprocess.Popen, deadline: float,
) -> tuple[list[str], str | None]:
    """Lines printed before "listening on ...", and that line itself (``None``
    if the deadline passed first)."""
    lines: list[str] = []
    while True:
        line = _readline_before(proc.stdout, deadline)
        if line is None:
            return lines, None
        line = line.rstrip("\n")
        if line.startswith("listening on http://"):
            return lines, line
        lines.append(line)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)


# === O1: create ================================================================


def test_o1_create_state_layout_and_json(tmp_path):
    directory = tmp_path / "S"
    result = jo.create_state(directory)

    assert _mode(directory) == 0o700
    assert _mode(directory / "spool") == 0o700
    assert _mode(directory / "journal") == 0o700
    assert set(result) == {"journal_uuid"}
    assert isinstance(result["journal_uuid"], str) and result["journal_uuid"]

    opened = rj.open_recovery_journal(directory / "journal")
    try:
        assert opened.state == "ready"
        assert opened.snapshot()["journal_uuid"] == result["journal_uuid"]
    finally:
        opened.close()


def test_o1_create_refuses_dangling_symlink_without_creating_target(tmp_path, capsys):
    target = tmp_path / "absent-target"
    alias = tmp_path / "S"
    alias.symlink_to(target, target_is_directory=True)
    code, report, _err = _run_main(["create", "--state-dir", str(alias)], capsys)
    assert code == 1
    assert report == {"error": "state_exists"}
    assert alias.is_symlink()
    assert not target.exists()


def test_o1_create_twice_exits_1_state_exists_and_changes_nothing(tmp_path, capsys):
    directory = tmp_path / "S"
    jo.create_state(directory)
    before = _tree_snapshot(directory)

    code, report, _err = _run_main(["create", "--state-dir", str(directory)], capsys)

    assert code == 1
    # main()'s create branch reports the refusal under "error" (its own JSON
    # shape), unlike inspect's report, which carries "code" (jo.inspect_state).
    assert report.get("error") == "state_exists"
    assert _tree_snapshot(directory) == before


def test_o1_sync_order_is_parent_then_state_then_three_journal_syncs(tmp_path, monkeypatch):
    directory = tmp_path / "S"
    events: list[tuple] = []

    real_sync_directory = jo.sync_directory

    def recording_sync_directory(path):
        events.append(("sync_directory", path))
        return real_sync_directory(path)

    real_full_sync = journal_store._full_sync

    def recording_full_sync(fd):
        events.append(("full_sync",))
        return real_full_sync(fd)

    monkeypatch.setattr(jo, "sync_directory", recording_sync_directory)
    monkeypatch.setattr(journal_store, "_full_sync", recording_full_sync)

    jo.create_state(directory)

    sync_directory_events = [event for event in events if event[0] == "sync_directory"]
    assert sync_directory_events == [
        ("sync_directory", directory.parent), ("sync_directory", directory),
    ]
    state_index = events.index(("sync_directory", directory))
    # create_recovery_journal -> JournalStore.create's genesis write: one
    # directory sync after the schema and row land, one anchor-slot file
    # sync, one more directory sync after the anchor -- three full_sync
    # calls, confirmed against the actual (unchanged, byte-identical to
    # baseline) journal_store.py rather than the plan prose's "4 syncs".
    assert events[state_index + 1:] == [("full_sync",)] * 3, events


def test_o1_parent_sync_failure_exits_1_spool_write_failed_and_no_genesis(
    tmp_path, monkeypatch, capsys,
):
    directory = tmp_path / "S"

    def failing_sync_directory(_path):
        raise jsp.SpoolError("spool_write_failed")

    monkeypatch.setattr(jo, "sync_directory", failing_sync_directory)

    code, report, _err = _run_main(["create", "--state-dir", str(directory)], capsys)

    assert code == 1
    assert report.get("error") == "spool_write_failed"
    assert directory.is_dir()  # mkdir S already ran
    assert not (directory / "spool").exists()
    assert not (directory / "journal").exists()


# === O2: inspect on a ready state ==============================================


def test_o2_inspect_ready_exits_0_with_resume_token_and_unchanged_tree(tmp_path, capsys):
    directory = tmp_path / "S"
    jo.create_state(directory)
    before = _tree_snapshot(directory)

    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)

    assert code == 0
    assert report["verdict"] == "ready"
    token = report["resume"]["token"]
    assert isinstance(token, str) and len(token) == 64
    independent = rj.inspect_recovery_journal(directory / "journal")
    assert token == independent.report["resume"]["token"]
    assert _tree_snapshot(directory) == before


# === O3: inspect while the journal is open =====================================


def test_o3_inspect_while_journal_locked_exits_3(tmp_path, capsys):
    """Stands in for "a front door runs": the front door's only exclusive
    resource here is the journal's flock, held for exactly as long as it
    serves, so holding it directly exercises the same refusal."""
    directory = tmp_path / "S"
    jo.create_state(directory)
    held_open = rj.open_recovery_journal(directory / "journal")
    try:
        code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    finally:
        held_open.close()
    assert code == 3
    assert report.get("code") == "journal_locked"


# === O4: held and WAL-absent images ============================================


def test_o4_held_image_exits_1_with_persist_hold_and_unpersisted_in_anchor(tmp_path, capsys):
    directory = _build_held_image(tmp_path, "o4-held")

    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)

    assert code == 1
    assert report["verdict"] == "held"
    assert report["next_open"] == ["persist_hold"]
    assert report["finding"]["in_anchor"] is False


def test_o4_wal_absent_full_size_db_exits_6_and_gains_no_file(tmp_path, capsys):
    directory = tmp_path / "S"
    jo.create_state(directory)
    journal = rj.open_recovery_journal(directory / "journal")
    try:
        journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    finally:
        journal.close()

    # A raw checkpointing connection, closed with nothing else attached: the
    # WAL is removed (unlike the journal's own no-checkpoint-on-close opens).
    raw = sqlite3.connect(str(directory / "journal" / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        raw.close()
    assert not (directory / "journal" / journal_store.WAL_FILENAME).exists()
    before = _tree_snapshot(directory)

    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)

    assert code == 6
    assert report["verdict"] == "unverified"
    assert report["reason"] == "wal_absent"
    assert _tree_snapshot(directory) == before


# === O5: spool survey ==========================================================


def test_o5_spool_survey_orphan_missing_mismatched_and_temporary(tmp_path, capsys):
    directory = tmp_path / "S"
    jo.create_state(directory)
    spool_directory = directory / "spool"

    referenced_body = (FIXTURES / "notification-firing.json").read_bytes()
    referenced_digest = ji.body_digest(referenced_body)
    spool = jsp.JournalSpool.open(spool_directory)
    assert spool.store(referenced_body, referenced_digest) == "written"
    outcome = ji.sanitize_notification(referenced_body)
    assert outcome.source is not None
    journal = rj.open_recovery_journal(directory / "journal")
    try:
        journal.admit(outcome.source)
    finally:
        journal.close()

    # An orphan: spooled, never admitted -- an H9-style capacity refusal
    # leaves exactly this shape; reproduced directly rather than over HTTP,
    # since this file does not own the front door's own test suite.
    orphan_body = _distinct_notification_body("o5-orphan")
    orphan_digest = ji.body_digest(orphan_body)
    assert spool.store(orphan_body, orphan_digest) == "written"

    # A temporary: a `.tmp-*` name left by a write that never completed.
    tmp_name = f".tmp-{'a' * 64}-{'b' * 16}"
    (spool_directory / tmp_name).write_bytes(b"partial")
    os.chmod(spool_directory / tmp_name, 0o600)

    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    assert code == 0
    survey = report["spool"]
    assert orphan_digest in survey["orphans"]
    assert survey["orphans_total"] == 1
    assert referenced_digest not in survey["orphans"]
    assert survey["temporaries"] == 1

    # A hand-deleted referenced entry: exits 5, listed under `missing`.
    (spool_directory / referenced_digest).unlink()
    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    assert code == 5
    assert referenced_digest in report["spool"]["missing"]

    # Restored, then rewritten: exits 5, listed under `mismatched`.
    spool_again = jsp.JournalSpool.open(spool_directory)
    assert spool_again.store(referenced_body, referenced_digest) == "written"
    (spool_directory / referenced_digest).write_bytes(b"tampered bytes, same name")
    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    assert code == 5
    assert referenced_digest in report["spool"]["mismatched"]

    # Referenced entry restored; the orphan rewritten instead: exits 5,
    # listed under `mismatched_orphans`.
    (spool_directory / referenced_digest).write_bytes(referenced_body)
    (spool_directory / orphan_digest).write_bytes(b"tampered orphan bytes")
    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    assert code == 5
    assert orphan_digest in report["spool"]["mismatched_orphans"]

    # Moved out by hand, as the runbook says (step 8): inspect is clean
    # again, and a fresh admission of the same bytes rewrites the entry
    # (critic 14).
    (spool_directory / orphan_digest).rename(tmp_path / "evidence-mismatched-orphan")
    code, report, _err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    assert code == 0
    spool_once_more = jsp.JournalSpool.open(spool_directory)
    assert spool_once_more.store(orphan_body, orphan_digest) == "written"


def test_o5_spool_custody_failure_exits_4_with_spool_code_in_report_and_stderr(tmp_path, capsys):
    directory = tmp_path / "S"
    jo.create_state(directory)

    os.chmod(directory / "spool", 0o755)
    code, report, err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    assert code == 4
    # A spool custody failure with the journal itself ready: inspect_state
    # reports it under "spool_error", distinct from the journal-open "code"
    # key (critic 8d).
    assert report.get("spool_error") == "spool_permissions"
    assert "spool_permissions" in err
    os.chmod(directory / "spool", 0o700)  # restore, so teardown can clean up

    shutil.rmtree(directory / "spool")
    code, report, err = _run_main(["inspect", "--state-dir", str(directory)], capsys)
    assert code == 4
    assert report.get("spool_error") == "spool_missing"
    assert "spool_missing" in err


# === O6: journaled_receiver.main in a subprocess ===============================


def test_o6_prints_resolved_directories_before_listening_and_sigint_exits_0(tmp_path):
    directory = tmp_path / "S"
    runs_directory = tmp_path / "runs"
    jo.create_state(directory)

    proc = _spawn_journaled_receiver(directory, runs_directory)
    try:
        lines, listening = _wait_for_listening_line(proc, time.monotonic() + 10)
        assert listening is not None, "child never printed its listening line"
        assert any(str(directory) in line for line in lines)
        assert any(str(runs_directory) in line for line in lines)
        assert "journaled admission-only mode: Notifications are recorded durably; " \
            "no Run is started" in lines
        assert "dispatch held: restart_recovery (inspect, then restart with --resume-token)" \
            in lines
    finally:
        proc.send_signal(signal.SIGINT)
        code = proc.wait(timeout=10)
    assert code == 0


def test_o6_stale_resume_token_exits_1_with_resume_stale_on_stderr_and_frees_port(tmp_path):
    directory = tmp_path / "S"
    runs_directory = tmp_path / "runs"
    jo.create_state(directory)
    stale_token = rj.inspect_recovery_journal(directory / "journal").report["resume"]["token"]

    # One clean boot moves the head (every open commits `restart_recovery`),
    # so `stale_token` -- read before this boot -- is stale afterwards.
    warm_up = _spawn_journaled_receiver(directory, runs_directory)
    try:
        _lines, listening = _wait_for_listening_line(warm_up, time.monotonic() + 10)
        assert listening is not None
    finally:
        warm_up.send_signal(signal.SIGINT)
        warm_up.wait(timeout=10)

    proc = _spawn_journaled_receiver(
        directory, runs_directory, "--resume-token", stale_token, "--operator", "o6-tester",
    )
    try:
        _lines, listening = _wait_for_listening_line(proc, time.monotonic() + 10)
        _out, err = proc.communicate(timeout=10)
    finally:
        _stop(proc)

    assert proc.returncode == 1
    assert "resume_stale" in err
    assert listening is None


def test_o6_resume_against_held_image_exits_1_resume_not_applied_and_frees_port(tmp_path):
    directory = _build_held_image(tmp_path, "o6-held")
    runs_directory = tmp_path / "runs"

    proc = _spawn_journaled_receiver(
        directory, runs_directory, "--resume-token", "0" * 64, "--operator", "o6-tester",
    )
    try:
        _lines, listening = _wait_for_listening_line(proc, time.monotonic() + 10)
        _out, err = proc.communicate(timeout=10)
    finally:
        _stop(proc)

    assert proc.returncode == 1
    assert "resume_not_applied" in err
    assert listening is None


@pytest.mark.parametrize("held", [False, True])
def test_o6_refused_start_closes_bound_listener_in_process(tmp_path, monkeypatch, held):
    directory = _build_held_image(tmp_path, "held") if held else tmp_path / "S"
    if not held:
        jo.create_state(directory)
    sockets = []
    receiver_type = jreceiver.JournaledReceiver

    def capture_receiver(*args, **kwargs):
        receiver = receiver_type(*args, **kwargs)
        sockets.append(receiver._server.socket)
        assert sockets[-1].getsockname()[1] > 0
        return receiver

    monkeypatch.setattr(jreceiver, "JournaledReceiver", capture_receiver)
    assert jreceiver.main([
        "--state-dir", str(directory), "--runs-directory", str(tmp_path / "runs"),
        "--port", "0", "--resume-token", "0" * 64, "--operator", "tester",
    ]) == 1
    assert len(sockets) == 1
    assert sockets[0].fileno() == -1


def test_o6_resume_token_without_operator_exits_2(tmp_path):
    directory = tmp_path / "S"
    runs_directory = tmp_path / "runs"
    jo.create_state(directory)

    proc = _spawn_journaled_receiver(directory, runs_directory, "--resume-token", "0" * 64)
    try:
        _out, _err = proc.communicate(timeout=10)
    finally:
        _stop(proc)
    assert proc.returncode == 2


def test_o6_main_refuses_symlink_state_before_journal_access(tmp_path, capsys):
    directory = tmp_path / "S"
    jo.create_state(directory)
    alias = tmp_path / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    before = _tree_snapshot(directory)
    assert jreceiver.main([
        "--state-dir", str(alias), "--runs-directory", str(tmp_path / "runs"),
        "--port", "0", "--resume-token", "0" * 64, "--operator", "tester",
    ]) == 1
    assert "state_path_invalid" in capsys.readouterr().err
    assert _tree_snapshot(directory) == before


# === O7: least privilege =======================================================


def test_o7_subprocess_runs_with_minimal_environment_and_serves(tmp_path):
    directory = tmp_path / "S"
    runs_directory = tmp_path / "runs"
    jo.create_state(directory)
    minimal_env = {"PATH": os.environ.get("PATH", os.defpath), "PYTHONPATH": str(REPOSITORY)}

    proc = _spawn_journaled_receiver(directory, runs_directory, env=minimal_env)
    try:
        _lines, listening = _wait_for_listening_line(proc, time.monotonic() + 10)
        assert listening is not None, f"child never listened; stderr so far: {proc.stderr}"
        port = int(listening.rsplit(":", 1)[1])
        response = http_request(f"http://127.0.0.1:{port}/health")
        assert response.status in (200, 503)
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)


# === O8: a state directory with no journal =====================================


def test_o8_state_directory_without_journal_exits_4_journal_missing(tmp_path, capsys):
    """The case list's one-line summary says "exits 1"; the same section's
    own exit-code table for ``inspect`` puts every open error other than
    ``journal_locked`` at exit 4 ("any other open error"), and
    ``journal_operator.inspect_state`` implements exactly that table:
    ``journal_missing`` is not ``journal_locked``, so it is exit 4. There is
    no separate "create" hint text on stderr -- the code itself, printed by
    ``main``, is the only diagnostic (no caller data, closed code sets).

    The "journal" directory itself must exist (0700) but hold none of the
    store's three files: an absent directory fails custody a step earlier,
    at ``_check_directory``, with ``journal_path_invalid`` instead (as
    ``JournalStore.open`` distinguishes: custody first, "missing" second)."""
    directory = tmp_path / "S"
    directory.mkdir(mode=0o700)
    (directory / "spool").mkdir(mode=0o700)
    (directory / "journal").mkdir(mode=0o700)
    before = _tree_snapshot(directory)

    code, report, err = _run_main(["inspect", "--state-dir", str(directory)], capsys)

    assert code == 4
    assert report.get("code") == "journal_missing"
    assert "journal_missing" in err
    assert _tree_snapshot(directory) == before


def test_o8_serving_uninitialized_journal_exits_1_with_create_hint(tmp_path, capsys):
    directory = tmp_path / "S"
    directory.mkdir(mode=0o700)
    (directory / "journal").mkdir(mode=0o700)
    (directory / "spool").mkdir(mode=0o700)
    before = _tree_snapshot(directory)
    assert jreceiver.main([
        "--state-dir", str(directory), "--runs-directory", str(tmp_path / "runs"),
        "--port", "0",
    ]) == 1
    stderr = capsys.readouterr().err
    assert "journal_missing" in stderr
    assert "journal_operator create" in stderr
    assert _tree_snapshot(directory) == before


def test_o1_state_sync_happens_after_both_child_directories_exist(tmp_path, monkeypatch):
    directory = tmp_path / "S"
    actual_sync = jo.sync_directory
    observed = []

    def check_children_then_sync(path):
        if path == directory:
            observed.append(path)
            assert (path / "spool").is_dir()
            assert (path / "journal").is_dir()
        return actual_sync(path)

    monkeypatch.setattr(jo, "sync_directory", check_children_then_sync)
    jo.create_state(directory)
    assert observed == [directory]
