"""Content-addressed body spool tests (ticket 37, unit 17b, implementer B1).

Real filesystem, real syncs, real custody checks throughout; nothing here
fakes durability except where a test injects a specific fault to prove the
latch. Tests never write repository files: every spool lives under a private
0700 ``tmp_path`` subdirectory.
"""

from __future__ import annotations

import ast
import errno
import fcntl
import os
import stat
import sys
import threading
from pathlib import Path

import pytest

from grafana_jsm_sandbox import journal_spool, journal_store
from grafana_jsm_sandbox.journal_ingress import body_digest

darwin_only = pytest.mark.skipif(sys.platform != "darwin", reason="F_FULLFSYNC is darwin-only")
linux_only = pytest.mark.skipif(sys.platform != "linux", reason="linux fsync variant")


def new_spool_dir(tmp_path: Path, name: str = "spool") -> Path:
    directory = tmp_path / name
    directory.mkdir(mode=0o700)
    return directory


def tree_signature(directory: Path) -> dict[str, tuple]:
    """A cheap fingerprint of every entry's mode and content, to prove a
    read-only pass changed nothing."""
    signature = {}
    for path in sorted(directory.iterdir()):
        mode = oct(path.lstat().st_mode)
        if path.is_symlink():
            signature[path.name] = ("link", mode, os.readlink(path))
        else:
            signature[path.name] = ("file", mode, path.read_bytes())
    return signature


# --- Module shape ---------------------------------------------------------------


def test_module_shape():
    assert journal_spool.MAX_SPOOL_BYTES == 256 * 2**20
    assert journal_spool.MAX_SPOOL_ENTRIES == 20_000
    assert journal_spool.SPOOL_ERROR_CODES == frozenset({
        "spool_argument", "spool_missing", "spool_path_invalid", "spool_permissions",
        "spool_sync_unsupported", "spool_full", "spool_conflict", "spool_write_failed",
        "spool_broken",
    })
    assert set(journal_spool.__all__) == {
        "MAX_SPOOL_BYTES", "MAX_SPOOL_ENTRIES", "SPOOL_ERROR_CODES", "JournalSpool", "SpoolError",
        "create_spool", "full_sync", "survey_spool", "sync_directory",
    }


def test_import_allowlist():
    source = Path(journal_spool.__file__).read_text()
    tree = ast.parse(source)
    allowed_modules = {
        "__future__", "dataclasses", "fcntl", "os", "re", "secrets", "stat", "sys", "threading",
        "pathlib",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed_modules, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                assert node.module in allowed_modules, node.module
            else:
                assert node.level == 1 and node.module == "journal_ingress"
                assert {alias.name for alias in node.names} == {
                    "MAX_INGRESS_BODY_BYTES", "body_digest",
                }


@pytest.mark.parametrize("module", ["journal_spool", "journaled_receiver", "journal_operator"])
def test_no_deletion_calls_anywhere(module):
    """S9 covers every new module, including from-imported deletion aliases."""
    source = Path(journal_spool.__file__).with_name(f"{module}.py").read_text()
    tree = ast.parse(source)
    banned = {"unlink", "remove", "rmdir", "rmtree", "truncate"}
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names if alias.name in banned
    }
    found = [
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in banned
    ]
    found.extend(
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in imported | banned
    )
    assert found == [], module


