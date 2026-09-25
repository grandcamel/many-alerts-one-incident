"""The recovery journal's pure reducer: projection, admission planning and
replay (ticket 37, unit 15, module 2).

Plan functions build sealed records from a projection and fresh inputs.
``verify_commit`` re-derives every journal-computed field from a projection
and a candidate commit and raises on any difference; ``apply_delta`` folds
the resulting ``Delta`` into the projection with plain assignments that
cannot fail. The live path (``recovery_journal.py``) and
``replay`` call exactly the same functions, so a stored history that is
tampered but re-signed is still caught: only a genuine semantic divergence,
never a missing check on one path, gives the two paths different answers.

Pure: no clock, randomness, filesystem, ``sqlite3`` or ``threading``. Every
decision input is a projection field or a record; nothing here consults a
clock or configuration outside the bounds recorded in genesis.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable, Iterator, Sequence
from types import MappingProxyType

from .forwarder_json import canonical_json, tagged_digest
from .journal_records import (
    CAPACITY_CODES,
    DEDUPE_RULE,
    MAX_REFUSAL_RECORDS,
    MAX_RUN_HOLD_RECORD_BYTES,
    REFUSAL_RESOLVED_RESERVE,
    REFUSAL_RULE,
    RESUMABLE_HOLDS,
    RESUME_RULE,
    V1_BOUND_CEILINGS,
    ZERO_DIGEST,
    Draft,
    Head,
    Position,
    Record,
    Stamp,
    WalFound,
    seal,
    thaw,
)
from .journal_source import (
    SourceRecord,
    dedupe_key,
    source_digest,
    source_from_json,
    source_to_json,
)

RECORD_OVERHEAD_BYTES = 384
REFUSAL_KEY_TAG = "rj.refusal-key.v1"
FRONT_DOOR_STATE_TAG = "rj.front-door-state.v1"
_REFUSAL_KEY_FIELDS = (
    "alerts", "code", "members", "members_omitted", "refused_group", "resolved", "source_group",
)

REPLAY_ERROR_CODES = frozenset({
    "replay_chain", "replay_framing", "replay_generation", "replay_boot",
    "replay_clock", "replay_tail_incomplete", "replay_shape", "replay_mismatch",
})

_ADMISSIONS_CODE, _PENDING_CODE, _BYTES_CODE = CAPACITY_CODES
_ADMISSION_PAIR_SHAPE = ("admission", "dedupe_decision")
MAX_RUN_HOLDS = 1_024
RUN_HOLD_MEMBERS_TAG = "rj.run-hold-members.v2"
RUN_HOLDS_STATE_TAG = "rj.run-holds.v2"


class ReplayError(ValueError):
    """A fixed, non-diagnostic replay/decision rejection; never embeds caller data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail_replay(code: str) -> None:
    raise ReplayError(code) from None


# --- Bounds -------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class JournalBounds:
    max_admissions: int = 10_000
    max_pending_fingerprints: int = 1_024
    ordinary_bytes: int = 112 * 2**20
    total_bytes: int = 128 * 2**20


DEFAULT_BOUNDS = JournalBounds()


# --- Projection value types -----------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Baseline:
    admission_id: str
    dedupe_key: str
    complete: bool


@dataclasses.dataclass(frozen=True)
class PendingEntry:
    fingerprint: str
    admission_id: str
    arrival_seq: int
    source_group: str
    status: str
    values: tuple[tuple[str, str | None], ...] | None


@dataclasses.dataclass(frozen=True)
class RunHold:
    admission_id: str
    reason: str
    since_commit_seq: int
    member_digest: str


@dataclasses.dataclass(frozen=True)
class CapacityRefusal:
    code: str
    limit: int
    observed: int
    requested: int


@dataclasses.dataclass(frozen=True)
class RefusalNotRecorded:
    """Why a planned ``ingress_refusal`` writes nothing; never an exception:
    the class is still sent to the caller even when this is returned."""

    reason: str  # "coalesced" | "limit" | "no_room"


@dataclasses.dataclass(frozen=True)
class Plan:
    records: tuple[Record, ...]
    charge: int
    outcome: dict[str, object]


@dataclasses.dataclass(frozen=True)
class Delta:
    """Opaque to callers: built only by ``verify_commit`` and consumed only by
    ``apply_delta``, which applies every field with a plain assignment.
    """

    head: Head
    generation: int
    journal_uuid: str | None
    bounds: JournalBounds | None
    boot_id: str
    last_mono_us: int
    new_boot_id: str | None
    logical_bytes: int
    admission_count: int
    last_arrival_seq: int
    baseline_update: tuple[str, Baseline] | None
    pending_updates: tuple[tuple[str, PendingEntry], ...]
    dispatch_hold_add: tuple[str, int] | None
    refusal_key_add: str | None = None
    refusal_unreserved: bool = False
    dispatch_hold_clear: str | None = None
    resume_commit_seq: int | None = None
    run_hold_add: tuple[str, RunHold] | None = None


