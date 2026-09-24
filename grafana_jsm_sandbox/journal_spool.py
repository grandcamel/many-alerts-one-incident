"""The content-addressed body spool: every admitted Notification's exact
bytes, keyed by ``body_digest``, held for the run-lifecycle unit's input
(ticket 37, unit 17b). It is not the journal: the journal never holds a raw
body (spec L156-159).

Custody, not deletion, is the whole defense here. A same-uid process can
tamper with an entry between boots; every read this module does re-verifies
an entry against its own name before trusting it. There is no deletion path:
a temp left by a failed write, or an entry a later admission no longer
references, is never removed, only reported by ``survey_spool``.

Error discipline matches ``forwarder_json`` and ``journal_store``: every
``except`` body only assigns a local variable, and a fresh error is raised
after the ``try`` statement with ``from None``.
"""

from __future__ import annotations

import fcntl
import os
import secrets
import stat
import sys
import threading
from pathlib import Path

from .journal_ingress import MAX_INGRESS_BODY_BYTES, body_digest

MAX_SPOOL_BYTES = 256 * 2**20  # injectable per instance; the spool is never replayed
MAX_SPOOL_ENTRIES = 20_000  # injectable; 2x the default max_admissions (critic 6)
SPOOL_ERROR_CODES = frozenset({
    "spool_argument", "spool_missing", "spool_path_invalid", "spool_permissions",
    "spool_sync_unsupported", "spool_full", "spool_conflict", "spool_write_failed",
    "spool_broken",
})

_HEX = frozenset("0123456789abcdef")
_TEMP_PREFIX = ".tmp-"
_SURVEY_LIST_CAP = 32


class SpoolError(Exception):
    """A fixed, non-diagnostic spool rejection; never embeds a path or bytes."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _hex64(name: str) -> bool:
    return len(name) == 64 and all(char in _HEX for char in name)


def _lstat(path: Path) -> os.stat_result | None:
    """``None`` only when the path is absent; any other ``OSError`` propagates."""
    result = None
    try:
        result = os.lstat(path)
    except FileNotFoundError:
        pass
    return result


def _maybe_present(path: Path) -> bool:
    # An unreadable name is treated as present-but-broken, not absent, so the
    # custody check below turns it into a conflict rather than a silent overwrite.
    present = True
    try:
        present = _lstat(path) is not None
    except OSError:
        pass
    return present


def _check_spool_directory(directory: Path) -> None:
    stat_result = None
    try:
        stat_result = _lstat(directory)
    except OSError:
        pass
    if stat_result is None:
        raise SpoolError("spool_missing")
    if stat.S_ISLNK(stat_result.st_mode) or not stat.S_ISDIR(stat_result.st_mode):
        raise SpoolError("spool_path_invalid")
    if stat_result.st_uid != os.geteuid() or stat_result.st_mode & 0o077:
        raise SpoolError("spool_permissions")


def _verify_entry(path: Path, digest: str) -> tuple[bool, int]:
    """Read-only custody check for one entry: regular, 0600, euid-owned, one
    link, at most the ingress body bound, and its content matches its name.
    Shared by ``JournalSpool.store`` and ``survey_spool``.
    """
    ok = True
    size = 0
    fd = None
    try:
        # Nonblocking open lets fstat reject a FIFO without waiting for a writer.
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except OSError:
        ok = False
    if ok:
        try:
            entry_stat = os.fstat(fd)
            size = entry_stat.st_size
            ok = (
                stat.S_ISREG(entry_stat.st_mode) and entry_stat.st_mode & 0o777 == 0o600
                and entry_stat.st_uid == os.geteuid() and entry_stat.st_nlink == 1
                and size <= MAX_INGRESS_BODY_BYTES
            )
            content = os.read(fd, size + 1) if ok else b""
            ok = ok and len(content) == size and body_digest(content) == digest
        except OSError:
            ok = False
        finally:
            _close(fd)
    return ok, size


def _close(fd: int) -> None:
    """Close once: retrying an ambiguous close may close a reused descriptor."""
    failed = False
    try:
        os.close(fd)
    except OSError:
        failed = True
    if failed:
        raise SpoolError("spool_write_failed") from None


# --- Sync primitives ----------------------------------------------------------


def full_sync(fd: int) -> None:
    """Fail-closed full sync of an open fd. The same platform selection as
    ``journal_store._full_sync``, restated because that primitive is private.
    Never falls back to a weaker sync.
    """
    if sys.platform == "darwin":
        if not hasattr(fcntl, "F_FULLFSYNC"):
            raise SpoolError("spool_sync_unsupported")
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        return
    if sys.platform == "linux":
        os.fsync(fd)
        return
    raise SpoolError("spool_sync_unsupported")


def sync_directory(path: Path) -> None:
    if not isinstance(path, Path):
        raise SpoolError("spool_argument")
    fd = None
    code = None
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        full_sync(fd)
    except OSError:
        code = "spool_write_failed"
    finally:
        if fd is not None:
            try:
                _close(fd)
            except SpoolError:
                code = "spool_write_failed"
    if code is not None:
        raise SpoolError(code) from None


def create_spool(directory: Path) -> None:
    """``journal_operator`` only. Refuses an existing path; syncing the parent
    and the new directory is the caller's job (``V23``)."""
    if not isinstance(directory, Path):
        raise SpoolError("spool_argument")
    code = None
    try:
        os.mkdir(str(directory), 0o700)
    except OSError:
        code = "spool_path_invalid"
    if code is not None:
        raise SpoolError(code) from None


