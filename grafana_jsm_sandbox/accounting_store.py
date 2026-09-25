"""Receiver-owned durable accounting event store; no reservation interface."""

import errno
import fcntl
import hashlib
import os
import sqlite3
import stat
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .accounting_events import AccountingEvent, AccountingEventError, decode_event
from .accounting_transition import AccountingTransitionError, apply_event, replay_accounting
from .forwarder_json import JSONPolicyError, canonical_json, parse_json

DB_FILENAME = 'ledger.sqlite3'
WAL_FILENAME = 'ledger.sqlite3-wal'
ANCHOR_FILENAME = 'anchor'
LOCK_FILENAME = 'lock'
APPLICATION_ID = 0x41434C47
USER_VERSION = 1
PAGE_SIZE = 4096
ANCHOR_BYTES = 8192
SLOT_BYTES = 1024
SLOT_OFFSETS = (0, 4096)
ANCHOR_MAGIC = b'ACANCHOR'
ANCHOR_TAG = b'acct.anchor.v1\0'
MAX_ANCHOR_BODY = 960
MAX_EVENTS = 8192
_CREATE_FLAGS = os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
_HEX = frozenset('0123456789abcdef')
_UUID_DASHES = (8, 13, 18, 23)
_TOP_KEYS = frozenset({'format', 'counter', 'ledger_uuid', 'ledger_generation',
                       'experiment_id', 'head', 'hold'})
_HEAD_KEYS = frozenset({'sequence', 'event_digest'})
_HOLD_KEYS = frozenset({'code', 'observed_sequence', 'boot_id'})
RECOVERY_HOLDS = frozenset({
    'ledger_truncated', 'ledger_anchor_missing', 'ledger_anchor_invalid',
    'ledger_anchor_conflict', 'ledger_identity_mismatch', 'ledger_schema_invalid',
    'ledger_corrupt', 'ledger_event_invalid', 'ledger_replay_mismatch',
    'event_conflict', 'tail_adopted_unreconciled', 'capacity_exhausted',
})
_SCHEMA_SQL = (
    ('CREATE TABLE ledger_events (\n'
     '  sequence INTEGER PRIMARY KEY CHECK (sequence BETWEEN 1 AND 8192),\n'
     '  event_id TEXT NOT NULL UNIQUE CHECK (length(event_id) = 36),\n'
     '  event_type TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 64),\n'
     '  body BLOB NOT NULL CHECK (length(body) BETWEEN 2 AND 16384),\n'
     '  event_digest TEXT NOT NULL UNIQUE CHECK (length(event_digest) = 64)\n'
     ') STRICT'),
    ('CREATE TRIGGER ledger_events_no_update BEFORE UPDATE ON ledger_events\n'
     "  BEGIN SELECT RAISE(ABORT, 'append_only'); END"),
    ('CREATE TRIGGER ledger_events_no_delete BEFORE DELETE ON ledger_events\n'
     "  BEGIN SELECT RAISE(ABORT, 'append_only'); END"),
    ('CREATE TRIGGER ledger_events_contiguous BEFORE INSERT ON ledger_events\n'
     '  WHEN NEW.sequence != (SELECT coalesce(max(sequence), 0) + 1 FROM ledger_events)\n'
     "  BEGIN SELECT RAISE(ABORT, 'sequence'); END"),
)
_SCHEMA_QUERY = 'SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY name'
_ROWS_QUERY = ('SELECT sequence, event_id, event_type, body, event_digest '
               'FROM ledger_events ORDER BY sequence')
_INSERT = ('INSERT INTO ledger_events '
           '(sequence, event_id, event_type, body, event_digest) VALUES (?, ?, ?, ?, ?)')
_SETTINGS = (
    ('synchronous', 'FULL', 2), ('fullfsync', 'ON', 1),
    ('checkpoint_fullfsync', 'ON', 1), ('trusted_schema', 'OFF', 0),
    ('cell_size_check', 'ON', 1), ('max_page_count', 40960, 40960),
    ('journal_size_limit', 8 * 2**20, 8 * 2**20),
    ('wal_autocheckpoint', 1000, 1000),
)


