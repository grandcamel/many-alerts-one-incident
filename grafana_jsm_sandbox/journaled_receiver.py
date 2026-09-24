"""The journaled front door: durable admission before the 202, no Run
(ticket 37, unit 17b). Opt-in, separate from the demo:

    python3 -m grafana_jsm_sandbox.journaled_receiver --state-dir S

Every accepted Notification is spooled by ``body_digest``, then admitted into
the recovery journal, before the 202 is sent (spec L193-196; ADR12 L27). No
spawner, upstream client or subprocess module is imported or constructed
here: a journaled 202 means "durably admitted and body retained", never "a
Run will start" (plan Deferred 1). The demo's own command, ``receiver.py``
and every file the legacy-identity contract names are untouched and read no
state this module writes.

Listener hardening (probe r1; critics 1 and 2) keeps a hostile or trickling
caller from putting its own bytes into a response, a log line or stderr, and
bounds the work one connection can hold open. Error discipline matches
``journal_spool``: every ``except`` body only assigns a local variable or
passes, and a fresh error is raised after the ``try`` statement.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import io
import json
import logging
import os
import re
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType

from .journal_ingress import (
    INGRESS_HTTP_STATUS,
    MAX_INGRESS_BODY_BYTES,
    oversize_refusal,
    refusal_to_json,
    sanitize_notification,
)
from .journal_spool import MAX_SPOOL_BYTES, MAX_SPOOL_ENTRIES, JournalSpool, SpoolError
from .recovery_journal import (
    JournalError,
    RecoveryJournal,
    ResumeRequest,
    new_id,
    open_recovery_journal,
)

logger = logging.getLogger(__name__)

MODE = "journaled-admission-only"

MAX_IN_FLIGHT = 8
MAX_CONNECTIONS = 32
REQUEST_DEADLINE_SECONDS = 10.0
RETRY_AFTER_SECONDS = 10
BUSY_RETRY_AFTER_SECONDS = 1  # 10 = this demo's group_interval

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_RUNS_DIRECTORY = Path("runs")

FRONT_DOOR_CODES = frozenset({
    "state_missing", "state_path_invalid", "state_permissions", "state_placement_invalid",
    "listener_bind_failed", "front_door_argument", "resume_not_applied",
})
HTTP_CODES = frozenset({
    "not_found", "busy", "journal_opening", "http_length_required",
    "http_content_length_invalid", "http_body_incomplete", "http_request_invalid",
    "http_header_invalid", "http_method_unsupported", "receiver_error",
})
STDLIB_ERROR_CODES = MappingProxyType({
    400: "http_request_invalid", 414: "http_request_invalid", 431: "http_header_invalid",
    501: "http_method_unsupported", 505: "http_request_invalid",
})

_RUN_STATUS = "not_dispatched"
_MAX_SAFE_INTEGER = 2**53 - 1
_CONTENT_LENGTH_PATTERN = re.compile(r"[0-9]{1,16}")
_READ_BUFFER_BYTES = 65_536
_SHUTDOWN_POLL_INTERVAL = 0.05

# Restated: journal_records.MAX_REFUSAL_RECORDS and REFUSAL_RESOLVED_RESERVE, not
# importable here (not part of recovery_journal's public surface). Fixed forever
# under the frozen `rule` literal `first-per-membership-v1`; used only as the
# health placeholder before the journal is open, when no live value exists yet.
_REFUSAL_LIMIT = 256
_REFUSAL_RESERVE = 64


class FrontDoorError(Exception):
    """A fixed, non-diagnostic front-door rejection; never embeds caller data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


# --- Metrics: thread-safe counters and gauges for /health ---------------------