# --- Read-only survey -----------------------------------------------------------


def survey_spool(directory: Path, referenced: frozenset[str]) -> dict[str, object]:
    """Inspect only: writes nothing. Every 64-hex entry, referenced and
    orphaned alike, is content-verified with ``store``'s own custody checks,
    bounded by at most ``MAX_SPOOL_ENTRIES`` files of at most
    ``MAX_INGRESS_BODY_BYTES`` bytes (critic 14).
    """
    if not isinstance(directory, Path) or type(referenced) is not frozenset:
        raise SpoolError("spool_argument")
    _check_spool_directory(directory)
    names = None
    code = None
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        code = "spool_path_invalid"
    if code is not None:
        raise SpoolError(code) from None

    total_bytes = 0
    seen: set[str] = set()
    orphans: list[str] = []
    orphans_total = 0
    mismatched: list[str] = []
    mismatched_total = 0
    mismatched_orphans: list[str] = []
    mismatched_orphans_total = 0
    temporaries = 0
    unexpected = 0

    for name in names:
        if _hex64(name):
            seen.add(name)
            ok, size = _verify_entry(directory / name, name)
            total_bytes += size
            is_referenced = name in referenced
            if ok and not is_referenced:
                orphans_total += 1
                if len(orphans) < _SURVEY_LIST_CAP:
                    orphans.append(name)
            elif not ok and is_referenced:
                mismatched_total += 1
                if len(mismatched) < _SURVEY_LIST_CAP:
                    mismatched.append(name)
            elif not ok:
                mismatched_orphans_total += 1
                if len(mismatched_orphans) < _SURVEY_LIST_CAP:
                    mismatched_orphans.append(name)
        elif name.startswith(_TEMP_PREFIX):
            temporaries += 1
        else:
            unexpected += 1

    missing: list[str] = []
    missing_total = 0
    for digest in sorted(referenced - seen):
        missing_total += 1
        if len(missing) < _SURVEY_LIST_CAP:
            missing.append(digest)

    return {
        "entries": len(names), "bytes": total_bytes, "referenced": len(referenced),
        "orphans": orphans, "orphans_total": orphans_total,
        "missing": missing, "missing_total": missing_total,
        "mismatched": mismatched, "mismatched_total": mismatched_total,
        "mismatched_orphans": mismatched_orphans,
        "mismatched_orphans_total": mismatched_orphans_total,
        "temporaries": temporaries, "unexpected": unexpected,
    }


# --- The live spool -------------------------------------------------------------


