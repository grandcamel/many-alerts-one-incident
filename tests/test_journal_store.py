"""Physical storage tests for the recovery journal (ticket 37, unit 15, module 3).

Real SQLite and real syncs throughout; nothing here fakes durability. Tests
that only need to *read* a journal image copy a module-scoped base image with
``shutil.copytree`` instead of paying the create-transaction's real syncs
again. Real-sync count and wall time are recorded at teardown and never
asserted (Implementer C's budget is 250 real syncs).
"""

from __future__ import annotations

import ast
import dataclasses
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox.forwarder_json import canonical_json
from grafana_jsm_sandbox.journal_records import (
    ZERO_DIGEST,
    Draft,
    Head,
    Position,
    Stamp,
    seal,
)
from grafana_jsm_sandbox.journal_source import (
    HTTP_PROVENANCE,
    SourceAlert,
    SourceRecord,
    source_digest,
    source_to_json,
)

pytestmark = pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE (Python >= 3.12)",
)

# The repo root, from this file's own path: a subprocess import path must not
# depend on the pytest invocation's cwd (G8).
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BOUNDS = {
    "max_admissions": 10_000, "max_pending_fingerprints": 1_024,
    "ordinary_bytes": 112 * 2**20, "total_bytes": 128 * 2**20,
}


class Factory:
    """Builds a chained, digest-consistent sequence of sealed records for one boot."""

    def __init__(self, journal_uuid: str, boot_id: str = "boot-0") -> None:
        self.journal_uuid = journal_uuid
        self.boot_id = boot_id
        self.event_seq = 0
        self.commit_seq = 0
        self.prev_digest = ZERO_DIGEST
        self._mono = 0
        self._admissions = 0

    def _stamp(self) -> Stamp:
        self._mono += 1
        wall_time = f"2026-09-23T00:00:{self._mono % 60:02d}.000000Z"
        return Stamp(boot_id=self.boot_id, wall_time=wall_time, mono_us=self._mono)

    def genesis(self, *, bounds: dict | None = None) -> object:
        self.event_seq, self.commit_seq = 1, 1
        draft = Draft(
            event_id="genesis", event_type="journal_genesis", actor="receiver", ids={},
            data={"format": "rj.journal.v1", "journal_uuid": self.journal_uuid,
                  "bounds": bounds or DEFAULT_BOUNDS},
        )
        position = Position(
            journal_generation=1, event_seq=1, commit_seq=1, commit_index=0, commit_size=1,
            prev_record_digest=ZERO_DIGEST,
        )
        record = seal(draft, position, self._stamp())
        self.prev_digest = record.record_digest
        return record

    def admission_pair(self, fingerprint: str = "fp1") -> tuple:
        self._admissions += 1
        admission_id = f"adm-{self._admissions}"
        source = SourceRecord(
            source_group="a" * 64,
            alerts=(SourceAlert(fingerprint=fingerprint, status="firing", values=None, starts_at=None),),
            truncated_alerts=0, body_digest="b" * 64, provenance=HTTP_PROVENANCE,
        )
        self.commit_seq += 1
        commit_seq = self.commit_seq
        stamp = self._stamp()

        self.event_seq += 1
        admission = seal(
            Draft(
                event_id=admission_id, event_type="admission", actor="receiver",
                ids={"admission_id": admission_id},
                data={"arrival_seq": self._admissions, "decision": "admitted", "dispatch_holds": (),
                      "source": source_to_json(source), "source_digest": source_digest(source)},
            ),
            Position(
                journal_generation=1, event_seq=self.event_seq, commit_seq=commit_seq,
                commit_index=0, commit_size=2, prev_record_digest=self.prev_digest,
            ),
            stamp,
        )
        self.prev_digest = admission.record_digest

        key = hashlib.sha256(fingerprint.encode("ascii")).hexdigest()
        self.event_seq += 1
        dedupe = seal(
            Draft(
                event_id=f"{admission_id}-dd", event_type="dedupe_decision", actor="receiver",
                ids={"admission_id": admission_id},
                data={"rule": "latest-admitted-v1", "result": "admitted", "source_group": "a" * 64,
                      "dedupe_key": key,
                      "baseline_before": None,
                      "baseline_after": {"admission_id": admission_id, "complete": True, "dedupe_key": key},
                      "superseded": (), "pending_count_after": 1},
            ),
            Position(
                journal_generation=1, event_seq=self.event_seq, commit_seq=commit_seq,
                commit_index=1, commit_size=2, prev_record_digest=self.prev_digest,
            ),
            stamp,
        )
        self.prev_digest = dedupe.record_digest
        return admission, dedupe

    def restart(self, *, new_boot_id: str, recovered: Head, anchor_lag: int = 0) -> object:
        self.boot_id = new_boot_id
        self.commit_seq += 1
        self.event_seq += 1
        record = seal(
            Draft(
                event_id=f"restart-{self.commit_seq}", event_type="restart_recovery", actor="receiver",
                ids={},
                data={"previous_boot_id": "boot-0", "recovered": {
                          "commit_seq": recovered.commit_seq, "event_seq": recovered.event_seq,
                          "record_digest": recovered.record_digest},
                      "anchor_lag": anchor_lag, "wal_found": None,
                      "dispatch_hold": "restart_recovery", "prior_leases": "invalid"},
            ),
            Position(
                journal_generation=1, event_seq=self.event_seq, commit_seq=self.commit_seq,
                commit_index=0, commit_size=1, prev_record_digest=self.prev_digest,
            ),
            self._stamp(),
        )
        self.prev_digest = record.record_digest
        return record


def new_dir(tmp_path: Path, name: str = "journal") -> Path:
    directory = tmp_path / name
    directory.mkdir(mode=0o700)
    return directory


def create_store(tmp_path: Path, name: str = "journal") -> tuple:
    directory = new_dir(tmp_path, name)
    journal_uuid = str(uuid.uuid4())
    factory = Factory(journal_uuid)
    genesis = factory.genesis()
    store = journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    return directory, journal_uuid, factory, store


@pytest.fixture(scope="module")
def base_image(tmp_path_factory) -> tuple:
    """One created-and-closed journal, reused via ``shutil.copytree`` by read-only tests."""
    base_dir = tmp_path_factory.mktemp("base") / "journal"
    base_dir.mkdir(mode=0o700)
    journal_uuid = str(uuid.uuid4())
    factory = Factory(journal_uuid)
    genesis = factory.genesis()
    store = journal_store.JournalStore.create(base_dir, genesis, journal_uuid=journal_uuid)
    admission, dedupe = factory.admission_pair("fp1")
    store.append([admission, dedupe])
    store.close()
    return base_dir, journal_uuid, genesis


def copy_image(base_image: tuple, tmp_path: Path, name: str = "journal") -> Path:
    base_dir, _journal_uuid, _genesis = base_image
    target = tmp_path / name
    shutil.copytree(base_dir, target)
    return target


@pytest.fixture(scope="module", autouse=True)
def _sync_budget():
    counts = {"n": 0}
    original = journal_store._full_sync

    def counting_full_sync(fd: int) -> None:
        counts["n"] += 1
        return original(fd)

    journal_store._full_sync = counting_full_sync
    start = time.perf_counter()
    yield counts
    elapsed = time.perf_counter() - start
    journal_store._full_sync = original
    print(f"\n[test_journal_store] real syncs={counts['n']} wall={elapsed:.2f}s")


# --- C1: create layout -------------------------------------------------------


def test_c1_create_layout(tmp_path):
    directory, journal_uuid, _factory, store = create_store(tmp_path)
    try:
        assert oct(directory.stat().st_mode & 0o777) == oct(0o700)
        for name, size in (
            (journal_store.DB_FILENAME, None), (journal_store.WAL_FILENAME, None),
            (journal_store.ANCHOR_FILENAME, journal_store.ANCHOR_BYTES),
            (journal_store.LOCK_FILENAME, None),
        ):
            path = directory / name
            assert path.exists()
            assert oct(path.stat().st_mode & 0o777) == oct(0o600)
            if size is not None:
                assert path.stat().st_size == size
        assert not (directory / "journal.sqlite3-shm").exists()

        connection = store._connection
        assert connection.getconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE) is True
        cursor = connection.cursor()
        assert cursor.execute("PRAGMA application_id").fetchone()[0] == journal_store.APPLICATION_ID
        assert cursor.execute("PRAGMA user_version").fetchone()[0] == journal_store.USER_VERSION
        rows = tuple(cursor.execute("SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY name"))
        assert rows == journal_store._reference_schema_rows()

        assert store.anchor is not None
        assert store.anchor.journal_uuid == journal_uuid
        assert store.anchor.counter == 1
        assert store.anchor.hold is None
    finally:
        store.close()


# --- C2: create refusals ------------------------------------------------------


def test_c2_create_missing_directory(tmp_path):
    directory = tmp_path / "does-not-exist"
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "journal_path_invalid"


def test_c2_create_wrong_mode(tmp_path):
    directory = tmp_path / "journal"
    directory.mkdir(mode=0o750)
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "journal_permissions"