def test_except_bodies_only_assign_or_pass():
    """House rule: no raise inside an except body anywhere in this module."""
    source = Path(journal_spool.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            for statement in node.body:
                assert not isinstance(statement, ast.Raise), ast.dump(statement)


# --- create_spool and JournalSpool.open() argument checks -----------------------


def test_create_spool_makes_a_0700_directory(tmp_path):
    directory = tmp_path / "fresh-spool"
    journal_spool.create_spool(directory)
    assert oct(directory.stat().st_mode & 0o777) == oct(0o700)


def test_create_spool_refuses_an_existing_path(tmp_path):
    directory = tmp_path / "already-there"
    directory.mkdir(mode=0o700)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.create_spool(directory)
    assert excinfo.value.code in journal_spool.SPOOL_ERROR_CODES
    assert list(directory.iterdir()) == []


def test_open_argument_errors(tmp_path):
    directory = new_spool_dir(tmp_path)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.JournalSpool.open(str(directory))
    assert excinfo.value.code == "spool_argument"
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.JournalSpool.open(directory, max_bytes="256")
    assert excinfo.value.code == "spool_argument"
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.JournalSpool.open(directory, max_entries=1.5)
    assert excinfo.value.code == "spool_argument"


def test_open_counts_existing_entries_and_bytes(tmp_path):
    directory = new_spool_dir(tmp_path)
    body = b"pre-existing"
    digest = body_digest(body)
    (directory / digest).write_bytes(body)
    os.chmod(directory / digest, 0o600)
    (directory / ".tmp-leftover-0123456789abcdef").write_bytes(b"xx")
    (directory / "not-a-digest").write_bytes(b"y")

    spool = journal_spool.JournalSpool.open(directory)
    status = spool.status()
    assert status["entries"] == 3
    assert status["bytes"] == len(body)
    assert status["state"] == "ok"
    assert status["code"] is None
    assert status["written_this_boot"] == 0
    assert status["full_refusals_this_boot"] == 0


# --- S1: store writes, in order --------------------------------------------------


def test_s1_store_new_entry_written_with_exact_bytes_and_mode(tmp_path):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S1 new entry body"
    digest = body_digest(body)

    assert spool.store(body, digest) == "written"

    entry_path = directory / digest
    assert entry_path.read_bytes() == body
    assert oct(entry_path.stat().st_mode & 0o777) == oct(0o600)
    assert [p.name for p in directory.iterdir()] == [digest]
    status = spool.status()
    assert status["bytes"] == len(body)
    assert status["entries"] == 1
    assert status["written_this_boot"] == 1


def test_s1_store_syncs_file_then_renames_then_syncs_directory(tmp_path, monkeypatch):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S1 ordering body"
    digest = body_digest(body)

    events: list[str] = []
    real_full_sync = journal_spool.full_sync
    real_rename = os.rename

    def recording_full_sync(fd: int) -> None:
        kind = "dir_sync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file_sync"
        events.append(kind)
        real_full_sync(fd)

    def recording_rename(src: str, dst: str) -> None:
        events.append("rename")
        real_rename(src, dst)

    monkeypatch.setattr(journal_spool, "full_sync", recording_full_sync)
    monkeypatch.setattr(os, "rename", recording_rename)

    assert spool.store(body, digest) == "written"
    assert events == ["file_sync", "rename", "dir_sync"]


@pytest.mark.parametrize("written", [0, 3])
def test_s1_short_write_leaves_temp_and_latches(tmp_path, monkeypatch, written):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S1 complete body must be retained"
    digest = body_digest(body)
    real_write = os.write
    writes = []

    def short_write(fd, content):
        writes.append(len(content))
        return real_write(fd, content[:written])

    monkeypatch.setattr(os, "write", short_write)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_write_failed"
    assert spool.broken == "spool_write_failed"
    assert writes == [len(body)]
    assert not (directory / digest).exists()
    [temporary] = list(directory.iterdir())
    assert temporary.name.startswith(".tmp-")
    assert temporary.read_bytes() == body[:written]
    assert spool.status()["written_this_boot"] == 0
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_broken"
    assert writes == [len(body)]


@pytest.mark.parametrize("stage", ["temporary", "directory", "existing"])
def test_s4_close_failure_is_coded_and_latches_without_retry(tmp_path, monkeypatch, stage):
    directory = new_spool_dir(tmp_path)
    body = b"S4 close failure body"
    digest = body_digest(body)
    if stage == "existing":
        journal_spool.JournalSpool.open(directory).store(body, digest)
    spool = journal_spool.JournalSpool.open(directory)
    real_close = os.close
    failed_closes = []

    def fail_close(fd):
        is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        real_close(fd)
        if is_directory == (stage == "directory"):
            failed_closes.append(fd)
            raise OSError(errno.EIO, "close failure canary")

    monkeypatch.setattr(os, "close", fail_close)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_write_failed"
    assert excinfo.value.__context__ is None
    assert spool.broken == "spool_write_failed"
    assert len(failed_closes) == 1
    assert spool.status()["written_this_boot"] == 0
    if stage == "temporary":
        assert not (directory / digest).exists()
        [temporary] = list(directory.iterdir())
        assert temporary.name.startswith(".tmp-")
        assert temporary.read_bytes() == body
    else:
        assert (directory / digest).read_bytes() == body
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_broken"
    assert len(failed_closes) == 1


# --- S2: repeat and a fresh instance ---------------------------------------------


def test_s2_repeat_same_instance_is_present_with_no_io(tmp_path, monkeypatch):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S2 repeat body"
    digest = body_digest(body)
    assert spool.store(body, digest) == "written"

    calls: list[object] = []
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda *a, **k: (calls.append(a), real_open(*a, **k))[1])

    assert spool.store(body, digest) == "present"
    assert calls == []


