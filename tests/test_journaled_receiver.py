"""HTTP tests for the journaled admission-only front door (ticket 37, unit
17b; Tester T2a, cases H1-H20 with H7b, H9b, H11b and H14b).

Reconciled against the landed ``grafana_jsm_sandbox.journal_spool``,
``journaled_receiver`` and ``journal_operator`` modules and the implementation
plan's HTTP contract (``reviews/receiver-journal/implementation-plan.md``).
One spot patches an implementation detail the plan itself does not name (the
stdlib method the handler class leaves unoverridden); confirmed against the
landed source and marked below.

Real sockets on ephemeral ports throughout, no fixed ports, no sleeps for
synchronisation (a 5 s bound only ever catches a hang, per "Ownership and
validation"). The admission-only mode pins (H1's runs/``Popen`` checks, H19's
``mode``/``runs`` fields, H20's ``run`` value) live in their own
``test_admission_only_mode_*`` functions, per critic 7 and U17-P18, so the
run-lifecycle unit can supersede exactly that set by name.
"""

from __future__ import annotations

import http.client
import http.server
import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_reducer as jrd
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import journaled_receiver as jrecv
from grafana_jsm_sandbox import recovery_journal as rj
from grafana_jsm_sandbox.journal_operator import create_state
from grafana_jsm_sandbox.journaled_receiver import FrontDoorError, JournaledReceiver
from grafana_jsm_sandbox.recovery_journal import ResumeRequest
from grafana_jsm_sandbox.replay import replay
from tests.conftest import FIXTURES, get_health, http_request, post_notification
from tests.test_recovery_journal_crash import (
    commit_groups,
    flip_byte_in_group,
    open_held,
    wal_frames,
)

_STATE_SUBDIR = "S"
_RUNS_SUBDIR = "runs"
_JOURNAL_SUBDIR = "journal"
_SPOOL_SUBDIR = "spool"

_DATA_CANARY = "h15-canary with spaces ☃"
_TOKEN_CANARY = "h15CANARYtoken"  # header/method/version safe: no CR, LF, colon or space


def _default_state_dir(tmp_path: Path) -> Path:
    return tmp_path / _STATE_SUBDIR


# === Body builders ============================================================