class LedgerError(Exception):
    """Fixed failure code, with no caller data or filesystem path."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EventReceipt:
    ledger_uuid: str
    ledger_generation: int
    experiment_id: str
    sequence: int
    event_id: str
    event_digest: str
    anchor_counter: int
    read_back: bool = True


@dataclass(frozen=True, slots=True)
class Inspection:
    state: str
    code: str | None
    head: tuple[int, str] | None
    ledger_uuid: str | None
    experiment_id: str | None


@dataclass(frozen=True, slots=True)
class ReservationView:
    """A stopped v1 Receiver ledger's verified reservation evidence."""

    state: str
    code: str | None
    head: tuple[int, str] | None = None
    ledger_uuid: str | None = None
    generation: int | None = None
    experiment_id: str | None = None
    population: str | None = None
    reservations: tuple = ()


@dataclass(frozen=True, slots=True)
class ArchiveActiveView:
    """Query-only stopped v1 event image; the writer lock is no longer held."""

    state: str
    code: str | None
    head: tuple[int, str] | None = None
    population: str | None = None
    events: tuple[AccountingEvent, ...] = ()


def _require(condition, code='ledger_argument'):
    if not condition:
        raise LedgerError(code)


def _uuid_ok(value):
    return type(value) is str and len(value) == 36 and all(
        character == '-' if position in _UUID_DASHES else character in _HEX
        for position, character in enumerate(value)
    )


def _digest_ok(value):
    return type(value) is str and len(value) == 64 and all(c in _HEX for c in value)


def _lstat(path):
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _check_stat(path, *, directory=False):
    found = _lstat(path)
    _require(found is not None, 'ledger_missing')
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    _require(kind(found.st_mode) and not stat.S_ISLNK(found.st_mode),
             'ledger_path_invalid')
    _require(found.st_uid == os.geteuid() and not found.st_mode & 0o077,
             'ledger_permissions')
    if not directory:
        _require(found.st_nlink == 1, 'ledger_permissions')
    return found


def _check_directory(path):
    _require(isinstance(path, Path) and not any(c in str(path) for c in '?#%'),
             'ledger_path_invalid')
    return _check_stat(path, directory=True)


def _take_lock(path):
    try:
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600)
    except OSError:
        raise LedgerError('ledger_path_invalid') from None
    try:
        found = os.fstat(fd)
        _require(stat.S_ISREG(found.st_mode) and found.st_nlink == 1 and
                 found.st_uid == os.geteuid() and not found.st_mode & 0o077,
                 'ledger_permissions')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except LedgerError:
        os.close(fd)
        raise
    except OSError as error:
        os.close(fd)
        code = 'ledger_locked' if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK) else (
            'ledger_path_invalid')
        raise LedgerError(code) from None
    return fd


def _release_handles(connection, lock_fd):
    failed = False
    if connection is not None:
        try:
            connection.close()
        except Exception:  # noqa: BLE001 - cleanup must still release the lock.
            failed = True
    if lock_fd is not None:
        try:
            os.close(lock_fd)
        except OSError:
            failed = True
    return failed


def _capability():
    _require(sqlite3.sqlite_version_info >= (3, 37, 0) and
             hasattr(sqlite3.Connection, 'setconfig') and
             hasattr(sqlite3, 'SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE'),
             'sqlite_unsupported')
    _require(sys.platform == 'linux' or
             (sys.platform == 'darwin' and hasattr(fcntl, 'F_FULLFSYNC')),
             'ledger_sync_unsupported')


def _sqlite_code(error):
    value = getattr(error, 'sqlite_errorcode', None)
    if type(value) is int and value & 0xFF in (sqlite3.SQLITE_CORRUPT,
                                                sqlite3.SQLITE_NOTADB):
        return 'ledger_corrupt'
    return 'ledger_open_failed'