def test_s2_fresh_instance_verifies_once_and_syncs_directory(tmp_path, monkeypatch):
    directory = new_spool_dir(tmp_path)
    original = journal_spool.JournalSpool.open(directory)
    body = b"S2 fresh instance body"
    digest = body_digest(body)
    assert original.store(body, digest) == "written"

    fresh = journal_spool.JournalSpool.open(directory)
    sync_kinds: list[str] = []
    real_full_sync = journal_spool.full_sync

    def recording_full_sync(fd: int) -> None:
        sync_kinds.append("dir_sync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file_sync")
        real_full_sync(fd)

    monkeypatch.setattr(journal_spool, "full_sync", recording_full_sync)
    assert fresh.store(body, digest) == "present"
    assert sync_kinds == ["dir_sync"]

    # Verified this boot now: a second call on the fresh instance does no I/O.
    calls: list[object] = []
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda *a, **k: (calls.append(a), real_open(*a, **k))[1])
    assert fresh.store(body, digest) == "present"
    assert calls == []


# --- S3: a conflicting pre-existing entry ----------------------------------------


def test_s3_conflicting_entry_latches_and_stays_byte_identical(tmp_path):
    directory = new_spool_dir(tmp_path)
    expected_body = b"S3 expected body"
    digest = body_digest(expected_body)
    entry_path = directory / digest
    entry_path.write_bytes(b"S3 tampered on-disk content")
    os.chmod(entry_path, 0o600)
    before = entry_path.read_bytes()

    spool = journal_spool.JournalSpool.open(directory)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(expected_body, digest)
    assert excinfo.value.code == "spool_conflict"
    assert spool.broken == "spool_conflict"
    assert entry_path.read_bytes() == before

    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(expected_body, digest)
    assert excinfo.value.code == "spool_broken"
    assert entry_path.read_bytes() == before
    assert spool.status()["state"] == "broken"
    assert spool.status()["code"] == "spool_conflict"


# --- S4: an injected file-sync failure -------------------------------------------


@darwin_only
def test_s4_file_sync_failure_leaves_temp_and_latches(tmp_path, monkeypatch):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S4 body"
    digest = body_digest(body)
    real_fcntl = fcntl.fcntl

    def failing_fcntl(fd, request, *args):
        if request == fcntl.F_FULLFSYNC:
            raise OSError(errno.EIO, os.strerror(errno.EIO))
        return real_fcntl(fd, request, *args)

    monkeypatch.setattr(fcntl, "fcntl", failing_fcntl)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_write_failed"
    assert spool.broken == "spool_write_failed"
    assert not (directory / digest).exists()
    temps = [p.name for p in directory.iterdir() if p.name.startswith(".tmp-")]
    assert len(temps) == 1

    monkeypatch.undo()
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_broken"


# --- S5: the byte cap and the entry cap ------------------------------------------


def test_s5_over_byte_cap_is_uncounted_and_not_latched(tmp_path):
    directory = new_spool_dir(tmp_path)
    body = b"x" * 100
    digest = body_digest(body)
    spool = journal_spool.JournalSpool.open(directory, max_bytes=50)

    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_full"
    assert spool.broken is None
    assert list(directory.iterdir()) == []
    assert spool.status()["full_refusals_this_boot"] == 1

    assert spool.status()["state"] == "ok"


def test_s5_over_byte_cap_present_body_is_still_present(tmp_path):
    directory = new_spool_dir(tmp_path)
    body = b"x" * 40
    digest = body_digest(body)
    roomy = journal_spool.JournalSpool.open(directory, max_bytes=1_000)
    assert roomy.store(body, digest) == "written"

    # A fresh instance opened with a cap the existing entry alone already
    # exceeds must still report it present, never spool_full.
    tight = journal_spool.JournalSpool.open(directory, max_bytes=10)
    assert tight.store(body, digest) == "present"