class JournalSpool:
    """Content-addressed spool for one spool directory. One process writes
    it, because the front door takes the journal's flock first; a
    ``threading.Lock`` here serializes its own handler threads.
    """

    def __init__(
        self, *, directory: Path, max_bytes: int, max_entries: int, bytes_used: int, entries: int,
    ) -> None:
        self.directory = directory
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._bytes = bytes_used
        self._entries = entries
        self._verified: set[str] = set()
        self._broken: str | None = None
        self._written_this_boot = 0
        self._full_refusals_this_boot = 0

    @classmethod
    def open(
        cls, directory: Path, *,
        max_bytes: int = MAX_SPOOL_BYTES, max_entries: int = MAX_SPOOL_ENTRIES,
    ) -> JournalSpool:
        """Never creates. Lstat custody of the directory, then sums the sizes
        of 64-hex entries and counts every directory entry alike."""
        if (
            not isinstance(directory, Path) or type(max_bytes) is not int
            or type(max_entries) is not int
        ):
            raise SpoolError("spool_argument")
        _check_spool_directory(directory)
        total_bytes = 0
        total_entries = 0
        code = None
        try:
            with os.scandir(directory) as scan:
                for entry in scan:
                    total_entries += 1
                    if _hex64(entry.name):
                        total_bytes += entry.stat(follow_symlinks=False).st_size
        except OSError:
            code = "spool_path_invalid"
        if code is not None:
            raise SpoolError(code) from None
        return cls(
            directory=directory, max_bytes=max_bytes, max_entries=max_entries,
            bytes_used=total_bytes, entries=total_entries,
        )

    def store(self, body: bytes, digest: str) -> str:
        """``"written"`` or ``"present"``. Under one lock, so concurrent
        handler threads serialize on the spool the same way they do on the
        journal.
        """
        ok = type(body) is bytes and type(digest) is str
        if ok:
            ok = digest == body_digest(body)
        if not ok:
            raise SpoolError("spool_argument")
        with self._lock:
            return self._store_locked(body, digest)

    def _store_locked(self, body: bytes, digest: str) -> str:
        if self._broken is not None:
            raise SpoolError("spool_broken")
        if digest in self._verified:
            return "present"
        path = self.directory / digest
        if _maybe_present(path):
            return self._verify_existing(path, digest)
        return self._write_new(path, body, digest)

    def _verify_existing(self, path: Path, digest: str) -> str:
        code = None
        try:
            ok, _size = _verify_entry(path, digest)
        except SpoolError:
            code = "spool_write_failed"
        if code is not None:
            self._broken = code
            raise SpoolError(code) from None
        if not ok:
            self._broken = "spool_conflict"
            raise SpoolError("spool_conflict") from None
        code = None
        try:
            sync_directory(self.directory)  # a W3 entry may not yet be durable
        except SpoolError:
            code = "spool_write_failed"
        if code is not None:
            self._broken = code
            raise SpoolError(code) from None
        self._verified.add(digest)
        return "present"

    def _write_new(self, path: Path, body: bytes, digest: str) -> str:
        if self._bytes + len(body) > self.max_bytes or self._entries + 1 > self.max_entries:
            self._full_refusals_this_boot += 1
            raise SpoolError("spool_full")
        temp_path = self.directory / f"{_TEMP_PREFIX}{digest}-{secrets.token_hex(8)}"
        fd = None
        code = None
        try:
            fd = os.open(
                str(temp_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
            )
        except OSError:
            code = "spool_write_failed"
        if code is not None:
            self._broken = code
            raise SpoolError(code) from None
        self._entries += 1  # the temp is a directory entry from here on, whatever happens next
        try:
            # A short write is an incomplete body, even without an OSError.
            # Retain the temporary and latch; do not sync or rename it.
            if os.write(fd, body) != len(body):
                code = "spool_write_failed"
            else:
                full_sync(fd)
        except (OSError, SpoolError):
            code = "spool_write_failed"
        finally:
            try:
                _close(fd)
            except SpoolError:
                code = "spool_write_failed"
        if code is None:
            try:
                os.rename(str(temp_path), str(path))
            except OSError:
                code = "spool_write_failed"
        if code is None:
            try:
                sync_directory(self.directory)
            except SpoolError:
                code = "spool_write_failed"
        if code is not None:
            self._broken = code
            raise SpoolError(code) from None
        self._bytes += len(body)
        self._verified.add(digest)
        self._written_this_boot += 1
        return "written"

    @property
    def broken(self) -> str | None:
        return self._broken

    def status(self) -> dict[str, object]:
        return {
            "state": "broken" if self._broken is not None else "ok",
            "code": self._broken,
            "bytes": self._bytes,
            "max_bytes": self.max_bytes,
            "entries": self._entries,
            "max_entries": self.max_entries,
            "written_this_boot": self._written_this_boot,
            "full_refusals_this_boot": self._full_refusals_this_boot,
        }


__all__ = [
    "MAX_SPOOL_BYTES",
    "MAX_SPOOL_ENTRIES",
    "SPOOL_ERROR_CODES",
    "JournalSpool",
    "SpoolError",
    "create_spool",
    "full_sync",
    "survey_spool",
    "sync_directory",
]