class Projection:
    """Plain mutable fold state. Later record families add their own fields
    that only their own record types write (extension rule R4); admission
    transitions never touch them.
    """

    def __init__(self) -> None:
        self.journal_uuid: str | None = None
        self.generation: int = 0
        self.bounds: JournalBounds | None = None
        self.head: Head | None = None
        self.boot_id: str | None = None
        self.last_mono_us: int = 0
        self.seen_boot_ids: set[str] = set()
        self.logical_bytes: int = 0
        self.admission_count: int = 0
        self.last_arrival_seq: int = 0
        self.baselines: dict[str, Baseline] = {}
        self.pending: dict[str, PendingEntry] = {}
        self.run_holds: dict[str, RunHold] = {}
        self.dispatch_holds: dict[str, int] = {}
        # Front-door fields (unit 17): no admission transition reads or writes
        # these (R4).
        self.refusal_keys: set[str] = set()
        self.refusal_count: int = 0
        self.refusal_unreserved_count: int = 0
        self.resume_count: int = 0
        self.last_resume_commit_seq: int | None = None
        # Boot fields: set only in apply_delta, from the existing genesis and
        # restart deltas.
        self.boot_start_commit_seq: int | None = None
        self.boot_recovered: Head | None = None


def new_projection() -> Projection:
    return Projection()


# --- The decision function (shared by plan_admission and verify_commit) -------


@dataclasses.dataclass(frozen=True)
class _Decision:
    result: str
    baseline_before: Baseline | None
    baseline_after: Baseline
    superseded: tuple[tuple[str, str], ...]
    new_pending: int


def _decide(p: Projection, source: SourceRecord, admission_id: str) -> _Decision:
    key = dedupe_key(source)
    group = source.source_group
    complete = source.truncated_alerts == 0  # None (unknown) or >0 is incomplete
    before = p.baselines.get(group)
    if complete and before is not None and before.complete and before.dedupe_key == key:
        # Suppressed: the group's baseline is unchanged. Pending entries of its
        # members that another group has since claimed return to this, the
        # latest, arrival; nothing is created.
        reclaimed = tuple(sorted(
            (alert.fingerprint, p.pending[alert.fingerprint].admission_id)
            for alert in source.alerts
            if alert.fingerprint in p.pending and p.pending[alert.fingerprint].source_group != group
        ))
        return _Decision("suppressed", before, before, reclaimed, 0)
    superseded = tuple(sorted(
        (alert.fingerprint, p.pending[alert.fingerprint].admission_id)
        for alert in source.alerts if alert.fingerprint in p.pending
    ))
    result = "pending_reduced" if superseded else "admitted"
    baseline_after = Baseline(admission_id, key, complete)
    new_pending = len(source.alerts) - len(superseded)
    return _Decision(result, before, baseline_after, superseded, new_pending)


def _baseline_json(baseline: Baseline | None) -> dict | None:
    if baseline is None:
        return None
    return {
        "admission_id": baseline.admission_id, "complete": baseline.complete,
        "dedupe_key": baseline.dedupe_key,
    }


def _superseded_json(superseded: tuple[tuple[str, str], ...]) -> tuple[dict, ...]:
    return tuple(
        {"admission_id": admission_id, "fingerprint": fp} for fp, admission_id in superseded
    )


def _pending_count_after(p: Projection, decision: _Decision) -> int:
    if decision.result == "suppressed":
        return len(p.pending)
    return len(p.pending) + decision.new_pending


def _pending_updates(
    p: Projection, source: SourceRecord, decision: _Decision, admission_id: str, arrival_seq: int,
) -> tuple[tuple[str, PendingEntry], ...]:
    alerts_by_fingerprint = {alert.fingerprint: alert for alert in source.alerts}
    fingerprints = (
        (fp for fp, _admission_id in decision.superseded) if decision.result == "suppressed"
        else (alert.fingerprint for alert in source.alerts)
    )
    updates = []
    for fingerprint in fingerprints:
        alert = alerts_by_fingerprint[fingerprint]
        updates.append((fingerprint, PendingEntry(
            fingerprint=fingerprint, admission_id=admission_id, arrival_seq=arrival_seq,
            source_group=source.source_group, status=alert.status, values=alert.values,
        )))
    return tuple(updates)


def dispatch_holds(p: Projection) -> tuple[str, ...]:
    return tuple(sorted(p.dispatch_holds))


# --- Plan functions -------------------------------------------------------------