class _Metrics:
    """Bounded counters and gauges. Every key set is closed, so memory never
    grows with caller input."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts = {
            "busy": 0, "http_length_required": 0, "http_content_length_invalid": 0,
            "http_body_incomplete": 0, "connections_refused": 0, "deadline_exceeded": 0,
            "starts_at_dropped": 0,
        }
        self._gauges = {"in_flight": 0, "connections_open": 0}
        # Each keyed by a closed code or result set, so memory is bounded.
        self._protocol_errors: collections.Counter[str] = collections.Counter()
        self._backpressure: collections.Counter[str] = collections.Counter()
        self._admitted: collections.Counter[str] = collections.Counter()
        self._unrecorded_refusals: collections.Counter[str] = collections.Counter()

    def bump(self, name: str, by: int = 1) -> None:
        with self._lock:
            self._counts[name] += by

    def gauge(self, name: str, delta: int) -> None:
        with self._lock:
            self._gauges[name] += delta

    def bump_protocol_error(self, code: str) -> None:
        with self._lock:
            self._protocol_errors[code] += 1

    def bump_backpressure(self, code: str) -> None:
        with self._lock:
            self._backpressure[code] += 1

    def bump_admitted(self, result: str) -> None:
        with self._lock:
            self._admitted[result] += 1

    def bump_unrecorded_refusal(self, code: str) -> None:
        with self._lock:
            self._unrecorded_refusals[code] += 1

    def unrecorded_refusals(self) -> dict[str, int]:
        with self._lock:
            return dict(self._unrecorded_refusals)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "busy": self._counts["busy"],
                "http_length_required": self._counts["http_length_required"],
                "http_content_length_invalid": self._counts["http_content_length_invalid"],
                "http_body_incomplete": self._counts["http_body_incomplete"],
                "in_flight": self._gauges["in_flight"],
                "connections_open": self._gauges["connections_open"],
                "connections_refused": self._counts["connections_refused"],
                "deadline_exceeded": self._counts["deadline_exceeded"],
                "protocol_errors": dict(self._protocol_errors),
                "backpressure": dict(self._backpressure),
                "admitted": dict(self._admitted),
                "starts_at_dropped": self._counts["starts_at_dropped"],
            }


# --- Construction-time checks: argument shape, custody of S, placement --------


def _check_front_door_arguments(
    state_directory: object, runs_directory: object, host: object, port: object,
    max_in_flight: object, max_connections: object, request_deadline: object,
    spool_max_bytes: object, spool_max_entries: object,
) -> None:
    ok = (
        isinstance(state_directory, (str, Path)) and isinstance(runs_directory, (str, Path))
        and type(host) is str and type(port) is int
        and type(max_in_flight) is int and max_in_flight > 0
        and type(max_connections) is int and max_connections > 0
        and type(request_deadline) in (int, float) and request_deadline > 0
        and type(spool_max_bytes) is int and spool_max_bytes > 0
        and type(spool_max_entries) is int and spool_max_entries > 0
    )
    if not ok:
        raise FrontDoorError("front_door_argument")


def _lstat_or_none(path: Path) -> os.stat_result | None:
    """``None`` only when ``path`` is absent; any other ``OSError`` propagates."""
    result = None
    try:
        result = path.lstat()
    except FileNotFoundError:
        pass
    return result


def _check_state_directory(directory: Path) -> None:
    """Custody of ``S``, mirroring the spool's own rule: a directory, not a
    symlink, euid-owned, mode 0700."""
    stat_result = None
    try:
        stat_result = _lstat_or_none(directory)
    except OSError:
        pass
    if stat_result is None:
        raise FrontDoorError("state_missing")
    if stat.S_ISLNK(stat_result.st_mode) or not stat.S_ISDIR(stat_result.st_mode):
        raise FrontDoorError("state_path_invalid")
    if stat_result.st_uid != os.geteuid() or stat_result.st_mode & 0o077:
        raise FrontDoorError("state_permissions")


def _check_placement(state_directory: Path, runs_directory: Path) -> None:
    """Neither directory may contain the other (plan Deferred 2; V20)."""
    resolved_state = state_directory.resolve()
    resolved_runs = runs_directory.resolve()
    overlaps = (
        resolved_state == resolved_runs
        or resolved_state in resolved_runs.parents
        or resolved_runs in resolved_state.parents
    )
    if overlaps:
        raise FrontDoorError("state_placement_invalid")


# --- One monotonic deadline per request ----------------------------------------


class _DeadlineReader(io.RawIOBase):
    """Wraps the handler's socket so one deadline covers the whole request:
    keep-alive idle wait, request line, headers and body. Re-arms
    ``settimeout(remaining)`` before each ``recv_into``, so a byte-at-a-time
    trickle cannot re-arm a fixed per-call timeout (probe r1b).
    """

    def __init__(self, handler: _Handler) -> None:
        super().__init__()
        self._handler = handler

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        handler = self._handler
        remaining = handler.deadline - time.monotonic()
        timed_out = remaining <= 0
        result = 0
        if not timed_out:
            handler.connection.settimeout(remaining)
            try:
                result = handler.connection.recv_into(b)
            except TimeoutError:
                timed_out = True
        if timed_out:
            handler.server.front_door._metrics.bump("deadline_exceeded")
            raise TimeoutError from None
        return result


# --- Content-Length framing (steps 3-4 of the HTTP contract) ------------------


@dataclasses.dataclass(frozen=True)
class _ContentLengthResult:
    """``code`` is ``None`` for an unambiguous, in-range length; otherwise the
    response code to send (``http_length_required`` or
    ``http_content_length_invalid``), and ``value`` stays ``None``."""

    code: str | None
    value: int | None = None


def _parse_content_length(headers) -> _ContentLengthResult:
    transfer_encoding = headers.get_all("Transfer-Encoding") or []
    content_lengths = headers.get_all("Content-Length") or []
    if transfer_encoding or not content_lengths:
        return _ContentLengthResult(code="http_length_required")
    single = len(content_lengths) == 1 and _CONTENT_LENGTH_PATTERN.fullmatch(content_lengths[0])
    if not single:
        return _ContentLengthResult(code="http_content_length_invalid")
    value = int(content_lengths[0])
    if value > _MAX_SAFE_INTEGER:
        return _ContentLengthResult(code="http_content_length_invalid")
    return _ContentLengthResult(code=None, value=value)


# --- The listener handler -------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    """Serves only ``POST /notification`` and ``GET /health``. No stdlib error
    path may echo a caller byte into a response, a log line or stderr (V14).
    """

    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self.rfile = io.BufferedReader(_DeadlineReader(self), _READ_BUFFER_BYTES)

    def handle_one_request(self) -> None:
        self.deadline = time.monotonic() + self.server.front_door._request_deadline
        super().handle_one_request()

    def log_message(self, format: str, *args: object) -> None:
        """Silenced: this also silences the stdlib's own ``log_error`` calls."""

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        # message/explain carry caller-derived text (probe c1b); never used.
        front_door_code = STDLIB_ERROR_CODES.get(code, "receiver_error")
        status = code if code in STDLIB_ERROR_CODES else 500
        self.server.front_door._metrics.bump_protocol_error(front_door_code)
        self._respond(status, front_door_code, close=True)

    # -- routing --

    def do_GET(self) -> None:
        self.close_connection = self.close_connection or self._has_unread_body()
        if self.path != "/health":
            self._respond(404, "not_found")
            return
        status, payload = self.server.front_door.health()
        self._respond_health(status, payload)

    def do_POST(self) -> None:
        if self.path != "/notification":
            self._respond(404, "not_found", close=self._has_unread_body())
            return
        front_door = self.server.front_door
        if not front_door._in_flight.acquire(blocking=False):
            front_door._metrics.bump("busy")
            self._respond(503, "busy", retry_after=BUSY_RETRY_AFTER_SECONDS, close=True)
            return
        front_door._metrics.gauge("in_flight", 1)
        failed_type = None
        try:
            self._handle_notification(front_door)
        except Exception as error:  # noqa: BLE001 - fixed response, never exception text.
            failed_type = type(error).__name__
        finally:
            front_door._metrics.gauge("in_flight", -1)
            front_door._in_flight.release()
        if failed_type is not None:
            self._respond_receiver_error(failed_type)

    def _has_unread_body(self) -> bool:
        lengths = self.headers.get_all("Content-Length") or []
        return bool(self.headers.get_all("Transfer-Encoding") or lengths not in ([], ["0"]))

    # -- POST /notification, step by step (see docs "Journaled HTTP contract") --

    def _handle_notification(self, front_door: JournaledReceiver) -> None:
        journal = front_door._journal
        if journal is None:
            self._respond(503, "journal_opening", retry_after=RETRY_AFTER_SECONDS, close=True)
            return
        state = journal.state
        if state != "ready":
            code = "journal_closed" if state == "closed" else "journal_held"
            self._respond(503, code, retry_after=RETRY_AFTER_SECONDS, close=True)
            return
        if front_door._spool.broken is not None:
            self._respond(503, "spool_broken", retry_after=RETRY_AFTER_SECONDS, close=True)
            return

        framing = _parse_content_length(self.headers)
        if framing.code == "http_length_required":
            front_door._metrics.bump("http_length_required")
            self._respond(411, framing.code, close=True)
            return
        if framing.code == "http_content_length_invalid":
            front_door._metrics.bump("http_content_length_invalid")
            self._respond(400, framing.code, close=True)
            return
        declared_length = framing.value

        if declared_length > MAX_INGRESS_BODY_BYTES:
            refusal = oversize_refusal(declared_length)
            front_door._record_refusal(journal, refusal_to_json(refusal))
            self._respond(413, "ingress_too_large", close=True)
            return

        body = self._read_body(declared_length)
        if body is None:
            front_door._metrics.bump("http_body_incomplete")
            self._respond(400, "http_body_incomplete", close=True)
            return

        outcome = sanitize_notification(body)
        if outcome.refusal is not None:
            front_door._record_refusal(journal, refusal_to_json(outcome.refusal))
            status = INGRESS_HTTP_STATUS[outcome.refusal.code]
            self._respond(status, outcome.refusal.code, close=False)
            return
        source = outcome.source

        precheck = journal.admission_precheck()
        if precheck is not None:
            front_door._metrics.bump_backpressure(precheck)
            self._respond(503, precheck, retry_after=RETRY_AFTER_SECONDS, close=False)
            return

        spool_code = None
        try:
            front_door._spool.store(body, source.body_digest)
        except SpoolError as error:
            spool_code = error.code
        if spool_code is not None:
            self._respond(503, spool_code, retry_after=RETRY_AFTER_SECONDS, close=False)
            return

        admit_code = None
        receipt = None
        try:
            receipt = journal.admit(source)
        except JournalError as error:
            admit_code = error.code
        if admit_code is not None:
            if admit_code == "source_invalid":
                self._respond(500, admit_code, close=False)
            else:
                self._respond(503, admit_code, retry_after=RETRY_AFTER_SECONDS, close=False)
            return

        if outcome.starts_at_dropped:
            front_door._metrics.bump("starts_at_dropped", len(outcome.starts_at_dropped))
        front_door._metrics.bump_admitted(receipt.result)
        self._respond_receipt(receipt)

    def _read_body(self, n: int) -> bytes | None:
        body = None
        try:
            body = self.rfile.read(n)
        except TimeoutError:
            body = None
        if body is not None and len(body) != n:
            body = None
        return body

    # -- responses: never a caller byte, never Server/traceback text --

    def _reset_write_timeout(self) -> None:
        # Responses are at most about 1 KiB; a near-zero read deadline must
        # not also cut short the write that follows it.
        try:
            self.connection.settimeout(self.server.front_door._request_deadline)
        except OSError:
            pass

    def _respond(
        self, status: int, code: str, *, retry_after: int | None = None, close: bool = False,
    ) -> None:
        self._reset_write_timeout()
        body = code.encode("ascii")
        self.close_connection = self.close_connection or close
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _respond_health(self, status: int, payload: dict) -> None:
        self._reset_write_timeout()
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _respond_receipt(self, receipt) -> None:
        payload = {
            "admission_id": receipt.admission_id, "arrival_seq": receipt.arrival_seq,
            "commit_seq": receipt.commit_seq, "decision": receipt.decision,
            "dispatch_holds": list(receipt.dispatch_holds), "result": receipt.result,
            "run": _RUN_STATUS,
        }
        self._reset_write_timeout()
        body = json.dumps(payload).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _respond_receiver_error(self, exc_type: str) -> None:
        logger.error("notification handling failed: %s", exc_type)
        self._respond(500, "receiver_error", close=True)


