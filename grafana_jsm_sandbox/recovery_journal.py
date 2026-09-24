"""The Receiver-facing recovery journal handle: create, verified open,
restart replay, admission and holds (ticket 37, unit 15, module 4).

This is the I/O shell: it owns one ``threading.Lock`` that serializes every
public operation, reads the clock and mints IDs through ``id_factory``, and
maps store and reducer codes onto the closed hold vocabulary. It drives
``journal_store.JournalStore.rows()`` through the reducer's
``group_commits``/``verify_commit``/``apply_delta`` at open -- the store
deliberately leaves commit framing and replay to this module -- and it is the
only place that calls ``journal_store.JournalStore.persist_hold``: a verified
recovery finding is persisted before the journal is returned held; a process
finding never is.

Error discipline matches ``forwarder_json``: every ``except`` body only
assigns a local variable or passes, and a fresh error is raised after the
``try`` statement, so no ``JournalError`` carries a wrapped exception in
``__cause__`` or ``__context__``. A ``BaseException`` is never caught; a
``finally`` clause latches the hold or closes the store on its way out.
"""

from __future__ import annotations

import dataclasses
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

from .journal_records import MAX_SEQ, RecordError, Stamp, format_wall_time, validate_id
from .journal_reducer import (
    DEFAULT_BOUNDS,
    CapacityRefusal,
    JournalBounds,
    ReplayError,
    apply_delta,
    dispatch_holds,
    group_commits,
    new_projection,
    pending_digest,
    pending_entries,
    plan_admission,
    plan_capacity_hold,
    plan_genesis,
    plan_restart,
    state_digest,
    verify_commit,
)
from .journal_source import SourceError, SourceRecord, source_digest, validate_source
from .journal_store import Finding, JournalStore, StoreError

HOLD_SCOPES = ("recovery", "process")

JOURNAL_ERROR_CODES = frozenset({
    "journal_argument", "journal_path_invalid", "journal_permissions", "journal_locked",
    "journal_missing", "journal_exists", "journal_sync_unsupported", "sqlite_unsupported",
    "journal_create_failed", "journal_closed", "journal_held", "source_invalid",
    "capacity_admissions", "capacity_pending", "capacity_bytes", "journal_write_failed",
    "journal_clock_invalid", "journal_divergence", "journal_capacity_recovery",
})

# Framing/replay codes raised by group_commits/verify_commit during open map onto the
# store's durable hold vocabulary; every one of them is a recovery-scope finding.
_REPLAY_HOLD_CODES = MappingProxyType({
    "replay_chain": "journal_chain_broken",
    "replay_framing": "journal_chain_broken",
    "replay_generation": "journal_chain_broken",
    "replay_tail_incomplete": "journal_tail_unverified",
    "replay_shape": "journal_replay_mismatch",
    "replay_mismatch": "journal_replay_mismatch",
    "replay_boot": "journal_replay_mismatch",
    "replay_clock": "journal_replay_mismatch",
})