def plan_genesis(*, journal_uuid: str, bounds: JournalBounds, event_id: str, stamp: Stamp) -> Plan:
    bounds_json = {
        "max_admissions": bounds.max_admissions,
        "max_pending_fingerprints": bounds.max_pending_fingerprints,
        "ordinary_bytes": bounds.ordinary_bytes, "total_bytes": bounds.total_bytes,
    }
    position = Position(
        journal_generation=1, event_seq=1, commit_seq=1, commit_index=0, commit_size=1,
        prev_record_digest=ZERO_DIGEST,
    )
    record = seal(
        Draft(
            event_id=event_id, event_type="journal_genesis", actor="receiver", ids={},
            data={"format": "rj.journal.v1", "journal_uuid": journal_uuid, "bounds": bounds_json},
        ),
        position, stamp,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    outcome = MappingProxyType({"journal_uuid": journal_uuid, "bounds": bounds})
    return Plan(records=(record,), charge=charge, outcome=outcome)


def plan_restart(
    p: Projection, *, event_id: str, stamp: Stamp, anchor_lag: int, wal_found: WalFound | None,
) -> Plan | CapacityRefusal:
    recovered = {
        "commit_seq": p.head.commit_seq, "event_seq": p.head.event_seq,
        "record_digest": p.head.record_digest,
    }
    wal_found_json = (
        None if wal_found is None else {"size": wal_found.size, "digest": wal_found.digest}
    )
    position = Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    record = seal(
        Draft(
            event_id=event_id, event_type="restart_recovery", actor="receiver", ids={},
            data={
                "previous_boot_id": p.boot_id, "recovered": recovered, "anchor_lag": anchor_lag,
                "wal_found": wal_found_json, "dispatch_hold": "restart_recovery",
                "prior_leases": "invalid",
            },
        ),
        position, stamp,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    outcome = MappingProxyType({"anchor_lag": anchor_lag, "dispatch_hold": "restart_recovery"})
    return Plan(records=(record,), charge=charge, outcome=outcome)


def plan_admission(
    p: Projection, source: SourceRecord, *, admission_id: str, dedupe_event_id: str, stamp: Stamp,
) -> Plan | CapacityRefusal:
    decision = _decide(p, source, admission_id)
    if p.admission_count + 1 > p.bounds.max_admissions:
        return CapacityRefusal(_ADMISSIONS_CODE, p.bounds.max_admissions, p.admission_count, 1)
    if decision.result != "suppressed":
        pending_after = len(p.pending) + decision.new_pending
        if pending_after > p.bounds.max_pending_fingerprints:
            return CapacityRefusal(
                _PENDING_CODE, p.bounds.max_pending_fingerprints, len(p.pending),
                decision.new_pending,
            )

    active_holds = dispatch_holds(p)
    admission_decision = "held" if active_holds else "admitted"
    arrival_seq = p.last_arrival_seq + 1
    digest_of_source = source_digest(source)

    admission_position = Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=2,
        prev_record_digest=p.head.record_digest,
    )
    admission_record = seal(
        Draft(
            event_id=admission_id, event_type="admission", actor="receiver",
            ids={"admission_id": admission_id},
            data={
                "arrival_seq": arrival_seq, "decision": admission_decision,
                "dispatch_holds": active_holds, "source": source_to_json(source),
                "source_digest": digest_of_source,
            },
        ),
        admission_position, stamp,
    )

    dedupe_position = Position(
        journal_generation=p.generation, event_seq=admission_position.event_seq + 1,
        commit_seq=admission_position.commit_seq, commit_index=1, commit_size=2,
        prev_record_digest=admission_record.record_digest,
    )
    dedupe_record = seal(
        Draft(
            event_id=dedupe_event_id, event_type="dedupe_decision", actor="receiver",
            ids={"admission_id": admission_id},
            data={
                "rule": DEDUPE_RULE, "result": decision.result, "source_group": source.source_group,
                "dedupe_key": dedupe_key(source),
                "baseline_before": _baseline_json(decision.baseline_before),
                "baseline_after": _baseline_json(decision.baseline_after),
                "superseded": _superseded_json(decision.superseded),
                "pending_count_after": _pending_count_after(p, decision),
            },
        ),
        dedupe_position, stamp,
    )

    charge = len(admission_record.body) + len(dedupe_record.body) + 2 * RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.ordinary_bytes, p.logical_bytes, charge)

    outcome = MappingProxyType({
        "decision": admission_decision, "result": decision.result, "dispatch_holds": active_holds,
        "source_group": source.source_group, "dedupe_key": dedupe_key(source),
        "superseded": decision.superseded, "arrival_seq": arrival_seq,
    })
    return Plan(records=(admission_record, dedupe_record), charge=charge, outcome=outcome)