def test_s5_over_entry_cap_counts_temporaries_and_unexpected(tmp_path):
    directory = new_spool_dir(tmp_path)
    (directory / ".tmp-leftover-aaaaaaaaaaaaaaaa").write_bytes(b"")
    (directory / "unexpected-name").write_bytes(b"")
    spool = journal_spool.JournalSpool.open(directory, max_entries=3)

    body1 = b"S5 first body"
    digest1 = body_digest(body1)
    assert spool.store(body1, digest1) == "written"
    status = spool.status()
    assert status["entries"] == 3
    assert status["max_entries"] == 3

    body2 = b"S5 second body"
    digest2 = body_digest(body2)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body2, digest2)
    assert excinfo.value.code == "spool_full"
    assert spool.broken is None

    # A present body is still present at the cap.
    assert spool.store(body1, digest1) == "present"


# --- S6: custody -------------------------------------------------------------------


def test_s6_open_missing_directory(tmp_path):
    directory = tmp_path / "absent"
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.JournalSpool.open(directory)
    assert excinfo.value.code == "spool_missing"


def test_s6_open_symlinked_directory(tmp_path):
    real = tmp_path / "real-spool"
    real.mkdir(mode=0o700)
    link = tmp_path / "link-spool"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.JournalSpool.open(link)
    assert excinfo.value.code == "spool_path_invalid"


def test_s6_open_wrong_mode_directory(tmp_path):
    directory = tmp_path / "spool-0755"
    directory.mkdir(mode=0o755)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.JournalSpool.open(directory)
    assert excinfo.value.code == "spool_permissions"


def test_s6_symlinked_entry_is_a_conflict(tmp_path):
    directory = new_spool_dir(tmp_path)
    body = b"S6 symlink target body"
    digest = body_digest(body)
    target = tmp_path / "elsewhere"
    target.write_bytes(body)
    (directory / digest).symlink_to(target)

    spool = journal_spool.JournalSpool.open(directory)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_conflict"


def test_s6_hard_linked_entry_is_a_conflict(tmp_path):
    directory = new_spool_dir(tmp_path)
    body = b"S6 hard link body"
    digest = body_digest(body)
    entry_path = directory / digest
    entry_path.write_bytes(body)
    os.chmod(entry_path, 0o600)
    os.link(entry_path, directory / "extra-link")

    spool = journal_spool.JournalSpool.open(directory)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_conflict"


def test_s6_wrong_mode_entry_is_a_conflict(tmp_path):
    directory = new_spool_dir(tmp_path)
    body = b"S6 world-readable body"
    digest = body_digest(body)
    entry_path = directory / digest
    entry_path.write_bytes(body)
    os.chmod(entry_path, 0o644)

    spool = journal_spool.JournalSpool.open(directory)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, digest)
    assert excinfo.value.code == "spool_conflict"


@pytest.mark.parametrize("operation", ["store", "survey"])
def test_s6_fifo_entry_is_rejected_without_waiting_for_a_writer(tmp_path, operation):
    directory = new_spool_dir(tmp_path)
    body = b"S6 FIFO is never a body"
    digest = body_digest(body)
    entry = directory / digest
    os.mkfifo(entry, 0o600)
    spool = journal_spool.JournalSpool.open(directory)
    done = threading.Event()
    outcomes = []

    def inspect_entry():
        try:
            if operation == "store":
                outcomes.append(spool.store(body, digest))
            else:
                outcomes.append(journal_spool.survey_spool(directory, frozenset()))
        except journal_spool.SpoolError as error:
            outcomes.append(error.code)
        finally:
            done.set()

    worker = threading.Thread(target=inspect_entry, daemon=True)
    worker.start()
    completed = done.wait(2)
    try:
        assert completed, "custody check blocked opening a FIFO"
    finally:
        if not completed:
            # Release a regressed blocking open so the test leaves no worker behind.
            fd = os.open(entry, os.O_RDWR | os.O_NONBLOCK)
            worker.join(timeout=2)
            os.close(fd)
        else:
            worker.join(timeout=2)
    assert not worker.is_alive()
    assert stat.S_ISFIFO(entry.lstat().st_mode)
    if operation == "store":
        assert outcomes == ["spool_conflict"]
        assert spool.broken == "spool_conflict"
    else:
        assert outcomes[0]["mismatched_orphans"] == [digest]


def test_s6_error_args_never_carry_a_path_or_bytes(tmp_path):
    directory = tmp_path / "definitely-absent-spool-directory"
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.JournalSpool.open(directory)
    for arg in excinfo.value.args:
        assert isinstance(arg, str)
        assert str(directory) not in arg
    assert excinfo.value.args == ("spool_missing",)


