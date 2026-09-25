"""Physical storage for the recovery journal: one SQLite database in WAL mode,
an append-only table, an exclusive single-writer lock, and a two-slot anchor
file (ticket 37, unit 15, module 3).

This module knows nothing about admission semantics, dedupe, or the pure
reducer; it never imports ``journal_reducer``. It owns capability, path,
permission and lock checks; the connection and its settings; the exact DDL and
schema comparison; the ordered row-verification pipeline through typed decode
(digest, parse, chain, columns, typed -- framing and replay are the caller's,
via the reducer); duplicate lookup and the append transaction; and the anchor
file's codec and sync primitive.

Error discipline matches ``forwarder_json``: every ``except`` body only
assigns a local variable, and a fresh error is raised after the ``try``
statement with ``from None``.
"""

from __future__ import annotations

import dataclasses
import errno
import fcntl
import hashlib
import os
import sqlite3
import stat
import struct
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from .forwarder_json import JSONPolicyError, canonical_json, parse_json
from .journal_records import (
    MAX_GENERATION,
    MAX_SEQ,
    ZERO_DIGEST,
    Head,
    Record,
    RecordError,
    WalFound,
    content_digest,
    decode_record,
    open_record,
    validate_id,
    verify_body,
)
from .journal_source import SourceError

DB_FILENAME = "journal.sqlite3"
WAL_FILENAME = "journal.sqlite3-wal"
ANCHOR_FILENAME = "anchor"
LOCK_FILENAME = "lock"

APPLICATION_ID = 0x524A4E4C  # "RJNL"
USER_VERSION = 1
MIN_SQLITE_VERSION = (3, 37, 0)

PAGE_SIZE = 4_096
MAX_PAGE_COUNT = 40_960
JOURNAL_SIZE_LIMIT = 8 * 2**20
WAL_AUTOCHECKPOINT_PAGES = 1_000

ANCHOR_BYTES = 8_192
ANCHOR_SLOT_BYTES = 1_024
ANCHOR_SLOT_OFFSETS = (0, 4_096)
ANCHOR_MAGIC = b"RJANCHOR"
ANCHOR_FORMAT = "rj.anchor.v1"
MAX_ANCHOR_BODY_BYTES = 960
WAL_TAG = b"rj.wal.v1"