def plan_capacity_hold(
    p: Projection, refusal: CapacityRefusal, *, event_id: str, stamp: Stamp,
    refused_source_digest: str,
) -> Plan | CapacityRefusal | None:
    if refusal.code in p.dispatch_holds:
        return None
    position = Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    record = seal(
        Draft(
            event_id=event_id, event_type="capacity_hold", actor="receiver", ids={},
            data={
                "code": refusal.code, "limit": refusal.limit, "observed": refusal.observed,
                "requested": refusal.requested, "refused_source_digest": refused_source_digest,
                "action": "set",
            },
        ),
        position, stamp,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    outcome = MappingProxyType({"code": refusal.code})
    return Plan(records=(record,), charge=charge, outcome=outcome)


def refusal_key(summary: dict) -> str:
    """The dedupe key for an ingress refusal (D12, restated as membership-
    inclusive by U17-P3): the summary without ``body_bytes``/``body_digest``,
    so a re-render (only ``message``/``body_digest`` change) coalesces, and a
    membership change (a fingerprint turning Resolved) earns its own record.
    """
    payload = {field: summary[field] for field in _REFUSAL_KEY_FIELDS}
    return tagged_digest(REFUSAL_KEY_TAG, payload)


def plan_ingress_refusal(
    p: Projection, summary: dict, *, event_id: str, stamp: Stamp,
) -> Plan | RefusalNotRecorded:
    key = refusal_key(summary)
    if key in p.refusal_keys:
        return RefusalNotRecorded("coalesced")
    unreserved = not (type(summary["resolved"]) is int and summary["resolved"] > 0)
    if p.refusal_count + 1 > MAX_REFUSAL_RECORDS:
        return RefusalNotRecorded("limit")
    if unreserved and (
        p.refusal_unreserved_count + 1 > MAX_REFUSAL_RECORDS - REFUSAL_RESOLVED_RESERVE
    ):
        return RefusalNotRecorded("limit")

    position = Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    record = seal(
        Draft(
            event_id=event_id, event_type="ingress_refusal", actor="receiver", ids={},
            data={
                "rule": REFUSAL_RULE, "summary": summary, "refusal_key": key,
                "refusal_seq": p.refusal_count + 1,
            },
        ),
        position, stamp,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return RefusalNotRecorded("no_room")
    outcome = MappingProxyType({"refusal_key": key, "refusal_seq": p.refusal_count + 1})
    return Plan(records=(record,), charge=charge, outcome=outcome)


def plan_operator_resume(
    p: Projection, *, event_id: str, stamp: Stamp, operator: str, reason: str,
) -> Plan | CapacityRefusal:
    since_commit_seq = p.dispatch_holds["restart_recovery"]
    inspected = {
        "commit_seq": p.boot_recovered.commit_seq, "event_seq": p.boot_recovered.event_seq,
        "record_digest": p.boot_recovered.record_digest,
    }
    position = Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    record = seal(
        Draft(
            event_id=event_id, event_type="operator_action", actor="operator", ids={},
            data={
                "action": "resume", "rule": RESUME_RULE, "hold": "restart_recovery",
                "since_commit_seq": since_commit_seq, "inspected": inspected,
                "pending_digest": pending_digest(p), "operator": operator, "reason": reason,
            },
        ),
        position, stamp,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    outcome = MappingProxyType({"since_commit_seq": since_commit_seq})
    return Plan(records=(record,), charge=charge, outcome=outcome)


def plan_run_hold(
    p: Projection, *, job_id: str, admission_id: str, event_id: str,
    reason: str, stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Describe a durable hold only; this plan has no dispatch authority."""
    if p.head is None or p.bounds is None or p.boot_id != stamp.boot_id:
        _fail_replay("replay_mismatch")
    if job_id in p.run_holds or any(
        held.admission_id == admission_id for held in p.run_holds.values()
    ):
        _fail_replay("replay_mismatch")
    members = tuple(sorted(
        fingerprint for fingerprint, entry in p.pending.items()
        if entry.admission_id == admission_id
    ))
    if not 1 <= len(members) <= 32:
        _fail_replay("replay_mismatch")
    if len(p.run_holds) >= MAX_RUN_HOLDS:
        return CapacityRefusal("capacity_run_holds", MAX_RUN_HOLDS, len(p.run_holds), 1)
    position = Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    record = seal(
        Draft(
            event_id=event_id, event_type="run_hold", actor="receiver",
            ids={"job_id": job_id, "admission_id": admission_id},
            data={
                "rule": "run-hold-v2", "reason": reason,
                "based_on_commit_seq": p.head.commit_seq,
                "pending_digest": pending_digest(p), "member_count": len(members),
                "member_digest": tagged_digest(RUN_HOLD_MEMBERS_TAG, members),
            },
        ), position, stamp, schema_version=2,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    return Plan(records=(record,), charge=charge, outcome=MappingProxyType({
        "job_id": job_id, "admission_id": admission_id,
    }))


# --- verify_commit: re-derive every journal-computed field, or raise ----------


def _commit_shape(records: tuple[Record, ...]) -> str:
    types = tuple(record.event_type for record in records)
    if types == ("journal_genesis",):
        return "genesis"
    if types == ("restart_recovery",):
        return "restart"
    if types == ("capacity_hold",):
        return "capacity_hold"
    if types == ("ingress_refusal",):
        return "ingress_refusal"
    if types == ("operator_action",):
        return "operator_action"
    if types == ("run_hold",):
        return "run_hold"
    if types == _ADMISSION_PAIR_SHAPE:
        return "admission_pair"
    _fail_replay("replay_shape")


def _verify_genesis(record: Record) -> Delta:
    bounds_data = record.data["bounds"]
    for key in ("max_admissions", "max_pending_fingerprints", "ordinary_bytes", "total_bytes"):
        if not 1 <= bounds_data[key] <= V1_BOUND_CEILINGS[key]:
            _fail_replay("replay_mismatch")
    if bounds_data["ordinary_bytes"] > bounds_data["total_bytes"]:
        _fail_replay("replay_mismatch")
    bounds = JournalBounds(
        max_admissions=bounds_data["max_admissions"],
        max_pending_fingerprints=bounds_data["max_pending_fingerprints"],
        ordinary_bytes=bounds_data["ordinary_bytes"], total_bytes=bounds_data["total_bytes"],
    )
    head = Head(
        generation=record.position.journal_generation, commit_seq=record.position.commit_seq,
        event_seq=record.position.event_seq, record_digest=record.record_digest,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    return Delta(
        head=head, generation=record.position.journal_generation,
        journal_uuid=record.data["journal_uuid"], bounds=bounds, boot_id=record.stamp.boot_id,
        last_mono_us=record.stamp.mono_us, new_boot_id=record.stamp.boot_id, logical_bytes=charge,
        admission_count=0, last_arrival_seq=0, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None,
    )


def _verify_restart(p: Projection, record: Record, commit_seq: int) -> Delta:
    recovered = record.data["recovered"]
    if (
        recovered["commit_seq"] != p.head.commit_seq or recovered["event_seq"] != p.head.event_seq
        or recovered["record_digest"] != p.head.record_digest
    ):
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        _fail_replay("replay_mismatch")
    head = Head(
        generation=p.generation, commit_seq=commit_seq, event_seq=record.position.event_seq,
        record_digest=record.record_digest,
    )
    return Delta(
        head=head, generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=record.stamp.boot_id, last_mono_us=record.stamp.mono_us,
        new_boot_id=record.stamp.boot_id, logical_bytes=p.logical_bytes + charge,
        admission_count=p.admission_count, last_arrival_seq=p.last_arrival_seq,
        baseline_update=None, pending_updates=(),
        dispatch_hold_add=("restart_recovery", commit_seq),
    )


_CAPACITY_LIMITS = MappingProxyType({
    _ADMISSIONS_CODE: lambda p: p.bounds.max_admissions,
    _PENDING_CODE: lambda p: p.bounds.max_pending_fingerprints,
    _BYTES_CODE: lambda p: p.bounds.ordinary_bytes,
})
_CAPACITY_OBSERVED = MappingProxyType({
    _ADMISSIONS_CODE: lambda p: p.admission_count,
    _PENDING_CODE: lambda p: len(p.pending),
    _BYTES_CODE: lambda p: p.logical_bytes,
})


def _verify_capacity_hold(p: Projection, record: Record, commit_seq: int) -> Delta:
    data = record.data
    code = data["code"]
    if code in p.dispatch_holds:
        _fail_replay("replay_mismatch")
    limit_ok = data["limit"] == _CAPACITY_LIMITS[code](p)
    observed_ok = data["observed"] == _CAPACITY_OBSERVED[code](p)
    if not limit_ok or not observed_ok:
        _fail_replay("replay_mismatch")
    if data["observed"] + data["requested"] <= data["limit"]:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        _fail_replay("replay_mismatch")
    head = Head(
        generation=p.generation, commit_seq=commit_seq, event_seq=record.position.event_seq,
        record_digest=record.record_digest,
    )
    return Delta(
        head=head, generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=(code, commit_seq),
    )


def _verify_ingress_refusal(p: Projection, record: Record, commit_seq: int) -> Delta:
    summary = record.data["summary"]
    if record.data["refusal_seq"] != p.refusal_count + 1:
        _fail_replay("replay_mismatch")
    if p.refusal_count + 1 > MAX_REFUSAL_RECORDS:
        _fail_replay("replay_mismatch")
    unreserved = not (type(summary["resolved"]) is int and summary["resolved"] > 0)
    if unreserved and (
        p.refusal_unreserved_count + 1 > MAX_REFUSAL_RECORDS - REFUSAL_RESOLVED_RESERVE
    ):
        _fail_replay("replay_mismatch")
    key = refusal_key(summary)
    if record.data["refusal_key"] != key or key in p.refusal_keys:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        _fail_replay("replay_mismatch")
    head = Head(
        generation=p.generation, commit_seq=commit_seq, event_seq=record.position.event_seq,
        record_digest=record.record_digest,
    )
    return Delta(
        head=head, generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, refusal_key_add=key, refusal_unreserved=unreserved,
    )


def _verify_operator_action(p: Projection, record: Record, commit_seq: int) -> Delta:
    data = record.data
    hold = data["hold"]
    # Replay re-checks the validator's own rule: a resume never clears a capacity hold.
    if hold not in RESUMABLE_HOLDS or hold not in p.dispatch_holds:
        _fail_replay("replay_mismatch")
    if data["since_commit_seq"] != p.dispatch_holds[hold]:
        _fail_replay("replay_mismatch")
    # Immediacy: the resume is the first commit after the restart that
    # started this boot (I20; J1 graft 1).
    if p.head.commit_seq != p.boot_start_commit_seq:
        _fail_replay("replay_mismatch")
    inspected = data["inspected"]
    if p.boot_recovered is None or (
        inspected["commit_seq"] != p.boot_recovered.commit_seq
        or inspected["event_seq"] != p.boot_recovered.event_seq
        or inspected["record_digest"] != p.boot_recovered.record_digest
    ):
        _fail_replay("replay_mismatch")
    if data["pending_digest"] != pending_digest(p):
        _fail_replay("replay_mismatch")
    # Charged to the total region, like restart_recovery (an operator can
    # resume after the ordinary region is exhausted).
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        _fail_replay("replay_mismatch")
    head = Head(
        generation=p.generation, commit_seq=commit_seq, event_seq=record.position.event_seq,
        record_digest=record.record_digest,
    )
    return Delta(
        head=head, generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, dispatch_hold_clear=hold, resume_commit_seq=commit_seq,
    )


def _verify_run_hold(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 2 or len(record.body) > MAX_RUN_HOLD_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    plan = plan_run_hold(
        p, job_id=record.ids["job_id"], admission_id=record.ids["admission_id"],
        event_id=record.event_id, reason=record.data["reason"], stamp=record.stamp,
    )
    if isinstance(plan, CapacityRefusal) or (
        plan.records[0].body != record.body
        or plan.records[0].record_digest != record.record_digest
    ):
        _fail_replay("replay_mismatch")
    head = Head(
        generation=p.generation, commit_seq=commit_seq, event_seq=record.position.event_seq,
        record_digest=record.record_digest,
    )
    held = RunHold(
        admission_id=record.ids["admission_id"], reason=record.data["reason"],
        since_commit_seq=commit_seq, member_digest=record.data["member_digest"],
    )
    return Delta(
        head=head, generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + plan.charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, run_hold_add=(record.ids["job_id"], held),
    )


def _verify_admission_pair(
    p: Projection, admission: Record, dedupe: Record, commit_seq: int,
) -> Delta:
    admission_id = admission.ids["admission_id"]
    if admission_id != admission.event_id or dedupe.ids["admission_id"] != admission_id:
        _fail_replay("replay_shape")

    source = source_from_json(thaw(admission.data["source"]))
    if source_digest(source) != admission.data["source_digest"]:
        _fail_replay("replay_mismatch")

    decision = _decide(p, source, admission_id)
    if p.admission_count + 1 > p.bounds.max_admissions:
        _fail_replay("replay_mismatch")
    pending_after = len(p.pending) + decision.new_pending
    if decision.result != "suppressed" and pending_after > p.bounds.max_pending_fingerprints:
        _fail_replay("replay_mismatch")
    charge = len(admission.body) + len(dedupe.body) + 2 * RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        _fail_replay("replay_mismatch")

    active_holds = dispatch_holds(p)
    expected_decision = "held" if active_holds else "admitted"
    arrival_seq = p.last_arrival_seq + 1

    checks = (
        admission.data["arrival_seq"] == arrival_seq,
        admission.data["decision"] == expected_decision,
        tuple(admission.data["dispatch_holds"]) == active_holds,
        dedupe.data["rule"] == DEDUPE_RULE,
        dedupe.data["result"] == decision.result,
        dedupe.data["source_group"] == source.source_group,
        dedupe.data["dedupe_key"] == dedupe_key(source),
        dedupe.data["baseline_before"] == _baseline_json(decision.baseline_before),
        dedupe.data["baseline_after"] == _baseline_json(decision.baseline_after),
        tuple(dedupe.data["superseded"]) == _superseded_json(decision.superseded),
        dedupe.data["pending_count_after"] == _pending_count_after(p, decision),
    )
    if not all(checks):
        _fail_replay("replay_mismatch")

    head = Head(
        generation=p.generation, commit_seq=commit_seq, event_seq=dedupe.position.event_seq,
        record_digest=dedupe.record_digest,
    )
    pending_updates = _pending_updates(p, source, decision, admission_id, arrival_seq)
    baseline_update = (source.source_group, decision.baseline_after)
    return Delta(
        head=head, generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=admission.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + charge, admission_count=p.admission_count + 1,
        last_arrival_seq=arrival_seq, baseline_update=baseline_update,
        pending_updates=pending_updates, dispatch_hold_add=None,
    )


def verify_commit(p: Projection, records: Sequence[Record]) -> Delta:
    records = tuple(records)
    if not records:
        _fail_replay("replay_framing")
    if any(type(record) is not Record for record in records):
        _fail_replay("replay_shape")
    size = records[0].position.commit_size
    commit_seq = records[0].position.commit_seq
    if len(records) != size:
        _fail_replay("replay_framing")
    for index, record in enumerate(records):
        pos = record.position
        if pos.commit_seq != commit_seq or pos.commit_size != size or pos.commit_index != index:
            _fail_replay("replay_framing")

    expected_commit_seq = 1 if p.head is None else p.head.commit_seq + 1
    if commit_seq != expected_commit_seq:
        _fail_replay("replay_framing")

    expected_event_seq = 1 if p.head is None else p.head.event_seq + 1
    expected_prev_digest = ZERO_DIGEST if p.head is None else p.head.record_digest
    for record in records:
        seq_ok = record.position.event_seq == expected_event_seq
        digest_ok = record.position.prev_record_digest == expected_prev_digest
        if not seq_ok or not digest_ok:
            _fail_replay("replay_chain")
        expected_event_seq += 1
        expected_prev_digest = record.record_digest

    # Genesis opens generation 1; every later record stays in the projection's.
    expected_generation = p.generation or 1
    if any(record.position.journal_generation != expected_generation for record in records):
        _fail_replay("replay_generation")

    boot_ids = {record.stamp.boot_id for record in records}
    if len(boot_ids) != 1:
        _fail_replay("replay_boot")
    stamps = {(record.stamp.wall_time, record.stamp.mono_us) for record in records}
    if len(stamps) != 1:
        _fail_replay("replay_clock")
    boot_id = records[0].stamp.boot_id
    mono_us = records[0].stamp.mono_us

    shape = _commit_shape(records)
    if shape == "genesis":
        if p.journal_uuid is not None or p.head is not None:
            _fail_replay("replay_boot")
        return _verify_genesis(records[0])
    if shape == "restart":
        if boot_id in p.seen_boot_ids:
            _fail_replay("replay_boot")
        if records[0].data["previous_boot_id"] != p.boot_id:
            _fail_replay("replay_boot")
        return _verify_restart(p, records[0], commit_seq)

    if boot_id != p.boot_id:
        _fail_replay("replay_boot")
    if mono_us < p.last_mono_us:
        _fail_replay("replay_clock")
    if shape == "capacity_hold":
        return _verify_capacity_hold(p, records[0], commit_seq)
    if shape == "ingress_refusal":
        return _verify_ingress_refusal(p, records[0], commit_seq)
    if shape == "operator_action":
        return _verify_operator_action(p, records[0], commit_seq)
    if shape == "run_hold":
        return _verify_run_hold(p, records[0], commit_seq)
    return _verify_admission_pair(p, records[0], records[1], commit_seq)


def apply_delta(p: Projection, delta: Delta) -> None:
    if delta.new_boot_id is not None:
        # Read before p.head moves: the head this boot's restart recovered
        # (None at genesis), and the commit that started this boot.
        p.boot_recovered = p.head
        p.boot_start_commit_seq = delta.head.commit_seq
    p.head = delta.head
    p.generation = delta.generation
    if delta.journal_uuid is not None:
        p.journal_uuid = delta.journal_uuid
    if delta.bounds is not None:
        p.bounds = delta.bounds
    p.boot_id = delta.boot_id
    p.last_mono_us = delta.last_mono_us
    if delta.new_boot_id is not None:
        p.seen_boot_ids.add(delta.new_boot_id)
    p.logical_bytes = delta.logical_bytes
    p.admission_count = delta.admission_count
    p.last_arrival_seq = delta.last_arrival_seq
    if delta.baseline_update is not None:
        group, baseline = delta.baseline_update
        p.baselines[group] = baseline
    for fingerprint, entry in delta.pending_updates:
        p.pending[fingerprint] = entry
    if delta.dispatch_hold_add is not None:
        code, commit_seq = delta.dispatch_hold_add
        if code not in p.dispatch_holds:
            p.dispatch_holds[code] = commit_seq
    if delta.refusal_key_add is not None:
        p.refusal_keys.add(delta.refusal_key_add)
        p.refusal_count += 1
        if delta.refusal_unreserved:
            p.refusal_unreserved_count += 1
    if delta.dispatch_hold_clear is not None:
        del p.dispatch_holds[delta.dispatch_hold_clear]
    if delta.run_hold_add is not None:
        job_id, held = delta.run_hold_add
        p.run_holds[job_id] = held
    if delta.resume_commit_seq is not None:
        p.resume_count += 1
        p.last_resume_commit_seq = delta.resume_commit_seq


# --- Grouping and replay --------------------------------------------------------


def group_commits(records: Iterable[Record]) -> Iterator[tuple[Record, ...]]:
    current: list[Record] = []
    expected_size: int | None = None
    expected_commit_seq: int | None = None
    for record in records:
        if type(record) is not Record:
            _fail_replay("replay_shape")
        pos = record.position
        if current and pos.commit_seq != expected_commit_seq:
            _fail_replay("replay_framing")
        if not current:
            if pos.commit_index != 0:
                _fail_replay("replay_framing")
            expected_commit_seq = pos.commit_seq
            expected_size = pos.commit_size
        elif pos.commit_size != expected_size or pos.commit_index != len(current):
            _fail_replay("replay_framing")
        current.append(record)
        if len(current) == expected_size:
            yield tuple(current)
            current = []
            expected_size = None
            expected_commit_seq = None
    if current:
        _fail_replay("replay_tail_incomplete")


def replay(records: Iterable[Record]) -> Projection:
    p = new_projection()
    for group in group_commits(records):
        apply_delta(p, verify_commit(p, group))
    return p


# --- Read-only projections and digests ------------------------------------------


def pending_entries(p: Projection) -> tuple[PendingEntry, ...]:
    return tuple(sorted(p.pending.values(), key=lambda entry: entry.fingerprint))


def _values_json(values: tuple[tuple[str, str | None], ...] | None) -> dict[str, str | None] | None:
    if values is None:
        return None
    return dict(values)


def _list_digest(tag: str, items: Iterable[object]) -> str:
    canonical_items = sorted(canonical_json(item, ascii_only=True) for item in items)
    leaves = b"".join(hashlib.sha256(item).digest() for item in canonical_items)
    header = tag.encode("ascii") + b"\x00" + len(canonical_items).to_bytes(4, "big")
    return hashlib.sha256(header + leaves).hexdigest()


def pending_digest(p: Projection) -> str:
    items = [
        [entry.fingerprint, entry.admission_id, entry.arrival_seq, entry.source_group, entry.status,
         _values_json(entry.values)]
        for entry in p.pending.values()
    ]
    return _list_digest("rj.pending-set.v1", items)


def run_holds_digest(p: Projection) -> str:
    items = [
        [job_id, held.admission_id, held.reason, held.since_commit_seq, held.member_digest]
        for job_id, held in sorted(p.run_holds.items())
    ]
    return tagged_digest(RUN_HOLDS_STATE_TAG, items)


def state_digest(p: Projection) -> str:
    head = None
    if p.head is not None:
        head = {
            "commit_seq": p.head.commit_seq, "event_seq": p.head.event_seq,
            "generation": p.head.generation, "record_digest": p.head.record_digest,
        }
    baseline_items = [
        [group, baseline.admission_id, baseline.complete, baseline.dedupe_key]
        for group, baseline in p.baselines.items()
    ]
    hold_items = sorted([code, commit_seq] for code, commit_seq in p.dispatch_holds.items())
    payload = {
        "journal_uuid": p.journal_uuid, "generation": p.generation, "head": head,
        "admission_count": p.admission_count, "last_arrival_seq": p.last_arrival_seq,
        "logical_bytes": p.logical_bytes, "dispatch_holds": hold_items,
        "pending_digest": pending_digest(p),
        "baseline_digest": _list_digest("rj.baseline-set.v1", baseline_items),
    }
    return tagged_digest("rj.state.v1", payload)


def front_door_digest(p: Projection) -> str:
    """Front-door state only, under its own tag. The front-door fields are not
    in ``state_digest``'s formula, which stays ``rj.state.v1`` (J1-AO-5,
    J2-AO-1); a refusal or a resume still changes ``state_digest`` through
    the head and byte count, and a resume through the dispatch holds too."""
    payload = {
        "refusal_count": p.refusal_count, "refusal_unreserved_count": p.refusal_unreserved_count,
        "refusal_keys_digest": _list_digest("rj.refusal-key-set.v1", p.refusal_keys),
        "resume_count": p.resume_count, "last_resume_commit_seq": p.last_resume_commit_seq,
    }
    return tagged_digest(FRONT_DOOR_STATE_TAG, payload)


__all__ = [
    "DEFAULT_BOUNDS",
    "FRONT_DOOR_STATE_TAG",
    "MAX_RUN_HOLDS",
    "RECORD_OVERHEAD_BYTES",
    "REFUSAL_KEY_TAG",
    "REPLAY_ERROR_CODES",
    "Baseline",
    "CapacityRefusal",
    "Delta",
    "JournalBounds",
    "PendingEntry",
    "Plan",
    "Projection",
    "RefusalNotRecorded",
    "ReplayError",
    "RunHold",
    "apply_delta",
    "dispatch_holds",
    "front_door_digest",
    "group_commits",
    "new_projection",
    "pending_digest",
    "pending_entries",
    "plan_admission",
    "plan_capacity_hold",
    "plan_genesis",
    "plan_ingress_refusal",
    "plan_operator_resume",
    "plan_restart",
    "plan_run_hold",
    "refusal_key",
    "replay",
    "run_holds_digest",
    "state_digest",
    "verify_commit",
]