# --- S7: argument checks on store() ----------------------------------------------


def test_s7_store_digest_mismatch_is_spool_argument(tmp_path):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S7 body"
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body, "0" * 64)
    assert excinfo.value.code == "spool_argument"
    assert list(directory.iterdir()) == []


def test_s7_store_bytearray_is_spool_argument(tmp_path):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S7 bytearray body"
    digest = body_digest(body)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(bytearray(body), digest)
    assert excinfo.value.code == "spool_argument"
    assert list(directory.iterdir()) == []


def test_s7_store_str_is_spool_argument(tmp_path):
    directory = new_spool_dir(tmp_path)
    spool = journal_spool.JournalSpool.open(directory)
    body = b"S7 str body"
    digest = body_digest(body)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(body.decode("ascii"), digest)
    assert excinfo.value.code == "spool_argument"
    assert list(directory.iterdir()) == []


# --- S8: full_sync platform selection --------------------------------------------


@darwin_only
def test_s8_full_sync_darwin_matches_journal_store(tmp_path, monkeypatch):
    if not hasattr(fcntl, "F_FULLFSYNC"):
        pytest.skip("F_FULLFSYNC not defined on this interpreter")
    probe = tmp_path / "probe-darwin"
    probe.write_bytes(b"x")
    fd = os.open(str(probe), os.O_RDWR)
    try:
        calls = []
        real_fcntl = fcntl.fcntl

        def recording_fcntl(fd_arg, request, *args):
            calls.append((fd_arg, request))
            return real_fcntl(fd_arg, request, *args)

        monkeypatch.setattr(fcntl, "fcntl", recording_fcntl)
        journal_spool.full_sync(fd)
        journal_store._full_sync(fd)
        assert calls == [(fd, fcntl.F_FULLFSYNC), (fd, fcntl.F_FULLFSYNC)]
    finally:
        os.close(fd)


@linux_only
def test_s8_full_sync_linux_calls_os_fsync(tmp_path, monkeypatch):
    probe = tmp_path / "probe-linux"
    probe.write_bytes(b"x")
    fd = os.open(str(probe), os.O_RDWR)
    try:
        calls = []
        real_fsync = os.fsync

        def recording_fsync(fd_arg):
            calls.append(fd_arg)
            return real_fsync(fd_arg)

        monkeypatch.setattr(os, "fsync", recording_fsync)
        journal_spool.full_sync(fd)
        assert calls == [fd]
        calls.clear()
        journal_store._full_sync(fd)
        assert calls == [fd]
    finally:
        os.close(fd)


def test_s8_unknown_platform_gives_spool_sync_unsupported(tmp_path, monkeypatch):
    probe = tmp_path / "probe-unknown"
    probe.write_bytes(b"x")
    fd = os.open(str(probe), os.O_RDWR)
    try:
        monkeypatch.setattr(sys, "platform", "win32")
        with pytest.raises(journal_spool.SpoolError) as excinfo:
            journal_spool.full_sync(fd)
        assert excinfo.value.code == "spool_sync_unsupported"
        with pytest.raises(journal_store.StoreError) as store_excinfo:
            journal_store._full_sync(fd)
        assert store_excinfo.value.code == "journal_sync_unsupported"
    finally:
        os.close(fd)


# --- S9: survey_spool --------------------------------------------------------------