def _valid_body(fingerprint: str, *, status: str = "firing", group_key: str | None = None) -> bytes:
    payload = {
        "groupKey": group_key or f'{{}}:{{alertname="{fingerprint}"}}',
        "alerts": [{"fingerprint": fingerprint, "status": status}],
        # Grafana always sends this (the real fixtures do too); without it
        # `truncated_alerts` stays None, `complete` is never true, and a
        # byte-identical resend can never dedupe as "suppressed".
        "truncatedAlerts": 0,
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _many_alerts_body(
    group_key: str, total: int, resolved: int, *, extra: dict | None = None,
) -> bytes:
    """A raw Grafana-shaped webhook body with ``total`` alerts, the first
    ``resolved`` of them Resolved and the rest Firing."""
    alerts = [
        {"fingerprint": f"h6alert{i:03d}", "status": "resolved" if i < resolved else "firing"}
        for i in range(total)
    ]
    payload = {"groupKey": group_key, "alerts": alerts}
    if extra:
        payload.update(extra)
    return json.dumps(payload, sort_keys=True).encode("utf-8")


# === Raw socket / HTTP helpers =================================================


def _address(front_door: JournaledReceiver) -> tuple[str, int]:
    site = urlsplit(front_door.url)
    return site.hostname, site.port


def _raw_socket(front_door: JournaledReceiver, *, timeout: float = 5.0) -> socket.socket:
    return socket.create_connection(_address(front_door), timeout=timeout)


def _raw_request(
    method: str, target: str, headers: list[tuple[str, str]], body: bytes = b"",
) -> bytes:
    lines = [f"{method} {target} HTTP/1.1"]
    lines.extend(f"{name}: {value}" for name, value in headers)
    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8", errors="surrogateescape") + body


def _exchange(sock: socket.socket, raw: bytes) -> tuple[int, dict[str, str], bytes]:
    """Send one well-formed request and parse its status line, headers and body."""
    sock.sendall(raw)
    response = http.client.HTTPResponse(sock)
    response.begin()
    return response.status, dict(response.getheaders()), response.read()


def _recv_all(sock: socket.socket, *, timeout: float = 5.0) -> bytes:
    """Every byte `sock` sends before it closes, bounded by `timeout`."""
    sock.settimeout(timeout)
    chunks = []
    try:
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError:
        pass
    return b"".join(chunks)


def _header(headers: dict[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


# === Polling (no sleeps for synchronisation; a 5 s hang bound only) ===========


def _poll(get_value, *, timeout: float = 5.0, interval: float = 0.02):
    deadline = time.monotonic() + timeout
    value = None
    while time.monotonic() < deadline:
        value = get_value()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s; last value={value!r}")


def _poll_health(front_door: JournaledReceiver, predicate, *, timeout: float = 5.0):
    def check():
        status, body = front_door.health()
        return (status, body) if predicate(body) else None

    return _poll(check, timeout=timeout)


# === Filesystem snapshots =======================================================


def _file_snapshot(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir()) if path.is_file()}


def _spool_files(state_directory: Path) -> dict[str, bytes]:
    return _file_snapshot(state_directory / _SPOOL_SUBDIR)


# === A persisted `journal_truncated` hold with no WAL (H7b; K6's
# `persisted_hold_no_wal`) ======================================================


def _persist_truncation_then_drop_wal(journal_directory: Path) -> None:
    """One real open commits `restart_recovery`; flipping a byte in that
    commit's WAL frame turns the next open into a lost-tail
    `journal_truncated` finding, because the append that wrote it already
    advanced the durable anchor past it. That open persists the finding;
    only then is the WAL removed, leaving a full-size DB the WAL pre-check
    cannot see past."""
    rj.open_recovery_journal(journal_directory).close()
    wal_path = journal_directory / journal_store.WAL_FILENAME
    wal_bytes = wal_path.read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path.write_bytes(flip_byte_in_group(wal_bytes, groups[-1]))
    open_held(journal_directory).close()
    wal_path.unlink()


def _flaky_wall_clock(*, fail_after: int):
    """A real wall clock that raises starting from its `fail_after + 1`-th call."""
    calls = {"n": 0}

    def wall_clock() -> int:
        calls["n"] += 1
        if calls["n"] > fail_after:
            raise RuntimeError("no canary")
        return time.time_ns()

    return wall_clock


def _drive_to_capacity_admissions(receiver: JournaledReceiver) -> bytes:
    """Two distinct admissions, then a third whose refusal first writes the
    durable `capacity_admissions` dispatch hold; returns that third body."""
    for index in range(2):
        assert post_notification(receiver, _valid_body(f"cap-{index}")).status == 202
    third_body = _valid_body("cap-2")
    response = post_notification(receiver, third_body)
    assert response.status == 503
    assert response.body.decode() == "capacity_admissions"
    return third_body


_CAPACITY_TWO_BOUNDS = jrd.JournalBounds(
    max_admissions=2, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
    total_bytes=128 * 2**20,
)


# === Fixtures ====================================================================


@pytest.mark.parametrize("method,target", [("POST", "/other"), ("GET", "/health")])
def test_h13_unread_body_closes_connection(front_door, method, target):
    with _raw_socket(front_door) as sock:
        status, headers, _body = _exchange(sock, _raw_request(
            method, target, [("Host", "localhost"), ("Content-Length", "4")], b"DATA",
        ))
        assert status == (404 if method == "POST" else 200)
        assert _header(headers, "Connection") == "close"


@pytest.mark.parametrize("kind", ["health", "receipt", "refusal"])
def test_h13_explicit_connection_close_is_honored(front_door, kind):
    body = b"" if kind == "health" else (
        _valid_body("close") if kind == "receipt" else b"not-json"
    )
    with _raw_socket(front_door) as sock:
        status, headers, _body = _exchange(sock, _raw_request(
            "GET" if kind == "health" else "POST",
            "/health" if kind == "health" else "/notification",
            [("Host", "localhost"), ("Connection", "close"),
             ("Content-Length", str(len(body)))], body,
        ))
        assert status == {"health": 200, "receipt": 202, "refusal": 400}[kind]
        assert _header(headers, "Connection") == "close"
        assert sock.recv(1) == b""


def test_h13_consumed_refusal_keeps_connection_usable(front_door):
    with _raw_socket(front_door) as sock:
        status, headers, _body = _exchange(sock, _raw_request(
            "POST", "/notification", [("Host", "localhost"), ("Content-Length", "3")], b"bad",
        ))
        assert status == 400
        assert _header(headers, "Connection") is None
        assert _exchange(sock, _raw_request("GET", "/health", [("Host", "localhost")]))[0] == 200


def test_h15_unexpected_exception_logs_type_only(front_door, monkeypatch, caplog):
    def failed(_body):
        raise ValueError(_DATA_CANARY)

    monkeypatch.setattr(jrecv, "sanitize_notification", failed)
    assert post_notification(front_door, _valid_body("exception-type")).status == 500
    assert "notification handling failed: ValueError" in caplog.text
    assert _DATA_CANARY not in caplog.text


@pytest.mark.parametrize("kind", ["invalid", "members", "oversize"])
def test_h5_failed_refusal_record_preserves_class_and_counts_unrecorded(
    front_door, monkeypatch, caplog, kind,
):
    bodies = {
        "invalid": b"bad",
        "members": _many_alerts_body('{}:{alertname="refused"}', 33, 1),
        "oversize": b"",
    }
    expected = {
        "invalid": (400, "ingress_json_invalid"),
        "members": (422, "ingress_too_many_alerts"),
        "oversize": (413, "ingress_too_large"),
    }
    before = front_door.journal.snapshot()["head"]

    def fail_record(_self, _summary):
        raise rj.JournalError("journal_write_failed")

    monkeypatch.setattr(rj.RecoveryJournal, "record_refusal", fail_record)
    body = bodies[kind]
    length = 300_000 if kind == "oversize" else len(body)
    with _raw_socket(front_door) as sock:
        status, _headers, response = _exchange(sock, _raw_request(
            "POST", "/notification", [("Host", "localhost"), ("Content-Length", str(length))],
            body,
        ))
    status_expected, code = expected[kind]
    assert (status, response.decode()) == (status_expected, code)
    assert front_door.health()[1]["refusals"]["this_boot"][code]["unrecorded"] == 1
    assert front_door.journal.snapshot()["head"] == before
    assert front_door.health()[1]["spool"]["entries"] == 0
    assert "ingress refusal not recorded: journal_write_failed" in caplog.text


@pytest.fixture
def start_front_door(tmp_path):
    """Factory: `create_state` (unless `directory` already exists) and start
    a `JournaledReceiver` on an ephemeral port. Every receiver it starts is
    stopped at teardown, harmlessly even if the test already stopped it."""
    started: list[JournaledReceiver] = []

    def start(
        directory: Path | None = None, *, bounds=None, **receiver_kwargs,
    ) -> JournaledReceiver:
        target = directory if directory is not None else _default_state_dir(tmp_path)
        if not target.exists():
            create_state(target, **({"bounds": bounds} if bounds is not None else {}))
        receiver = JournaledReceiver(
            target, runs_directory=tmp_path / _RUNS_SUBDIR, port=0, **receiver_kwargs,
        )
        receiver.start()
        real_stop, done = receiver.stop, False

        def stop_once() -> None:
            nonlocal done
            if not done:
                done = True
                real_stop()

        receiver.stop = stop_once
        started.append(receiver)
        return receiver

    yield start
    for receiver in started:
        receiver.stop()


@pytest.fixture
def front_door(start_front_door) -> JournaledReceiver:
    """A ready `JournaledReceiver` over a fresh state directory, default
    bounds, stopped at teardown."""
    return start_front_door()


# === H1 =========================================================================


def test_h1_replay_admits_durably_and_resolves_pending(front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    statuses = replay(front_door.url, pause=0)
    assert statuses == [202, 202, 202]

    firing = (FIXTURES / "notification-firing.json").read_bytes()
    resolved = (FIXTURES / "notification-resolved.json").read_bytes()
    spool_files = _spool_files(directory)
    assert set(spool_files) == {ji.body_digest(firing), ji.body_digest(resolved)}
    assert spool_files[ji.body_digest(firing)] == firing
    assert spool_files[ji.body_digest(resolved)] == resolved

    snapshot = front_door.journal.snapshot()
    # Every admit() call advances the count, suppressed repeats included (runbook
    # "Capacity is per generation": suppressed repeats count toward admissions).
    assert snapshot["counts"]["admissions"] == 3
    assert any(hold["code"] == "restart_recovery" for hold in snapshot["dispatch_holds"])

    # The group's current baseline (the resolved fixture) posted again, live: an
    # idempotent held-decision receipt (V1, V17). Re-posting `firing` here would
    # not be a repeat of the *latest* record for this group (the group's last
    # commit was the resolved fixture), so it would supersede, not suppress.
    repeat_receipt = json.loads(post_notification(front_door, resolved).body)
    assert repeat_receipt["decision"] == "held"
    assert repeat_receipt["result"] == "suppressed"

    front_door.stop()
    inspection = rj.inspect_recovery_journal(directory / _JOURNAL_SUBDIR)
    pending = {entry["fingerprint"]: entry for entry in inspection.report["pending"]}
    assert pending["87e2f184874a3b71"]["status"] == "resolved"


def test_admission_only_mode_h1_no_run_directory_and_no_popen(front_door, tmp_path, monkeypatch):
    def _raising_popen(*args, **kwargs):
        raise AssertionError("subprocess.Popen must never run in admission-only mode")

    monkeypatch.setattr(subprocess, "Popen", _raising_popen)
    statuses = replay(front_door.url, pause=0)
    assert statuses == [202, 202, 202]
    assert not (tmp_path / _RUNS_SUBDIR).exists()


# === H2 =========================================================================


def test_h2_spool_entry_exists_before_the_admission_commit(front_door, tmp_path, monkeypatch):
    directory = _default_state_dir(tmp_path)
    body = _valid_body("h2")
    digest = ji.body_digest(body)
    spool_path = directory / _SPOOL_SUBDIR / digest
    seen_at_commit: list[bool] = []
    real_append = journal_store.JournalStore.append

    def spying_append(self, records, **kwargs):
        seen_at_commit.append(spool_path.exists() and spool_path.read_bytes() == body)
        return real_append(self, records, **kwargs)

    monkeypatch.setattr(journal_store.JournalStore, "append", spying_append)
    response = post_notification(front_door, body)
    assert response.status == 202
    assert seen_at_commit and all(seen_at_commit)  # V2, V17: spooled before the commit

    front_door.stop()
    inspection = rj.inspect_recovery_journal(directory / _JOURNAL_SUBDIR)
    assert digest in inspection.references


# === H3 =========================================================================


def test_h3_resume_at_open_clears_the_hold_and_a_bare_restart_re_holds(start_front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    first = start_front_door(directory)
    assert post_notification(first, _valid_body("h3-a")).status == 202
    first.stop()

    inspection = rj.inspect_recovery_journal(directory / _JOURNAL_SUBDIR)
    token = inspection.report["resume"]["token"]

    second = start_front_door(directory, resume=ResumeRequest(token=token, operator="h3-operator"))
    _, body = second.health()
    assert body["resume"]["this_boot"] == "resumed"
    # health's `journal.dispatch_holds` is a list of bare codes, not `snapshot()`'s
    # list of {"code", "since_commit_seq"} dicts.
    assert body["journal"]["dispatch_holds"] == []

    receipt = json.loads(post_notification(second, _valid_body("h3-b")).body)
    assert receipt["decision"] == "admitted"
    second.stop()

    third = start_front_door(directory)
    _, body = third.health()
    assert "restart_recovery" in body["journal"]["dispatch_holds"]


# === H4 =========================================================================


def test_h4_stale_token_raises_resume_stale_and_writes_nothing(start_front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    create_state(directory)
    stale_token = rj.inspect_recovery_journal(directory / _JOURNAL_SUBDIR).report["resume"]["token"]

    plain = start_front_door(directory)
    assert post_notification(plain, _valid_body("h4")).status == 202
    plain.stop()

    before = _file_snapshot(directory / _JOURNAL_SUBDIR)
    with pytest.raises(rj.JournalError) as excinfo:
        start_front_door(directory, resume=ResumeRequest(token=stale_token, operator="h4-operator"))
    assert excinfo.value.code == "resume_stale"
    after = _file_snapshot(directory / _JOURNAL_SUBDIR)
    assert after == before


# === H5 =========================================================================

_H5_GROUP_KEY = '{}:{alertname="h5-refusals"}'


def test_h5_refusals_over_http_get_their_mapped_status_and_code_body(
    front_door, tmp_path, monkeypatch,
):
    not_json = b"not json"
    outcome = ji.sanitize_notification(not_json)
    response = post_notification(front_door, not_json)
    assert response.status == 400
    assert response.body.decode() == outcome.refusal.code == "ingress_json_invalid"

    many_body = _many_alerts_body(_H5_GROUP_KEY, 33, 1)
    many_outcome = ji.sanitize_notification(many_body)
    response = post_notification(front_door, many_body)
    assert response.status == 422
    assert response.body.decode() == many_outcome.refusal.code == "ingress_too_many_alerts"

    non_ascii_body = json.dumps({
        "groupKey": "h5-é-group", "alerts": [{"fingerprint": "h5-x", "status": "firing"}],
    }).encode("utf-8")
    non_ascii_outcome = ji.sanitize_notification(non_ascii_body)
    response = post_notification(front_door, non_ascii_body)
    assert response.status == ji.INGRESS_HTTP_STATUS[non_ascii_outcome.refusal.code] == 422
    assert response.body.decode() == non_ascii_outcome.refusal.code

    sock = _raw_socket(front_door)
    try:
        raw = b"POST /notification HTTP/1.1\r\nHost: x\r\nContent-Length: 300000\r\n\r\n"
        status, headers, body = _exchange(sock, raw)
        assert status == 413
        assert body.decode() == "ingress_too_large"
        assert _header(headers, "Connection") == "close"
    finally:
        sock.close()

    def _divergent_sanitize(_body: bytes) -> ji.IngressOutcome:
        refusal = ji.IngressRefusal(
            code="ingress_divergence", body_bytes=len(_body), body_digest=ji.body_digest(_body),
            source_group=None, refused_group=None, alerts=None, resolved=None, members=(),
            members_omitted=0,
        )
        return ji.IngressOutcome(source=None, refusal=refusal, starts_at_dropped=())

    monkeypatch.setattr(jrecv, "sanitize_notification", _divergent_sanitize)
    response = post_notification(front_door, b"anything")
    assert response.status == 500
    assert response.body.decode() == "ingress_divergence"
    monkeypatch.undo()  # the real sanitizer is needed again below

    _, health_before = front_door.health()
    before_counts = dict(health_before["refusals"]["this_boot"].get("ingress_too_many_alerts", {}))
    re_render = _many_alerts_body(_H5_GROUP_KEY, 33, 1, extra={"message": "a different render"})
    assert post_notification(front_door, re_render).status == 422  # coalesced: same key
    two_resolved = _many_alerts_body(_H5_GROUP_KEY, 33, 2)
    assert post_notification(front_door, two_resolved).status == 422  # a new key: resolved changed

    _, health_after = front_door.health()
    after_counts = health_after["refusals"]["this_boot"]["ingress_too_many_alerts"]
    assert after_counts["coalesced"] == before_counts.get("coalesced", 0) + 1  # the re-render
    assert after_counts["recorded"] == before_counts.get("recorded", 0) + 1  # the new key

    front_door.stop()
    inspection = rj.inspect_recovery_journal(_default_state_dir(tmp_path) / _JOURNAL_SUBDIR)
    for entry in inspection.report["refusals"]["recent"]:
        resolved_first = [member[1] == "resolved" for member in entry["summary"]["members"]]
        assert resolved_first == sorted(resolved_first, reverse=True)


# === H6 =========================================================================

_H6_FRAMING_CASES = [
    ("chunked_without_length", [("Transfer-Encoding", "chunked")], 411, "http_length_required"),
    ("no_content_length", [], 411, "http_length_required"),
    ("length_and_chunked", [("Content-Length", "4"), ("Transfer-Encoding", "chunked")],
     411, "http_length_required"),
    ("duplicate_length", [("Content-Length", "4"), ("Content-Length", "4")],
     400, "http_content_length_invalid"),
    ("non_numeric_length", [("Content-Length", "12a")], 400, "http_content_length_invalid"),
    ("negative_length", [("Content-Length", "-1")], 400, "http_content_length_invalid"),
    ("seventeen_digit_length", [("Content-Length", "12345678901234567")],
     400, "http_content_length_invalid"),
    ("length_at_two_pow_53", [("Content-Length", "9007199254740992")],
     400, "http_content_length_invalid"),
]


@pytest.mark.parametrize(
    "case_id, extra_headers, expected_status, expected_code", _H6_FRAMING_CASES,
)
def test_h6_framing_defects_on_raw_sockets(
    front_door, case_id, extra_headers, expected_status, expected_code,
):
    before = front_door.journal.snapshot()["head"]
    sock = _raw_socket(front_door)
    try:
        raw = _raw_request("POST", "/notification", [("Host", "x"), *extra_headers])
        status, headers, body = _exchange(sock, raw)
        assert status == expected_status, case_id
        assert body.decode() == expected_code, case_id
        connection = _header(headers, "Connection")
        if connection is not None:
            assert connection == "close", case_id
    finally:
        sock.close()
    assert front_door.journal.snapshot()["head"] == before


# === H7 / H7b ====================================================================


def test_h7_held_at_start_from_a_missing_database(start_front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    create_state(directory)
    journal_dir = directory / _JOURNAL_SUBDIR
    (journal_dir / journal_store.WAL_FILENAME).unlink(missing_ok=True)
    (journal_dir / journal_store.DB_FILENAME).unlink()

    receiver = start_front_door(directory)
    sock = _raw_socket(receiver)
    try:
        raw = _raw_request("POST", "/notification", [("Host", "x"), ("Content-Length", "2611")])
        status, headers, body = _exchange(sock, raw)
        assert status == 503
        assert body.decode() == "journal_held"
        assert _header(headers, "Retry-After") == "10"
    finally:
        sock.close()

    status, health_body = receiver.health()
    assert status == 503
    assert health_body["journal"]["hold"] == {
        "code": "journal_truncated", "scope": "recovery", "persisted": True,
    }
    assert not any((directory / _SPOOL_SUBDIR).iterdir())


@pytest.mark.skipif(sys.platform != "darwin", reason="no-read full-body 503 qualified on Darwin only")
def test_h7_held_journal_refuses_full_fixture_body(start_front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    create_state(directory)
    (directory / _JOURNAL_SUBDIR / journal_store.WAL_FILENAME).unlink(missing_ok=True)
    (directory / _JOURNAL_SUBDIR / journal_store.DB_FILENAME).unlink()
    receiver = start_front_door(directory)
    response = post_notification(receiver, (FIXTURES / "notification-firing.json").read_bytes())
    assert response.status == 503
    assert response.body == b"journal_held"
    assert _header(response.headers, "Retry-After") == "10"
    assert not any((directory / _SPOOL_SUBDIR).iterdir())


@pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE "
    "(Python >= 3.12)",
)
def test_h7b_persisted_truncation_without_a_wal_starts_held(start_front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    create_state(directory)
    journal_dir = directory / _JOURNAL_SUBDIR
    _persist_truncation_then_drop_wal(journal_dir)
    # The runbook's point: inspect alone cannot resolve this image (critic 9).
    assert rj.inspect_recovery_journal(journal_dir).report["verdict"] == "unverified"

    receiver = start_front_door(directory)
    status, body = receiver.health()
    assert status == 503
    assert body["journal"]["hold"]["code"] == "journal_truncated"
    assert body["journal"]["hold"]["persisted"] is True
    assert not (journal_dir / journal_store.WAL_FILENAME).exists()


# === H8 =========================================================================


def test_h8_wall_clock_fault_latches_then_holds(start_front_door):
    receiver = start_front_door(wall_clock=_flaky_wall_clock(fail_after=1))
    first = post_notification(receiver, _valid_body("h8-a"))
    assert first.status == 503
    assert first.body.decode() == "journal_clock_invalid"

    second = post_notification(receiver, _valid_body("h8-b"))
    assert second.status == 503
    assert second.body.decode() == "journal_held"

    status, body = receiver.health()
    assert status == 503
    assert body["journal"]["hold"]["code"] == "journal_clock_invalid"


# === H9 / H9b ====================================================================


def test_h9_third_distinct_body_hits_capacity_admissions(start_front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    receiver = start_front_door(directory, bounds=_CAPACITY_TWO_BOUNDS)
    third_body = _drive_to_capacity_admissions(receiver)

    response = post_notification(receiver, third_body)
    assert response.status == 503
    assert _header(response.headers, "Retry-After") == "10"

    holds = {hold["code"] for hold in receiver.journal.snapshot()["dispatch_holds"]}
    assert "capacity_admissions" in holds

    digest = ji.body_digest(third_body)
    spool_path = directory / _SPOOL_SUBDIR / digest
    assert spool_path.exists()
    assert spool_path.read_bytes() == third_body

    receiver.stop()
    inspection = rj.inspect_recovery_journal(directory / _JOURNAL_SUBDIR)
    assert digest not in inspection.references  # spooled, never admitted: an orphan


def test_h9b_further_posts_after_capacity_are_refused_without_spooling(start_front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    receiver = start_front_door(directory, bounds=_CAPACITY_TWO_BOUNDS)
    _drive_to_capacity_admissions(receiver)

    spool_before = _spool_files(directory)
    head_before = receiver.journal.snapshot()["head"]
    _, health_before = receiver.health()
    backpressure_before = health_before["http"]["backpressure"].get("capacity_admissions", 0)

    fourth = _valid_body("cap-3")
    repeat_third = _valid_body("cap-2")
    for body in (fourth, repeat_third):
        response = post_notification(receiver, body)
        assert response.status == 503
        assert response.body.decode() == "capacity_admissions"
        assert _header(response.headers, "Retry-After") == "10"

    assert _spool_files(directory) == spool_before  # V24: nothing new spooled
    assert receiver.journal.snapshot()["head"] == head_before
    _, health_after = receiver.health()
    assert health_after["http"]["backpressure"]["capacity_admissions"] == backpressure_before + 2

    receiver.stop()
    inspection = rj.inspect_recovery_journal(directory / _JOURNAL_SUBDIR)
    orphans = [name for name in _spool_files(directory) if name not in inspection.references]
    assert len(orphans) == 1


# === H10 ========================================================================


def test_h10_spool_sync_failure_then_broken(front_door, monkeypatch):
    from grafana_jsm_sandbox import journal_spool as jspool

    head_before = front_door.journal.snapshot()["head"]

    def failing_full_sync(fd: int) -> None:
        raise OSError("no canary")

    monkeypatch.setattr(jspool, "full_sync", failing_full_sync)
    first = post_notification(front_door, _valid_body("h10-a"))
    assert first.status == 503
    assert first.body.decode() == "spool_write_failed"

    second = post_notification(front_door, _valid_body("h10-b"))
    assert second.status == 503
    assert second.body.decode() == "spool_broken"

    status, body = front_door.health()
    assert status == 503
    assert body["spool"]["state"] == "broken"
    assert body["spool"]["code"] == "spool_write_failed"
    assert front_door.journal.snapshot()["head"] == head_before


# === H11 / H11b ==================================================================


def test_h11_busy_when_the_in_flight_cap_is_reached(start_front_door):
    receiver = start_front_door(max_in_flight=1, request_deadline=30.0)
    body = _valid_body("h11")
    stalling = _raw_socket(receiver, timeout=10.0)
    try:
        header = f"POST /notification HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n\r\n"
        stalling.sendall(header.encode() + body[: len(body) // 2])
        _poll_health(receiver, lambda b: b["http"]["in_flight"] == 1)

        response = post_notification(receiver, _valid_body("h11-second"))
        assert response.status == 503
        assert response.body.decode() == "busy"
        assert _header(response.headers, "Retry-After") == "1"

        status, _ = receiver.health()
        assert status == 200
    finally:
        stalling.close()


def test_h11b_connection_cap_refuses_the_excess_at_accept(start_front_door):
    receiver = start_front_door(max_connections=2, request_deadline=30.0)
    baseline_threads = threading.active_count()
    first = _raw_socket(receiver, timeout=10.0)
    second = _raw_socket(receiver, timeout=10.0)
    try:
        _poll_health(receiver, lambda b: b["http"]["connections_open"] == 2)

        third = _raw_socket(receiver, timeout=5.0)
        try:
            assert third.recv(4096) == b""  # refused at accept, with no response
        finally:
            third.close()

        _, body = receiver.health()
        assert body["http"]["connections_refused"] >= 1
        assert threading.active_count() <= baseline_threads + 2  # no thread for the excess
    finally:
        first.close()
        second.close()

    _poll_health(receiver, lambda b: b["http"]["connections_open"] == 0)
    assert post_notification(receiver, _valid_body("h11b")).status == 202


# === H12 ========================================================================


def test_h12_eight_concurrent_posts_get_contiguous_arrival_seqs(front_door, tmp_path):
    directory = _default_state_dir(tmp_path)
    bodies = [_valid_body(f"h12-{i}") for i in range(8)]
    results: list[dict | None] = [None] * 8
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            response = post_notification(front_door, bodies[index])
            assert response.status == 202
            results[index] = json.loads(response.body)
        except BaseException as error:  # noqa: BLE001 - surfaced via `errors`, not swallowed.
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10.0)
    assert not errors, errors
    assert all(results)

    arrival_seqs = sorted(result["arrival_seq"] for result in results)
    assert arrival_seqs == list(range(arrival_seqs[0], arrival_seqs[0] + 8))

    live_pending_digest = front_door.journal.snapshot()["pending_digest"]
    front_door.stop()
    assert len(_spool_files(directory)) == 8
    inspection = rj.inspect_recovery_journal(directory / _JOURNAL_SUBDIR)
    assert inspection.report["journal"]["pending_digest"] == live_pending_digest


# === H13 ========================================================================


def test_h13_unknown_routes_are_not_found(front_door):
    for method, target in (("GET", "/notification"), ("POST", "/other"), ("GET", "/x")):
        response = http_request(front_door.url + target, method=method)
        assert response.status == 404, target
        assert response.body.decode() == "not_found", target


# === H14 / H14b ==================================================================


def test_h14_body_deadline_closes_the_connection(start_front_door):
    receiver = start_front_door(request_deadline=1.0)
    before_head = receiver.journal.snapshot()["head"]
    body = _valid_body("h14")
    half = body[: len(body) // 2]
    sock = _raw_socket(receiver, timeout=5.0)
    start = time.monotonic()
    try:
        header = f"POST /notification HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n\r\n"
        sock.sendall(header.encode() + half)
        raw = _recv_all(sock, timeout=5.0)
    finally:
        sock.close()
    elapsed = time.monotonic() - start
    print(f"[test_journaled_receiver] h14 elapsed={elapsed:.2f}s")
    assert elapsed < 5.0, "the deadline reader did not close the connection"
    if raw:
        _, _, body_out = raw.partition(b"\r\n\r\n")
        assert body_out.decode() == "http_body_incomplete"

    _, health_body = _poll_health(receiver, lambda b: b["http"]["http_body_incomplete"] >= 1)
    assert health_body["http"]["deadline_exceeded"] >= 1
    assert receiver.journal.snapshot()["head"] == before_head


def test_h14b_body_trickle_never_re_arms_the_deadline(start_front_door):
    receiver = start_front_door(request_deadline=1.0)
    before_head = receiver.journal.snapshot()["head"]
    declared = 200
    sock = _raw_socket(receiver, timeout=5.0)
    start = time.monotonic()
    sent = 0
    try:
        header = f"POST /notification HTTP/1.1\r\nHost: x\r\nContent-Length: {declared}\r\n\r\n"
        sock.sendall(header.encode())
        while time.monotonic() - start < 3.0 and sent < declared:
            try:
                sock.sendall(b"a")
            except OSError:
                break
            sent += 1
            time.sleep(0.1)  # the trickle itself, at probe r1b's own rate: not a sync wait
        _recv_all(sock, timeout=5.0)
    finally:
        sock.close()
    elapsed = time.monotonic() - start
    print(f"[test_journaled_receiver] h14b body trickle elapsed={elapsed:.2f}s sent={sent}")
    assert elapsed < 5.0
    assert sent < declared, "the trickle was not cut by the deadline"

    _poll_health(receiver, lambda b: b["http"]["deadline_exceeded"] >= 1)
    assert receiver.journal.snapshot()["head"] == before_head


def test_h14b_header_trickle_closes_with_no_response(start_front_door):
    receiver = start_front_door(request_deadline=1.0)
    _, before_health = receiver.health()
    before = before_health["http"]["deadline_exceeded"]
    header = b"POST /notification HTTP/1.1\r\nHost: x\r\nX-Trickle: "
    sock = _raw_socket(receiver, timeout=5.0)
    start = time.monotonic()
    sent = 0
    try:
        while time.monotonic() - start < 3.0 and sent < len(header):
            try:
                sock.sendall(header[sent : sent + 1])
            except OSError:
                break
            sent += 1
            time.sleep(0.1)
        raw = _recv_all(sock, timeout=5.0)
    finally:
        sock.close()
    elapsed = time.monotonic() - start
    print(f"[test_journaled_receiver] h14b header trickle elapsed={elapsed:.2f}s")
    assert elapsed < 5.0
    assert raw == b""  # the header phase gets no response at all (probe r1b)
    _poll_health(receiver, lambda b: b["http"]["deadline_exceeded"] > before)


# === H15 ========================================================================


def test_h15_data_canaries_never_reach_response_health_log_or_durable_bytes(
    front_door, tmp_path, caplog,
):
    directory = _default_state_dir(tmp_path)
    admitted_body = json.dumps({
        "groupKey": '{}:{alertname="h15-admitted"}',
        "alerts": [{"fingerprint": "h15fp", "status": "firing"}],
        "message": _DATA_CANARY, "commonAnnotations": {"summary": _DATA_CANARY},
    }).encode("utf-8")
    response = post_notification(front_door, admitted_body)
    assert response.status == 202
    assert _DATA_CANARY not in response.body.decode()

    refused_body = json.dumps({
        "groupKey": '{}:{alertname="h15-refused"}',
        "alerts": [{"fingerprint": _DATA_CANARY, "status": "firing"}],
    }).encode("utf-8")
    outcome = ji.sanitize_notification(refused_body)
    assert outcome.refusal is not None
    refused_response = post_notification(front_door, refused_body)
    assert _DATA_CANARY not in refused_response.body.decode()

    _, health_body = front_door.health()
    assert _DATA_CANARY not in json.dumps(health_body)
    assert _DATA_CANARY not in caplog.text

    journal_dir = directory / _JOURNAL_SUBDIR
    for name in (journal_store.DB_FILENAME, journal_store.WAL_FILENAME):
        path = journal_dir / name
        if path.exists():
            assert _DATA_CANARY.encode("utf-8") not in path.read_bytes()

    spool_files = _spool_files(directory)
    assert spool_files[ji.body_digest(admitted_body)] == admitted_body  # the canary lives only here
    assert ji.body_digest(refused_body) not in spool_files  # a refusal is never spooled (V4)


def test_h15_raw_socket_protocol_canaries_are_never_reflected(front_door, capfd):
    long_header_value = _DATA_CANARY + "a" * 70_000
    cases = [
        ("method", f"{_TOKEN_CANARY} / HTTP/1.1\r\nHost: x\r\n\r\n".encode(),
         501, jrecv.STDLIB_ERROR_CODES[501]),
        ("target",
         ("GET /" + _DATA_CANARY * 3000 + " HTTP/1.1\r\nHost: x\r\n\r\n").encode(
             "utf-8", errors="surrogateescape",
         ),
         414, jrecv.STDLIB_ERROR_CODES[414]),
        ("version", f"GET / HTTP/{_TOKEN_CANARY}\r\n\r\n".encode(), None,
         jrecv.STDLIB_ERROR_CODES[400]),
        # A header line without a colon is not one of the stdlib's own parse
        # failures (LineTooLong or too-many-headers): email.parser drops it
        # silently and parsing simply stops there, so nothing after it in the
        # header block is seen (probe r1a's own `header_name_bad` got no
        # status line at all). Placed before Content-Length, that reads here
        # as a plain framing refusal, not a `send_error`/`STDLIB_ERROR_CODES`
        # path; the canary still never reaches the reply.
        ("header_name",
         (f"POST /notification HTTP/1.1\r\nHost: x\r\n{_TOKEN_CANARY}\r\n"
          "Content-Length: 4\r\n\r\n").encode(),
         411, "http_length_required"),
        ("long_header",
         f"GET /health HTTP/1.1\r\nHost: x\r\nX-Long: {long_header_value}\r\n\r\n".encode(
             "utf-8", errors="surrogateescape",
         ),
         431, jrecv.STDLIB_ERROR_CODES[431]),
    ]
    for label, raw, expected_status, expected_code in cases:
        sock = _raw_socket(front_door)
        try:
            sock.sendall(raw)
            reply = _recv_all(sock, timeout=5.0)
        finally:
            sock.close()
        assert _TOKEN_CANARY.encode() not in reply, label
        assert _DATA_CANARY.encode("utf-8") not in reply, label
        if expected_status is None:
            assert reply == expected_code.encode(), label  # bare-code reply (probe r1a)
        else:
            head, _, body = reply.partition(b"\r\n\r\n")
            assert head.startswith(f"HTTP/1.1 {expected_status} ".encode()), label
            assert body.decode() == expected_code, label

        _, health_body = front_door.health()
        if label == "header_name":
            assert health_body["http"]["http_length_required"] >= 1, label
        else:
            assert health_body["http"]["protocol_errors"].get(expected_code, 0) >= 1, label

    out, err = capfd.readouterr()
    assert _TOKEN_CANARY not in out and _TOKEN_CANARY not in err
    assert _DATA_CANARY not in out and _DATA_CANARY not in err


def test_h15_injected_exception_messages_never_reach_stderr(front_door, monkeypatch, capfd):
    def _raising_sanitize(_body: bytes):
        raise RuntimeError(_DATA_CANARY)

    monkeypatch.setattr(jrecv, "sanitize_notification", _raising_sanitize)
    response = post_notification(front_door, _valid_body("h15-exc"))
    assert response.status == 500
    assert response.body.decode() == "receiver_error"
    monkeypatch.undo()

    # `_Handler` (the plan names no handler class) inherits `send_response`
    # unchanged from the stdlib: only `send_error`, `log_message` and
    # `handle_error` are overridden.
    def _raising_send_response(self, *args, **kwargs):
        raise RuntimeError(_DATA_CANARY)

    monkeypatch.setattr(http.server.BaseHTTPRequestHandler, "send_response", _raising_send_response)
    try:
        post_notification(front_door, _valid_body("h15-exc2"))
    except Exception:  # noqa: BLE001, S110 - the server drops the connection; only stderr matters.
        pass

    out, err = capfd.readouterr()
    assert _DATA_CANARY not in out and _DATA_CANARY not in err
    assert "Traceback" not in err


# === H16 ========================================================================


def test_h16_placement_and_missing_state_directory(tmp_path):
    runs_a = tmp_path / "runs-a"
    runs_a.mkdir(mode=0o700)  # create_state needs its parent to exist
    state_a = runs_a / "S"  # S nested inside runs_directory
    create_state(state_a)
    with pytest.raises(FrontDoorError) as exc_a:
        JournaledReceiver(state_a, runs_directory=runs_a, port=0)
    assert exc_a.value.code == "state_placement_invalid"

    state_b = tmp_path / "S-b"
    create_state(state_b)
    with pytest.raises(FrontDoorError) as exc_b:  # runs_directory nested inside S
        JournaledReceiver(state_b, runs_directory=state_b / "runs", port=0)
    assert exc_b.value.code == "state_placement_invalid"

    state_c = tmp_path / "missing"
    with pytest.raises(FrontDoorError) as exc_c:
        JournaledReceiver(state_c, runs_directory=tmp_path / "runs-c", port=0)
    assert exc_c.value.code == "state_missing"
    assert not state_c.exists()


# === H17 ========================================================================


def test_h17_a_lost_ack_makes_the_retry_suppressed(front_door, tmp_path, monkeypatch):
    directory = _default_state_dir(tmp_path)
    body = _valid_body("h17")
    request = _raw_request(
        "POST", "/notification", [("Host", "x"), ("Content-Length", str(len(body)))], body,
    )
    committed = threading.Event()

    def drop_receipt(handler, receipt):
        assert receipt.result == "admitted"
        handler.close_connection = True
        handler.connection.shutdown(socket.SHUT_RDWR)
        committed.set()

    with monkeypatch.context() as patch:
        patch.setattr(jrecv._Handler, "_respond_receipt", drop_receipt)
        with _raw_socket(front_door) as sock:
            sock.sendall(request)
            assert sock.recv(1) == b""
            assert committed.wait(5)

    retry = json.loads(post_notification(front_door, body).body)
    assert retry["result"] == "suppressed"  # `result`, not `decision` (H1 pins the same split)
    assert retry["decision"] == "held"
    # The original admission, then the suppressed retry: both count (H1's rule).
    assert front_door.journal.snapshot()["counts"]["admissions"] == 2
    assert len(_spool_files(directory)) == 1


# === H18 ========================================================================


def test_h18_bind_before_open_leaves_the_journal_untouched(tmp_path):
    directory = tmp_path / "S-bind"
    create_state(directory)
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    try:
        before = _file_snapshot(directory / _JOURNAL_SUBDIR)
        with pytest.raises(FrontDoorError) as excinfo:
            JournaledReceiver(
                directory, runs_directory=tmp_path / "runs-bind", host="127.0.0.1", port=port,
            )
        assert excinfo.value.code == "listener_bind_failed"
        after = _file_snapshot(directory / _JOURNAL_SUBDIR)
        assert after == before
    finally:
        blocker.close()


@pytest.mark.parametrize("full_body", [
    False,
    pytest.param(True, marks=pytest.mark.skipif(
        sys.platform != "darwin", reason="no-read full-body 503 qualified on Darwin only",
    )),
])
def test_h18_serves_503_journal_opening_while_the_journal_opens(
    tmp_path, monkeypatch, full_body,
):
    directory = tmp_path / "S-opening"
    create_state(directory)
    release = threading.Event()
    real_open = jrecv.open_recovery_journal

    def blocking_open(*args, **kwargs):
        release.wait(5.0)
        return real_open(*args, **kwargs)

    monkeypatch.setattr(jrecv, "open_recovery_journal", blocking_open)
    receiver = JournaledReceiver(directory, runs_directory=tmp_path / "runs-opening", port=0)
    starter = threading.Thread(target=receiver.start, daemon=True)
    starter.start()
    try:
        def _opening_response():
            try:
                if full_body:
                    response = post_notification(
                        receiver, (FIXTURES / "notification-firing.json").read_bytes(),
                    )
                    return response.status, response.headers, response.body
                with _raw_socket(receiver) as sock:
                    return _exchange(sock, _raw_request(
                        "POST", "/notification", [("Host", "x"), ("Content-Length", "2611")],
                    ))
            except Exception:  # noqa: BLE001 - not yet serving; keep polling.
                return None

        response = _poll(_opening_response, timeout=5.0)
        assert response[0] == 503
        assert response[2] == b"journal_opening"
        assert _header(response[1], "Retry-After") == "10"
        status, body = receiver.health()
        assert status == 503
        assert body["journal"]["state"] == "opening"
    finally:
        release.set()
        starter.join(5.0)
    receiver.stop()


# === H19 ========================================================================


def test_h19_health_key_set_and_status_code_rule(start_front_door, tmp_path):
    receiver = start_front_door()
    response = get_health(receiver)
    assert response.status == 200
    assert _header(response.headers, "Content-Type") == "application/json"
    assert _header(response.headers, "Cache-Control") == "no-store"
    body = json.loads(response.body)
    assert set(body) == {"mode", "runs", "journal", "resume", "refusals", "http", "spool"}
    assert set(body["journal"]) == {
        "state", "hold", "dispatch_holds", "head_commit_seq", "admissions", "pending_fingerprints",
    }
    assert body["journal"]["state"] == "ready"
    assert body["journal"]["hold"] is None
    assert set(body["resume"]) == {"this_boot"}
    assert set(body["refusals"]) == {"recorded", "limit", "reserve", "this_boot"}
    assert set(body["spool"]) == {
        "state", "code", "bytes", "max_bytes", "entries", "max_entries",
        "written_this_boot", "full_refusals_this_boot",
    }
    assert body["http"]["in_flight"] <= jrecv.MAX_IN_FLIGHT
    assert body["http"]["connections_open"] <= jrecv.MAX_CONNECTIONS
    for code in body["refusals"]["this_boot"]:
        assert code in ji.INGRESS_REFUSAL_CODES

    # 200 even with a capacity_admissions dispatch hold (critic 10).
    capacity_receiver = start_front_door(tmp_path / "S-capacity", bounds=_CAPACITY_TWO_BOUNDS)
    _drive_to_capacity_admissions(capacity_receiver)
    status_capacity, body_capacity = capacity_receiver.health()
    assert status_capacity == 200
    assert "capacity_admissions" in body_capacity["journal"]["dispatch_holds"]

    # 200 even after a spool_full refusal (critic 10): the spool is counted, not latched.
    tight_receiver = start_front_door(tmp_path / "S-tight", spool_max_entries=1)
    assert post_notification(tight_receiver, _valid_body("h19-c")).status == 202
    full = post_notification(tight_receiver, _valid_body("h19-d"))
    assert full.status == 503
    assert full.body.decode() == "spool_full"
    status_tight, body_tight = tight_receiver.health()
    assert status_tight == 200
    assert body_tight["spool"]["state"] == "ok"

    # 503 while held (opening/closed are covered by H7/H7b and H18).
    held_directory = tmp_path / "S-held"
    create_state(held_directory)
    journal_dir = held_directory / _JOURNAL_SUBDIR
    (journal_dir / journal_store.WAL_FILENAME).unlink(missing_ok=True)
    (journal_dir / journal_store.DB_FILENAME).unlink()
    held_receiver = start_front_door(held_directory)
    status_held, _ = held_receiver.health()
    assert status_held == 503


def test_admission_only_mode_h19_mode_and_runs_fields(front_door):
    response = get_health(front_door)
    body = json.loads(response.body)
    assert body["mode"] == jrecv.MODE == "journaled-admission-only"
    assert body["runs"] == "not_dispatched"


# === H20 ========================================================================


def test_h20_receipt_shape_and_content_type(front_door):
    response = post_notification(front_door, _valid_body("h20"))
    assert response.status == 202
    assert _header(response.headers, "Content-Type") == "application/json"
    receipt = json.loads(response.body)
    assert set(receipt) == {
        "admission_id", "arrival_seq", "commit_seq", "decision", "dispatch_holds", "result", "run",
    }


def test_admission_only_mode_h20_run_not_dispatched(front_door):
    response = post_notification(front_door, _valid_body("h20-mode"))
    receipt = json.loads(response.body)
    assert receipt["run"] == "not_dispatched"


def test_h14_keep_alive_arms_a_fresh_deadline_per_request(start_front_door):
    receiver = start_front_door(request_deadline=0.8)
    sock = _raw_socket(receiver)
    try:
        for _ in range(2):
            sock.sendall(b"GET /health HTTP/1.1\r\nHost: x\r\n")
            time.sleep(0.5)
            status, _, body = _exchange(sock, b"\r\n")
            assert status == 200
            assert json.loads(body)["journal"]["state"] == "ready"
    finally:
        sock.close()


def test_h11_thread_start_failure_releases_connection_slot(front_door, monkeypatch):
    def refuse_thread_start(self, request, client_address):
        raise RuntimeError("synthetic thread start failure")

    monkeypatch.setattr(jrecv.ThreadingHTTPServer, "process_request", refuse_thread_start)
    with pytest.raises(RuntimeError, match="synthetic thread start failure"):
        front_door._server.process_request(object(), ("127.0.0.1", 0))
    assert front_door.health()[1]["http"]["connections_open"] == 0
    semaphore = front_door._server._connection_semaphore
    acquired = 0
    try:
        for _ in range(jrecv.MAX_CONNECTIONS):
            assert semaphore.acquire(blocking=False)
            acquired += 1
        assert not semaphore.acquire(blocking=False)
    finally:
        for _ in range(acquired):
            semaphore.release()


def test_h11_unexpected_exception_releases_inflight_slot(start_front_door, monkeypatch):
    receiver = start_front_door(max_in_flight=1)

    def raise_unexpected(_body):
        raise RuntimeError("synthetic handling failure")

    with monkeypatch.context() as patch:
        patch.setattr(jrecv, "sanitize_notification", raise_unexpected)
        response = post_notification(receiver, _valid_body("inflight-failed"))
        assert response.status == 500
    assert receiver.health()[1]["http"]["in_flight"] == 0
    response = post_notification(receiver, _valid_body("inflight-recovered"))
    assert response.status == 202