# --- The listener server: connection cap, silent error logging ----------------


class _Server(ThreadingHTTPServer):
    def __init__(
        self, server_address: tuple[str, int], handler_class: type[_Handler],
        front_door: JournaledReceiver, max_connections: int,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.front_door = front_door
        self._connection_semaphore = threading.Semaphore(max_connections)

    def process_request(self, request, client_address) -> None:
        if not self._connection_semaphore.acquire(blocking=False):
            self.front_door._metrics.bump("connections_refused")
            self.shutdown_request(request)
            return
        self.front_door._metrics.gauge("connections_open", 1)
        started = False
        try:
            super().process_request(request, client_address)
            started = True
        finally:
            if not started:
                self._release_connection_slot()

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release_connection_slot()

    def _release_connection_slot(self) -> None:
        self.front_door._metrics.gauge("connections_open", -1)
        self._connection_semaphore.release()

    def handle_error(self, request, client_address) -> None:
        exc_type = sys.exc_info()[0]
        logger.error(
            "front door connection error: %s", "unknown" if exc_type is None else exc_type.__name__
        )


# --- The front door ---------------------------------------------------------------


class JournaledReceiver:
    """The journaled front door: durable admission before the 202, and no Run."""

    def __init__(
        self, state_directory: Path, *, runs_directory: Path = DEFAULT_RUNS_DIRECTORY,
        host: str = DEFAULT_HOST, port: int = 0, resume: ResumeRequest | None = None,
        max_in_flight: int = MAX_IN_FLIGHT, max_connections: int = MAX_CONNECTIONS,
        request_deadline: float = REQUEST_DEADLINE_SECONDS,
        spool_max_bytes: int = MAX_SPOOL_BYTES, spool_max_entries: int = MAX_SPOOL_ENTRIES,
        wall_clock=time.time_ns, mono_clock=time.monotonic_ns, id_factory=new_id,
    ) -> None:
        _check_front_door_arguments(
            state_directory, runs_directory, host, port, max_in_flight, max_connections,
            request_deadline, spool_max_bytes, spool_max_entries,
        )
        state_directory = Path(state_directory)
        runs_directory = Path(runs_directory)
        _check_state_directory(state_directory)
        _check_placement(state_directory, runs_directory)

        self._state_directory = state_directory
        self._runs_directory = runs_directory
        self._resume = resume
        self._request_deadline = request_deadline
        self._spool_max_bytes = spool_max_bytes
        self._spool_max_entries = spool_max_entries
        self._wall_clock = wall_clock
        self._mono_clock = mono_clock
        self._id_factory = id_factory
        self._host = host
        self._metrics = _Metrics()
        self._in_flight = threading.Semaphore(max_in_flight)
        self._journal: RecoveryJournal | None = None
        self._spool: JournalSpool | None = None
        self._http_thread: threading.Thread | None = None

        code = None
        server = None
        try:
            server = _Server((host, port), _Handler, self, max_connections)
        except OSError:
            code = "listener_bind_failed"
        if code is not None:
            raise FrontDoorError(code) from None
        self._server = server

    @property
    def url(self) -> str:
        port = self._server.server_address[1]
        return f"http://{self._host}:{port}"

    @property
    def journal(self) -> RecoveryJournal | None:
        return self._journal

    def start(self) -> None:
        """Bind already happened at construction. Serve 503 ``journal_opening``
        until the spool and journal are open, then admit."""
        self._http_thread = threading.Thread(
            target=self._server.serve_forever, args=(_SHUTDOWN_POLL_INTERVAL,),
            name="journaled-receiver-http", daemon=True,
        )
        self._http_thread.start()
        opened = False
        try:
            self._spool = JournalSpool.open(
                self._state_directory / "spool",
                max_bytes=self._spool_max_bytes, max_entries=self._spool_max_entries,
            )
            self._journal = open_recovery_journal(
                self._state_directory / "journal", wall_clock=self._wall_clock,
                mono_clock=self._mono_clock, id_factory=self._id_factory, resume=self._resume,
            )
            opened = True
        finally:
            if not opened:
                self._shutdown_listener()
        if self._resume is not None and self._journal.resumed_this_boot is None:
            # The held open already did exactly what an open without resume does.
            self._shutdown_listener()
            self._journal.close()
            self._journal = None
            raise FrontDoorError("resume_not_applied")

    def _shutdown_listener(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._http_thread is not None:
            self._http_thread.join(timeout=5)

    def stop(self) -> None:
        self._shutdown_listener()
        if self._journal is not None:
            self._journal.close()

    def _record_refusal(self, journal: RecoveryJournal, summary: dict) -> None:
        """A 4xx needs no durable record to be sent. If the journal cannot
        record it (held, or a write fault that latches), the code is logged
        and counted ``unrecorded``; the refusal's class is still sent.
        """
        unrecorded_code = None
        try:
            journal.record_refusal(summary)
        except JournalError as error:
            unrecorded_code = error.code
        if unrecorded_code is not None:
            logger.warning("ingress refusal not recorded: %s", unrecorded_code)
            self._metrics.bump_unrecorded_refusal(summary["code"])

    def health(self) -> tuple[int, dict[str, object]]:
        journal = self._journal
        if journal is None:
            journal_json = {
                "state": "opening", "hold": None, "dispatch_holds": None,
                "head_commit_seq": None, "admissions": None, "pending_fingerprints": None,
            }
            refusals_recorded = None
            refusals_limit, refusals_reserve = _REFUSAL_LIMIT, _REFUSAL_RESERVE
            this_boot: dict[str, dict[str, int]] = {}
            resume_state = "not_requested"
        else:
            snapshot = journal.snapshot()
            hold = None
            if snapshot["hold"] is not None:
                hold = {
                    "code": snapshot["hold"]["code"], "scope": snapshot["hold"]["scope"],
                    "persisted": snapshot["hold"]["persisted"],
                }
            dispatch_holds = (
                None if snapshot["dispatch_holds"] is None
                else [entry["code"] for entry in snapshot["dispatch_holds"]]
            )
            head_commit_seq = None if snapshot["head"] is None else snapshot["head"]["commit_seq"]
            admissions = None if snapshot["counts"] is None else snapshot["counts"]["admissions"]
            pending_fingerprints = (
                None if snapshot["counts"] is None
                else snapshot["counts"]["pending_fingerprints"]
            )
            journal_json = {
                "state": snapshot["state"], "hold": hold, "dispatch_holds": dispatch_holds,
                "head_commit_seq": head_commit_seq, "admissions": admissions,
                "pending_fingerprints": pending_fingerprints,
            }
            status = journal.front_door_status()
            refusals_recorded = status["refusals"]["recorded"]
            refusals_limit = status["refusals"]["limit"]
            refusals_reserve = status["refusals"]["reserve"]
            this_boot = {
                code: dict(counts) for code, counts in status["refusals"]["this_boot"].items()
            }
            resume_state = status["resume"]["this_boot"]

        for code, count in self._metrics.unrecorded_refusals().items():
            bucket = this_boot.setdefault(code, {})
            bucket["unrecorded"] = bucket.get("unrecorded", 0) + count

        spool = self._spool
        if spool is None:
            spool_json = {
                "state": "ok", "code": None, "bytes": 0, "max_bytes": self._spool_max_bytes,
                "entries": 0, "max_entries": self._spool_max_entries, "written_this_boot": 0,
                "full_refusals_this_boot": 0,
            }
        else:
            spool_json = spool.status()

        ready = journal_json["state"] == "ready" and spool_json["state"] != "broken"
        payload = {
            "mode": MODE, "runs": _RUN_STATUS, "journal": journal_json,
            "resume": {"this_boot": resume_state},
            "refusals": {
                "recorded": refusals_recorded, "limit": refusals_limit, "reserve": refusals_reserve,
                "this_boot": this_boot,
            },
            "http": self._metrics.snapshot(), "spool": spool_json,
        }
        return (200 if ready else 503), payload


# --- Command line ---------------------------------------------------------------


def _print_start_refusal(code: str) -> None:
    print(f"refused to start: {code}", file=sys.stderr, flush=True)
    if code in {"state_missing", "journal_missing", "spool_missing"}:
        hint = "For explicit setup use journal_operator create --state-dir NEW_STATE."
    else:
        hint = "Stop and inspect the state before retrying; preserve any damaged files."
    print(hint, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve the journaled, admission-only front door for one state directory."
    )
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--runs-directory", default=str(DEFAULT_RUNS_DIRECTORY))
    parser.add_argument("--resume-token")
    parser.add_argument("--operator")
    parser.add_argument("--reason", default="restart-inspected")
    arguments = parser.parse_args(argv)

    if arguments.resume_token is not None and arguments.operator is None:
        print("--resume-token requires --operator", file=sys.stderr, flush=True)
        return 2

    resume = None
    if arguments.resume_token is not None:
        resume = ResumeRequest(
            token=arguments.resume_token, operator=arguments.operator, reason=arguments.reason,
        )

    state_directory = Path(arguments.state_dir)
    runs_directory = Path(arguments.runs_directory).resolve()
    # Flushed: an operator watching this through a pipe or a log collector
    # needs these lines promptly, not once stdout's block buffer fills.
    print(f"state directory: {state_directory.resolve()}", flush=True)
    print(f"runs directory: {runs_directory}", flush=True)

    receiver = None
    code = None
    try:
        receiver = JournaledReceiver(
            state_directory, runs_directory=runs_directory, host=arguments.host,
            port=arguments.port, resume=resume,
        )
    except FrontDoorError as error:
        code = error.code
    if code is not None:
        _print_start_refusal(code)
        return 1

    started = False
    try:
        receiver.start()
        started = True
    except (FrontDoorError, JournalError, SpoolError) as error:
        code = error.code
    if not started:
        _print_start_refusal(code)
        return 1

    print(
        "journaled admission-only mode: Notifications are recorded durably; no Run is started",
        flush=True,
    )
    if "restart_recovery" in (receiver.health()[1]["journal"]["dispatch_holds"] or []):
        print(
            "dispatch held: restart_recovery (inspect, then restart with --resume-token)",
            flush=True,
        )
    print(f"listening on {receiver.url}", flush=True)
    stop_event = threading.Event()
    try:
        while not stop_event.wait(timeout=1.0):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
    return 0


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_RUNS_DIRECTORY",
    "FRONT_DOOR_CODES",
    "HTTP_CODES",
    "MAX_CONNECTIONS",
    "MAX_IN_FLIGHT",
    "MODE",
    "REQUEST_DEADLINE_SECONDS",
    "STDLIB_ERROR_CODES",
    "FrontDoorError",
    "JournaledReceiver",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