def test_c2_create_symlinked_directory(tmp_path):
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(link, genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "journal_path_invalid"


@pytest.mark.parametrize("filename", ["journal.sqlite3", "journal.sqlite3-wal", "anchor"])
def test_c2_create_existing_file(tmp_path, filename):
    directory = new_dir(tmp_path)
    (directory / filename).write_bytes(b"x")
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "journal_exists"
    # Nothing else was created, and the lock file was released, not leaked open.
    assert not (directory / "lock").exists() or _can_lock(directory / "lock")


def _can_lock(path: Path) -> bool:
    fd = os.open(str(path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    finally:
        os.close(fd)


# --- C3: open ownership --------------------------------------------------------


def test_c3_open_empty_directory_stays_empty(tmp_path):
    directory = new_dir(tmp_path)
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.open(directory)
    assert excinfo.value.code == "journal_missing"
    assert list(directory.iterdir()) == []


def test_c3_open_symlinked_db(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    target = tmp_path / "elsewhere"
    target.write_bytes(b"not a database")
    db_path = directory / journal_store.DB_FILENAME
    db_path.unlink()
    db_path.symlink_to(target)
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.open(directory)
    assert excinfo.value.code == "journal_path_invalid"


def test_c3_open_symlinked_anchor(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    target = tmp_path / "elsewhere-anchor"
    target.write_bytes(b"x" * journal_store.ANCHOR_BYTES)
    anchor_path = directory / journal_store.ANCHOR_FILENAME
    anchor_path.unlink()
    anchor_path.symlink_to(target)
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.open(directory)
    assert excinfo.value.code == "journal_path_invalid"


def test_c3_open_symlinked_lock(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    target = tmp_path / "elsewhere-lock"
    target.write_bytes(b"")
    lock_path = directory / journal_store.LOCK_FILENAME
    if lock_path.exists():
        lock_path.unlink()
    lock_path.symlink_to(target)
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.open(directory)
    assert excinfo.value.code == "journal_path_invalid"


def test_c3_open_hard_linked_db(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    db_path = directory / journal_store.DB_FILENAME
    os.link(db_path, directory / "extra-link")
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.open(directory)
    assert excinfo.value.code == "journal_permissions"


def test_c3_open_wrong_mode_file(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    os.chmod(directory / journal_store.ANCHOR_FILENAME, 0o644)
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.open(directory)
    assert excinfo.value.code == "journal_permissions"


# --- C4: locking ---------------------------------------------------------------


def test_c4_second_open_in_process_is_locked(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        with pytest.raises(journal_store.StoreError) as excinfo:
            journal_store.JournalStore.open(directory)
        assert excinfo.value.code == "journal_locked"
    finally:
        store.close()


def test_c4_second_open_from_subprocess_is_locked(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        script = (
            f"import sys; sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            "from pathlib import Path\n"
            "from grafana_jsm_sandbox import journal_store\n"
            "try:\n"
            f"    journal_store.JournalStore.open(Path({str(directory)!r}))\n"
            "    print('opened')\n"
            "except journal_store.StoreError as error:\n"
            "    print(error.code)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True, timeout=10,
        )
        assert result.stdout.strip() == "journal_locked", result.stderr
    finally:
        store.close()


def test_c4_raw_connect_sees_database_locked(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
        try:
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                raw.execute("SELECT * FROM journal_events").fetchall()
        finally:
            raw.close()
    finally:
        store.close()


# --- C5: append-only triggers --------------------------------------------------


def test_c5_raw_update_and_delete_are_aborted(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        connection = store._connection
        with pytest.raises(sqlite3.DatabaseError, match="append_only"):
            connection.execute("UPDATE journal_events SET event_type='x' WHERE event_seq=1")
        with pytest.raises(sqlite3.DatabaseError, match="append_only"):
            connection.execute("DELETE FROM journal_events WHERE event_seq=1")
    finally:
        store.close()


def test_c5_no_update_or_delete_dml_outside_ddl():
    source = Path(journal_store.__file__).read_text()
    start = source.index("SCHEMA_SQL = (")
    end = source.index("\n)\n", start) + len("\n)\n")
    outside_ddl = source[:start] + source[end:]
    for match in re.finditer(r"\bUPDATE\b|\bDELETE\b", outside_ddl):
        pytest.fail(f"found {match.group()!r} outside SCHEMA_SQL at offset {match.start()}")


# --- C6: anchor codec -----------------------------------------------------------


def _anchor_bytes(slot0: bytes | None, slot1: bytes | None) -> bytes:
    buffer = bytearray(b"\x00" * journal_store.ANCHOR_BYTES)
    for slot, offset in ((slot0, journal_store.ANCHOR_SLOT_OFFSETS[0]),
                         (slot1, journal_store.ANCHOR_SLOT_OFFSETS[1])):
        if slot is not None:
            buffer[offset:offset + journal_store.ANCHOR_SLOT_BYTES] = slot
    return bytes(buffer)


def _slot(journal_uuid: str, counter: int, commit_seq: int = 1, hold: dict | None = None) -> bytes:
    body = {
        "counter": counter, "format": "rj.anchor.v1", "journal_uuid": journal_uuid,
        "head": {"commit_seq": commit_seq, "event_seq": commit_seq, "generation": 1,
                  "record_digest": "a" * 64},
        "hold": hold,
    }
    return journal_store._encode_slot(body)


def test_c6_slot_parity_alternation(tmp_path):
    journal_uuid = str(uuid.uuid4())
    raw = _anchor_bytes(None, _slot(journal_uuid, counter=1))
    state, finding = journal_store._analyze_anchor(raw)
    assert finding is None
    assert state.counter == 1

    raw = _anchor_bytes(_slot(journal_uuid, counter=2, commit_seq=2), _slot(journal_uuid, counter=1))
    state, finding = journal_store._analyze_anchor(raw)
    assert finding is None
    assert state.counter == 2 and state.head.commit_seq == 2


def test_c6_torn_newest_slot_falls_back_to_older(tmp_path):
    journal_uuid = str(uuid.uuid4())
    older = _slot(journal_uuid, counter=1)
    newer = bytearray(_slot(journal_uuid, counter=2, commit_seq=2))
    newer[20] ^= 0xFF  # corrupt the payload/checksum region of the newer slot
    raw = _anchor_bytes(bytes(newer), older)
    state, finding = journal_store._analyze_anchor(raw)
    assert finding is None
    assert state.counter == 1


@pytest.mark.parametrize(
    "build",
    [
        lambda u: _anchor_bytes(None, None),  # both slots torn
        lambda u: _anchor_bytes(_slot(u, 1), _slot(u, 1))[:8000],  # wrong size
        lambda u: _anchor_bytes(_slot(u, 3, commit_seq=3), _slot(u, 1)),  # counter gap != 1
        lambda u: _anchor_bytes(_slot(u, 2, commit_seq=2), _slot(u, 2, commit_seq=2)),  # parity mismatch
        lambda u: _anchor_bytes(
            _slot(u, 2, commit_seq=1, hold=None),
            _slot(u, 1, commit_seq=1, hold={"boot_id": "b", "code": "journal_corrupt", "observed_commit_seq": None}),
        ),  # newer has no hold, older does
    ],
)
def test_c6_invalid_anchor_variants(build):
    journal_uuid = str(uuid.uuid4())
    raw = build(journal_uuid)
    state, finding = journal_store._analyze_anchor(raw)
    assert state is None
    assert finding.code == "journal_anchor_invalid"
    assert finding.scope == "recovery"


def test_c6_foreign_journal_uuid_gives_identity_mismatch(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    foreign_uuid = str(uuid.uuid4())
    body = {
        "counter": 3, "format": "rj.anchor.v1", "journal_uuid": foreign_uuid,
        "head": {"commit_seq": 2, "event_seq": 3, "generation": 1, "record_digest": "a" * 64},
        "hold": None,
    }
    slot = journal_store._encode_slot(body)  # counter 3 is odd: slot index 1 (offset 4096)
    raw = _anchor_bytes(None, slot)
    (directory / journal_store.ANCHOR_FILENAME).write_bytes(raw)
    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding is not None
        assert store.finding.code == "journal_identity_mismatch"
        assert store.finding.scope == "recovery"
    finally:
        store.close()


# --- C7: sync primitive ---------------------------------------------------------


darwin_only = pytest.mark.skipif(sys.platform != "darwin", reason="F_FULLFSYNC is darwin-only")
linux_only = pytest.mark.skipif(sys.platform != "linux", reason="linux fsync variant")


@darwin_only
def test_c7_append_issues_one_fullfsync_on_the_anchor(tmp_path, monkeypatch):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        calls: list[tuple[str, int]] = []
        real_fcntl = fcntl.fcntl
        anchor_fd_holder: list[int] = []

        real_open = os.open

        def recording_open(path, flags, *args):
            fd = real_open(path, flags, *args)
            if str(path).endswith(journal_store.ANCHOR_FILENAME):
                anchor_fd_holder.append(fd)
            return fd

        def recording_fcntl(fd, request, *args):
            if request == fcntl.F_FULLFSYNC:
                calls.append(("F_FULLFSYNC", fd))
            return real_fcntl(fd, request, *args)

        monkeypatch.setattr(fcntl, "fcntl", recording_fcntl)
        monkeypatch.setattr(os, "open", recording_open)

        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])

        anchor_syncs = [call for call in calls if call[1] in anchor_fd_holder]
        assert len(anchor_syncs) == 1
    finally:
        monkeypatch.undo()
        store.close()


@darwin_only
def test_c7_append_with_sync_directory_orders_directory_then_anchor(tmp_path, monkeypatch):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        order: list[str] = []
        real_fcntl = fcntl.fcntl
        real_execute = journal_store.JournalStore._commit_sql

        def recording_commit_sql(self, records):
            order.append("commit")
            return real_execute(self, records)

        def recording_fcntl(fd, request, *args):
            if request == fcntl.F_FULLFSYNC:
                order.append("fsync")
            return real_fcntl(fd, request, *args)

        monkeypatch.setattr(fcntl, "fcntl", recording_fcntl)
        monkeypatch.setattr(journal_store.JournalStore, "_commit_sql", recording_commit_sql)

        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe], sync_directory=True)

        assert order == ["commit", "fsync", "fsync"]
    finally:
        monkeypatch.undo()
        store.close()


@linux_only
def test_c7_linux_uses_os_fsync(tmp_path, monkeypatch):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        calls = []
        real_fsync = os.fsync

        def recording_fsync(fd):
            calls.append(fd)
            return real_fsync(fd)

        monkeypatch.setattr(os, "fsync", recording_fsync)
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        assert calls
    finally:
        monkeypatch.undo()
        store.close()


def test_c7_unsupported_platform_gives_sync_unsupported(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert journal_store._sync_primitive_available() is False
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store._full_sync(0)
    assert excinfo.value.code == "journal_sync_unsupported"
    monkeypatch.undo()


def test_c7_unsupported_platform_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_store, "_sync_primitive_available", lambda: False)
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    directory = new_dir(tmp_path)
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "journal_sync_unsupported"
    monkeypatch.undo()


# --- C8: fsync-failure injection -------------------------------------------------


@pytest.mark.parametrize("errno_value", [errno.ENOTSUP, errno.ENODEV])  # not 95: that's EMULTIHOP on darwin
def test_c8_anchor_fsync_failure_refuses_later_appends(tmp_path, monkeypatch, errno_value):
    if sys.platform != "darwin":
        pytest.skip("F_FULLFSYNC is darwin-only")
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        real_fcntl = fcntl.fcntl

        def failing_fcntl(fd, request, *args):
            if request == fcntl.F_FULLFSYNC:
                raise OSError(errno_value, os.strerror(errno_value))
            return real_fcntl(fd, request, *args)

        monkeypatch.setattr(fcntl, "fcntl", failing_fcntl)
        admission, dedupe = factory.admission_pair("fp1")
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.append([admission, dedupe])
        assert excinfo.value.code == "store_write_failed"

        monkeypatch.undo()
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.append(factory.admission_pair("fp2"))
        assert excinfo.value.code == "store_write_failed"
    finally:
        store.close()

    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.finding is None
        rows = list(reopened.rows())
        assert [record.event_type for record in rows] == ["journal_genesis", "admission", "dedupe_decision"]
    finally:
        reopened.close()


def test_c8_directory_fsync_failure_refuses_later_appends(tmp_path, monkeypatch):
    if sys.platform != "darwin":
        pytest.skip("F_FULLFSYNC is darwin-only")
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        real_fcntl = fcntl.fcntl
        directory_stat = os.stat(directory)

        def is_directory_fd(fd: int) -> bool:
            try:
                return os.path.samestat(os.fstat(fd), directory_stat)
            except OSError:
                return False

        def failing_fcntl(fd, request, *args):
            if request == fcntl.F_FULLFSYNC and is_directory_fd(fd):
                raise OSError(95, "Operation not supported")
            return real_fcntl(fd, request, *args)

        monkeypatch.setattr(fcntl, "fcntl", failing_fcntl)
        admission, dedupe = factory.admission_pair("fp1")
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.append([admission, dedupe], sync_directory=True)
        assert excinfo.value.code == "store_write_failed"
    finally:
        monkeypatch.undo()
        store.close()


# --- C9: find_duplicate ---------------------------------------------------------


def test_c9_exact_duplicate_returns_stored_positions_without_write(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        seqs = store.append([admission, dedupe])
        counter_before = store.anchor.counter

        duplicate = store.find_duplicate([admission, dedupe])
        assert duplicate == journal_store.Duplicate(event_seqs=seqs)
        assert store.anchor.counter == counter_before

        count = store._connection.execute("SELECT count(*) FROM journal_events").fetchone()[0]
        assert count == 3  # genesis + admission + dedupe_decision, no re-insert
    finally:
        store.close()


def test_c9_partial_overlap_conflicts(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        admission2, _dedupe2 = factory.admission_pair("fp2")
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.find_duplicate([admission, admission2])
        assert excinfo.value.code == "store_event_conflict"
        count = store._connection.execute("SELECT count(*) FROM journal_events").fetchone()[0]
        assert count == 3
    finally:
        store.close()


def test_c9_reordered_records_conflict(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.find_duplicate([dedupe, admission])
        assert excinfo.value.code == "store_event_conflict"
    finally:
        store.close()


def test_c9_no_match_returns_none(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        assert store.find_duplicate([admission, dedupe]) is None
    finally:
        store.close()


# --- C10: classify_sqlite_error --------------------------------------------------


def _fake_error(code: int, name: str) -> sqlite3.Error:
    error = sqlite3.OperationalError("synthetic")
    error.sqlite_errorcode = code
    error.sqlite_errorname = name
    return error


@pytest.mark.parametrize("code,name", [
    (11, "SQLITE_CORRUPT"), (26, "SQLITE_NOTADB"), (779, "SQLITE_CORRUPT_INDEX"),
    (523, "SQLITE_CORRUPT_SEQUENCE"), (267, "SQLITE_CORRUPT_VTAB"),
])
def test_c10_recovery_primary_codes(code, name):
    finding = journal_store.classify_sqlite_error(_fake_error(code, name))
    assert finding.code == "journal_corrupt"
    assert finding.scope == "recovery"
    assert finding.sqlite_error == name


@pytest.mark.parametrize("code,name", [
    (10, "SQLITE_IOERR"), (522, "SQLITE_IOERR_SHORT_READ"), (3850, "SQLITE_IOERR_LOCK"),
    (14, "SQLITE_CANTOPEN"), (5, "SQLITE_BUSY"), (13, "SQLITE_FULL"), (2067, "SQLITE_CONSTRAINT_UNIQUE"),
])
def test_c10_process_primary_codes(code, name):
    finding = journal_store.classify_sqlite_error(_fake_error(code, name))
    assert finding.code == "journal_open_failed"
    assert finding.scope == "process"
    assert finding.sqlite_error == name


def test_c10_missing_errorcode_attribute_is_process():
    error = sqlite3.OperationalError("no attributes set")
    finding = journal_store.classify_sqlite_error(error)
    assert finding.code == "journal_open_failed"
    assert finding.scope == "process"
    assert finding.sqlite_error is None


# --- C11: format tamper on closed images -----------------------------------------


def test_c11_dropped_trigger_gives_schema_invalid(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("DROP TRIGGER journal_events_no_update")
        raw.commit()
    finally:
        raw.close()
    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_schema_invalid"
        assert store.finding.scope == "recovery"
    finally:
        store.close()


def test_c11_extra_index_gives_schema_invalid(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("CREATE INDEX extra_idx ON journal_events(event_type)")
        raw.commit()
    finally:
        raw.close()
    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_schema_invalid"
    finally:
        store.close()


def test_c11_journal_mode_delete_gives_schema_invalid(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA journal_mode=DELETE")
    finally:
        raw.close()
    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_schema_invalid"
    finally:
        store.close()


def test_c11_user_version_2_gives_process_schema_unsupported(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA user_version=2")
        raw.commit()
    finally:
        raw.close()
    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_schema_unsupported"
        assert store.finding.scope == "process"
    finally:
        store.close()


def test_c11_changed_application_id_gives_identity_mismatch(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA application_id=1")
        raw.commit()
    finally:
        raw.close()
    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_identity_mismatch"
    finally:
        store.close()


def test_c11_empty_presentation_with_valid_anchor_gives_truncated(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    store.close()
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA writable_schema=ON")
        raw.execute("DELETE FROM sqlite_master")
        raw.execute("PRAGMA application_id=0")
        raw.execute("PRAGMA user_version=0")
        raw.commit()
        raw.execute("PRAGMA writable_schema=OFF")
        raw.execute("VACUUM")
    finally:
        raw.close()
    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.finding.code == "journal_truncated"
        assert reopened.finding.scope == "recovery"
    finally:
        reopened.close()


# --- C12: wal_found -----------------------------------------------------------


def test_c12_wal_found_records_size_and_digest(tmp_path):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    admission, dedupe = factory.admission_pair("fp1")
    store.append([admission, dedupe])
    store.close()

    wal_path = directory / journal_store.WAL_FILENAME
    assert wal_path.exists()
    expected = journal_store._wal_found(wal_path)

    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.wal_found == expected
        assert reopened.wal_found is not None
        assert reopened.wal_found.size == wal_path.stat().st_size
    finally:
        reopened.close()


def test_c12_wal_found_is_none_when_absent(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    wal_path = directory / journal_store.WAL_FILENAME
    if wal_path.exists():
        wal_path.unlink()
    assert journal_store._wal_found(wal_path) is None


# --- C13: persist_hold -----------------------------------------------------------


def test_c13_persist_hold_writes_two_synced_slots(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        counter_before = store.anchor.counter
        wrote = store.persist_hold("journal_corrupt", boot_id="boot-hold")
        assert wrote is True
        assert store.anchor.counter == counter_before + 2
        assert store.anchor.hold.code == "journal_corrupt"
        assert store.anchor.hold.boot_id == "boot-hold"

        again = store.persist_hold("journal_corrupt", boot_id="boot-hold-2")
        assert again is False
        assert store.anchor.counter == counter_before + 2  # unchanged; idempotent
    finally:
        store.close()

    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.finding is not None
        assert reopened.finding.code == "journal_corrupt"
    finally:
        reopened.close()


def test_c13_torn_second_hold_write_still_reads_as_held(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    real_write_slot = journal_store.JournalStore._write_slot
    calls = {"n": 0}

    def tearing_write_slot(self, body):
        calls["n"] += 1
        if calls["n"] == 2:
            # Simulate a torn second write: write, but corrupt one byte after the sync.
            real_write_slot(self, body)
            path = self.anchor_path
            offset = journal_store.ANCHOR_SLOT_OFFSETS[(self.anchor.counter) % 2]
            fd = os.open(str(path), os.O_WRONLY)
            try:
                os.pwrite(fd, b"\xff", offset + 20)
            finally:
                os.close(fd)
            return
        real_write_slot(self, body)

    store._write_slot = tearing_write_slot.__get__(store, journal_store.JournalStore)
    store.persist_hold("journal_corrupt", boot_id="boot-hold")
    store.close()

    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.finding is not None
        assert reopened.finding.code == "journal_corrupt"
    finally:
        reopened.close()


# --- C14: capability gate --------------------------------------------------------


def test_c14_capability_gate_blocks_create_and_open(tmp_path, monkeypatch):
    directory = new_dir(tmp_path)
    monkeypatch.setattr(journal_store, "no_ckpt_supported", lambda: False)
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    try:
        with pytest.raises(journal_store.StoreError) as excinfo:
            journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
        assert excinfo.value.code == "sqlite_unsupported"
        assert list(directory.iterdir()) == []

        with pytest.raises(journal_store.StoreError) as excinfo:
            journal_store.JournalStore.open(directory)
        assert excinfo.value.code == "sqlite_unsupported"
        assert list(directory.iterdir()) == []
    finally:
        monkeypatch.undo()


# --- C15: anchor forward compatibility --------------------------------------------


def test_c15_newer_anchor_format_gives_process_schema_unsupported(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    body = {
        "counter": 3, "format": "rj.anchor.v2", "journal_uuid": base_image[1],
        "head": {"commit_seq": 2, "event_seq": 3, "generation": 1, "record_digest": "a" * 64},
        "hold": None,
    }
    slot = journal_store._encode_slot(body)
    before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
    (directory / journal_store.ANCHOR_FILENAME).write_bytes(_anchor_bytes(before[0:1024], slot))
    raw_before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()

    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_schema_unsupported"
        assert store.finding.scope == "process"
    finally:
        store.close()
    raw_after = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
    assert raw_after == raw_before


def test_c15_unknown_hold_code_gives_process_schema_unsupported(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    body = {
        "counter": 3, "format": "rj.anchor.v1", "journal_uuid": base_image[1],
        "head": {"commit_seq": 2, "event_seq": 3, "generation": 1, "record_digest": "a" * 64},
        "hold": {"boot_id": "boot-x", "code": "journal_future_hold", "observed_commit_seq": None},
    }
    slot = journal_store._encode_slot(body)
    before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
    (directory / journal_store.ANCHOR_FILENAME).write_bytes(_anchor_bytes(before[0:1024], slot))

    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_schema_unsupported"
        assert store.finding.scope == "process"
    finally:
        store.close()


def test_c15_extra_key_gives_process_schema_unsupported(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    body = {
        "counter": 3, "format": "rj.anchor.v1", "journal_uuid": base_image[1],
        "head": {"commit_seq": 2, "event_seq": 3, "generation": 1, "record_digest": "a" * 64},
        "hold": None, "extra": "field",
    }
    slot = journal_store._encode_slot(body)
    before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
    (directory / journal_store.ANCHOR_FILENAME).write_bytes(_anchor_bytes(before[0:1024], slot))

    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding.code == "journal_schema_unsupported"
        assert store.finding.scope == "process"
    finally:
        store.close()


# --- Hardening: hold codes, paths, open failures, anchor codec, writes -----------

PLAN_RECOVERY_HOLD_CODES = frozenset({
    "journal_truncated", "journal_anchor_missing", "journal_anchor_invalid",
    "journal_anchor_conflict", "journal_identity_mismatch", "journal_schema_invalid",
    "journal_corrupt", "journal_record_invalid", "journal_chain_broken",
    "journal_tail_unverified", "journal_replay_mismatch", "journal_event_conflict",
})
SCHEMA_UNSUPPORTED = journal_store.Finding("journal_schema_unsupported", "process", None)
OPEN_FAILED = journal_store.Finding("journal_open_failed", "process", None)


class SimulatedCrash(BaseException):
    pass


def _open(directory: Path) -> journal_store.JournalStore:
    return journal_store.JournalStore.open(directory)


def _file_bytes(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


def _assert_opens_ready(directory: Path) -> None:
    store = _open(directory)
    try:
        assert store.finding is None
    finally:
        store.close()


def _resigned_row(envelope: dict, event_seq: int, event_id: str, event_type: str) -> tuple:
    body = canonical_json(envelope, ascii_only=True)
    digest = hashlib.sha256(b"rj.record.v1\x00" + body).hexdigest()
    return event_seq, event_id, event_type, body, digest


def _bad_source_admission(admission) -> dict:
    envelope = json.loads(admission.body)
    envelope["data"]["source"]["alerts"][0]["status"] = "Firing"
    return envelope


def test_c13_recovery_hold_codes_are_the_plan_table():
    assert journal_store.RECOVERY_HOLD_CODES == PLAN_RECOVERY_HOLD_CODES


@pytest.mark.parametrize("code", sorted(PLAN_RECOVERY_HOLD_CODES))
def test_c13_every_recovery_code_persists_and_reads_back(tmp_path, base_image, code):
    directory = copy_image(base_image, tmp_path)
    store = _open(directory)
    try:
        assert store.persist_hold(code, boot_id="boot-hold") is True
    finally:
        store.close()
    reopened = _open(directory)
    try:
        assert reopened.finding == journal_store.Finding(code, "recovery", None)
        assert reopened.anchor.hold.code == code
    finally:
        reopened.close()


@pytest.mark.parametrize("char", ["?", "#", "%"])
def test_c2_create_refuses_uri_reserved_directory_names(tmp_path, char):
    parent = new_dir(tmp_path, "parent")
    directory = parent / f"j{char}x"
    directory.mkdir(mode=0o700)
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "journal_path_invalid"
    assert [path.name for path in parent.iterdir()] == [directory.name]
    assert list(directory.iterdir()) == []


def test_c3_open_refuses_uri_reserved_directory_names(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path, name="j?x")
    before = _file_bytes(directory)
    with pytest.raises(journal_store.StoreError) as excinfo:
        _open(directory)
    assert excinfo.value.code == "journal_path_invalid"
    assert [path.name for path in tmp_path.iterdir()] == ["j?x"]
    assert _file_bytes(directory) == before


def test_c3_connection_to_any_other_file_is_refused(tmp_path, base_image, monkeypatch):
    directory = copy_image(base_image, tmp_path)
    decoy = copy_image(base_image, tmp_path, name="decoy")
    real_connect = sqlite3.connect

    def redirecting_connect(database, *args, **kwargs):
        return real_connect(database.replace(str(directory), str(decoy)), *args, **kwargs)

    monkeypatch.setattr(journal_store.sqlite3, "connect", redirecting_connect)
    with pytest.raises(journal_store.StoreError) as excinfo:
        _open(directory)
    assert excinfo.value.code == "journal_path_invalid"
    monkeypatch.undo()
    _assert_opens_ready(directory)  # the lock was released


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-0000 file")
def test_e13_unreadable_wal_is_a_process_finding(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    wal_path = directory / journal_store.WAL_FILENAME
    os.chmod(wal_path, 0)
    try:
        store = _open(directory)
        try:
            assert store.finding == OPEN_FAILED
        finally:
            store.close()
    finally:
        os.chmod(wal_path, 0o600)
    _assert_opens_ready(directory)


@pytest.mark.parametrize("error", [
    OSError(errno.EIO, "Input/output error"), _fake_error(522, "SQLITE_IOERR_SHORT_READ"),
])
def test_e13_transient_connect_failure_is_a_process_finding(
    tmp_path, base_image, monkeypatch, error,
):
    directory = copy_image(base_image, tmp_path)
    before = _file_bytes(directory)

    def failing_connect(self):
        raise error

    monkeypatch.setattr(journal_store.JournalStore, "_connect", failing_connect)
    store = _open(directory)
    try:
        assert (store.finding.code, store.finding.scope) == ("journal_open_failed", "process")
    finally:
        store.close()
    monkeypatch.undo()
    assert _file_bytes(directory) == before
    _assert_opens_ready(directory)


def test_e13_sqlite_error_in_the_genesis_check_is_classified(tmp_path, base_image, monkeypatch):
    directory = copy_image(base_image, tmp_path)

    def failing_check(cursor, anchor_journal_uuid):
        raise _fake_error(11, "SQLITE_CORRUPT")

    monkeypatch.setattr(journal_store, "_genesis_uuid_conflicts", failing_check)
    store = _open(directory)
    try:
        assert (store.finding.code, store.finding.scope) == ("journal_corrupt", "recovery")
    finally:
        store.close()


def test_open_releases_the_lock_on_an_unexpected_exception(tmp_path, base_image, monkeypatch):
    directory = copy_image(base_image, tmp_path)

    def exploding_read_anchor(self):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(journal_store.JournalStore, "_read_anchor", exploding_read_anchor)
    with pytest.raises(RuntimeError):
        _open(directory)
    monkeypatch.undo()
    _assert_opens_ready(directory)


@pytest.mark.parametrize("body", [b"[]", b"12", b"null", b'"x"'])
def test_verified_non_object_body_is_process_schema_unsupported(body):
    digest = hashlib.sha256(b"rj.record.v1\x00" + body).hexdigest()
    row = (1, "genesis", "journal_genesis", body, digest)
    assert journal_store._verify_row(row, None, set()) == (None, SCHEMA_UNSUPPORTED)


def test_resigned_row_with_an_invalid_source_is_process_schema_unsupported():
    factory = Factory(str(uuid.uuid4()))
    genesis = factory.genesis()
    admission, _dedupe = factory.admission_pair("fp1")
    row = _resigned_row(_bad_source_admission(admission), 2, admission.event_id, "admission")
    assert journal_store._verify_row(row, genesis, {genesis.event_id}) == (
        None, SCHEMA_UNSUPPORTED,
    )


def test_malformed_prev_record_digest_is_process_not_chain_broken():
    factory = Factory(str(uuid.uuid4()))
    genesis = factory.genesis()
    admission, _dedupe = factory.admission_pair("fp1")
    envelope = json.loads(admission.body)
    envelope["prev_record_digest"] = "A" * 64
    row = _resigned_row(envelope, 2, admission.event_id, "admission")
    assert journal_store._verify_row(row, genesis, {genesis.event_id}) == (
        None, SCHEMA_UNSUPPORTED,
    )


def test_sqlite_error_during_the_row_scan_is_classified(tmp_path, base_image, monkeypatch):
    directory = copy_image(base_image, tmp_path)
    store = _open(directory)
    try:
        monkeypatch.setattr(journal_store, "_SELECT_ROWS_SQL", "SELECT nope FROM journal_events")
        assert list(store.rows()) == []
        assert (store.finding.code, store.finding.scope) == ("journal_open_failed", "process")
    finally:
        store.close()


class _OneRowCursor:
    def __init__(self, row: tuple) -> None:
        self._row = row

    def execute(self, *_args):
        return self

    def fetchone(self) -> tuple:
        return self._row


def test_genesis_check_leaves_an_undecodable_first_row_to_the_pipeline():
    factory = Factory(str(uuid.uuid4()))
    factory.genesis()
    admission, _dedupe = factory.admission_pair("fp1")
    _, _, _, body, digest = _resigned_row(_bad_source_admission(admission), 1, "x", "admission")
    cursor = _OneRowCursor(("journal_genesis", body, digest))
    assert journal_store._genesis_uuid_conflicts(cursor, str(uuid.uuid4())) is False


def test_c9_undecodable_stored_body_is_a_conflict(tmp_path):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    admission, dedupe = factory.admission_pair("fp1")
    store.close()
    forged = _resigned_row(_bad_source_admission(admission), 2, admission.event_id, "admission")
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("INSERT INTO journal_events VALUES (?, ?, ?, ?, ?)", forged)
        raw.execute(
            "INSERT INTO journal_events VALUES (?, ?, ?, ?, ?)",
            (3, dedupe.event_id, dedupe.event_type, dedupe.body, dedupe.record_digest),
        )
        raw.commit()
    finally:
        raw.close()
    reopened = _open(directory)
    try:
        with pytest.raises(journal_store.StoreError) as excinfo:
            reopened.find_duplicate([admission, dedupe])
        assert excinfo.value.code == "store_event_conflict"
    finally:
        reopened.close()


def _fail_lstat_for(monkeypatch, target: Path) -> None:
    real_lstat = os.lstat

    def failing_lstat(path, *args, **kwargs):
        if Path(path) == target:
            raise OSError(errno.EIO, "Input/output error")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(journal_store.os, "lstat", failing_lstat)


@pytest.mark.parametrize("filename", [journal_store.DB_FILENAME, journal_store.WAL_FILENAME])
def test_transient_lstat_error_is_process_not_absent(tmp_path, base_image, monkeypatch, filename):
    directory = copy_image(base_image, tmp_path)
    _fail_lstat_for(monkeypatch, directory / filename)
    store = _open(directory)
    try:
        assert store.finding == OPEN_FAILED
        assert store.wal_found is None
    finally:
        store.close()


def test_c13_writer_refuses_to_erase_a_persisted_verdict(tmp_path):
    directory, journal_uuid, factory, store = create_store(tmp_path)
    try:
        store.persist_hold("journal_truncated", boot_id="boot-hold")
        head = store.anchor.head
        pair = list(factory.admission_pair("fp1"))
        refused = (
            lambda: store.write_anchor(head), lambda: store.write_anchor(head),
            store.finish_open, lambda: store.append(pair),
            lambda: store._write_slot(journal_store._anchor_body(journal_uuid, head, None)),
        )
        for call in refused:
            with pytest.raises(journal_store.StoreError) as excinfo:
                call()
            assert excinfo.value.code == "store_write_failed"
        assert store.anchor.hold.code == "journal_truncated"
    finally:
        store.close()
    reopened = _open(directory)
    try:
        assert reopened.finding.code == "journal_truncated"
    finally:
        reopened.close()


def test_writes_are_refused_while_a_finding_holds(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA user_version=2")
        raw.commit()
    finally:
        raw.close()
    anchor_before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
    store = _open(directory)
    try:
        assert store.finding == SCHEMA_UNSUPPORTED
        for call in (lambda: store.write_anchor(store.anchor.head), store.finish_open):
            with pytest.raises(journal_store.StoreError) as excinfo:
                call()
            assert excinfo.value.code == "store_write_failed"
    finally:
        store.close()
    assert (directory / journal_store.ANCHOR_FILENAME).read_bytes() == anchor_before


@pytest.mark.parametrize("size", [0, 100])
def test_db_shorter_than_a_page_is_truncated_and_the_wal_kept(tmp_path, base_image, size):
    directory = copy_image(base_image, tmp_path)
    with open(directory / journal_store.DB_FILENAME, "r+b") as handle:
        handle.truncate(size)
    before = _file_bytes(directory)
    assert len(before[journal_store.WAL_FILENAME]) > 0
    store = _open(directory)
    try:
        assert store.finding == journal_store.Finding("journal_truncated", "recovery", None)
        assert store._connection is None
    finally:
        store.close()
    assert _file_bytes(directory) == before


def test_c14_sqlite_below_the_minimum_version_is_refused(tmp_path, monkeypatch):
    directory = new_dir(tmp_path)
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    monkeypatch.setattr(journal_store.sqlite3, "sqlite_version_info", (3, 36, 0))
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "sqlite_unsupported"
    with pytest.raises(journal_store.StoreError) as excinfo:
        _open(directory)
    assert excinfo.value.code == "sqlite_unsupported"
    assert list(directory.iterdir()) == []


# Anchor codec: slot validity.

ANCHOR_UUID = "22222222-2222-2222-2222-222222222222"
ANCHOR_HEAD = {"commit_seq": 1, "event_seq": 1, "generation": 1, "record_digest": "a" * 64}
ANCHOR_HOLD = {"boot_id": "boot-1", "code": "journal_corrupt", "observed_commit_seq": None}


def _v1_body(counter: int = 1, **overrides) -> dict:
    body = {
        "counter": counter, "format": "rj.anchor.v1", "journal_uuid": ANCHOR_UUID,
        "head": dict(ANCHOR_HEAD), "hold": None,
    }
    body.update(overrides)
    return body


def _raw_slot(payload: bytes) -> bytes:
    header = journal_store.ANCHOR_MAGIC + struct.pack(">I", len(payload))
    slot = header + payload + hashlib.sha256(header + payload).digest()
    return slot + b"\x00" * (journal_store.ANCHOR_SLOT_BYTES - len(slot))


INVALID_V1_BODIES = {
    "unhashable hold code": _v1_body(hold=dict(ANCHOR_HOLD, code={"not": "hashable"})),
    "integer hold code": _v1_body(hold=dict(ANCHOR_HOLD, code=7)),
    "hold not an object": _v1_body(hold="held"),
    "free-text boot_id": _v1_body(hold=dict(ANCHOR_HOLD, boot_id="free text")),
    "negative observed_commit_seq": _v1_body(hold=dict(ANCHOR_HOLD, observed_commit_seq=-1)),
    "non-uuid journal_uuid": _v1_body(journal_uuid="not-a-uuid"),
    "uppercase journal_uuid": _v1_body(journal_uuid=ANCHOR_UUID.replace("2", "A")),
    "generation 0": _v1_body(head=dict(ANCHOR_HEAD, generation=0)),
    "generation 2**31": _v1_body(head=dict(ANCHOR_HEAD, generation=2**31)),
    "commit_seq 0": _v1_body(head=dict(ANCHOR_HEAD, commit_seq=0)),
    "event_seq 0": _v1_body(head=dict(ANCHOR_HEAD, event_seq=0)),
    "string commit_seq": _v1_body(head=dict(ANCHOR_HEAD, commit_seq="1")),
    "head not an object": _v1_body(head=[1]),
    "counter 0": _v1_body(counter=0),
}


@pytest.mark.parametrize("name", sorted(INVALID_V1_BODIES))
def test_c6_invalid_v1_slot_makes_the_anchor_invalid(name):
    body = INVALID_V1_BODIES[name]
    slot = journal_store._encode_slot(body)
    raw = _anchor_bytes(slot, None) if body["counter"] == 0 else _anchor_bytes(None, slot)
    assert journal_store._analyze_anchor(raw) == (
        None, journal_store.Finding("journal_anchor_invalid", "recovery", None),
    )


def test_c6_invalid_slot_on_disk_is_a_finding_and_releases_the_lock(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    slot = journal_store._encode_slot(INVALID_V1_BODIES["unhashable hold code"])
    anchor = _anchor_bytes(None, slot)
    (directory / journal_store.ANCHOR_FILENAME).write_bytes(anchor)
    store = _open(directory)
    try:
        assert store.finding.code == "journal_anchor_invalid"
    finally:
        store.close()
    assert (directory / journal_store.ANCHOR_FILENAME).read_bytes() == anchor


def test_c6_non_canonical_slot_is_not_intact():
    payload = json.dumps(
        _v1_body(counter=2, head=dict(ANCHOR_HEAD, commit_seq=2)),
        sort_keys=True, separators=(", ", ": "),
    ).encode("ascii")
    raw = _anchor_bytes(_raw_slot(payload), journal_store._encode_slot(_v1_body(counter=1)))
    state, finding = journal_store._analyze_anchor(raw)
    assert finding is None
    assert state.counter == 1


@pytest.mark.parametrize("newest,offset", [(2, 2_000), (3, 8_000)])
def test_c6_nonzero_padding_up_to_the_next_slot_is_not_intact(newest, offset):
    # The newest slot's region (slot 0 for an even counter, slot 1 for an odd
    # one) carries a stray byte after its 1,024 bytes: only the older survives.
    slots = {
        counter: journal_store._encode_slot(
            _v1_body(counter=counter, head=dict(ANCHOR_HEAD, commit_seq=counter)),
        )
        for counter in (newest - 1, newest)
    }
    raw = bytearray(_anchor_bytes(*(slots[c] for c in sorted(slots, key=lambda c: c % 2))))
    raw[offset] = 1
    state, finding = journal_store._analyze_anchor(bytes(raw))
    assert finding is None
    assert state.counter == newest - 1


# find_duplicate: exactly one stored commit.


def test_c9_part_of_a_stored_commit_is_a_conflict(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.find_duplicate([admission])
        assert excinfo.value.code == "store_event_conflict"
    finally:
        store.close()


def test_c9_records_from_different_commits_are_a_conflict(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        _admission1, dedupe1 = pair1 = factory.admission_pair("fp1")
        _admission2, dedupe2 = pair2 = factory.admission_pair("fp2")
        store.append(list(pair1))
        store.append(list(pair2))
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.find_duplicate([dedupe1, dedupe2])
        assert excinfo.value.code == "store_event_conflict"
    finally:
        store.close()


# Error custody and write failures.


def test_store_except_bodies_only_assign_and_never_raise():
    tree = ast.parse(Path(journal_store.__file__).read_text(encoding="utf-8"))
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert handlers
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), handler.lineno
        assert not any(isinstance(inner, ast.Raise) for inner in ast.walk(handler)), handler.lineno


def test_c2_refusal_carries_no_chained_exception(tmp_path):
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    with pytest.raises(journal_store.StoreError) as excinfo:
        journal_store.JournalStore.create(tmp_path / "missing", genesis, journal_uuid=journal_uuid)
    assert excinfo.value.code == "journal_path_invalid"
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None


def _failing_sync(fd: int) -> None:
    raise OSError(errno.EIO, "Input/output error")


@pytest.mark.parametrize("operation", ["write_anchor", "persist_hold"])
def test_failed_anchor_write_latches_the_store(tmp_path, monkeypatch, operation):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        monkeypatch.setattr(journal_store, "_full_sync", _failing_sync)
        with pytest.raises(journal_store.StoreError) as excinfo:
            if operation == "write_anchor":
                store.write_anchor(store.anchor.head)
            else:
                store.persist_hold("journal_corrupt", boot_id="boot-hold")
        assert excinfo.value.code == "store_write_failed"
        assert excinfo.value.__context__ is None
        monkeypatch.undo()
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.append(list(factory.admission_pair("fp1")))
        assert excinfo.value.code == "store_write_failed"
    finally:
        store.close()


def test_c13_crash_between_hold_slots_is_completed_by_the_next_persist(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    real_write_slot = journal_store.JournalStore._write_slot
    calls = {"n": 0}

    def crashing_write_slot(self, body):
        calls["n"] += 1
        if calls["n"] == 2:
            raise SimulatedCrash
        real_write_slot(self, body)

    store._write_slot = crashing_write_slot.__get__(store, journal_store.JournalStore)
    with pytest.raises(SimulatedCrash):
        store.persist_hold("journal_corrupt", boot_id="boot-hold")
    store.close()

    reopened = _open(directory)
    try:
        assert reopened.finding.code == "journal_corrupt"
        assert reopened.persist_hold("journal_corrupt", boot_id="boot-later") is True
        assert reopened.persist_hold("journal_corrupt", boot_id="boot-later") is False
    finally:
        reopened.close()
    bodies = journal_store._slot_bodies((directory / journal_store.ANCHOR_FILENAME).read_bytes())
    assert [(body["hold"]["code"], body["hold"]["boot_id"]) for body in bodies] == [
        ("journal_corrupt", "boot-hold"), ("journal_corrupt", "boot-hold"),
    ]


def test_append_checks_records_before_begin(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        forged = dataclasses.replace(dedupe, record_digest="0" * 64)
        for records in ([admission, object()], [admission, forged], [], "not a list"):
            with pytest.raises(journal_store.StoreError) as excinfo:
                store.append(records)
            assert excinfo.value.code == "journal_argument"
            assert not store._connection.in_transaction
        count = store._connection.execute("SELECT count(*) FROM journal_events").fetchone()[0]
        assert count == 1
        assert store.append([admission, dedupe]) == (2, 3)
    finally:
        store.close()


def test_find_duplicate_refuses_on_a_broken_store(tmp_path, monkeypatch):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        monkeypatch.setattr(journal_store, "_full_sync", _failing_sync)
        with pytest.raises(journal_store.StoreError):
            store.append([admission, dedupe])
        monkeypatch.undo()
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.find_duplicate([admission, dedupe])
        assert excinfo.value.code == "store_write_failed"
    finally:
        store.close()


def test_verified_head_advances_only_once_the_caller_resumes_past_a_commit(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    store = _open(directory)
    try:
        rows = store.rows()
        genesis = next(rows)
        assert store.verified_head is None
        next(rows)
        genesis_head = journal_store._record_head(genesis)
        assert store.verified_head == genesis_head
        dedupe = next(rows)
        assert store.verified_head == genesis_head
        assert next(rows, None) is None
        assert store.verified_head == journal_store._record_head(dedupe)
    finally:
        store.close()


def test_open_reads_back_journal_size_limit_and_query_only(tmp_path, base_image, monkeypatch):
    directory = copy_image(base_image, tmp_path)
    statements: list[str] = []
    real_connect = journal_store.JournalStore._connect

    def tracing_connect(self):
        connection = real_connect(self)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(journal_store.JournalStore, "_connect", tracing_connect)
    store = _open(directory)
    try:
        assert store.finding is None
    finally:
        store.close()
    assert "PRAGMA journal_size_limit" in statements
    assert "PRAGMA query_only" in statements


# =================================================================================
# Unit 15a gap coverage (independent mutation review, G1-G7; G8 fixed test above).
# =================================================================================


# --- G1: the row-verification pipeline -------------------------------------------


def _g1_wrong_resigned_prev_digest(genesis, admission, _dedupe):
    envelope = json.loads(admission.body)
    envelope["prev_record_digest"] = "b" * 64  # valid hex64, but not genesis's digest
    row = _resigned_row(
        envelope, admission.position.event_seq, admission.event_id, admission.event_type,
    )
    return row, genesis, {genesis.event_id}


def _g1_stale_digest_column(genesis, admission, _dedupe):
    stale_digest = "c" * 64  # well-formed hex64 that does not hash the real body
    row = (
        admission.position.event_seq, admission.event_id, admission.event_type,
        admission.body, stale_digest,
    )
    return row, genesis, {genesis.event_id}


def _g1_repeated_event_id(genesis, admission, _dedupe):
    row = (
        admission.position.event_seq, admission.event_id, admission.event_type,
        admission.body, admission.record_digest,
    )
    return row, genesis, {admission.event_id}  # already seen earlier in the same scan


def _g1_mismatched_event_type_column(genesis, admission, _dedupe):
    row = (
        admission.position.event_seq, admission.event_id, "dedupe_decision",
        admission.body, admission.record_digest,
    )
    return row, genesis, {genesis.event_id}


@pytest.mark.parametrize(
    "build,expected",
    [
        (_g1_wrong_resigned_prev_digest, "journal_chain_broken"),
        (_g1_stale_digest_column, "journal_record_invalid"),
        (_g1_repeated_event_id, "journal_event_conflict"),
        (_g1_mismatched_event_type_column, "journal_record_invalid"),
    ],
    ids=["wrong_prev_digest", "stale_digest_column", "repeated_event_id", "mismatched_event_type"],
)
def test_g1_verify_row_pipeline_cases(build, expected):
    factory = Factory(str(uuid.uuid4()))
    genesis = factory.genesis()
    admission, dedupe = factory.admission_pair("fp1")
    row, previous, seen_ids = build(genesis, admission, dedupe)
    record, finding = journal_store._verify_row(row, previous, seen_ids)
    assert record is None
    assert finding.code == expected
    assert finding.scope == "recovery"


def test_g1_resigned_body_update_breaks_chain_end_to_end(tmp_path, base_image):
    directory = copy_image(base_image, tmp_path)
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("DROP TRIGGER journal_events_no_update")
        event_seq, body = raw.execute(
            "SELECT event_seq, body FROM journal_events WHERE event_type = 'admission'"
        ).fetchone()
        envelope = json.loads(bytes(body))
        envelope["data"]["arrival_seq"] = 2  # any other still-valid value; re-signed below
        new_body = canonical_json(envelope, ascii_only=True)
        new_digest = hashlib.sha256(b"rj.record.v1\x00" + new_body).hexdigest()
        raw.execute(
            "UPDATE journal_events SET body = ?, record_digest = ? WHERE event_seq = ?",
            (new_body, new_digest, event_seq),
        )
        raw.commit()
        # Recreate the trigger with the plan's exact DDL, so the schema still matches at open.
        raw.execute(journal_store.SCHEMA_SQL[1])
        raw.commit()
    finally:
        raw.close()

    store = journal_store.JournalStore.open(directory)
    try:
        assert store.finding is None
        list(store.rows())  # drain; the dedupe row's prev_record_digest now points nowhere
        assert store.finding.code == "journal_chain_broken"
        assert store.finding.scope == "recovery"
    finally:
        store.close()


# --- G2: find_duplicate compares content, not just event_ids ---------------------


def _forged_pair_same_ids(admission, dedupe, fingerprint: str) -> tuple:
    """A self-consistent admission/dedupe pair reusing ``admission``/``dedupe``'s event_ids
    and positions, but content built from a different fingerprint."""
    forged_source = SourceRecord(
        source_group="a" * 64,
        alerts=(SourceAlert(fingerprint=fingerprint, status="firing", values=None, starts_at=None),),
        truncated_alerts=0, body_digest="b" * 64, provenance=HTTP_PROVENANCE,
    )
    admission_id = admission.ids["admission_id"]
    forged_admission = seal(
        Draft(
            event_id=admission.event_id, event_type="admission", actor="receiver",
            ids={"admission_id": admission_id},
            data={"arrival_seq": 1, "decision": "admitted", "dispatch_holds": (),
                  "source": source_to_json(forged_source), "source_digest": source_digest(forged_source)},
        ),
        admission.position, admission.stamp,
    )
    key = hashlib.sha256(fingerprint.encode("ascii")).hexdigest()
    forged_dedupe = seal(
        Draft(
            event_id=dedupe.event_id, event_type="dedupe_decision", actor="receiver",
            ids={"admission_id": admission_id},
            data={"rule": "latest-admitted-v1", "result": "admitted", "source_group": "a" * 64,
                  "dedupe_key": key, "baseline_before": None,
                  "baseline_after": {"admission_id": admission_id, "complete": True, "dedupe_key": key},
                  "superseded": (), "pending_count_after": 1},
        ),
        dedupe.position, dedupe.stamp,
    )
    return forged_admission, forged_dedupe


def test_g2_find_duplicate_detects_differing_content_at_the_same_event_ids(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        counter_before = store.anchor.counter
        count_before = store._connection.execute("SELECT count(*) FROM journal_events").fetchone()[0]

        forged_admission, forged_dedupe = _forged_pair_same_ids(admission, dedupe, "fp2")
        assert forged_admission.event_id == admission.event_id
        assert forged_dedupe.event_id == dedupe.event_id

        with pytest.raises(journal_store.StoreError) as excinfo:
            store.find_duplicate([forged_admission, forged_dedupe])
        assert excinfo.value.code == "store_event_conflict"

        assert store.anchor.counter == counter_before
        count_after = store._connection.execute("SELECT count(*) FROM journal_events").fetchone()[0]
        assert count_after == count_before
    finally:
        store.close()


# --- G3: the WAL is kept across reopen, ready or held -----------------------------


def test_g3_no_ckpt_on_close_keeps_wal_bytes_ready_and_held(tmp_path, base_image):
    # Ready open: closing must not checkpoint or otherwise touch the DB/WAL bytes.
    ready_dir = copy_image(base_image, tmp_path, name="ready")
    db_before = (ready_dir / journal_store.DB_FILENAME).read_bytes()
    wal_before = (ready_dir / journal_store.WAL_FILENAME).read_bytes()
    store = journal_store.JournalStore.open(ready_dir)
    try:
        assert store.finding is None
        assert store._connection.getconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE) is True
    finally:
        store.close()
    assert (ready_dir / journal_store.DB_FILENAME).read_bytes() == db_before
    assert (ready_dir / journal_store.WAL_FILENAME).read_bytes() == wal_before

    # Held open (a dropped trigger still leaves a live connection): same guarantee.
    held_dir = copy_image(base_image, tmp_path, name="held")
    raw = sqlite3.connect(str(held_dir / journal_store.DB_FILENAME))
    try:
        # Closing the last connection to a WAL-mode db normally checkpoints and
        # deletes the WAL; set the same dbconfig the store uses so this raw
        # tampering connection leaves the WAL as the held open below will find it.
        raw.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        raw.execute("DROP TRIGGER journal_events_no_update")
        raw.commit()
    finally:
        raw.close()
    db_before_held = (held_dir / journal_store.DB_FILENAME).read_bytes()
    wal_before_held = (held_dir / journal_store.WAL_FILENAME).read_bytes()
    held_store = journal_store.JournalStore.open(held_dir)
    try:
        assert held_store.finding.code == "journal_schema_invalid"
        assert held_store._connection is not None
        assert held_store._connection.getconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE) is True
    finally:
        held_store.close()
    assert (held_dir / journal_store.DB_FILENAME).read_bytes() == db_before_held
    assert (held_dir / journal_store.WAL_FILENAME).read_bytes() == wal_before_held


# --- G4: write ordering, including the pwrite itself ------------------------------


def _fd_kind(fd: int, anchor_path: Path, directory_path: Path) -> str:
    try:
        current = os.fstat(fd)
    except OSError:
        return "other"
    # In create(), the directory sync right after COMMIT happens before the
    # anchor file exists, so a missing target (not yet created) is not a match.
    for kind, target in (("anchor", anchor_path), ("dir", directory_path)):
        try:
            if os.path.samestat(current, os.stat(target)):
                return kind
        except OSError:
            continue
    return "other"


def _instrument_writes(
    monkeypatch, anchor_path: Path, directory_path: Path, connection: sqlite3.Connection | None = None,
) -> list:
    """Tag every COMMIT, pwrite and full-sync by fd kind, in call order.

    ``connection`` is the store's already-open connection, for an ``append()``
    on an already-created store (``_connect`` will not run again). Left
    ``None`` for a fresh ``create()``, where patching ``_connect`` is enough.
    """
    order: list = []
    real_connect = journal_store.JournalStore._connect
    real_pwrite = os.pwrite
    real_fcntl = fcntl.fcntl
    real_fsync = os.fsync

    def trace(sql: str) -> None:
        if sql.strip() == "COMMIT":
            order.append("commit")

    if connection is not None:
        connection.set_trace_callback(trace)

    def tracing_connect(self):
        connection = real_connect(self)
        connection.set_trace_callback(trace)
        return connection

    def recording_pwrite(fd, data, offset):
        order.append(f"pwrite:{_fd_kind(fd, anchor_path, directory_path)}")
        return real_pwrite(fd, data, offset)

    def recording_fcntl(fd, request, *args):
        if request == fcntl.F_FULLFSYNC:
            order.append(f"sync:{_fd_kind(fd, anchor_path, directory_path)}")
        return real_fcntl(fd, request, *args)

    def recording_fsync(fd):
        order.append(f"sync:{_fd_kind(fd, anchor_path, directory_path)}")
        return real_fsync(fd)

    monkeypatch.setattr(journal_store.JournalStore, "_connect", tracing_connect)
    monkeypatch.setattr(os, "pwrite", recording_pwrite)
    if sys.platform == "darwin":
        monkeypatch.setattr(fcntl, "fcntl", recording_fcntl)
    else:
        monkeypatch.setattr(os, "fsync", recording_fsync)
    return order


@darwin_only
def test_g4_append_write_order_without_directory_sync(tmp_path, monkeypatch):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        order = _instrument_writes(monkeypatch, store.anchor_path, directory, store._connection)
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        assert order == ["commit", "pwrite:anchor", "sync:anchor"]
    finally:
        monkeypatch.undo()
        store.close()


@darwin_only
def test_g4_append_write_order_with_directory_sync(tmp_path, monkeypatch):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        order = _instrument_writes(monkeypatch, store.anchor_path, directory, store._connection)
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe], sync_directory=True)
        assert order == ["commit", "sync:dir", "pwrite:anchor", "sync:anchor"]
    finally:
        monkeypatch.undo()
        store.close()


@darwin_only
def test_g4_create_write_order(tmp_path, monkeypatch):
    directory = new_dir(tmp_path)
    journal_uuid = str(uuid.uuid4())
    genesis = Factory(journal_uuid).genesis()
    anchor_path = directory / journal_store.ANCHOR_FILENAME
    order = _instrument_writes(monkeypatch, anchor_path, directory)
    store = journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    try:
        # Genesis: COMMIT; sync the directory; write+sync the anchor; sync the directory again.
        assert order == ["commit", "sync:dir", "pwrite:anchor", "sync:anchor", "sync:dir"]
    finally:
        monkeypatch.undo()
        store.close()


@linux_only
def test_g4_append_write_order_without_directory_sync_linux(tmp_path, monkeypatch):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        order = _instrument_writes(monkeypatch, store.anchor_path, directory, store._connection)
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        assert order == ["commit", "pwrite:anchor", "sync:anchor"]
    finally:
        monkeypatch.undo()
        store.close()


# --- G5: anchor codec reach --------------------------------------------------------


def test_g5_stale_newer_payload_without_checksum_update_falls_back():
    journal_uuid = str(uuid.uuid4())
    older = _slot(journal_uuid, counter=1, commit_seq=1)
    newer = bytearray(_slot(journal_uuid, counter=2, commit_seq=2))
    length = struct.unpack(">I", bytes(newer[8:12]))[0]
    payload = bytes(newer[12:12 + length])
    assert b'"commit_seq":2' in payload
    mutated = payload.replace(b'"commit_seq":2', b'"commit_seq":3')
    assert len(mutated) == len(payload)  # stays ASCII, same length; checksum left stale
    newer[12:12 + length] = mutated
    raw = _anchor_bytes(bytes(newer), older)
    state, finding = journal_store._analyze_anchor(raw)
    assert finding is None
    assert state.counter == 1  # fell back to the older, still-intact slot


def test_g5_lone_slot_wrong_parity_is_anchor_invalid():
    journal_uuid = str(uuid.uuid4())
    # counter=1 belongs at slot index 1 (offset 4096); placing it at index 0 is wrong parity.
    raw = _anchor_bytes(_slot(journal_uuid, counter=1), None)
    state, finding = journal_store._analyze_anchor(raw)
    assert state is None
    assert finding.code == "journal_anchor_invalid"
    assert finding.scope == "recovery"


def test_g5_anchor_read_io_error_gives_process_open_failed(tmp_path, base_image, monkeypatch):
    directory = copy_image(base_image, tmp_path)
    before = _file_bytes(directory)
    real_read = os.read

    def failing_read(fd, n):
        if n == journal_store.ANCHOR_BYTES + 1:  # the anchor read's own request size
            raise OSError(errno.EIO, "Input/output error")
        return real_read(fd, n)

    monkeypatch.setattr(journal_store.os, "read", failing_read)
    store = journal_store.JournalStore.open(directory)
    try:
        assert (store.finding.code, store.finding.scope) == ("journal_open_failed", "process")
    finally:
        store.close()
    monkeypatch.undo()
    assert _file_bytes(directory) == before


# --- G6: exact DDL golden -----------------------------------------------------------

# Copied verbatim from the plan's "Schema (exact DDL)" section. The source's SCHEMA_SQL
# splits the same four statements without trailing semicolons; content is identical.
SCHEMA_SQL_GOLDEN = (
    (
        "CREATE TABLE journal_events (\n"
        "  event_seq     INTEGER PRIMARY KEY CHECK (event_seq >= 1),\n"
        "  event_id      TEXT NOT NULL UNIQUE CHECK (length(event_id) BETWEEN 1 AND 128),\n"
        "  event_type    TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 64),\n"
        "  body          BLOB NOT NULL CHECK (length(body) BETWEEN 2 AND 16384),\n"
        "  record_digest TEXT NOT NULL UNIQUE CHECK (length(record_digest) = 64)\n"
        ") STRICT"
    ),
    (
        "CREATE TRIGGER journal_events_no_update BEFORE UPDATE ON journal_events\n"
        "  BEGIN SELECT RAISE(ABORT, 'append_only'); END"
    ),
    (
        "CREATE TRIGGER journal_events_no_delete BEFORE DELETE ON journal_events\n"
        "  BEGIN SELECT RAISE(ABORT, 'append_only'); END"
    ),
    (
        "CREATE TRIGGER journal_events_contiguous BEFORE INSERT ON journal_events\n"
        "  WHEN NEW.event_seq != (SELECT coalesce(max(event_seq), 0) + 1 FROM journal_events)\n"
        "  BEGIN SELECT RAISE(ABORT, 'event_seq'); END"
    ),
)


def test_g6_schema_sql_matches_the_plan_ddl_golden():
    assert journal_store.SCHEMA_SQL == SCHEMA_SQL_GOLDEN


def test_g6_noncontiguous_event_seq_insert_aborts(tmp_path):
    _directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="event_seq"):
            store._connection.execute(
                "INSERT INTO journal_events (event_seq, event_id, event_type, body, record_digest) "
                "VALUES (?, ?, ?, ?, ?)",
                (3, "bogus", "admission", b'{"x":1}', "d" * 64),
            )
    finally:
        store.close()


# --- G7: root fixes just made -------------------------------------------------------


class _FailingSelectConnection:
    """Delegates to a real connection, but raises on find_duplicate's own SELECT."""

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real

    def execute(self, sql, *args):
        if sql.startswith("SELECT event_seq, event_id, body FROM"):
            raise sqlite3.OperationalError("synthetic select failure")
        return self._real.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_g7_find_duplicate_select_failure_latches_broken(tmp_path):
    _directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        admission, dedupe = factory.admission_pair("fp1")
        store.append([admission, dedupe])
        store._connection = _FailingSelectConnection(store._connection)

        with pytest.raises(journal_store.StoreError) as excinfo:
            store.find_duplicate([admission, dedupe])
        assert excinfo.value.code == "store_write_failed"
        assert excinfo.value.__cause__ is None
        assert excinfo.value.__context__ is None

        with pytest.raises(journal_store.StoreError) as excinfo:
            store.append(list(factory.admission_pair("fp2")))
        assert excinfo.value.code == "store_write_failed"
    finally:
        store.close()


def test_g7_finish_open_query_only_failure_latches_broken(tmp_path, base_image, monkeypatch):
    directory = copy_image(base_image, tmp_path)
    store = _open(directory)
    try:
        assert store.finding is None

        def failing_set_pragma(cursor, name, value, expected):
            if name == "query_only":
                raise sqlite3.OperationalError("synthetic query_only failure")

        monkeypatch.setattr(journal_store, "_set_pragma", failing_set_pragma)
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.finish_open()
        assert excinfo.value.code == "store_write_failed"
        monkeypatch.undo()

        with pytest.raises(journal_store.StoreError) as excinfo:
            store.write_anchor(store.anchor.head)
        assert excinfo.value.code == "store_write_failed"
    finally:
        store.close()


# === Unit 15a review gaps: durability settings, anchor checks, and more =====
#
# G1 (blocking): the connection settings table ("each set, then read back")
# was never asserted against the live connection, on either a freshly
# created or a reopened store.

DURABILITY_PRAGMAS = (
    ("synchronous", 2),
    ("fullfsync", 1),
    ("checkpoint_fullfsync", 1),
    ("trusted_schema", 0),
    ("cell_size_check", 1),
    ("max_page_count", journal_store.MAX_PAGE_COUNT),
    ("journal_size_limit", journal_store.JOURNAL_SIZE_LIMIT),
    ("wal_autocheckpoint", journal_store.WAL_AUTOCHECKPOINT_PAGES),
    ("locking_mode", "exclusive"),
    ("journal_mode", "wal"),
    ("page_size", journal_store.PAGE_SIZE),
)


def _assert_durability_pragmas(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    for name, expected in DURABILITY_PRAGMAS:
        actual = cursor.execute(f"PRAGMA {name}").fetchone()[0]
        assert actual == expected, f"PRAGMA {name}: expected {expected!r}, got {actual!r}"


def test_durability_settings_read_back_on_created_store(tmp_path):
    _directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        _assert_durability_pragmas(store._connection)
    finally:
        store.close()


def test_durability_settings_read_back_on_reopened_store(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    store.close()
    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.finding is None
        _assert_durability_pragmas(reopened._connection)
    finally:
        reopened.close()


# --- G2: two anchor-analysis checks that had no isolating test -------------
#
# `test_c6_invalid_anchor_variants` already isolates the counter-gap and
# newer-has-no-hold checks. These two isolate the remaining pair of
# comparisons in the same `or` chain: with everything else held valid
# (matching journal_uuid, a counter gap of 1, no hold on either slot), only
# the check under test can be the reason the anchor is invalid.


def test_c6_newer_head_behind_older_is_invalid():
    journal_uuid = str(uuid.uuid4())
    newer = _slot(journal_uuid, counter=2, commit_seq=3)  # counter even -> slot index 0
    older = _slot(journal_uuid, counter=1, commit_seq=5)  # counter odd -> slot index 1
    raw = _anchor_bytes(newer, older)
    state, finding = journal_store._analyze_anchor(raw)
    assert state is None
    assert finding.code == "journal_anchor_invalid"
    assert finding.scope == "recovery"


def test_c6_differing_journal_uuid_between_valid_slots_is_invalid():
    older = _slot(str(uuid.uuid4()), counter=1, commit_seq=1)
    newer = _slot(str(uuid.uuid4()), counter=2, commit_seq=2)
    raw = _anchor_bytes(newer, older)
    state, finding = journal_store._analyze_anchor(raw)
    assert state is None
    assert finding.code == "journal_anchor_invalid"
    assert finding.scope == "recovery"


# --- G2: a row whose event_seq column disagrees with its body --------------


def test_event_seq_column_disagreeing_with_body_is_a_chain_finding():
    # PLAN DISCREPANCY: the gap list this test closes describes the result as
    # `journal_record_invalid`. The source's "Chain" step (`_chain_finding`)
    # is what actually compares the body's `event_seq` against the SQL
    # column -- `_column_finding` only compares `event_id`/`event_type`, not
    # `event_seq` -- and a mismatch there gives recovery `journal_chain_broken`,
    # matching the plan's own open-sequence table (step 10.3, "Chain"). This
    # test asserts the real, verified behavior; the mutant it kills is
    # dropping the `body_seq != event_seq` disjunct from `_chain_finding`.
    factory = Factory(str(uuid.uuid4()))
    genesis = factory.genesis()
    admission, _dedupe = factory.admission_pair("fp1")
    # The body still says event_seq=2 (its real, internally-consistent
    # value); only the SQL column claims 3. The chain (prev_record_digest)
    # and contiguity (body_seq == expected_seq) both stay valid, so this
    # isolates the body-vs-column comparison alone.
    row = (3, admission.event_id, admission.event_type, admission.body, admission.record_digest)
    record, finding = journal_store._verify_row(row, genesis, {genesis.event_id})
    assert record is None
    assert finding.code == "journal_chain_broken"
    assert finding.scope == "recovery"


# --- G2: persist_hold's observed_commit_seq -------------------------------


def test_persist_hold_records_observed_commit_seq_from_verified_head(tmp_path):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    store.append(factory.admission_pair("fp1"))
    store.append(factory.admission_pair("fp2"))
    store.close()

    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.finding is None
        rows = list(reopened.rows())
        assert len(rows) == 5  # genesis + two admission/dedupe_decision pairs
        assert reopened.verified_head.commit_seq == 3
        assert reopened.persist_hold("journal_corrupt", boot_id="boot-hold") is True
        assert reopened.anchor.hold.observed_commit_seq == 3
    finally:
        reopened.close()


# --- G2: a real integrity_check failure at open -----------------------------


def test_open_integrity_check_failure_gives_journal_corrupt(tmp_path):
    # Build a small, real, checkpointed image (not WAL frames only), then flip
    # one byte inside the `sqlite_autoindex_journal_events_1` (event_id index)
    # leaf page's stored key text. That corruption is invisible to the
    # presentation queries `_presentation_finding` runs before
    # `integrity_check` (they only touch `sqlite_schema`, page 1, and header
    # pragmas), and -- with `cell_size_check=ON`, this codebase's own setting
    # -- it does not raise a `sqlite3.Error` either: SQLite's `integrity_check`
    # reports it as a graceful, non-"ok" result row. Only the explicit
    # `PRAGMA integrity_check` comparison in `_presentation_finding` catches
    # it, so a mutant that skips that check would open this image ready.
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    store.append(factory.admission_pair("fp1"))
    store.append(factory.admission_pair("fp2"))
    store.append(factory.admission_pair("fp3"))
    store._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    store.close()

    db_path = directory / journal_store.DB_FILENAME
    data = bytearray(db_path.read_bytes())
    assert len(data) % journal_store.PAGE_SIZE == 0
    page_index = 2  # page 3 (1-indexed): the event_id autoindex's own page
    offset = page_index * journal_store.PAGE_SIZE + 4019
    data[offset] ^= 0xFF
    db_path.write_bytes(bytes(data))

    reopened = journal_store.JournalStore.open(directory)
    try:
        assert reopened.finding is not None
        assert reopened.finding.code == "journal_corrupt"
        assert reopened.finding.scope == "recovery"
        assert reopened.finding.sqlite_error is None  # via integrity_check, not a raised error
    finally:
        reopened.close()


# --- G4: root hardenings just made ------------------------------------------


def test_write_anchor_refuses_a_head_behind_the_current_anchor(tmp_path):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        store.append(factory.admission_pair("fp1"))  # anchor now at commit_seq=2
        before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        behind_head = Head(
            generation=1, commit_seq=1, event_seq=1, record_digest="a" * 64,
        )
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.write_anchor(behind_head)
        assert excinfo.value.code == "store_write_failed"
        after = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        assert after == before
    finally:
        store.close()


@pytest.mark.parametrize("case", ["event_seq_behind", "mistyped_commit_seq"])
def test_write_anchor_refuses_an_event_seq_behind_or_a_mistyped_head(tmp_path, case):
    directory, _journal_uuid, factory, store = create_store(tmp_path)
    try:
        store.append(factory.admission_pair("fp1"))
        current = store.anchor.head
        before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        if case == "event_seq_behind":
            head = Head(generation=1, commit_seq=current.commit_seq,
                        event_seq=current.event_seq - 1, record_digest="a" * 64)
        else:
            head = Head(generation=1, commit_seq="2", event_seq=current.event_seq,
                        record_digest="a" * 64)
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.write_anchor(head)
        assert excinfo.value.code == "store_write_failed"
        assert (directory / journal_store.ANCHOR_FILENAME).read_bytes() == before
    finally:
        store.close()


def test_write_anchor_refuses_a_body_the_reader_would_not_accept_as_v1(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        # `Head` does not enforce field types at runtime; a bool `generation`
        # is exactly the kind of body `_slot_kind` would refuse to read back.
        bad_head = Head(
            generation=True, commit_seq=1, event_seq=1, record_digest="a" * 64,
        )
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.write_anchor(bad_head)
        assert excinfo.value.code == "store_write_failed"
        after = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        assert after == before
    finally:
        store.close()


def test_persist_hold_with_a_different_code_than_the_existing_hold_is_refused(tmp_path):
    directory, _journal_uuid, _factory, store = create_store(tmp_path)
    try:
        assert store.persist_hold("journal_corrupt", boot_id="boot-1") is True
        before = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        with pytest.raises(journal_store.StoreError) as excinfo:
            store.persist_hold("journal_truncated", boot_id="boot-2")
        assert excinfo.value.code == "journal_argument"
        after = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        assert after == before
    finally:
        store.close()