class JournalError(Exception):
    """A fixed, non-diagnostic recovery-journal rejection; never embeds caller data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def new_id() -> str:
    return str(uuid.uuid4())


def _mint_id(id_factory: Callable[[], str]) -> str | None:
    """A fresh ID from ``id_factory``, or ``None`` when it raises or returns an invalid one."""
    try:
        value = validate_id(id_factory())
    except Exception:  # noqa: BLE001 - any factory fault reads as None, never raw.
        value = None
    return value


def _read_clock(
    wall_clock: Callable[[], int], mono_clock: Callable[[], int],
) -> tuple[str, int] | None:
    """``(wall_time, mono_us)`` from the two clocks, or ``None`` on any clock fault."""
    reading = None
    try:
        wall_ns, mono_ns = wall_clock(), mono_clock()
        if type(mono_ns) is int and 0 <= mono_ns // 1_000 <= MAX_SEQ:
            reading = (format_wall_time(wall_ns), mono_ns // 1_000)
    except Exception:  # noqa: BLE001 - any clock fault reads as None, never raw.
        reading = None
    return reading


@dataclasses.dataclass(frozen=True)
class AdmissionReceipt:
    admission_id: str
    arrival_seq: int
    commit_seq: int
    event_seqs: tuple[int, int]
    result: str
    decision: str
    dispatch_holds: tuple[str, ...]
    source_group: str
    dedupe_key: str
    superseded: tuple[tuple[str, str], ...]


# --- create and open ------------------------------------------------------------


def create_recovery_journal(
    directory: Path, *, bounds: JournalBounds = DEFAULT_BOUNDS,
    wall_clock: Callable[[], int] = time.time_ns, mono_clock: Callable[[], int] = time.monotonic_ns,
    id_factory: Callable[[], str] = new_id,
) -> RecoveryJournal:
    # Genesis is built and verified before anything is written, so every failure
    # up to JournalStore.create leaves no file behind: journal_argument, never
    # journal_create_failed (which tells the operator to remove files by hand).
    journal_uuid = _mint_id(id_factory)
    boot_id = _mint_id(id_factory)
    event_id = _mint_id(id_factory)
    reading = _read_clock(wall_clock, mono_clock)
    projection, plan = new_projection(), None
    if None not in (journal_uuid, boot_id, event_id, reading):
        try:
            stamp = Stamp(boot_id=boot_id, wall_time=reading[0], mono_us=reading[1])
            genesis = plan_genesis(
                journal_uuid=journal_uuid, bounds=bounds, event_id=event_id, stamp=stamp,
            )
            apply_delta(projection, verify_commit(projection, genesis.records))
            plan = genesis
        except Exception:  # noqa: BLE001 - a refused genesis writes nothing, never raw.
            plan = None
    if plan is None:
        raise JournalError("journal_argument")

    code = None
    try:
        store = JournalStore.create(directory, plan.records[0], journal_uuid=journal_uuid)
    except StoreError as error:
        code = error.code
    if code is not None:
        raise JournalError(code) from None
    return RecoveryJournal(
        directory=directory, store=store, projection=projection, boot_id=boot_id,
        id_factory=id_factory, wall_clock=wall_clock, mono_clock=mono_clock,
        verified_state_digest=state_digest(projection), lag_at_open=0,
    )


def open_recovery_journal(
    directory: Path, *, wall_clock: Callable[[], int] = time.time_ns,
    mono_clock: Callable[[], int] = time.monotonic_ns, id_factory: Callable[[], str] = new_id,
) -> RecoveryJournal:
    code = None
    try:
        store = JournalStore.open(directory)
    except StoreError as error:
        code = error.code
    if code is not None:
        raise JournalError(code) from None

    # Any non-clean exit from here on (a bug, or a BaseException such as a
    # crash) closes the store again, so its lock is never left behind.
    completed = False
    try:
        journal = _open_verified(
            store, wall_clock=wall_clock, mono_clock=mono_clock, id_factory=id_factory,
        )
        completed = True
    finally:
        if not completed:
            store.close()
    return journal


def _open_verified(
    store: JournalStore, *, wall_clock: Callable[[], int], mono_clock: Callable[[], int],
    id_factory: Callable[[], str],
) -> RecoveryJournal:
    """Replay and check the opened store; return it ready, or held on the first finding.

    A store or replay finding outranks a failed boot-id mint, which alone is a
    process ``journal_divergence``. A failed ``finish_open`` is a process
    ``journal_open_failed``: nothing has been written, and the next open retries.
    """
    boot_id = _mint_id(id_factory)
    candidate = new_projection()
    finding, lag = store.finding, None
    if finding is None:
        finding, lag = _replay_finding(store, candidate)
    if finding is None and boot_id is None:
        finding = Finding("journal_divergence", "process", None)
    if finding is None:
        finished = False
        try:
            store.finish_open()
            finished = True
        except StoreError:
            pass
        if not finished:
            finding = Finding("journal_open_failed", "process", None)
    if finding is not None:
        return _held_journal(
            store, finding, boot_id=boot_id, lag_at_open=lag, id_factory=id_factory,
            wall_clock=wall_clock, mono_clock=mono_clock,
        )

    journal = RecoveryJournal(
        directory=store.directory, store=store, projection=candidate, boot_id=boot_id,
        id_factory=id_factory, wall_clock=wall_clock, mono_clock=mono_clock,
        verified_state_digest=state_digest(candidate), lag_at_open=lag,
    )
    journal._run_restart_recovery(lag=lag, wal_found=store.wal_found)
    return journal


def _replay_finding(store: JournalStore, candidate) -> tuple[Finding | None, int | None]:
    """Replay every stored row into ``candidate``, then check its head against the anchor.

    Returns the finding, if any, and the anchor lag when the head comparison ran.
    """
    anchor = store.anchor.head
    anchor_record_ok = False
    replay_code = None
    try:
        for group in group_commits(store.rows()):
            apply_delta(candidate, verify_commit(candidate, group))
            for record in group:
                if record.position.event_seq != anchor.event_seq:
                    continue
                anchor_record_ok = (
                    record.position.commit_seq == anchor.commit_seq
                    and record.position.commit_index == record.position.commit_size - 1
                    and record.record_digest == anchor.record_digest
                    and record.position.journal_generation == anchor.generation
                )
    except ReplayError as error:
        replay_code = error.code

    # A digest/chain/column/typed finding raised inside store.rows() ends the
    # generator early; that store-level finding always outranks whatever
    # group_commits/verify_commit made of the truncated tail it was handed.
    if store.finding is not None:
        return store.finding, None
    if replay_code is not None:
        return Finding(_REPLAY_HOLD_CODES[replay_code], "recovery", None), None
    if candidate.head is None:  # an emptied table: every anchored record is gone
        return Finding("journal_truncated", "recovery", None), None

    lag = candidate.head.commit_seq - anchor.commit_seq
    code = None
    if lag < 0:
        code = "journal_truncated"
    elif lag > 1:
        code = "journal_tail_unverified"
    elif not anchor_record_ok:
        code = "journal_anchor_conflict"
    return (None if code is None else Finding(code, "recovery", None)), lag


def _held_journal(
    store: JournalStore, finding: Finding, *, boot_id: str | None, lag_at_open: int | None,
    id_factory: Callable[[], str], wall_clock: Callable[[], int], mono_clock: Callable[[], int],
) -> RecoveryJournal:
    """Persist a recovery finding into the anchor, close the store and return it held."""
    if finding.scope == "recovery" and boot_id is not None:
        try:
            # Also completes a hold that a crash left in only one of the two slots.
            store.persist_hold(finding.code, boot_id=boot_id)
        except StoreError:
            pass
    # Durable once the newest anchor slot carries it; after a failed first write
    # the anchor is unchanged and the next open re-derives the same verdict.
    hold = store.anchor.hold if store.anchor is not None else None
    persisted = finding.scope == "recovery" and hold is not None and hold.code == finding.code
    store.close()
    return RecoveryJournal(
        directory=store.directory, store=store, projection=None, boot_id=boot_id,
        id_factory=id_factory, wall_clock=wall_clock, mono_clock=mono_clock,
        hold_detail=(finding.code, finding.scope, persisted, finding.sqlite_error),
        lag_at_open=lag_at_open,
    )


# --- the handle -------------------------------------------------------------------


class RecoveryJournal:
    """The Receiver-facing recovery journal handle for one directory."""

    def __init__(
        self, *, directory: Path, store: JournalStore, projection, boot_id: str | None,
        id_factory: Callable[[], str], wall_clock: Callable[[], int],
        mono_clock: Callable[[], int], verified_state_digest: str | None = None,
        hold_detail: tuple[str, str, bool, str | None] | None = None,
        lag_at_open: int | None = None,
    ) -> None:
        self._directory = directory
        self._store = store
        self._projection = projection
        self._boot_id = boot_id
        self._id_factory = id_factory
        self._wall_clock = wall_clock
        self._mono_clock = mono_clock
        self._lock = threading.Lock()
        self._closed = False
        self._hold_detail = hold_detail
        self._verified_state_digest = verified_state_digest
        self._anchor_lag_at_open = lag_at_open
        self._refusals_this_boot: dict[str, tuple[int, str]] = {}

    # -- state --

    @property
    def state(self) -> str:
        with self._lock:
            return self._state()

    def _state(self) -> str:
        if self._closed:
            return "closed"
        if self._hold_detail is not None:
            return "held"
        return "ready"

    @property
    def hold(self) -> tuple[str, str] | None:
        with self._lock:
            if self._hold_detail is None:
                return None
            code, scope, _persisted, _sqlite_error = self._hold_detail
            return (code, scope)

    @property
    def dispatch_holds(self) -> tuple[str, ...]:
        with self._lock:
            projection = self._visible_projection()
            return () if projection is None else dispatch_holds(projection)

    def _visible_projection(self):
        """The projection, or ``None`` while held: a held journal shows no projection fields."""
        return None if self._hold_detail is not None else self._projection

    def _latch(self, code: str, scope: str) -> None:
        if self._hold_detail is None:
            self._hold_detail = (code, scope, False, None)

    def _latched_error(self, code: str) -> JournalError:
        """Latch ``code`` as a process hold and return the error that reports it."""
        self._latch(code, "process")
        return JournalError(code)

    # -- restart-on-open (called once, before the handle is returned) --

    def _run_restart_recovery(self, *, lag: int, wal_found) -> None:
        if lag == 1:
            written = False
            try:
                self._store.write_anchor(self._projection.head)
                written = True
            except (StoreError, RecordError):
                pass
            if not written:
                self._latch("journal_write_failed", "process")
                return
        new_boot_id = _mint_id(self._id_factory)
        if new_boot_id is None:
            self._latch("journal_divergence", "process")
            return
        reading = _read_clock(self._wall_clock, self._mono_clock)
        if reading is None:
            self._latch("journal_clock_invalid", "process")
            return
        stamp = Stamp(boot_id=new_boot_id, wall_time=reading[0], mono_us=reading[1])
        event_id = _mint_id(self._id_factory)
        plan = None
        if event_id is not None:
            try:
                plan = plan_restart(
                    self._projection, event_id=event_id, stamp=stamp, anchor_lag=lag,
                    wal_found=wal_found,
                )
            except RecordError:
                pass
        if plan is None:
            self._latch("journal_divergence", "process")
            return
        if isinstance(plan, CapacityRefusal):
            self._latch("journal_capacity_recovery", "process")
            return
        committed = False
        try:
            self._commit(plan, sync_directory=True)
            committed = True
        except JournalError:
            pass  # _commit has latched the hold
        if committed:
            self._boot_id = new_boot_id

    # -- the only write path --

    def _commit(self, plan, *, sync_directory: bool) -> tuple[int, ...]:
        code, duplicate = None, None
        try:
            duplicate = self._store.find_duplicate(plan.records)
        except StoreError as error:
            conflict = error.code == "store_event_conflict"
            code = "journal_divergence" if conflict else "journal_write_failed"
        if code is not None:
            raise self._latched_error(code) from None
        if duplicate is not None:
            return duplicate.event_seqs
        delta = None
        try:
            delta = verify_commit(self._projection, plan.records)
        except ReplayError:
            pass
        if delta is None:
            raise self._latched_error("journal_divergence") from None
        # Any failure latches journal_write_failed; a BaseException (a crash)
        # still latches on its way out, and passes through unchanged.
        event_seqs, completed, failed = (), False, False
        try:
            event_seqs = self._store.append(plan.records, sync_directory=sync_directory)
            completed = True
        except Exception:  # noqa: BLE001 - any ordinary append failure is journal_write_failed.
            failed = True
        finally:
            if not completed:
                self._latch("journal_write_failed", "process")
        if failed:
            raise JournalError("journal_write_failed") from None
        apply_delta(self._projection, delta)
        return event_seqs

    # -- admission --

    def _read_admit_stamp(self) -> Stamp | None:
        reading = _read_clock(self._wall_clock, self._mono_clock)
        if reading is None or reading[1] < self._projection.last_mono_us:
            return None
        return Stamp(boot_id=self._boot_id, wall_time=reading[0], mono_us=reading[1])

    def _bump_refusal(self, code: str, digest: str) -> None:
        count, _ = self._refusals_this_boot.get(code, (0, ""))
        self._refusals_this_boot[code] = (count + 1, digest)

    def admit(self, source: SourceRecord) -> AdmissionReceipt:
        with self._lock:
            if self._closed:
                raise JournalError("journal_closed")
            if self._hold_detail is not None:
                raise JournalError("journal_held")
            valid = None
            try:
                valid = validate_source(source)
            except SourceError:
                pass
            if valid is None:
                raise JournalError("source_invalid") from None
            stamp = self._read_admit_stamp()
            if stamp is None:
                raise self._latched_error("journal_clock_invalid")
            admission_id = _mint_id(self._id_factory)
            dedupe_event_id = None if admission_id is None else _mint_id(self._id_factory)
            if dedupe_event_id is None or dedupe_event_id == admission_id:
                raise self._latched_error("journal_divergence")

            plan = None
            try:
                plan = plan_admission(
                    self._projection, valid, admission_id=admission_id,
                    dedupe_event_id=dedupe_event_id, stamp=stamp,
                )
            except RecordError:
                pass
            if plan is None:
                raise self._latched_error("journal_divergence") from None
            if isinstance(plan, CapacityRefusal):
                raise self._capacity_refusal(plan, source=valid, stamp=stamp)

            event_seqs = self._commit(plan, sync_directory=False)
            outcome = plan.outcome
            return AdmissionReceipt(
                admission_id=admission_id, arrival_seq=outcome["arrival_seq"],
                commit_seq=self._projection.head.commit_seq,
                event_seqs=(event_seqs[0], event_seqs[1]), result=outcome["result"],
                decision=outcome["decision"], dispatch_holds=outcome["dispatch_holds"],
                source_group=outcome["source_group"], dedupe_key=outcome["dedupe_key"],
                superseded=outcome["superseded"],
            )

    def _capacity_refusal(
        self, refusal: CapacityRefusal, *, source: SourceRecord, stamp: Stamp,
    ) -> JournalError:
        """Count the refusal, write its first ``capacity_hold``; return the error to raise."""
        digest = source_digest(source)
        self._bump_refusal(refusal.code, digest)
        hold_event_id = _mint_id(self._id_factory)
        planned, hold_plan = False, None
        if hold_event_id is not None:
            try:
                hold_plan = plan_capacity_hold(
                    self._projection, refusal, event_id=hold_event_id, stamp=stamp,
                    refused_source_digest=digest,
                )
                planned = True
            except RecordError:
                pass
        if not planned:
            raise self._latched_error("journal_divergence") from None
        if isinstance(hold_plan, CapacityRefusal):
            raise self._latched_error("journal_capacity_recovery")
        if hold_plan is not None:  # None: this code's dispatch hold is already active
            self._commit(hold_plan, sync_directory=False)
        return JournalError(refusal.code)

    # -- read-only surface --

    def pending(self) -> tuple:
        with self._lock:
            projection = self._visible_projection()
            return () if projection is None else pending_entries(projection)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            hold = None
            if self._hold_detail is not None:
                code, scope, persisted, sqlite_error = self._hold_detail
                hold = {
                    "code": code, "scope": scope, "persisted": persisted,
                    "sqlite_error": sqlite_error,
                }

            anchor = self._store.anchor
            anchor_json = None
            if anchor is not None:
                # lag_at_open: head minus anchor commit_seq; null when open stopped earlier.
                anchor_json = {
                    "counter": anchor.counter, "commit_seq": anchor.head.commit_seq,
                    "event_seq": anchor.head.event_seq, "lag_at_open": self._anchor_lag_at_open,
                }
            wal_found = self._store.wal_found
            wal_found_json = (
                None if wal_found is None else {"size": wal_found.size, "digest": wal_found.digest}
            )
            refusals_json = {
                code: {"count": count, "last_source_digest": digest}
                for code, (count, digest) in self._refusals_this_boot.items()
            }

            p = self._visible_projection()
            if p is None:
                return {
                    "state": self._state(), "hold": hold, "journal_uuid": None, "generation": None,
                    "boot_id": None, "head": None, "anchor": anchor_json,
                    "wal_found": wal_found_json, "dispatch_holds": None, "counts": None,
                    "bytes": None, "bounds": None, "refusals_this_boot": refusals_json,
                    "verified_state_digest": None, "pending_digest": None, "state_digest": None,
                }

            head_json = {
                "commit_seq": p.head.commit_seq, "event_seq": p.head.event_seq,
                "record_digest": p.head.record_digest,
            }
            holds_json = [
                {"code": code, "since_commit_seq": seq}
                for code, seq in sorted(p.dispatch_holds.items())
            ]
            counts_json = {
                "records": p.head.event_seq, "admissions": p.admission_count,
                "pending_fingerprints": len(p.pending), "source_groups": len(p.baselines),
            }
            bytes_json = {
                "logical": p.logical_bytes, "ordinary_limit": p.bounds.ordinary_bytes,
                "total_limit": p.bounds.total_bytes,
            }
            bounds_json = {
                "max_admissions": p.bounds.max_admissions,
                "max_pending_fingerprints": p.bounds.max_pending_fingerprints,
                "ordinary_bytes": p.bounds.ordinary_bytes, "total_bytes": p.bounds.total_bytes,
            }
            return {
                "state": self._state(), "hold": hold, "journal_uuid": p.journal_uuid,
                "generation": p.generation, "boot_id": p.boot_id, "head": head_json,
                "anchor": anchor_json, "wal_found": wal_found_json, "dispatch_holds": holds_json,
                "counts": counts_json, "bytes": bytes_json, "bounds": bounds_json,
                "refusals_this_boot": refusals_json,
                "verified_state_digest": self._verified_state_digest,
                "pending_digest": pending_digest(p), "state_digest": state_digest(p),
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._store.close()

    def __enter__(self) -> RecoveryJournal:  # noqa: PYI034 - a concrete return type, not Self.
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = [
    "HOLD_SCOPES",
    "JOURNAL_ERROR_CODES",
    "AdmissionReceipt",
    "JournalError",
    "RecoveryJournal",
    "create_recovery_journal",
    "new_id",
    "open_recovery_journal",
]