def test_s9_survey_counts_and_lists_every_category(tmp_path):
    directory = new_spool_dir(tmp_path)

    referenced_body = b"S9 referenced body"
    referenced_digest = body_digest(referenced_body)
    (directory / referenced_digest).write_bytes(referenced_body)
    os.chmod(directory / referenced_digest, 0o600)

    orphan_body = b"S9 orphan body"
    orphan_digest = body_digest(orphan_body)
    (directory / orphan_digest).write_bytes(orphan_body)
    os.chmod(directory / orphan_digest, 0o600)

    missing_digest = body_digest(b"S9 never written body")

    mismatched_referenced_body = b"S9 expected referenced content"
    mismatched_referenced_digest = body_digest(mismatched_referenced_body)
    (directory / mismatched_referenced_digest).write_bytes(b"S9 tampered referenced")
    os.chmod(directory / mismatched_referenced_digest, 0o600)

    mismatched_orphan_body = b"S9 expected orphan content"
    mismatched_orphan_digest = body_digest(mismatched_orphan_body)
    (directory / mismatched_orphan_digest).write_bytes(b"S9 tampered orphan")
    os.chmod(directory / mismatched_orphan_digest, 0o600)

    symlinked_orphan_body = b"S9 symlinked orphan content"
    symlinked_orphan_digest = body_digest(symlinked_orphan_body)
    target = tmp_path / "elsewhere-s9"
    target.write_bytes(symlinked_orphan_body)
    (directory / symlinked_orphan_digest).symlink_to(target)

    (directory / ".tmp-leftover-0011223344556677").write_bytes(b"partial")
    (directory / "not-a-digest-name").write_bytes(b"???")

    referenced = frozenset({referenced_digest, mismatched_referenced_digest, missing_digest})
    before = tree_signature(directory)
    report = journal_spool.survey_spool(directory, referenced)
    after = tree_signature(directory)
    assert after == before  # writes nothing

    assert report["entries"] == 7
    assert report["referenced"] == 3
    assert report["orphans"] == [orphan_digest]
    assert report["orphans_total"] == 1
    assert report["missing"] == [missing_digest]
    assert report["missing_total"] == 1
    assert report["mismatched"] == [mismatched_referenced_digest]
    assert report["mismatched_total"] == 1
    assert sorted(report["mismatched_orphans"]) == sorted(
        [mismatched_orphan_digest, symlinked_orphan_digest],
    )
    assert report["mismatched_orphans_total"] == 2
    assert report["temporaries"] == 1
    assert report["unexpected"] == 1


def test_s9_lists_are_capped_at_32(tmp_path):
    directory = new_spool_dir(tmp_path)
    referenced_names = set()
    for index in range(40):
        body = f"S9 orphan cap body {index}".encode("ascii")
        digest = body_digest(body)
        (directory / digest).write_bytes(body)
        os.chmod(directory / digest, 0o600)
        referenced_names.add(digest)
    report = journal_spool.survey_spool(directory, frozenset())
    assert report["orphans_total"] == 40
    assert len(report["orphans"]) == 32


def test_s9_mismatched_orphan_predicts_the_latch(tmp_path):
    directory = new_spool_dir(tmp_path)
    expected_body = b"S9 latch prediction body"
    digest = body_digest(expected_body)
    (directory / digest).write_bytes(b"S9 different content on disk")
    os.chmod(directory / digest, 0o600)

    report = journal_spool.survey_spool(directory, frozenset())
    assert report["mismatched_orphans"] == [digest]

    spool = journal_spool.JournalSpool.open(directory)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        spool.store(expected_body, digest)
    assert excinfo.value.code == "spool_conflict"


def test_s9_survey_argument_errors(tmp_path):
    directory = new_spool_dir(tmp_path)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.survey_spool(str(directory), frozenset())
    assert excinfo.value.code == "spool_argument"
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.survey_spool(directory, set())
    assert excinfo.value.code == "spool_argument"


# --- S10: sync_directory -----------------------------------------------------------


def test_s10_sync_directory_syncs_its_own_descriptor(tmp_path, monkeypatch):
    directory = new_spool_dir(tmp_path)
    real_full_sync = journal_spool.full_sync
    seen_inodes = []

    def recording_full_sync(fd: int) -> None:
        seen_inodes.append(os.fstat(fd).st_ino)
        real_full_sync(fd)

    monkeypatch.setattr(journal_spool, "full_sync", recording_full_sync)
    journal_spool.sync_directory(directory)
    assert seen_inodes == [directory.stat().st_ino]


def test_s10_sync_directory_regular_file_fails(tmp_path):
    path = tmp_path / "not-a-directory"
    path.write_bytes(b"x")
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.sync_directory(path)
    assert excinfo.value.code == "spool_write_failed"


def test_s10_sync_directory_symlink_fails(tmp_path):
    real_dir = tmp_path / "real-target-dir"
    real_dir.mkdir(mode=0o700)
    link = tmp_path / "link-to-dir"
    link.symlink_to(real_dir, target_is_directory=True)
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.sync_directory(link)
    assert excinfo.value.code == "spool_write_failed"


def test_s10_sync_directory_argument_error(tmp_path):
    with pytest.raises(journal_spool.SpoolError) as excinfo:
        journal_spool.sync_directory(str(tmp_path))
    assert excinfo.value.code == "spool_argument"