def _full_sync(fd):
    if sys.platform == 'darwin':
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    elif sys.platform == 'linux':
        os.fsync(fd)
    else:
        raise LedgerError('ledger_sync_unsupported')


def _sync_path(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        _full_sync(fd)
    finally:
        os.close(fd)


def _set_pragma(cursor, name, value, expected):
    cursor.execute(f'PRAGMA {name}={value}')
    _require(cursor.execute(f'PRAGMA {name}').fetchone()[0] == expected,
             'sqlite_unsupported')


def _connect(path):
    connection = sqlite3.connect(f'file:{path}?mode=rw', uri=True,
                                 isolation_level=None, check_same_thread=False)
    try:
        connection.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        _require(connection.getconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE) is True,
                 'sqlite_unsupported')
        cursor = connection.cursor()
        _require(cursor.execute('PRAGMA database_list').fetchall() ==
                 [(0, 'main', os.path.realpath(path))], 'ledger_path_invalid')
        _require(cursor.execute('PRAGMA locking_mode=EXCLUSIVE').fetchone()[0] ==
                 'exclusive', 'sqlite_unsupported')
        for setting in _SETTINGS:
            _set_pragma(cursor, *setting)
        return connection
    except Exception:
        connection.close()
        raise


def _reference_schema():
    connection = sqlite3.connect(':memory:')
    try:
        for sql in _SCHEMA_SQL:
            connection.execute(sql)
        return tuple(connection.execute(_SCHEMA_QUERY))
    finally:
        connection.close()


def _encode_slot(body):
    payload = canonical_json(body, ascii_only=True)
    _require(1 <= len(payload) <= MAX_ANCHOR_BODY, 'ledger_anchor_invalid')
    header = ANCHOR_MAGIC + struct.pack('>I', len(payload))
    checksum = hashlib.sha256(ANCHOR_TAG + header + payload).digest()
    slot = header + payload + checksum
    return slot + bytes(SLOT_BYTES - len(slot))


def _slot_body(region):
    if region == bytes(len(region)):
        return 'empty', None
    if len(region) != 4096 or region[:8] != ANCHOR_MAGIC:
        return 'invalid', None
    length = struct.unpack('>I', region[8:12])[0]
    if not 1 <= length <= MAX_ANCHOR_BODY:
        return 'invalid', None
    end = 12 + length
    checksum = hashlib.sha256(ANCHOR_TAG + region[:end]).digest()
    if region[end:end + 32] != checksum or any(region[end + 32:]):
        return 'invalid', None
    try:
        body = parse_json(region[12:end], max_bytes=MAX_ANCHOR_BODY,
                          numbers='integer', ascii_only=True)
        if type(body) is not dict or canonical_json(body, ascii_only=True) != region[12:end]:
            return 'invalid', None
    except JSONPolicyError:
        return 'invalid', None
    if type(body.get('format')) is str and body['format'] != 'acct.anchor.v1':
        return 'newer', None
    if body.keys() != _TOP_KEYS:
        return 'invalid', None
    head, hold = body['head'], body['hold']
    valid = (
        type(body['counter']) is int and 1 <= body['counter'] < 2**53 and
        _uuid_ok(body['ledger_uuid']) and _uuid_ok(body['experiment_id']) and
        type(body['ledger_generation']) is int and
        1 <= body['ledger_generation'] < 2**31 and
        type(head) is dict and head.keys() == _HEAD_KEYS and
        type(head['sequence']) is int and 1 <= head['sequence'] <= MAX_EVENTS and
        _digest_ok(head['event_digest']) and
        (hold is None or (type(hold) is dict and hold.keys() == _HOLD_KEYS and
                          type(hold['code']) is str and
                          hold['code'] in RECOVERY_HOLDS and
                          _uuid_ok(hold['boot_id']) and
                          type(hold['observed_sequence']) is int and
                          0 <= hold['observed_sequence'] <= MAX_EVENTS))
    )
    return ('valid', body) if valid else ('invalid', None)


