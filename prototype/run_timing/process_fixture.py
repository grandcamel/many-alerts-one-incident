"""Real POSIX supervision of a CLOSED set of local, trusted fixture programs.

Not an OS sandbox or native model launcher. Group membership assumes these reviewed
fixtures do not setsid/escape. Output parent and source/interpreter are operator-trusted.
No callback, executable, shell command, extra argument or environment can be supplied.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .executor import Capture, Lifecycle
from .outcomes import Outcome, Transcript, seconds

SCENARIOS = frozenset({"success", "nonzero", "result_error", "duplicate", "malformed",
                       "silence", "ignore_interrupt", "held_pipe", "held_pipe_ignore",
                       "closed_pipes_alive", "flood", "oversized_line"})


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Inability to inspect cannot become containment success.
    return True


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


@dataclass(frozen=True)
class ProcessResult:
    outcome: Outcome
    actions: tuple[tuple[float, tuple[str, ...]], ...]
    elapsed_seconds: float
    total_bound_seconds: float
    cleanup_bound_seconds: float
    root_pid: int | None
    root_reaped: bool
    group_gone: bool
    pipes_closed: bool
    capture_complete: bool
    captured_bytes: int
    capture_sha256: str
    attempt_directory: str
    worker_sha256: str
    scope: str = "FIXED_HOST_FIXTURES_ONLY"
    native_launch: str = "CLOSED"


def validate_fixture_request(scenario: str, attempt_id: str, *, time_scale: float = 1.0,
                             capture_limit: int = 1024 * 1024,
                             cancel: threading.Event | None = None) -> float:
    """Validate the fixed fixture contract before callers make durable admissions."""
    if os.name != "posix":
        raise RuntimeError("POSIX fixture supervision required")
    if scenario not in SCENARIOS:
        raise ValueError("unknown fixed fixture")
    scale = seconds(time_scale)
    if not 0.001 <= scale <= 1:
        raise ValueError("time scale must be between 0.001 and 1")
    if not isinstance(attempt_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}",
                                                        attempt_id):
        raise ValueError("invalid attempt ID")
    if cancel is not None and not isinstance(cancel, threading.Event):
        raise TypeError("cancellation requires a threading.Event")
    if type(capture_limit) is not int or not 1 <= capture_limit <= 1024 * 1024:
        raise ValueError("fixture capture cap must be 1 byte to 1 MiB")
    return scale


def run_fixture(scenario: str, output_parent: Path, attempt_id: str, *,
                time_scale: float = 1.0, capture_limit: int = 1024 * 1024,
                cancel: threading.Event | None = None) -> ProcessResult:
    """Run exactly one fixed fixture; smaller test bounds cannot enlarge 270/20/10."""
    scale = validate_fixture_request(scenario, attempt_id, time_scale=time_scale,
                                     capture_limit=capture_limit, cancel=cancel)
    # Exclusive admission: an existing attempt, file or symlink is never removed/reused.
    directory = Path(output_parent).resolve(strict=True) / attempt_id
    worker = Path(__file__).with_name("_fixture_worker.py").resolve(strict=True)
    worker_bytes = worker.read_bytes()
    directory.mkdir(mode=0o700)
    snapshot = directory / "fixture.py"
    with snapshot.open("xb") as handle:
        handle.write(worker_bytes)
    snapshot.chmod(0o400)
    environment = {"HOME": str(directory), "TMPDIR": str(directory), "LC_ALL": "C"}
    command = [sys.executable, "-I", "-S", str(snapshot), scenario]
    life = Lifecycle()
    transcript = Transcript("fixture-only")
    capture = Capture(limit=capture_limit)
    pending = bytearray()
    actions = []
    process = None
    root_reaped = group_gone = pipes_closed = False
    exit_code = None
    io_failed = False
    started = time.monotonic()
    with selectors.DefaultSelector() as selector:
        try:
            try:
                process = subprocess.Popen(command, cwd=directory, env=environment,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, start_new_session=True,
                                           close_fds=True)
            except OSError:
                life.reasons.add("spawn_failure")
                life.revoked = True
                life.finished = True
                actions.append((time.monotonic() - started, ("revoke_fixture", "hold")))
            if process is not None:
                for stream in (process.stdout, process.stderr):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ)
                while not life.finished:
                    elapsed = time.monotonic() - started
                    exit_code = process.poll()  # Reaps the direct child, not grandchildren.
                    root_reaped = exit_code is not None
                    group_gone = not _group_alive(process.pid)
                    # Removing a failed descriptor is cleanup, not observed EOF.
                    pipes_closed = not selector.get_map() and not io_failed
                    running = not (root_reaped and group_gone)
                    changed = life.advance(elapsed / scale,
                                           cancel=bool(cancel and cancel.is_set()) or
                                           ((transcript.stop_requested or io_failed) and running),
                                           parent_exited=root_reaped,
                                           reaped=root_reaped and group_gone,
                                           pipes_closed=pipes_closed)
                    if changed:
                        actions.append((elapsed, changed))
                    if "interrupt" in changed and not group_gone:
                        _signal_group(process.pid, signal.SIGINT)
                    if "kill_and_reap" in changed and not group_gone:
                        _signal_group(process.pid, signal.SIGKILL)
                        # Forced orphan cleanup is visible even after a clean parent exit.
                        life.reasons.add("cancelled")
                    if life.finished:
                        break
                    boundary = (270 if life.cleanup_at is None else
                                life.end_at if life.killed else life.kill_at)
                    wait = max(0, min(0.01, (boundary - life.now) * scale))
                    for key, _ in selector.select(wait):
                        try:
                            data = os.read(key.fd, 8192)
                        except BlockingIOError:
                            continue
                        except OSError:
                            io_failed = True
                            capture.complete = False
                            transcript.reasons.add("malformed_evidence")
                            if key.fileobj is process.stdout:
                                pending.clear()
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                            continue
                        if not data:
                            selector.unregister(key.fileobj)
                            if key.fileobj is process.stdout and pending:
                                transcript.feed(bytes(pending))
                                pending.clear()
                            key.fileobj.close()
                            continue
                        if not capture.append(data):
                            transcript.reasons.add("capture_limit")
                            transcript.stop_requested = True
                            # No classifications may depend on unretained bytes or a
                            # prefix whose continuation was lost to the capture cap.
                            pending.clear()
                            continue
                        if key.fileobj is process.stdout:
                            pending.extend(data)
                            while b"\n" in pending:
                                line, _, rest = pending.partition(b"\n")
                                pending[:] = rest
                                transcript.feed(bytes(line))
                            if len(pending) > transcript.max_line_bytes:
                                transcript.reasons.add("capture_limit")
                                transcript.stop_requested = True
                                pending.clear()
            if io_failed:
                transcript.reasons.add("malformed_evidence")
        finally:
            # Exception paths also get bounded group cleanup, never unbounded communicate/wait.
            if process is not None:
                if _group_alive(process.pid):
                    _signal_group(process.pid, signal.SIGKILL)
                remaining = max(0, started + life.end_at * scale - time.monotonic())
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    life.reasons.add("containment_failure")
                for stream in (process.stdout, process.stderr):
                    stream.close()
    elapsed = time.monotonic() - started
    # Evidence above was sampled before cleanup/finalization; never fabricate pipe EOF.
    result = ProcessResult(transcript.outcome(exit_code, life.reasons), tuple(actions), elapsed,
                           300 * scale, life.end_at * scale,
                           process.pid if process else None, root_reaped,
                           group_gone, pipes_closed, capture.complete, len(capture.data),
                           hashlib.sha256(capture.data).hexdigest(), str(directory),
                           hashlib.sha256(worker_bytes).hexdigest())
    with (directory / "result.json").open("x") as handle:
        json.dump(asdict(result), handle, indent=2, default=str)
        handle.write("\n")
    return result
