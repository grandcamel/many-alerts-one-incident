"""The Receiver-facing recovery journal handle: create, verified open,
restart replay, admission and holds (ticket 37, unit 15, module 4), ingress
refusal records, resume at open and verify-only inspect (unit 17a).

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

from .journal_records import (
    MAX_REFUSAL_RECORDS,
    MAX_SEQ,
    REFUSAL_RESOLVED_RESERVE,
    Head,
    RecordError,
    Stamp,
    format_wall_time,
    refusal_summary_data,
    validate_id,
)
from .journal_reducer import (
    DEFAULT_BOUNDS,
    CapacityRefusal,
    JournalBounds,
    RefusalNotRecorded,
    ReplayError,
    apply_delta,
    dispatch_holds,
    front_door_digest,
    group_commits,
    new_projection,
    pending_digest,
    pending_entries,
    plan_admission,
    plan_capacity_hold,
    plan_genesis,
    plan_ingress_refusal,
    plan_operator_resume,
    plan_restart,
    reservation_claims_digest,
    run_holds_digest,
    state_digest,
    verify_commit,
)
from .journal_source import SourceError, SourceRecord, source_digest, validate_source
from .journal_store import (
    DB_FILENAME,
    PAGE_SIZE,
    WAL_FILENAME,
    Finding,
    JournalStore,
    StoreError,
    _check_directory,
)

HOLD_SCOPES = ("recovery", "process")

JOURNAL_ERROR_CODES = frozenset({
    "journal_argument", "journal_path_invalid", "journal_permissions", "journal_locked",
    "journal_missing", "journal_exists", "journal_sync_unsupported", "sqlite_unsupported",
    "journal_create_failed", "journal_closed", "journal_held", "source_invalid",
    "capacity_admissions", "capacity_pending", "capacity_bytes", "journal_write_failed",
    "journal_clock_invalid", "journal_divergence", "journal_capacity_recovery",
    "refusal_invalid", "resume_invalid", "resume_stale",
})

# record_refusal's outcomes, and verify-only inspect's bounds (unit 17).
REFUSAL_OUTCOMES = ("recorded", "coalesced", "limit", "no_room")
_HEX_DIGITS = frozenset("0123456789abcdef")
_MAX_INSPECT_PENDING = 1_024
_MAX_INSPECT_REFUSALS = 32
_LOCK_FILENAME = "lock"

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


@dataclasses.dataclass(frozen=True)
class ResumeRequest:
    """An operator's request to resume at open: the token is the record
    digest ``inspect_recovery_journal`` reported as the verified head."""

    token: str
    operator: str
    reason: str = "restart-inspected"


@dataclasses.dataclass(frozen=True)
class ResumeReceipt:
    """What a resume committed, held on the handle as ``resumed_this_boot``."""

    commit_seq: int
    hold: str
    since_commit_seq: int
    inspected: Head
    pending_digest: str
    operator: str
    reason: str


@dataclasses.dataclass(frozen=True)
class Inspection:
    """``inspect_recovery_journal``'s verify-only result: a closed, nonsecret
    JSON ``report`` (see docs), plus the admitted ``body_digest`` set for the
    spool survey. For any verdict other than ``ready``, ``references`` is
    empty and the report's ``journal``, ``pending``, ``refusals``, ``resumes``
    and ``resume`` fields are null.
    """

    report: dict
    references: frozenset[str]


def _resume_token_ok(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in _HEX_DIGITS for c in value)


def _check_resume_request(resume: ResumeRequest) -> None:
    ok = type(resume) is ResumeRequest and _resume_token_ok(resume.token)
    if ok:
        try:
            validate_id(resume.operator)
            validate_id(resume.reason)
        except RecordError:
            ok = False
    if not ok:
        raise JournalError("resume_invalid")


def _lstat_or_none(path: Path):
    """``None`` only when ``path`` is absent; any other ``OSError`` propagates."""
    result = None
    try:
        result = path.lstat()
    except FileNotFoundError:
        pass
    return result


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
    resume: ResumeRequest | None = None,
) -> RecoveryJournal:
    if resume is not None:
        _check_resume_request(resume)
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
            resume=resume,
        )
        completed = True
    finally:
        if not completed:
            store.close()
    return journal


def _open_verified(
    store: JournalStore, *, wall_clock: Callable[[], int], mono_clock: Callable[[], int],
    id_factory: Callable[[], str], resume: ResumeRequest | None = None,
) -> RecoveryJournal:
    """Replay and check the opened store; return it ready, or held on the first finding.

    A store or replay finding outranks a failed boot-id mint, which alone is a
    process ``journal_divergence``. A failed ``finish_open`` is a process
    ``journal_open_failed``: nothing has been written, and the next open retries.
    A stale ``resume`` token is checked here, after replay and before
    ``finish_open``, so a refused resume writes nothing (V10).
    """
    boot_id = _mint_id(id_factory)
    candidate = new_projection()
    finding, lag = store.finding, None
    if finding is None:
        finding, lag = _replay_finding(store, candidate)
    if finding is None and boot_id is None:
        finding = Finding("journal_divergence", "process", None)
    if finding is None and resume is not None and resume.token != candidate.head.record_digest:
        raise JournalError("resume_stale")
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
            wall_clock=wall_clock, mono_clock=mono_clock, resume_requested=resume is not None,
        )

    journal = RecoveryJournal(
        directory=store.directory, store=store, projection=candidate, boot_id=boot_id,
        id_factory=id_factory, wall_clock=wall_clock, mono_clock=mono_clock,
        verified_state_digest=state_digest(candidate), lag_at_open=lag,
        resume_requested=resume is not None,
    )
    journal._run_restart_recovery(lag=lag, wal_found=store.wal_found)
    if resume is not None and journal._hold_detail is None:
        journal._resume_at_open(resume)
    return journal


def _replay_finding(
    store: JournalStore, candidate, *, observe: Callable[[tuple], None] | None = None,
) -> tuple[Finding | None, int | None]:
    """Replay every stored row into ``candidate``, then check its head against the anchor.

    Returns the finding, if any, and the anchor lag when the head comparison ran.
    ``observe``, passed only by inspect, is called with each verified commit
    group; an exception it raises is a programming error and propagates
    unchanged (critic 8b).
    """
    anchor = store.anchor.head
    anchor_record_ok = False
    replay_code = None
    try:
        for group in group_commits(store.rows()):
            apply_delta(candidate, verify_commit(candidate, group))
            if observe is not None:
                observe(group)
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
    resume_requested: bool = False,
) -> RecoveryJournal:
    """Persist a recovery finding into the anchor, close the store and return it held.

    A held open never applies a resume (V9); ``resumed_this_boot`` stays None.
    """
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
        lag_at_open=lag_at_open, resume_requested=resume_requested,
    )


# --- the handle -------------------------------------------------------------------


class RecoveryJournal:
    """The Receiver-facing recovery journal handle for one directory."""

    def __init__(
        self, *, directory: Path, store: JournalStore, projection, boot_id: str | None,
        id_factory: Callable[[], str], wall_clock: Callable[[], int],
        mono_clock: Callable[[], int], verified_state_digest: str | None = None,
        hold_detail: tuple[str, str, bool, str | None] | None = None,
        lag_at_open: int | None = None, resume_requested: bool = False,
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
        # Front door (unit 17): per-boot ingress-refusal outcome counters,
        # kept apart from `_refusals_this_boot` (D11: capacity codes only).
        self._refusal_outcomes_this_boot: dict[str, dict[str, int]] = {}
        self._resume_requested = resume_requested
        self._resume_receipt: ResumeReceipt | None = None

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

    def _resume_at_open(self, resume: ResumeRequest) -> None:
        """Commit exactly one ``operator_action`` immediately after the
        restart this same open committed (I20; J1 graft 1). Called only when
        that restart committed cleanly; clock, ID, capacity and write faults
        latch exactly as for restart, and ``resumed_this_boot`` stays None.
        """
        if "restart_recovery" not in self._projection.dispatch_holds:
            return
        new_event_id = _mint_id(self._id_factory)
        if new_event_id is None:
            self._latch("journal_divergence", "process")
            return
        # Same boot as the restart, so a mono reading below its stamp is a
        # clock fault here, as in admit, not a replay divergence.
        stamp = self._read_admit_stamp()
        if stamp is None:
            self._latch("journal_clock_invalid", "process")
            return
        plan = None
        try:
            plan = plan_operator_resume(
                self._projection, event_id=new_event_id, stamp=stamp,
                operator=resume.operator, reason=resume.reason,
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
            self._commit(plan, sync_directory=False)
            committed = True
        except JournalError:
            pass  # _commit has latched the hold
        if committed:
            self._resume_receipt = ResumeReceipt(
                commit_seq=self._projection.head.commit_seq, hold="restart_recovery",
                since_commit_seq=plan.outcome["since_commit_seq"],
                inspected=self._projection.boot_recovered,
                pending_digest=pending_digest(self._projection),
                operator=resume.operator, reason=resume.reason,
            )

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

    def admission_precheck(self) -> str | None:
        """Advisory, exact in one direction (critic 6): once a
        ``capacity_admissions`` dispatch hold exists, every later ``admit``
        would refuse with the same code, so a front door can skip spooling
        first. It deliberately does not fire when the bound is merely
        reached, only once the durable hold exists. Takes no lock: one state
        read and one dict membership test, each atomic under the GIL; `admit`
        stays authoritative.
        """
        if self._closed or self._hold_detail is not None:
            return None
        if "capacity_admissions" in self._projection.dispatch_holds:
            return "capacity_admissions"
        return None

    def record_refusal(self, summary: dict) -> str:
        """Record one ``ingress_refusal``; returns a ``REFUSAL_OUTCOMES``
        value. A malformed ``summary`` never latches: ``refusal_invalid``
        means nothing was recorded, not that the journal is broken.
        """
        with self._lock:
            if self._closed:
                raise JournalError("journal_closed")
            if self._hold_detail is not None:
                raise JournalError("journal_held")
            normalized = None
            try:
                normalized = refusal_summary_data(summary)
            except RecordError:
                pass
            if normalized is None:
                raise JournalError("refusal_invalid") from None
            stamp = self._read_admit_stamp()
            if stamp is None:
                raise self._latched_error("journal_clock_invalid")
            event_id = _mint_id(self._id_factory)
            if event_id is None:
                raise self._latched_error("journal_divergence")

            plan = None
            try:
                plan = plan_ingress_refusal(
                    self._projection, normalized, event_id=event_id, stamp=stamp,
                )
            except RecordError:
                pass
            if plan is None:
                raise self._latched_error("journal_divergence") from None
            code = normalized["code"]
            if isinstance(plan, RefusalNotRecorded):
                self._bump_refusal_outcome(code, plan.reason)
                return plan.reason

            self._commit(plan, sync_directory=False)
            self._bump_refusal_outcome(code, "recorded")
            return "recorded"

    def _bump_refusal_outcome(self, code: str, outcome: str) -> None:
        bucket = self._refusal_outcomes_this_boot.setdefault(code, {})
        bucket[outcome] = bucket.get(outcome, 0) + 1

    @property
    def resumed_this_boot(self) -> ResumeReceipt | None:
        with self._lock:
            return self._resume_receipt

    def front_door_status(self) -> dict[str, object]:
        with self._lock:
            projection = self._visible_projection()
            recorded = None if projection is None else projection.refusal_count
            this_boot = {
                code: dict(counts) for code, counts in self._refusal_outcomes_this_boot.items()
            }
            if self._resume_receipt is not None:
                resume_state = "resumed"
            elif self._resume_requested:
                resume_state = "not_applied"
            else:
                resume_state = "not_requested"
            return {
                "refusals": {
                    "recorded": recorded, "limit": MAX_REFUSAL_RECORDS,
                    "reserve": REFUSAL_RESOLVED_RESERVE, "this_boot": this_boot,
                },
                "resume": {"this_boot": resume_state},
            }

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
            result = {
                "state": self._state(), "hold": hold, "journal_uuid": p.journal_uuid,
                "generation": p.generation, "boot_id": p.boot_id, "head": head_json,
                "anchor": anchor_json, "wal_found": wal_found_json, "dispatch_holds": holds_json,
                "counts": counts_json, "bytes": bytes_json, "bounds": bounds_json,
                "refusals_this_boot": refusals_json,
                "verified_state_digest": self._verified_state_digest,
                "pending_digest": pending_digest(p), "state_digest": state_digest(p),
            }
            if p.run_holds:
                result["run_holds"] = {
                    "count": len(p.run_holds), "digest": run_holds_digest(p),
                }
            if p.intents or p.confirmations:
                result["reservation_claims"] = {
                    "intents": len(p.intents), "confirmations": len(p.confirmations),
                    "digest": reservation_claims_digest(p),
                }
            return result

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


# --- verify-only inspect -----------------------------------------------------


def _next_open_for(finding: Finding) -> list[str]:
    return ["persist_hold"] if finding.scope == "recovery" else ["hold"]


def _inspect_finding_json(store: JournalStore, finding: Finding) -> dict:
    in_anchor = (
        store.anchor is not None and store.anchor.hold is not None
        and store.anchor.hold.code == finding.code
    )
    return {"code": finding.code, "scope": finding.scope, "in_anchor": in_anchor}


def _inspect_anchor_json(store: JournalStore, lag: int | None) -> dict | None:
    if store.anchor is None:
        return None
    return {
        "counter": store.anchor.counter, "commit_seq": store.anchor.head.commit_seq,
        "event_seq": store.anchor.head.event_seq, "lag": lag,
    }


def _inspect_wal_found_json(store: JournalStore) -> dict | None:
    if store.wal_found is None:
        return None
    return {"size": store.wal_found.size, "digest": store.wal_found.digest}


def _inspect_pending_json(p) -> list[dict]:
    entries = pending_entries(p)[:_MAX_INSPECT_PENDING]
    return [
        {
            "fingerprint": entry.fingerprint, "status": entry.status,
            "values": None if entry.values is None else dict(entry.values),
            "admission_id": entry.admission_id, "arrival_seq": entry.arrival_seq,
            "source_group": entry.source_group,
        }
        for entry in entries
    ]


def _held_report(
    store: JournalStore, finding: Finding, *, created: list[str], lag: int | None,
) -> dict:
    return {
        "mode": "verify_only", "verdict": "held", "reason": None, "created": created,
        "finding": _inspect_finding_json(store, finding),
        "anchor": _inspect_anchor_json(store, lag), "wal_found": _inspect_wal_found_json(store),
        "next_open": _next_open_for(finding),
        "journal": None, "pending": None, "refusals": None, "resumes": None, "resume": None,
    }


def _ready_report(
    store: JournalStore, candidate, *, created: list[str], lag: int,
    refusals_seen: list[tuple[int, dict]], last_resume: tuple[int, str, str, int] | None,
) -> dict:
    journal_json = {
        "journal_uuid": candidate.journal_uuid, "generation": candidate.generation,
        "head": {
            "commit_seq": candidate.head.commit_seq, "event_seq": candidate.head.event_seq,
            "record_digest": candidate.head.record_digest,
        },
        "dispatch_holds": [
            {"code": code, "since_commit_seq": seq}
            for code, seq in sorted(candidate.dispatch_holds.items())
        ],
        "counts": {
            "records": candidate.head.event_seq, "admissions": candidate.admission_count,
            "pending_fingerprints": len(candidate.pending),
            "source_groups": len(candidate.baselines),
        },
        "bytes": {
            "logical": candidate.logical_bytes, "ordinary_limit": candidate.bounds.ordinary_bytes,
            "total_limit": candidate.bounds.total_bytes,
        },
        "bounds": {
            "max_admissions": candidate.bounds.max_admissions,
            "max_pending_fingerprints": candidate.bounds.max_pending_fingerprints,
            "ordinary_bytes": candidate.bounds.ordinary_bytes,
            "total_bytes": candidate.bounds.total_bytes,
        },
        "pending_digest": pending_digest(candidate), "state_digest": state_digest(candidate),
        "front_door_digest": front_door_digest(candidate),
    }
    if candidate.run_holds:
        journal_json["run_holds"] = {
            "count": len(candidate.run_holds), "digest": run_holds_digest(candidate),
        }
    if candidate.intents or candidate.confirmations:
        journal_json["reservation_claims"] = {
            "intents": len(candidate.intents),
            "confirmations": len(candidate.confirmations),
            "digest": reservation_claims_digest(candidate),
        }
    refusals_json = {
        "recorded": candidate.refusal_count, "limit": MAX_REFUSAL_RECORDS,
        "reserve": REFUSAL_RESOLVED_RESERVE,
        "unreserved_recorded": candidate.refusal_unreserved_count,
        "recent": [
            {"commit_seq": commit_seq, "summary": summary}
            for commit_seq, summary in refusals_seen[-_MAX_INSPECT_REFUSALS:]
        ],
    }
    resumes_json = {
        "count": candidate.resume_count,
        "last": None if last_resume is None else {
            "commit_seq": last_resume[0], "operator": last_resume[1], "reason": last_resume[2],
            "inspected_commit_seq": last_resume[3],
        },
    }
    resume_json = {
        "token": candidate.head.record_digest, "head_commit_seq": candidate.head.commit_seq,
    }
    return {
        "mode": "verify_only", "verdict": "ready", "reason": None, "created": created,
        "finding": None, "anchor": _inspect_anchor_json(store, lag),
        "wal_found": _inspect_wal_found_json(store),
        "next_open": ["reanchor", "restart_recovery"] if lag == 1 else ["restart_recovery"],
        "journal": journal_json, "pending": _inspect_pending_json(candidate),
        "refusals": refusals_json, "resumes": resumes_json, "resume": resume_json,
    }


def inspect_recovery_journal(directory: Path) -> Inspection:
    """Verify-only: replays and checks the image exactly as a real open does,
    but writes nothing except an absent ``lock``, and returns ``unverified``
    without opening SQLite for a WAL-absent, full-size DB (V11; plan Deferred
    6; critic 14). Never calls
    ``finish_open``, ``write_anchor``, ``persist_hold``, ``plan_restart`` or
    ``append``; the store, once opened, is always closed in a ``finally``.
    """
    if not isinstance(directory, Path):
        raise JournalError("journal_argument")
    code, unverified, lock_absent_before = None, False, False
    try:
        # The store's own custody rule first, so the pre-check refuses exactly
        # what open refuses, and no stat failure escapes raw.
        _check_directory(directory)
        if _lstat_or_none(directory / WAL_FILENAME) is None:
            db_stat = _lstat_or_none(directory / DB_FILENAME)
            unverified = db_stat is not None and db_stat.st_size >= PAGE_SIZE
        lock_absent_before = _lstat_or_none(directory / _LOCK_FILENAME) is None
    except StoreError as error:
        code = error.code
    except OSError:
        code = "journal_path_invalid"
    if code is not None:
        raise JournalError(code) from None
    if unverified:
        # A WAL-absent image with a full-size DB: opening could create an
        # empty WAL and change the next restart's `wal_found` (J1 p1, p2).
        report = {
            "mode": "verify_only", "verdict": "unverified", "reason": "wal_absent",
            "created": [], "finding": None, "anchor": None, "wal_found": None,
            "next_open": ["unknown"], "journal": None, "pending": None,
            "refusals": None, "resumes": None, "resume": None,
        }
        return Inspection(report=report, references=frozenset())
    # With no WAL and the DB absent or short, `_verify_open` returns before
    # connecting in every case (anchor finding, persisted hold,
    # `journal_truncated`), so opening it here creates no WAL.

    store = None
    try:
        store = JournalStore.open(directory)
    except StoreError as error:
        code = error.code
    if code is not None:
        raise JournalError(code) from None

    created = ["lock"] if lock_absent_before else []
    candidate = new_projection()
    admitted_digests: set[str] = set()
    refusals_seen: list[tuple[int, dict]] = []
    last_resume: list[tuple[int, str, str, int] | None] = [None]

    def collect(group: tuple) -> None:
        for record in group:
            if record.event_type == "admission":
                admitted_digests.add(record.data["source"]["body_digest"])
            elif record.event_type == "ingress_refusal":
                # A plain JSON value in refusal_to_json's shape, not the
                # record's frozen mapping with tuple members.
                summary = record.data["summary"]
                members = [list(member) for member in summary["members"]]
                refusals_seen.append((record.position.commit_seq, dict(summary, members=members)))
            elif record.event_type == "operator_action":
                last_resume[0] = (
                    record.position.commit_seq, record.data["operator"], record.data["reason"],
                    record.data["inspected"]["commit_seq"],
                )

    try:
        finding = store.finding
        lag = None
        if finding is None:
            finding, lag = _replay_finding(store, candidate, observe=collect)
        if finding is not None:
            report = _held_report(store, finding, created=created, lag=lag)
            references: frozenset[str] = frozenset()
        else:
            report = _ready_report(
                store, candidate, created=created, lag=lag, refusals_seen=refusals_seen,
                last_resume=last_resume[0],
            )
            references = frozenset(admitted_digests)
    finally:
        store.close()
    return Inspection(report=report, references=references)


__all__ = [
    "HOLD_SCOPES",
    "JOURNAL_ERROR_CODES",
    "REFUSAL_OUTCOMES",
    "AdmissionReceipt",
    "Inspection",
    "JournalError",
    "RecoveryJournal",
    "ResumeReceipt",
    "ResumeRequest",
    "create_recovery_journal",
    "inspect_recovery_journal",
    "new_id",
    "open_recovery_journal",
]