SCHEMA_SQL = (
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

RECOVERY_HOLD_CODES = frozenset({
    "journal_truncated", "journal_anchor_missing", "journal_anchor_invalid",
    "journal_anchor_conflict", "journal_identity_mismatch", "journal_schema_invalid",
    "journal_corrupt", "journal_record_invalid", "journal_chain_broken",
    "journal_tail_unverified", "journal_replay_mismatch", "journal_event_conflict",
})
PROCESS_HOLD_CODES = frozenset({"journal_open_failed", "journal_schema_unsupported"})
STORE_ERROR_CODES = frozenset({
    "journal_argument", "journal_path_invalid", "journal_permissions", "journal_locked",
    "journal_missing", "journal_exists", "journal_sync_unsupported", "sqlite_unsupported",
    "journal_create_failed", "store_event_conflict", "store_write_failed",
})
RECOVERY_SQLITE_PRIMARY = frozenset({sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB})  # 11, 26

_INSERT_SQL = (
    "INSERT INTO journal_events (event_seq, event_id, event_type, body, record_digest) "
    "VALUES (?, ?, ?, ?, ?)"
)
_SELECT_ROWS_SQL = (
    "SELECT event_seq, event_id, event_type, body, record_digest "
    "FROM journal_events ORDER BY event_seq"
)
_SCHEMA_ROWS_SQL = "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY name"

# Each is set, then read back.
_SETTINGS = (
    ("synchronous", "FULL", 2), ("fullfsync", "ON", 1), ("checkpoint_fullfsync", "ON", 1),
    ("trusted_schema", "OFF", 0), ("cell_size_check", "ON", 1),
    ("max_page_count", MAX_PAGE_COUNT, MAX_PAGE_COUNT),
    ("journal_size_limit", JOURNAL_SIZE_LIMIT, JOURNAL_SIZE_LIMIT),
    ("wal_autocheckpoint", WAL_AUTOCHECKPOINT_PAGES, WAL_AUTOCHECKPOINT_PAGES),
)
_CREATE_FLAGS = os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
# The database is opened through a SQLite URI built from the directory path.
_URI_RESERVED = "?#%"

_HEX = frozenset("0123456789abcdef")
_UUID_DASHES = (8, 13, 18, 23)
_ANCHOR_BODY_KEYS = frozenset({"counter", "format", "head", "hold", "journal_uuid"})
_ANCHOR_HEAD_KEYS = frozenset({"commit_seq", "event_seq", "generation", "record_digest"})
_ANCHOR_HOLD_KEYS = frozenset({"boot_id", "code", "observed_commit_seq"})


class StoreError(Exception):
    """A fixed, non-diagnostic storage rejection; never embeds caller data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclasses.dataclass(frozen=True)
class AnchorHold:
    code: str
    boot_id: str
    observed_commit_seq: int | None


@dataclasses.dataclass(frozen=True)
class AnchorState:
    journal_uuid: str
    counter: int
    head: Head
    hold: AnchorHold | None


@dataclasses.dataclass(frozen=True)
class Finding:
    code: str
    scope: str  # "recovery" | "process"
    sqlite_error: str | None


@dataclasses.dataclass(frozen=True)
class Duplicate:
    event_seqs: tuple[int, ...]


def _recovery(code: str) -> Finding:
    return Finding(code, "recovery", None)


def _process(code: str) -> Finding:
    return Finding(code, "process", None)


# --- Capability and sync primitive ------------------------------------------


def no_ckpt_supported() -> bool:
    """Whether ``setconfig`` and the no-checkpoint-on-close flag exist (Python >= 3.12)."""
    return (
        hasattr(sqlite3.Connection, "setconfig")
        and hasattr(sqlite3, "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE")
    )


def _capability_ok() -> bool:
    return no_ckpt_supported() and sqlite3.sqlite_version_info >= MIN_SQLITE_VERSION


def _sync_primitive_available() -> bool:
    if sys.platform == "darwin":
        return hasattr(fcntl, "F_FULLFSYNC")
    return sys.platform == "linux"


def _full_sync(fd: int) -> None:
    """Fail-closed full sync of an open fd. Never falls back to a weaker sync."""
    if sys.platform == "darwin":
        if not hasattr(fcntl, "F_FULLFSYNC"):
            raise StoreError("journal_sync_unsupported")
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        return
    if sys.platform == "linux":
        os.fsync(fd)
        return
    raise StoreError("journal_sync_unsupported")


def _sync_path(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | os.O_CLOEXEC)
    try:
        _full_sync(fd)
    finally:
        os.close(fd)


def classify_sqlite_error(error: sqlite3.Error) -> Finding:
    """Classify by the primary result code (``sqlite_errorcode & 0xFF``), never the extended one."""
    name = getattr(error, "sqlite_errorname", None)
    sqlite_error = name if type(name) is str else None
    raw_code = getattr(error, "sqlite_errorcode", None)
    if type(raw_code) is not int:
        return Finding("journal_open_failed", "process", sqlite_error)
    if raw_code & 0xFF in RECOVERY_SQLITE_PRIMARY:
        return Finding("journal_corrupt", "recovery", sqlite_error)
    return Finding("journal_open_failed", "process", sqlite_error)


def _sqlite_step(action: Callable[[], object]) -> tuple[object, Finding | None]:
    result, finding = None, None
    try:
        result = action()
    except sqlite3.Error as error:
        finding = classify_sqlite_error(error)
    return result, finding


# --- Path and permission checks ---------------------------------------------


def _lstat(path: Path) -> os.stat_result | None:
    """``None`` only when the path is absent; any other ``OSError`` propagates."""
    result = None
    try:
        result = os.lstat(path)
    except FileNotFoundError:
        pass
    return result


def _maybe_present(path: Path) -> bool:
    # Before the lock an unreadable path counts as present; the checks repeated
    # under the lock turn the error into a finding.
    present = True
    try:
        present = _lstat(path) is not None
    except OSError:
        pass
    return present


def _open_existing(path: Path) -> int | None:
    """A read-only fd, or ``None`` only when the path is absent."""
    fd = None
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        pass
    return fd


def _check_stat(stat_result: os.stat_result, *, is_dir: bool) -> None:
    kind = stat.S_ISDIR if is_dir else stat.S_ISREG
    if stat.S_ISLNK(stat_result.st_mode) or not kind(stat_result.st_mode):
        raise StoreError("journal_path_invalid")
    if stat_result.st_uid != os.geteuid() or stat_result.st_mode & 0o077:
        raise StoreError("journal_permissions")
    if not is_dir and stat_result.st_nlink != 1:
        raise StoreError("journal_permissions")


def _check_directory(directory: Path) -> None:
    if any(char in _URI_RESERVED for char in str(directory)):
        raise StoreError("journal_path_invalid")
    stat_result = None
    try:
        stat_result = _lstat(directory)
    except OSError:
        pass
    if stat_result is None:
        raise StoreError("journal_path_invalid")
    _check_stat(stat_result, is_dir=True)


def _take_lock(lock_path: Path) -> int:
    fd = None
    try:
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError:
        pass
    if fd is None:
        raise StoreError("journal_path_invalid")
    code = None
    try:
        _check_stat(os.fstat(fd), is_dir=False)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except StoreError as error:
        code = error.code
    except OSError as error:
        locked = error.errno in (errno.EWOULDBLOCK, errno.EAGAIN)
        code = "journal_locked" if locked else "journal_path_invalid"
    if code is not None:
        os.close(fd)
        raise StoreError(code) from None
    return fd


# --- Connection settings, each set then read back ---------------------------


def _set_pragma(cursor: sqlite3.Cursor, name: str, value: object, expected: object) -> None:
    cursor.execute(f"PRAGMA {name}={value}")
    if cursor.execute(f"PRAGMA {name}").fetchone()[0] != expected:
        raise StoreError("sqlite_unsupported")


def _apply_connection_settings(connection: sqlite3.Connection) -> None:
    """Every non-format connection setting. May raise ``sqlite3.Error``."""
    cursor = connection.cursor()
    if cursor.execute("PRAGMA locking_mode=EXCLUSIVE").fetchone()[0] != "exclusive":
        raise StoreError("sqlite_unsupported")
    for name, value, expected in _SETTINGS:
        _set_pragma(cursor, name, value, expected)


def _configure_for_create(connection: sqlite3.Connection) -> None:
    """Page size and WAL mode: set only at create, before the first write."""
    cursor = connection.cursor()
    _set_pragma(cursor, "page_size", PAGE_SIZE, PAGE_SIZE)
    if cursor.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
        raise StoreError("sqlite_unsupported")


def _presentation_finding(connection: sqlite3.Connection) -> Finding | None:
    """Presentation, format and integrity checks, in order."""
    cursor = connection.cursor()
    schema_rows = tuple(cursor.execute(_SCHEMA_ROWS_SQL))
    application_id = cursor.execute("PRAGMA application_id").fetchone()[0]
    user_version = cursor.execute("PRAGMA user_version").fetchone()[0]
    journal_mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]
    if not schema_rows and application_id == 0 and user_version == 0:
        return _recovery("journal_truncated")
    if application_id != APPLICATION_ID:
        return _recovery("journal_identity_mismatch")
    if user_version > USER_VERSION:
        return _process("journal_schema_unsupported")
    if (
        user_version != USER_VERSION
        or schema_rows != _reference_schema_rows()
        or journal_mode != "wal"
    ):
        return _recovery("journal_schema_invalid")
    if tuple(cursor.execute("PRAGMA integrity_check")) != (("ok",),):
        return _recovery("journal_corrupt")
    return None


def _genesis_uuid_conflicts(cursor: sqlite3.Cursor, anchor_journal_uuid: str) -> bool:
    """True when a digest-verified genesis row names a different ``journal_uuid``.

    A row that fails digest, chain or typed verification is left to the full
    row pipeline (``rows()``); this only short-circuits the common case.
    """
    row = cursor.execute(
        "SELECT event_type, body, record_digest FROM journal_events WHERE event_seq = 1"
    ).fetchone()
    if row is None or row[0] != "journal_genesis":
        return False
    body, record_digest = bytes(row[1]), row[2]
    genesis = None
    try:
        genesis = decode_record(verify_body(body, record_digest), body, record_digest)
    except (RecordError, SourceError):
        pass
    return genesis is not None and genesis.data.get("journal_uuid") != anchor_journal_uuid


def _reference_schema_rows() -> tuple:
    reference = sqlite3.connect(":memory:")
    try:
        cursor = reference.cursor()
        cursor.execute("BEGIN")
        for statement in SCHEMA_SQL:
            cursor.execute(statement)
        cursor.execute("COMMIT")
        return tuple(cursor.execute(_SCHEMA_ROWS_SQL))
    finally:
        reference.close()


def _record_head(record: Record) -> Head:
    return Head(
        generation=record.position.journal_generation, commit_seq=record.position.commit_seq,
        event_seq=record.position.event_seq, record_digest=record.record_digest,
    )


def _row_params(record: Record) -> tuple:
    return (
        record.position.event_seq, record.event_id, record.event_type,
        record.body, record.record_digest,
    )


def _checked_records(records: object) -> tuple[Record, ...]:
    """Exact ``Record`` instances, each equal to what its own body decodes to."""
    agree = type(records) in (list, tuple) and len(records) > 0
    try:
        agree = agree and all(
            type(record) is Record and open_record(record.body) == record for record in records
        )
    except (RecordError, SourceError):
        agree = False
    if not agree:
        raise StoreError("journal_argument")
    return tuple(records)


# --- Anchor codec -------------------------------------------------------------


def _encode_slot(body: dict) -> bytes:
    payload = canonical_json(body, ascii_only=True)
    if not 1 <= len(payload) <= MAX_ANCHOR_BODY_BYTES:
        raise StoreError("journal_argument")
    header = ANCHOR_MAGIC + struct.pack(">I", len(payload))
    checksum = hashlib.sha256(header + payload).digest()
    slot = header + payload + checksum
    return slot + b"\x00" * (ANCHOR_SLOT_BYTES - len(slot))


def _decode_slot(region: bytes) -> dict | None:
    """The body of an intact slot region, else ``None``.

    Intact means magic, length, checksum, zero bytes up to the next slot or
    the end of the file, and a canonical JSON object.
    """
    if len(region) < ANCHOR_SLOT_BYTES or region[:8] != ANCHOR_MAGIC:
        return None
    length = struct.unpack(">I", region[8:12])[0]
    if not 1 <= length <= MAX_ANCHOR_BODY_BYTES:
        return None
    end = 12 + length
    if hashlib.sha256(region[:end]).digest() != region[end:end + 32] or any(region[end + 32:]):
        return None
    payload = region[12:end]
    body = None
    try:
        body = parse_json(
            payload, max_bytes=MAX_ANCHOR_BODY_BYTES, numbers="integer", ascii_only=True,
        )
        canonical = type(body) is dict and canonical_json(body, ascii_only=True) == payload
    except JSONPolicyError:
        canonical = False
    return body if canonical else None


def _slot_bodies(raw: bytes) -> list[dict | None]:
    ends = ANCHOR_SLOT_OFFSETS[1:] + (ANCHOR_BYTES,)
    return [_decode_slot(raw[start:end]) for start, end in zip(ANCHOR_SLOT_OFFSETS, ends)]


def _hex64(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(char in _HEX for char in value)


def _int_in(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _uuid_ok(value: object) -> bool:
    """Lowercase canonical UUID text, as ``journal_genesis`` records it."""
    return type(value) is str and len(value) == 36 and all(
        char == "-" if index in _UUID_DASHES else char in _HEX
        for index, char in enumerate(value)
    )


def _id_ok(value: object) -> bool:
    ok = True
    try:
        validate_id(value)
    except RecordError:
        ok = False
    return ok


def _slot_kind(body: dict) -> str:
    """``"v1"``; ``"newer"`` for a format this code does not know; ``"invalid"``
    for a v1-format slot that no v1 writer produces."""
    head, hold = body.get("head"), body.get("hold")
    if (
        body.keys() != _ANCHOR_BODY_KEYS
        or body["format"] != ANCHOR_FORMAT
        or (type(head) is dict and head.keys() != _ANCHOR_HEAD_KEYS)
        or (type(hold) is dict and (
            hold.keys() != _ANCHOR_HOLD_KEYS
            or (type(hold["code"]) is str and hold["code"] not in RECOVERY_HOLD_CODES)
        ))
    ):
        return "newer"
    head_ok = type(head) is dict and (
        _int_in(head["generation"], 1, MAX_GENERATION)
        and _int_in(head["commit_seq"], 1, MAX_SEQ)
        and _int_in(head["event_seq"], 1, MAX_SEQ)
        and _hex64(head["record_digest"])
    )
    observed = hold.get("observed_commit_seq") if type(hold) is dict else None
    hold_ok = hold is None or (
        type(hold) is dict and type(hold["code"]) is str and _id_ok(hold["boot_id"])
        and (observed is None or _int_in(observed, 0, MAX_SEQ))
    )
    valid = (
        _int_in(body["counter"], 1, MAX_SEQ) and _uuid_ok(body["journal_uuid"])
        and head_ok and hold_ok
    )
    return "v1" if valid else "invalid"


def _slot_counter(entry: tuple[int, dict, str]) -> int:
    counter = entry[1].get("counter")
    return counter if type(counter) is int else -1


def _anchor_state_from_body(body: dict) -> AnchorState:
    head_json = body["head"]
    head = Head(
        generation=head_json["generation"], commit_seq=head_json["commit_seq"],
        event_seq=head_json["event_seq"], record_digest=head_json["record_digest"],
    )
    hold_json = body["hold"]
    hold = None
    if hold_json is not None:
        hold = AnchorHold(
            code=hold_json["code"], boot_id=hold_json["boot_id"],
            observed_commit_seq=hold_json["observed_commit_seq"],
        )
    return AnchorState(
        journal_uuid=body["journal_uuid"], counter=body["counter"], head=head, hold=hold,
    )


def _anchor_body(journal_uuid: str, head: Head, hold: AnchorHold | None) -> dict:
    return {
        "counter": 0,  # overwritten by _write_slot with the real next counter
        "format": ANCHOR_FORMAT,
        "journal_uuid": journal_uuid,
        "head": {
            "commit_seq": head.commit_seq, "event_seq": head.event_seq,
            "generation": head.generation, "record_digest": head.record_digest,
        },
        "hold": None if hold is None else {
            "boot_id": hold.boot_id, "code": hold.code,
            "observed_commit_seq": hold.observed_commit_seq,
        },
    }


def _analyze_anchor(raw: bytes) -> tuple[AnchorState | None, Finding | None]:
    invalid = (None, _recovery("journal_anchor_invalid"))
    if len(raw) != ANCHOR_BYTES:
        return invalid
    intact = [
        (index, body, _slot_kind(body))
        for index, body in enumerate(_slot_bodies(raw)) if body is not None
    ]
    if not intact or any(kind == "invalid" for _, _, kind in intact):
        return invalid
    if max(intact, key=_slot_counter)[2] == "newer":
        return None, _process("journal_schema_unsupported")

    v1_slots = [(index, body) for index, body, kind in intact if kind == "v1"]
    if any(body["counter"] % 2 != index for index, body in v1_slots):
        return invalid
    if len(v1_slots) == 1:
        return _anchor_state_from_body(v1_slots[0][1]), None
    older, newer = sorted((body for _, body in v1_slots), key=lambda body: body["counter"])
    if (
        newer["counter"] - older["counter"] != 1
        or newer["journal_uuid"] != older["journal_uuid"]
        or newer["head"]["commit_seq"] < older["head"]["commit_seq"]
        or (older["hold"] is not None and newer["hold"] is None)
    ):
        return invalid
    return _anchor_state_from_body(newer), None


def _held_slot_count(raw: bytes) -> int:
    return sum(
        1 for body in _slot_bodies(raw)
        if body is not None and _slot_kind(body) == "v1" and body["hold"] is not None
    )


# --- Row verification pipeline -------------------------------------------------


def _chain_finding(envelope: dict, event_seq: int, previous: Record | None) -> Finding | None:
    body_seq, prev_digest = envelope.get("event_seq"), envelope.get("prev_record_digest")
    if type(body_seq) is not int or not _hex64(prev_digest):
        return _process("journal_schema_unsupported")
    expected_prev = previous.record_digest if previous is not None else ZERO_DIGEST
    expected_seq = previous.position.event_seq + 1 if previous is not None else 1
    if body_seq != event_seq or body_seq != expected_seq or prev_digest != expected_prev:
        return _recovery("journal_chain_broken")
    return None


def _column_finding(
    envelope: dict, event_id: str, event_type: str, seen_ids: set[str],
) -> Finding | None:
    body_id, body_type = envelope.get("event_id"), envelope.get("event_type")
    if type(body_id) is not str or type(body_type) is not str:
        return _process("journal_schema_unsupported")
    if body_id != event_id or body_type != event_type:
        return _recovery("journal_record_invalid")
    if event_id in seen_ids:
        return _recovery("journal_event_conflict")
    return None


def _verify_row(
    row: tuple, previous: Record | None, seen_ids: set[str],
) -> tuple[Record | None, Finding | None]:
    """One step of the physical-then-typed pipeline: digest, parse, chain, columns, typed decode."""
    event_seq, event_id, event_type, body_blob, record_digest = row
    body = bytes(body_blob)
    envelope, digest_failed = None, False
    try:
        envelope = verify_body(body, record_digest)
    except RecordError as error:
        digest_failed = error.code == "record_digest"
    finding = None
    if digest_failed:
        finding = _recovery("journal_record_invalid")
    elif type(envelope) is not dict:  # unparsable, or a verified body that is not an object
        finding = _process("journal_schema_unsupported")
    if finding is None:
        finding = _chain_finding(envelope, event_seq, previous)
    if finding is None:
        finding = _column_finding(envelope, event_id, event_type, seen_ids)
    record = None
    if finding is None:
        try:
            record = decode_record(envelope, body, record_digest)
        except (RecordError, SourceError):
            finding = _process("journal_schema_unsupported")
    return record, finding


def _same_commit(
    rows: list[tuple], stored: tuple[Record, ...], records: tuple[Record, ...],
) -> bool:
    """Whether the stored rows are exactly one whole commit with ``records``' content, in order."""
    if len(rows) != len(records):
        return False
    first_seq, commit_seq = rows[0][0], stored[0].position.commit_seq
    for index, ((event_seq, event_id, _), old, new) in enumerate(zip(rows, stored, records)):
        position = old.position
        if (
            event_seq != first_seq + index
            or event_id != new.event_id
            or position.commit_seq != commit_seq
            or position.commit_index != index
            or position.commit_size != len(records)
            or content_digest(old) != content_digest(new)
        ):
            return False
    return True


# --- The store -----------------------------------------------------------------


class JournalStore:
    """Physical storage for one recovery journal directory."""

    def __init__(
        self, *, directory: Path, connection: sqlite3.Connection | None, lock_fd: int,
        anchor_path: Path, db_path: Path,
    ) -> None:
        self.directory = directory
        self._connection = connection
        self._lock_fd = lock_fd
        self.anchor_path = anchor_path
        self.db_path = db_path
        self._wal_path = directory / WAL_FILENAME
        self.finding: Finding | None = None
        self.anchor: AnchorState | None = None
        self.wal_found: WalFound | None = None
        self.verified_head: Head | None = None
        self._held_slots = 0  # anchor slots carrying a hold, of the two
        self._broken = False
        self._closed = False

    # -- create and open --

    @classmethod
    def create(cls, directory: Path, genesis: Record, *, journal_uuid: str) -> JournalStore:
        if not _capability_ok():
            raise StoreError("sqlite_unsupported")
        # `Path(...)` always constructs a concrete `PosixPath`/`WindowsPath`, never the
        # base class itself, so this is an `isinstance` check rather than the usual
        # exact-type one; `Record` and `str` have no such subclassing surprise.
        if not isinstance(directory, Path) or not _uuid_ok(journal_uuid):
            raise StoreError("journal_argument")
        (genesis,) = _checked_records([genesis])
        matches_uuid = genesis.data.get("journal_uuid") == journal_uuid
        if genesis.event_type != "journal_genesis" or not matches_uuid:
            raise StoreError("journal_argument")
        if not _sync_primitive_available():
            raise StoreError("journal_sync_unsupported")
        _check_directory(directory)
        return cls._locked(directory, lambda store: store._create_files(genesis, journal_uuid))

    @classmethod
    def open(cls, directory: Path, *, require_wal: bool = False) -> JournalStore:
        if not _capability_ok():
            raise StoreError("sqlite_unsupported")
        if not isinstance(directory, Path):
            raise StoreError("journal_argument")
        if not _sync_primitive_available():
            raise StoreError("journal_sync_unsupported")
        _check_directory(directory)
        names = (DB_FILENAME, WAL_FILENAME, ANCHOR_FILENAME)
        if not any(_maybe_present(directory / name) for name in names):
            raise StoreError("journal_missing")
        if not require_wal:
            return cls._locked(directory, cls._open_steps)

        def inspect_step(store: JournalStore) -> None:
            # The claim view's earlier preflight is outside the store lock.
            # Recheck here before SQLite can recreate a missing WAL.
            if not _maybe_present(directory / WAL_FILENAME):
                raise StoreError("wal_absent")
            store._open_steps()

        return cls._locked(directory, inspect_step)

    @classmethod
    def _locked(cls, directory: Path, step: Callable[[JournalStore], None]) -> JournalStore:
        """Take the lock and run ``step``; any non-clean exit closes the store again."""
        store = cls(
            directory=directory, connection=None, lock_fd=_take_lock(directory / LOCK_FILENAME),
            anchor_path=directory / ANCHOR_FILENAME, db_path=directory / DB_FILENAME,
        )
        completed = False
        try:
            step(store)
            completed = True
        finally:
            if not completed:
                store.close()
        return store

    def _create_files(self, genesis: Record, journal_uuid: str) -> None:
        """Genesis. Nothing is ever deleted: a failure leaves the files in place."""
        code: str | None = None
        db_created = False
        try:
            paths = (self.db_path, self._wal_path, self.anchor_path)
            if any(_lstat(path) is not None for path in paths):
                raise StoreError("journal_exists")
            os.close(os.open(str(self.db_path), _CREATE_FLAGS | os.O_WRONLY, 0o600))
            db_created = True
            connection = self._connect()
            _apply_connection_settings(connection)
            _configure_for_create(connection)
            cursor = connection.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(f"PRAGMA application_id={APPLICATION_ID}")
            cursor.execute(f"PRAGMA user_version={USER_VERSION}")
            for statement in SCHEMA_SQL:
                cursor.execute(statement)
            cursor.execute(_INSERT_SQL, _row_params(genesis))
            cursor.execute("COMMIT")
            _sync_path(self.directory)
            anchor_fd = os.open(str(self.anchor_path), _CREATE_FLAGS | os.O_RDWR, 0o600)
            try:
                os.ftruncate(anchor_fd, ANCHOR_BYTES)
            finally:
                os.close(anchor_fd)
            self._write_slot(_anchor_body(journal_uuid, _record_head(genesis), None))
            _sync_path(self.directory)
        except StoreError as error:
            code = error.code
        except Exception:  # noqa: BLE001 - any other failure leaves files in place, never raw.
            code = "journal_create_failed" if db_created else "journal_path_invalid"
        if code is not None:
            raise StoreError(code) from None
        self.verified_head = _record_head(genesis)

    def _open_steps(self) -> None:
        finding = None
        try:
            self._verify_open()
        except OSError:
            finding = _process("journal_open_failed")
        except sqlite3.Error as error:
            finding = classify_sqlite_error(error)
        if finding is not None:
            self.finding = finding

    def _verify_open(self) -> None:
        """Every open check up to the row scan; stops at the first finding."""
        db_stat = _lstat(self.db_path)
        for stat_result in (db_stat, _lstat(self._wal_path), _lstat(self.anchor_path)):
            if stat_result is not None:
                _check_stat(stat_result, is_dir=False)
        self._read_anchor()
        if self.finding is not None:
            return
        if self.anchor.hold is not None:
            self.finding = _recovery(self.anchor.hold.code)
            return
        # Without its first page SQLite would treat the DB as new and discard the WAL.
        if db_stat is None or db_stat.st_size < PAGE_SIZE:
            self.finding = _recovery("journal_truncated")
            return
        self.wal_found = _wal_found(self._wal_path)
        connection = self._connect()
        _apply_connection_settings(connection)
        _set_pragma(connection.cursor(), "query_only", "ON", 1)
        self.finding = _presentation_finding(connection)
        if self.finding is None and _genesis_uuid_conflicts(
            connection.cursor(), self.anchor.journal_uuid,
        ):
            self.finding = _recovery("journal_identity_mismatch")

    # -- verification pipeline --

    def rows(self) -> Iterator[Record]:
        """Yield digest-, chain- and type-verified rows in order; stop at the first finding.

        ``verified_head`` advances only when the caller resumes after a
        commit's last record, that is, once it has accepted the whole commit.
        """
        if self._connection is None or self.finding is not None:
            return
        cursor, finding = _sqlite_step(lambda: self._connection.execute(_SELECT_ROWS_SQL))
        previous: Record | None = None
        seen_ids: set[str] = set()
        while finding is None:
            row, finding = _sqlite_step(cursor.fetchone)
            if row is None:
                break
            record, finding = _verify_row(row, previous, seen_ids)
            if record is None:
                break
            seen_ids.add(record.event_id)
            previous = record
            yield record
            if record.position.commit_index == record.position.commit_size - 1:
                self.verified_head = _record_head(record)
        self.finding = finding

    def finish_open(self) -> None:
        self._check_writable()
        self._guarded_write(lambda: _set_pragma(self._connection.cursor(), "query_only", "OFF", 0))

    # -- anchor writes --

    def write_anchor(self, head: Head) -> None:
        self._check_writable()
        if type(head) is not Head:
            raise StoreError("journal_argument")
        body = _anchor_body(self.anchor.journal_uuid, head, None)
        self._guarded_write(lambda: self._write_slot(body))

    def persist_hold(self, code: str, *, boot_id: str) -> bool:
        """Write the hold into both slots; False when both already carry it."""
        if self._closed or self._broken:
            raise StoreError("store_write_failed")
        if (
            self.anchor is None or type(code) is not str or code not in RECOVERY_HOLD_CODES
            or not _id_ok(boot_id)
        ):
            raise StoreError("journal_argument")
        hold, count = self.anchor.hold, 1
        if hold is not None and hold.code != code:
            raise StoreError("journal_argument")  # one persisted verdict per journal
        if hold is None:
            observed = self.verified_head.commit_seq if self.verified_head is not None else None
            hold, count = AnchorHold(code=code, boot_id=boot_id, observed_commit_seq=observed), 2
        elif self._held_slots == 2:
            return False
        body = _anchor_body(self.anchor.journal_uuid, self.anchor.head, hold)

        def write() -> None:
            for _ in range(count):
                self._write_slot(body)

        self._guarded_write(write)
        return True

    # -- duplicates and append --

    def find_duplicate(self, records: Sequence[Record]) -> Duplicate | None:
        self._check_writable()
        records = _checked_records(records)
        placeholders = ",".join("?" for _ in records)
        stored, failed = None, False
        try:
            stored = self._connection.execute(
                f"SELECT event_seq, event_id, body FROM journal_events "
                f"WHERE event_id IN ({placeholders}) ORDER BY event_seq",
                [record.event_id for record in records],
            ).fetchall()
        except sqlite3.Error:
            failed = True
        if failed:
            self._broken = True
            raise StoreError("store_write_failed")
        if not stored:
            return None
        stored_records = None
        try:
            stored_records = tuple(open_record(bytes(body)) for _, _, body in stored)
        except (RecordError, SourceError):
            pass
        if stored_records is None or not _same_commit(stored, stored_records, records):
            raise StoreError("store_event_conflict")
        return Duplicate(event_seqs=tuple(row[0] for row in stored))

    def append(self, records: Sequence[Record], *, sync_directory: bool = False) -> tuple[int, ...]:
        self._check_writable()
        records = _checked_records(records)

        def commit() -> None:
            self._commit_sql(records)
            if sync_directory:
                _sync_path(self.directory)
            head = _record_head(records[-1])
            self._write_slot(_anchor_body(self.anchor.journal_uuid, head, None))

        self._guarded_write(commit)
        return tuple(record.position.event_seq for record in records)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._connection is not None:
            try:
                self._connection.close()
            except sqlite3.Error:
                pass
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(self._lock_fd)

    # -- write discipline --

    def _check_writable(self) -> None:
        """Refuse once closed or broken, and while a finding or a persisted verdict holds."""
        held = self.finding is not None or self.anchor is None or self.anchor.hold is not None
        if held or self._connection is None or self._broken or self._closed:
            raise StoreError("store_write_failed")

    def _guarded_write(self, write: Callable[[], None]) -> None:
        """Run ``write``; any failure rolls back and latches the store broken (never retried)."""
        completed, failed = False, False
        try:
            write()
            completed = True
        except (sqlite3.Error, OSError, StoreError):
            failed = True
        finally:
            if not completed:
                self._broken = True
                self._rollback()
        if failed:
            raise StoreError("store_write_failed") from None

    def _rollback(self) -> None:
        if self._connection is None or not self._connection.in_transaction:
            return
        try:
            self._connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    # -- private seams --

    def _connect(self) -> sqlite3.Connection:
        """Connect to exactly ``db_path``, with no-checkpoint-on-close set before any statement."""
        self._connection = sqlite3.connect(
            f"file:{self.db_path}?mode=rw", uri=True, isolation_level=None,
            check_same_thread=False,
        )
        connection = self._connection
        connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        if connection.getconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE) is not True:
            raise StoreError("sqlite_unsupported")
        listed = connection.execute("PRAGMA database_list").fetchall()
        if listed != [(0, "main", os.path.realpath(self.db_path))]:
            raise StoreError("journal_path_invalid")
        return connection

    def _commit_sql(self, records: Sequence[Record]) -> None:
        cursor = self._connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        for record in records:
            cursor.execute(_INSERT_SQL, _row_params(record))
        cursor.execute("COMMIT")

    def _write_slot(self, body: dict) -> None:
        previous = self.anchor
        held_before = previous is not None and previous.hold is not None
        if held_before and body["hold"] is None:
            raise StoreError("store_write_failed")  # a persisted verdict is never erased
        counter = (previous.counter if previous is not None else 0) + 1
        body = dict(body, counter=counter)
        # Never write a slot the reader would refuse, or one whose head moved backwards.
        refused = _slot_kind(body) != "v1" or previous is not None and (
            body["head"]["commit_seq"] < previous.head.commit_seq
            or body["head"]["event_seq"] < previous.head.event_seq
        )
        if refused:
            raise StoreError("store_write_failed")
        slot = _encode_slot(body)
        fd = os.open(str(self.anchor_path), os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            if os.pwrite(fd, slot, ANCHOR_SLOT_OFFSETS[counter % 2]) != len(slot):
                raise OSError(errno.EIO, "short anchor write")
            _full_sync(fd)
        finally:
            os.close(fd)
        self.anchor = _anchor_state_from_body(body)
        self._held_slots = int(held_before) + int(body["hold"] is not None)

    def _read_anchor(self) -> None:
        fd = _open_existing(self.anchor_path)
        if fd is None:
            self.finding = _recovery("journal_anchor_missing")
            return
        try:
            raw = os.read(fd, ANCHOR_BYTES + 1)
        finally:
            os.close(fd)
        self.anchor, self.finding = _analyze_anchor(raw)
        if self.anchor is not None:
            self._held_slots = _held_slot_count(raw)


def _wal_found(wal_path: Path) -> WalFound | None:
    """Size and tagged digest of the WAL as found; ``None`` only when it is absent."""
    fd = _open_existing(wal_path)
    if fd is None:
        return None
    digest = hashlib.sha256(WAL_TAG + b"\x00")
    size = 0
    try:
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    finally:
        os.close(fd)
    return WalFound(size=size, digest=digest.hexdigest())


__all__ = [
    "ANCHOR_BYTES",
    "ANCHOR_FORMAT",
    "ANCHOR_MAGIC",
    "ANCHOR_SLOT_BYTES",
    "ANCHOR_SLOT_OFFSETS",
    "APPLICATION_ID",
    "DB_FILENAME",
    "JOURNAL_SIZE_LIMIT",
    "LOCK_FILENAME",
    "MAX_ANCHOR_BODY_BYTES",
    "MAX_PAGE_COUNT",
    "MIN_SQLITE_VERSION",
    "PAGE_SIZE",
    "PROCESS_HOLD_CODES",
    "RECOVERY_HOLD_CODES",
    "RECOVERY_SQLITE_PRIMARY",
    "SCHEMA_SQL",
    "STORE_ERROR_CODES",
    "USER_VERSION",
    "WAL_FILENAME",
    "WAL_TAG",
    "AnchorHold",
    "AnchorState",
    "Duplicate",
    "Finding",
    "JournalStore",
    "StoreError",
    "classify_sqlite_error",
    "no_ckpt_supported",
]