def _read_anchor_pair(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        raw = os.read(fd, ANCHOR_BYTES + 1)
    finally:
        os.close(fd)
    _require(len(raw) == ANCHOR_BYTES, 'ledger_anchor_invalid')
    slots = tuple(_slot_body(raw[start:start + 4096]) for start in SLOT_OFFSETS)
    _require(not any(kind == 'invalid' for kind, _ in slots),
             'ledger_anchor_invalid')
    _require(not any(kind == 'newer' for kind, _ in slots),
             'ledger_schema_unsupported')
    valid = [(index, body) for index, (kind, body) in enumerate(slots)
             if kind == 'valid']
    _require(valid, 'ledger_anchor_invalid')
    for index, body in valid:
        _require((body['counter'] - 1) % 2 == index, 'ledger_anchor_invalid')
    if len(valid) == 1:
        _require(valid[0][0] == 0 and valid[0][1]['counter'] == 1 and
                 slots[1][0] == 'empty', 'ledger_anchor_invalid')
        return valid[0][1], None
    older, newer = sorted((body for _, body in valid), key=lambda item: item['counter'])
    identity = lambda item: (item['ledger_uuid'], item['ledger_generation'],
                             item['experiment_id'])
    _require(newer['counter'] == older['counter'] + 1 and
             identity(newer) == identity(older) and
             newer['head']['sequence'] >= older['head']['sequence'] and
             not (older['hold'] is not None and newer['hold'] is None),
             'ledger_anchor_invalid')
    return newer, older


def _read_anchor(path):
    return _read_anchor_pair(path)[0]


def _check_older_anchor(projection, older):
    if older is not None:
        sequence = older['head']['sequence']
        _require(sequence <= projection.head_sequence and
                 projection.events[sequence - 1].digest == older['head']['event_digest'],
                 'ledger_anchor_conflict')


def _check_database_header(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        header = os.read(fd, 100)
    finally:
        os.close(fd)
    _require(len(header) == 100 and header[:16] == b'SQLite format 3\0' and
             struct.unpack('>H', header[16:18])[0] == PAGE_SIZE,
             'ledger_corrupt')


def _check_wal_header(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        header = os.read(fd, 32)
    finally:
        os.close(fd)
    _require(len(header) == 32 and
             struct.unpack('>III', header[:12]) in (
                 (0x377F0682, 3007000, PAGE_SIZE),
                 (0x377F0683, 3007000, PAGE_SIZE),
             ), 'ledger_corrupt')


def _write_anchor_slot(path, body):
    slot = _encode_slot(body)
    offset = SLOT_OFFSETS[(body['counter'] - 1) % 2]
    fd = os.open(str(path), os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _require(os.pwrite(fd, slot, offset) == len(slot), 'ledger_write_failed')
        _full_sync(fd)
    finally:
        os.close(fd)


def _persist_hold(path, anchor, code, observed_sequence):
    _require(code in RECOVERY_HOLDS and anchor['hold'] is None,
             'ledger_anchor_invalid')
    hold = {'code': code, 'observed_sequence': observed_sequence,
            'boot_id': str(uuid4())}
    for _ in range(2):
        anchor = dict(anchor, counter=anchor['counter'] + 1, hold=hold)
        _require(anchor['counter'] < 2**53, 'ledger_anchor_invalid')
        _write_anchor_slot(path, anchor)
        _require(_read_anchor(path) == anchor, 'ledger_anchor_invalid')
    return anchor


def _checked_event(event, *, genesis=False):
    _require(type(event) is AccountingEvent)
    try:
        checked = decode_event(event.raw, expected_digest=event.digest)
    except AccountingEventError:
        raise LedgerError('ledger_event_invalid') from None
    value = checked.fields()
    _require(value['actor_kind'] == 'receiver' and
             value['event_type'] != 'reservation_created', 'ledger_event_invalid')
    if genesis:
        _require(value['event_type'] == 'genesis' and
                 value['data']['population'] == 'unknown', 'ledger_event_invalid')
    return checked, value


def _read_rows(connection):
    events = []
    for row in connection.execute(_ROWS_QUERY):
        sequence, event_id, event_type, raw, digest = row
        try:
            checked = decode_event(bytes(raw), expected_digest=digest)
        except (AccountingEventError, TypeError, ValueError):
            raise LedgerError('ledger_event_invalid') from None
        value = checked.fields()
        _require((sequence, event_id, event_type) ==
                 (value['sequence'], value['event_id'], value['event_type']) and
                 value['actor_kind'] == 'receiver' and
                 value['event_type'] != 'reservation_created',
                 'ledger_event_invalid')
        if not events:
            _require(value['event_type'] == 'genesis' and
                     value['data']['population'] == 'unknown', 'ledger_event_invalid')
        events.append(checked)
    _require(events, 'ledger_missing')
    try:
        projection = replay_accounting(tuple(events))
    except AccountingTransitionError:
        raise LedgerError('ledger_replay_mismatch') from None
    return projection


def _verify_existing(directory, connection, anchor):
    cursor = connection.cursor()
    _require(cursor.execute('PRAGMA application_id').fetchone()[0] ==
             APPLICATION_ID, 'ledger_identity_mismatch')
    version = cursor.execute('PRAGMA user_version').fetchone()[0]
    _require(version <= USER_VERSION, 'ledger_schema_unsupported')
    _require(version == USER_VERSION and
             cursor.execute('PRAGMA page_size').fetchone()[0] == PAGE_SIZE and
             cursor.execute('PRAGMA journal_mode').fetchone()[0] == 'wal' and
             tuple(cursor.execute(_SCHEMA_QUERY)) == _reference_schema(),
             'ledger_schema_invalid')
    _require(tuple(cursor.execute('PRAGMA integrity_check')) == (('ok',),),
             'ledger_corrupt')
    projection = _read_rows(connection)
    _require((projection.ledger_uuid, projection.ledger_generation,
              projection.experiment_id) ==
             (anchor['ledger_uuid'], anchor['ledger_generation'],
              anchor['experiment_id']), 'ledger_identity_mismatch')
    anchored_sequence = anchor['head']['sequence']
    _require(anchored_sequence <= projection.head_sequence and
             projection.events[anchored_sequence - 1].digest ==
             anchor['head']['event_digest'], 'ledger_anchor_conflict')
    current, older = _read_anchor_pair(directory / ANCHOR_FILENAME)
    _require(current == anchor, 'ledger_anchor_conflict')
    _check_older_anchor(projection, older)
    _require(projection.head_sequence <= anchored_sequence + 1,
             'ledger_anchor_conflict')
    return projection


class LedgerStore:
    """Exclusive verified store of receiver-origin v1 accounting events."""

    def __init__(self, directory, connection, lock_fd, anchor, projection):
        self.directory = directory
        self._connection = connection
        self._lock_fd = lock_fd
        self._anchor = anchor
        self._projection = projection
        self._closed = False
        self._broken = False

    @property
    def head(self):
        return self.projection.head_sequence, self.projection.head_digest

    @property
    def projection(self):
        return self._projection

    def _writable(self):
        _require(not self._closed, 'ledger_closed')
        _require(self._anchor['hold'] is None, 'ledger_held')
        _require(not self._broken, 'ledger_closed')

    def _physical_head(self):
        try:
            _require(replay_accounting(self._projection.events) == self._projection,
                     'projection_conflict')
        except AccountingTransitionError:
            raise LedgerError('projection_conflict') from None
        anchor_path = self.directory / ANCHOR_FILENAME
        _require(_lstat(anchor_path) is not None, 'ledger_anchor_missing')
        _check_stat(anchor_path)
        anchor, older = _read_anchor_pair(anchor_path)
        _check_older_anchor(self.projection, older)
        row = self._connection.execute(
            'SELECT sequence, event_digest FROM ledger_events ORDER BY sequence DESC LIMIT 1'
        ).fetchone()
        _require(anchor == self._anchor and row == self.head,
                 'ledger_anchor_conflict')
        return anchor

    def _write_anchor(self, body):
        _require(body['counter'] == self._anchor['counter'] + 1 and
                 body['counter'] < 2**53, 'ledger_anchor_invalid')
        _write_anchor_slot(self.directory / ANCHOR_FILENAME, body)

    def append(self, event, *, expected_head):
        """Append one receiver event and read back SQL row and anchor before receipt."""
        self._writable()
        checked, value = _checked_event(event)
        try:
            self._physical_head()
        except LedgerError:
            self._broken = True
            raise
        except (OSError, sqlite3.Error):
            self._broken = True
            raise LedgerError('ledger_open_failed') from None
        event_id = value['event_id']
        try:
            existing = self._connection.execute(
                'SELECT sequence, body, event_digest FROM ledger_events WHERE event_id=?',
                (event_id,),
            ).fetchone()
        except (OSError, sqlite3.Error):
            self._broken = True
            raise LedgerError('ledger_open_failed') from None
        if existing is not None:
            if bytes(existing[1]) != checked.raw or existing[2] != checked.digest:
                try:
                    self._anchor = _persist_hold(
                        self.directory / ANCHOR_FILENAME, self._anchor,
                        'event_conflict', self.head[0],
                    )
                except (LedgerError, OSError):
                    self._broken = True
                    raise LedgerError('ledger_write_failed') from None
                raise LedgerError('event_conflict')
            return EventReceipt(self.projection.ledger_uuid,
                                self.projection.ledger_generation,
                                self.projection.experiment_id, existing[0],
                                event_id, checked.digest, self._anchor['counter'])
        _require(type(expected_head) is str and expected_head == self.head[1],
                 'stale_head')
        _require(self.head[0] < MAX_EVENTS, 'history_limit')
        try:
            next_projection = apply_event(self.projection, checked,
                                          expected_head=expected_head)
        except AccountingTransitionError as error:
            raise LedgerError(error.code) from None
        next_anchor = dict(self._anchor,
                           counter=self._anchor['counter'] + 1,
                           head={'sequence': next_projection.head_sequence,
                                 'event_digest': next_projection.head_digest})
        try:
            cursor = self._connection.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute(_INSERT, (value['sequence'], event_id, value['event_type'],
                                     checked.raw, checked.digest))
            cursor.execute('COMMIT')
            self._write_anchor(next_anchor)
            stored = cursor.execute(
                'SELECT sequence, event_id, event_type, body, event_digest '
                'FROM ledger_events WHERE sequence=?', (value['sequence'],)
            ).fetchone()
            _require(stored == (value['sequence'], event_id, value['event_type'],
                                checked.raw, checked.digest) and
                     _read_anchor(self.directory / ANCHOR_FILENAME) == next_anchor,
                     'ledger_readback_failed')
        except Exception:  # noqa: BLE001 - every ambiguous commit path latches the store.
            self._broken = True
            raise LedgerError('ledger_write_failed') from None
        self._anchor = next_anchor
        self._projection = next_projection
        return EventReceipt(self.projection.ledger_uuid,
                            self.projection.ledger_generation,
                            self.projection.experiment_id, value['sequence'],
                            event_id, checked.digest, next_anchor['counter'])

    @classmethod
    def create(cls, directory, genesis):
        _capability()
        checked, value = _checked_event(genesis, genesis=True)
        _require(isinstance(directory, Path) and not any(c in str(directory) for c in '?#%'),
                 'ledger_path_invalid')
        _require(_lstat(directory) is None, 'ledger_exists')
        lock_fd = None
        connection = None
        try:
            os.mkdir(directory, 0o700)
            _check_directory(directory)
            _sync_path(directory.parent)
            lock_fd = _take_lock(directory / LOCK_FILENAME)
            db_path = directory / DB_FILENAME
            fd = os.open(str(db_path), _CREATE_FLAGS | os.O_WRONLY, 0o600)
            os.close(fd)
            connection = _connect(db_path)
            cursor = connection.cursor()
            _set_pragma(cursor, 'page_size', PAGE_SIZE, PAGE_SIZE)
            _require(cursor.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal',
                     'sqlite_unsupported')
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute(f'PRAGMA application_id={APPLICATION_ID}')
            cursor.execute(f'PRAGMA user_version={USER_VERSION}')
            for sql in _SCHEMA_SQL:
                cursor.execute(sql)
            cursor.execute(_INSERT, (1, value['event_id'], 'genesis', checked.raw,
                                     checked.digest))
            cursor.execute('COMMIT')
            _sync_path(directory)
            anchor_path = directory / ANCHOR_FILENAME
            fd = os.open(str(anchor_path), _CREATE_FLAGS | os.O_RDWR, 0o600)
            try:
                os.ftruncate(fd, ANCHOR_BYTES)
                body = {'format': 'acct.anchor.v1', 'counter': 1,
                        'ledger_uuid': value['ledger_uuid'],
                        'ledger_generation': value['ledger_generation'],
                        'experiment_id': value['experiment_id'],
                        'head': {'sequence': 1, 'event_digest': checked.digest},
                        'hold': None}
                slot = _encode_slot(body)
                _require(os.pwrite(fd, slot, 0) == len(slot), 'ledger_write_failed')
                _full_sync(fd)
            finally:
                os.close(fd)
            _sync_path(directory)
            _require(_read_anchor(anchor_path) == body, 'ledger_anchor_invalid')
            projection = _read_rows(connection)
            _require(projection.head_digest == checked.digest, 'ledger_event_invalid')
            return cls(directory, connection, lock_fd, body, projection)
        except Exception as error:
            _release_handles(connection, lock_fd)
            if isinstance(error, LedgerError):
                raise
            raise LedgerError('ledger_create_failed') from None

    @classmethod
    def open(cls, directory):
        _capability()
        _check_directory(directory)
        lock_fd = _take_lock(directory / LOCK_FILENAME)
        connection = None
        anchor = None
        try:
            db_path = directory / DB_FILENAME
            anchor_path = directory / ANCHOR_FILENAME
            found = _check_stat(db_path)
            _require(_lstat(anchor_path) is not None, 'ledger_anchor_missing')
            _check_stat(anchor_path)
            _require(_lstat(directory / WAL_FILENAME) is not None,
                     'ledger_wal_absent')
            _check_stat(directory / WAL_FILENAME)
            anchor = _read_anchor(anchor_path)
            _require(anchor['hold'] is None, 'ledger_held')
            _require(found.st_size >= PAGE_SIZE, 'ledger_truncated')
            _check_database_header(db_path)
            _check_wal_header(directory / WAL_FILENAME)
            connection = _connect(db_path)
            projection = _verify_existing(directory, connection, anchor)
            anchored_sequence = anchor['head']['sequence']
            if projection.head_sequence == anchored_sequence + 1:
                hold = {'code': 'tail_adopted_unreconciled',
                        'observed_sequence': projection.head_sequence,
                        'boot_id': str(uuid4())}
                for _ in range(2):
                    anchor = dict(anchor, counter=anchor['counter'] + 1,
                                  head={'sequence': projection.head_sequence,
                                        'event_digest': projection.head_digest},
                                  hold=hold)
                    _write_anchor_slot(anchor_path, anchor)
                    _require(_read_anchor(anchor_path) == anchor,
                             'ledger_anchor_invalid')
                raise LedgerError('ledger_held')
            _require(projection.head_sequence == anchored_sequence,
                     'ledger_anchor_conflict')
            return cls(directory, connection, lock_fd, anchor, projection)
        except LedgerError as error:
            if anchor is not None and error.code in RECOVERY_HOLDS:
                try:
                    _persist_hold(anchor_path, anchor, error.code,
                                  anchor['head']['sequence'])
                except (LedgerError, OSError):
                    error = LedgerError('ledger_write_failed')
            _release_handles(connection, lock_fd)
            raise error from None
        except sqlite3.Error as error:
            code = _sqlite_code(error)
            if anchor is not None and code in RECOVERY_HOLDS:
                try:
                    _persist_hold(anchor_path, anchor, code,
                                  anchor['head']['sequence'])
                except (LedgerError, OSError):
                    code = 'ledger_write_failed'
            _release_handles(connection, lock_fd)
            raise LedgerError(code) from None
        except OSError:
            _release_handles(connection, lock_fd)
            raise LedgerError('ledger_open_failed') from None

    @classmethod
    def inspect(cls, directory):
        """Verify a stopped image without appending or acknowledging an event."""
        report, _projection = cls._inspect_verified(directory)
        return report

    @classmethod
    def inspect_reservation_view(cls, directory):
        """Expose only facts verified by v1 replay and the exact current anchor."""
        report, projection = cls._inspect_verified(directory)
        if report.state != 'ready':
            return ReservationView(report.state, report.code)
        # _read_rows rejects every reservation_created row and fixture origin;
        # the v1 store can therefore release only a verified empty tuple.
        return ReservationView(
            'ready', None, report.head, projection.ledger_uuid,
            projection.ledger_generation, projection.experiment_id,
            projection.population, (),
        )

    @classmethod
    def inspect_archive_active_view(cls, directory):
        """Release original rows only after query-only replay, anchor and close checks."""
        report, projection = cls._inspect_verified(directory)
        if report.state != 'ready':
            return ArchiveActiveView(report.state, report.code)
        return ArchiveActiveView(
            'ready', None, report.head, projection.population, projection.events,
        )

    @classmethod
    def _inspect_verified(cls, directory):
        """Shared query-only verification; the projection never escapes a bad close."""
        lock_fd = None
        connection = None
        projection = None
        try:
            _capability()
            _check_directory(directory)
            lock_fd = _take_lock(directory / LOCK_FILENAME)
            db_path = directory / DB_FILENAME
            found = _check_stat(db_path)
            _require(_lstat(directory / ANCHOR_FILENAME) is not None,
                     'ledger_anchor_missing')
            _check_stat(directory / ANCHOR_FILENAME)
            _require(_lstat(directory / WAL_FILENAME) is not None,
                     'ledger_wal_absent')
            _check_stat(directory / WAL_FILENAME)
            _require(found.st_size >= PAGE_SIZE, 'ledger_truncated')
            anchor = _read_anchor(directory / ANCHOR_FILENAME)
            if anchor['hold'] is not None:
                result = Inspection('held', anchor['hold']['code'], None,
                                    anchor['ledger_uuid'], anchor['experiment_id'])
            else:
                _check_database_header(db_path)
                _check_wal_header(directory / WAL_FILENAME)
                connection = _connect(db_path)
                cursor = connection.cursor()
                _set_pragma(cursor, 'query_only', 'ON', 1)
                projection = _verify_existing(directory, connection, anchor)
                _require(projection.head_sequence == anchor['head']['sequence'],
                         'ledger_tail_unverified')
                result = Inspection('ready', None, (projection.head_sequence,
                                                    projection.head_digest),
                                    projection.ledger_uuid, projection.experiment_id)
        except LedgerError as error:
            result = Inspection('held' if error.code in RECOVERY_HOLDS else
                                'unverified', error.code, None, None, None)
        except sqlite3.Error as error:
            code = _sqlite_code(error)
            result = Inspection('held' if code in RECOVERY_HOLDS else 'unverified',
                                code, None, None, None)
        except OSError:
            result = Inspection('unverified', 'ledger_open_failed', None, None, None)
        finally:
            close_failed = _release_handles(connection, lock_fd)
        if close_failed:
            return Inspection('unverified', 'ledger_close_failed', None, None, None), None
        return result, projection if result.state == 'ready' else None

    def close(self):
        if not self._closed:
            self._closed = True
            if _release_handles(self._connection, self._lock_fd):
                raise LedgerError('ledger_close_failed')

    def __enter__(self):
        return self

    def __exit__(self, *_unused):
        self.close()


__all__ = ['ArchiveActiveView', 'EventReceipt', 'Inspection', 'LedgerError',
           'LedgerStore', 'ReservationView']
