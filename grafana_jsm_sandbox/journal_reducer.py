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
    EFFECT_CLAIM_REASONS,
    MAX_EFFECT_INTENT_RECORD_BYTES,
    MAX_EFFECT_RECEIPT_RECORD_BYTES,
    MAX_ID_BYTES,
    MAX_LAUNCH_CLAIM_RECORD_BYTES,
    MAX_REFUSAL_RECORDS,
    MAX_RELEASE_INTENT_RECORD_BYTES,
    MAX_RELEASE_OBSERVATION_RECORD_BYTES,
    MAX_RUN_HOLD_RECORD_BYTES,
    MAX_RUN_INTENT_RECORD_BYTES,
    MAX_SEQ,
    MAX_SPAWN_ATTESTATION_RECORD_BYTES,
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
MAX_RESERVATION_CLAIMS = 256
RESERVATION_INTENT_TAG = "rj.reservation-intent.v2"
RESERVATION_CLAIMS_TAG = "rj.reservation-claims.v2"
INITIAL_INTENT_MEMBERS_TAG = "rj.initial-intent-members.v3"
INITIAL_INTENT_TAG = "rj.reservation-intent.v3"
INITIAL_INTENTS_STATE_TAG = "rj.initial-intents.v3"
INITIAL_CONFIRMATIONS_STATE_TAG = "rj.initial-confirmations.v3"
RUN_INTENT_TAG = "rj.run-intent.v3"
RUN_INTENT_STATE_TAG = "rj.run-intent-state.v3"
LAUNCH_CLAIM_TAG = "rj.launch-claim.v3"
LAUNCH_CLAIM_STATE_TAG = "rj.launch-claim-state.v3"
SPAWN_ATTESTATION_TAG = "rj.spawn-attestation.v3"
SPAWN_ATTESTATION_STATE_TAG = "rj.spawn-attestation-state.v3"
RELEASE_INTENT_TAG = "rj.release-intent.v3"
RELEASE_INTENT_STATE_TAG = "rj.release-intent-state.v3"
RELEASE_OBSERVATION_TAG = "rj.release-observation.v3"
RELEASE_OBSERVATION_STATE_TAG = "rj.release-observation-state.v3"
MAX_EFFECT_CLAIMS = 64
EFFECT_INTENT_TAG = "rj.effect-intent.v3"
EFFECT_INTENTS_STATE_TAG = "rj.effect-intents-state.v3"
EFFECT_RECEIPT_TAG = "rj.effect-receipt.v3"
EFFECT_RECEIPTS_STATE_TAG = "rj.effect-receipts-state.v3"
EFFECT_ROUTE_SERVICE_V3 = MappingProxyType({
    "anthropic.messages": "anthropic",
    "draft.create": "confluence", "draft.read": "confluence",
    "draft.update": "confluence",
    "eyes.change_query": "grafana", "eyes.run_telemetry_query": "grafana",
    "grafana_health": "grafana",
    "jira.comment.add": "jira", "jira.comment.get": "jira",
    "jira.comments.list": "jira", "jira.issue.create": "jira",
    "jira.issue.get": "jira", "jira.issue.update": "jira",
    "jira.search": "jira", "jira.transition": "jira",
    "logs_range": "grafana", "metrics_instant": "grafana",
    "metrics_range": "grafana",
    "pod_events": "kubernetes", "pod_list": "kubernetes",
    "pod_status": "kubernetes", "service_endpoints": "kubernetes",
    "reference.read": "confluence",
    "trace_get": "grafana", "traces_search": "grafana",
})
_UUID_DASHES = frozenset({8, 13, 18, 23})
_UUID_HEX = frozenset("0123456789abcdef")


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
class ReservationIntentClaim:
    journal_uuid: str
    journal_generation: int
    admission_id: str
    job_id: str
    intent_id: str
    attempt_id: str
    reservation_id: str
    run_id: str
    lease_id: str
    intent_digest: str
    based_on_commit_seq: int
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class InitialReservationIntentClaim:
    journal_uuid: str
    journal_generation: int
    admission_id: str
    job_id: str
    intent_id: str
    attempt_id: str
    reservation_id: str
    run_id: str
    lease_id: str
    member_count: int
    member_digest: str
    intent_digest: str
    based_on_commit_seq: int
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class ReservationConfirmationClaim:
    intent_id: str
    confirmation_event_id: str
    intent_digest: str
    ledger_uuid: str
    ledger_generation: int
    ledger_event_id: str
    sequence: int
    event_digest: str
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class RunIntentClaim:
    run_intent_id: str
    journal_uuid: str
    journal_generation: int
    admission_id: str
    job_id: str
    intent_id: str
    attempt_id: str
    reservation_id: str
    run_id: str
    model_lease_id: str
    initial_intent_digest: str
    confirmation_event_id: str
    ledger_uuid: str
    ledger_generation: int
    ledger_event_id: str
    ledger_sequence: int
    ledger_event_digest: str
    ledger_head_sequence: int
    ledger_head_digest: str
    member_count: int
    member_digest: str
    services: tuple[tuple[str, str, str], ...]
    run_intent_digest: str
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class LaunchClaim:
    launch_claim_id: str
    run_intent_id: str
    run_intent_digest: str
    journal_uuid: str
    admission_id: str
    job_id: str
    intent_id: str
    attempt_id: str
    reservation_id: str
    run_id: str
    model_lease_id: str
    receiver_boot_id: str
    forwarder_generation: str
    barrier_token_digest: str
    origin_us: int
    work_deadline_us: int
    flush_deadline_us: int
    hard_deadline_us: int
    grants: tuple[tuple[str, str, str, str, int], ...]
    launch_claim_digest: str
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class SpawnAttestationClaim:
    event_id: str
    claim_digest: str
    launch_claim_id: str
    run_id: str
    attempt_id: str
    receiver_boot_id: str
    observed_us: int
    witness_locator: str
    witness_identity_digest: str
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class ReleaseIntentClaim:
    event_id: str
    claim_digest: str
    spawn_attestation_id: str
    receiver_boot_id: str
    intended_release_us: int
    activated_grants: tuple[tuple[str, str, str, int], ...]
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class ReleaseObservationClaim:
    event_id: str
    claim_digest: str
    release_intent_id: str
    receiver_boot_id: str
    observed_us: int
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class EffectIntentClaim:
    event_id: str
    claim_digest: str
    operation_id: str
    run_id: str
    attempt_id: str
    receiver_boot_id: str
    forwarder_generation: str
    service: str
    route_id: str
    grant_id: str
    scope_digest: str
    flight_id: str
    forwarder_receipt_id: str
    request_digest: str
    target_digest: str
    observed_us: int
    expires_us: int
    committed_at_seq: int


@dataclasses.dataclass(frozen=True)
class EffectReceiptClaim:
    event_id: str
    claim_digest: str
    operation_id: str
    intent_event_id: str
    receiver_boot_id: str
    claimed_dispatch_state: str
    claimed_reason: str
    finalized_receipt_digest: str
    observed_us: int
    committed_at_seq: int


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
    reservation_intent_add: ReservationIntentClaim | None = None
    reservation_confirmation_add: ReservationConfirmationClaim | None = None
    initial_reservation_intent_add: InitialReservationIntentClaim | None = None
    initial_reservation_confirmation_add: ReservationConfirmationClaim | None = None
    run_intent_add: RunIntentClaim | None = None
    launch_claim_add: LaunchClaim | None = None
    spawn_attestation_add: SpawnAttestationClaim | None = None
    release_intent_add: ReleaseIntentClaim | None = None
    release_observation_add: ReleaseObservationClaim | None = None
    effect_intent_add: EffectIntentClaim | None = None
    effect_receipt_add: EffectReceiptClaim | None = None


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
        self.intents: dict[str, ReservationIntentClaim] = {}
        self.confirmations: dict[str, ReservationConfirmationClaim] = {}
        self.initial_intents: dict[str, InitialReservationIntentClaim] = {}
        self.initial_confirmations: dict[str, ReservationConfirmationClaim] = {}
        self.run_intent: RunIntentClaim | None = None
        self.launch_claim: LaunchClaim | None = None
        self.spawn_attestation: SpawnAttestationClaim | None = None
        self.release_intent: ReleaseIntentClaim | None = None
        self.release_observation: ReleaseObservationClaim | None = None
        self.effect_intents: dict[str, EffectIntentClaim] = {}
        self.effect_receipts: dict[str, EffectReceiptClaim] = {}
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
    if any(
        (claim.job_id == job_id) != (claim.admission_id == admission_id)
        for claim in p.initial_intents.values()
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


def _canonical_uuid(value: object) -> bool:
    return type(value) is str and len(value) == 36 and all(
        character == "-" if index in _UUID_DASHES else character in _UUID_HEX
        for index, character in enumerate(value)
    )


def _single_position(p: Projection) -> Position:
    return Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )


def _intent_digest_fields(
    p: Projection, *, job_id: str, admission_id: str, intent_id: str,
    attempt_id: str, reservation_id: str, run_id: str, lease_id: str,
) -> dict[str, object]:
    return {
        "journal_uuid": p.journal_uuid, "journal_generation": p.generation,
        "admission_id": admission_id, "job_id": job_id, "intent_id": intent_id,
        "attempt_id": attempt_id, "reservation_id": reservation_id,
        "run_id": run_id, "lease_id": lease_id,
        "based_on_commit_seq": p.head.commit_seq,
    }


def plan_reservation_intent(
    p: Projection, *, job_id: str, admission_id: str, intent_id: str,
    attempt_id: str, reservation_id: str, run_id: str, lease_id: str,
    stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Build a journal claim; no ledger receipt or dispatch authority."""
    if p.head is None or p.bounds is None or p.boot_id != stamp.boot_id:
        _fail_replay("replay_mismatch")
    if p.initial_intents:
        _fail_replay("replay_mismatch")
    if len(p.intents) + len(p.initial_intents) >= MAX_RESERVATION_CLAIMS:
        return CapacityRefusal(
            "capacity_reservation_intents", MAX_RESERVATION_CLAIMS,
            len(p.intents) + len(p.initial_intents), 1,
        )
    held = p.run_holds.get(job_id)
    members = tuple(sorted(
        fingerprint for fingerprint, entry in p.pending.items()
        if entry.admission_id == admission_id
    ))
    identifiers = (
        p.journal_uuid, admission_id, job_id, intent_id,
        attempt_id, reservation_id, run_id, lease_id,
    )
    if (
        held is None or held.admission_id != admission_id or not members
        or tagged_digest(RUN_HOLD_MEMBERS_TAG, members) != held.member_digest
        or not all(type(value) is str for value in identifiers)
        or len(set(identifiers)) != len(identifiers)
        or not all(_canonical_uuid(value) for value in (
            p.journal_uuid, admission_id, intent_id, attempt_id,
            reservation_id, run_id, lease_id,
        ))
        or intent_id in p.intents
    ):
        _fail_replay("replay_mismatch")
    fresh = {intent_id, attempt_id, reservation_id, run_id, lease_id}
    for prior in p.intents.values():
        prior_ids = {
            prior.intent_id, prior.attempt_id, prior.reservation_id,
            prior.run_id, prior.lease_id,
        }
        if fresh & prior_ids:
            _fail_replay("replay_mismatch")
    digest = tagged_digest(RESERVATION_INTENT_TAG, _intent_digest_fields(
        p, job_id=job_id, admission_id=admission_id, intent_id=intent_id,
        attempt_id=attempt_id, reservation_id=reservation_id,
        run_id=run_id, lease_id=lease_id,
    ))
    record = seal(
        Draft(
            event_id=intent_id, event_type="reservation_intent", actor="receiver",
            ids={
                "job_id": job_id, "admission_id": admission_id, "intent_id": intent_id,
                "attempt_id": attempt_id, "reservation_id": reservation_id,
                "run_id": run_id, "lease_id": lease_id,
            },
            data={
                "rule": "reservation-intent-v2",
                "based_on_commit_seq": p.head.commit_seq,
                "intent_digest": digest,
            },
        ), _single_position(p), stamp, schema_version=2,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    return Plan(records=(record,), charge=charge, outcome=MappingProxyType({
        "intent_id": intent_id, "intent_digest": digest,
    }))


def plan_initial_reservation_intent(
    p: Projection, *, job_id: str, admission_id: str, intent_id: str,
    attempt_id: str, reservation_id: str, run_id: str, lease_id: str,
    stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Build a first-attempt journal claim, without a writer or dispatch authority."""
    if p.head is None or p.bounds is None or p.boot_id != stamp.boot_id:
        _fail_replay("replay_mismatch")
    if p.dispatch_holds or p.run_holds or p.initial_intents:
        _fail_replay("replay_mismatch")
    if len(p.intents) + len(p.initial_intents) >= MAX_RESERVATION_CLAIMS:
        return CapacityRefusal(
            "capacity_reservation_intents", MAX_RESERVATION_CLAIMS,
            len(p.intents) + len(p.initial_intents), 1,
        )
    members = tuple(sorted(
        fingerprint for fingerprint, entry in p.pending.items()
        if entry.admission_id == admission_id
    ))
    identifiers = (
        p.journal_uuid, admission_id, job_id, intent_id,
        attempt_id, reservation_id, run_id, lease_id,
    )
    if (
        not 1 <= len(members) <= 32
        or not all(_canonical_uuid(value) for value in identifiers)
        or len(set(identifiers)) != len(identifiers)
        or any(claim.admission_id == admission_id for claim in p.intents.values())
        or any(claim.job_id == job_id for claim in p.intents.values())
        or any(held.admission_id == admission_id or held_job == job_id
               for held_job, held in p.run_holds.items())
    ):
        _fail_replay("replay_mismatch")
    fresh = {job_id, intent_id, attempt_id, reservation_id, run_id, lease_id}
    for prior in (*p.intents.values(), *p.initial_intents.values()):
        prior_ids = {
            prior.job_id, prior.intent_id, prior.attempt_id,
            prior.reservation_id, prior.run_id, prior.lease_id,
        }
        if fresh & prior_ids:
            _fail_replay("replay_mismatch")
    member_digest = tagged_digest(INITIAL_INTENT_MEMBERS_TAG, members)
    digest_fields = _intent_digest_fields(
        p, job_id=job_id, admission_id=admission_id, intent_id=intent_id,
        attempt_id=attempt_id, reservation_id=reservation_id,
        run_id=run_id, lease_id=lease_id,
    )
    digest_fields["member_count"] = len(members)
    digest_fields["member_digest"] = member_digest
    digest = tagged_digest(INITIAL_INTENT_TAG, digest_fields)
    record = seal(
        Draft(
            event_id=intent_id, event_type="reservation_intent", actor="receiver",
            ids={
                "job_id": job_id, "admission_id": admission_id, "intent_id": intent_id,
                "attempt_id": attempt_id, "reservation_id": reservation_id,
                "run_id": run_id, "lease_id": lease_id,
            },
            data={
                "rule": "reservation-intent-v3",
                "based_on_commit_seq": p.head.commit_seq,
                "member_count": len(members), "member_digest": member_digest,
                "intent_digest": digest,
            },
        ), _single_position(p), stamp, schema_version=3,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.ordinary_bytes, p.logical_bytes, charge)
    return Plan(records=(record,), charge=charge, outcome=MappingProxyType({
        "intent_id": intent_id, "intent_digest": digest,
    }))


def _confirmation_ledger_identity_conflict(
    p: Projection, *, ledger_uuid: str, ledger_generation: int,
    ledger_event_id: str, sequence: int,
) -> bool:
    """One derived cross-version index; neither claim map authenticates a ledger."""
    claims = (*p.confirmations.values(), *p.initial_confirmations.values())
    return any(
        prior.ledger_event_id == ledger_event_id or (
            prior.ledger_uuid, prior.ledger_generation, prior.sequence,
        ) == (ledger_uuid, ledger_generation, sequence)
        for prior in claims
    )


def plan_reservation_confirmation(
    p: Projection, *, intent_id: str, event_id: str, ledger_uuid: str,
    ledger_generation: int, ledger_event_id: str, sequence: int,
    event_digest: str, stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Build an unverified ledger observation claim; never a permit."""
    if p.head is None or p.bounds is None or p.boot_id != stamp.boot_id:
        _fail_replay("replay_mismatch")
    if len(p.confirmations) + len(p.initial_confirmations) >= MAX_RESERVATION_CLAIMS:
        return CapacityRefusal(
            "capacity_reservation_confirmations", MAX_RESERVATION_CLAIMS,
            len(p.confirmations) + len(p.initial_confirmations), 1,
        )
    claimed = p.intents.get(intent_id)
    if claimed is None or intent_id in p.confirmations:
        _fail_replay("replay_mismatch")
    identifiers = (
        claimed.journal_uuid, claimed.admission_id, claimed.job_id,
        claimed.intent_id, claimed.attempt_id, claimed.reservation_id,
        claimed.run_id, claimed.lease_id, event_id, ledger_uuid, ledger_event_id,
    )
    if not all(type(value) is str for value in identifiers) or (
        len(set(identifiers)) != len(identifiers)
    ) or not all(
        _canonical_uuid(value) for value in (event_id, ledger_uuid, ledger_event_id)
    ):
        _fail_replay("replay_mismatch")
    if _confirmation_ledger_identity_conflict(
        p, ledger_uuid=ledger_uuid, ledger_generation=ledger_generation,
        ledger_event_id=ledger_event_id, sequence=sequence,
    ) or any(
        prior.confirmation_event_id == event_id
        for prior in p.initial_confirmations.values()
    ):
        _fail_replay("replay_mismatch")
    record = seal(
        Draft(
            event_id=event_id, event_type="reservation_confirmation", actor="receiver",
            ids={"intent_id": intent_id},
            data={
                "rule": "reservation-confirmation-v2",
                "intent_digest": claimed.intent_digest,
                "ledger_uuid": ledger_uuid, "ledger_generation": ledger_generation,
                "ledger_event_id": ledger_event_id, "sequence": sequence,
                "event_digest": event_digest,
            },
        ), _single_position(p), stamp, schema_version=2,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    return Plan(records=(record,), charge=charge, outcome=MappingProxyType({
        "intent_id": intent_id, "claim_event_id": event_id,
    }))


def plan_initial_reservation_confirmation(
    p: Projection, *, intent_id: str, event_id: str, ledger_uuid: str,
    ledger_generation: int, ledger_event_id: str, sequence: int,
    event_digest: str, stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Build an unverified counterpart claim for one v3 initial intent."""
    if p.head is None or p.bounds is None or p.boot_id != stamp.boot_id:
        _fail_replay("replay_mismatch")
    if len(p.confirmations) + len(p.initial_confirmations) >= MAX_RESERVATION_CLAIMS:
        return CapacityRefusal(
            "capacity_reservation_confirmations", MAX_RESERVATION_CLAIMS,
            len(p.confirmations) + len(p.initial_confirmations), 1,
        )
    claimed = p.initial_intents.get(intent_id)
    if claimed is None or intent_id in p.initial_confirmations or intent_id in p.confirmations:
        _fail_replay("replay_mismatch")
    identifiers = (
        claimed.journal_uuid, claimed.admission_id, claimed.job_id,
        claimed.intent_id, claimed.attempt_id, claimed.reservation_id,
        claimed.run_id, claimed.lease_id, event_id, ledger_uuid, ledger_event_id,
    )
    if not all(_canonical_uuid(value) for value in identifiers) or (
        len(set(identifiers)) != len(identifiers)
    ) or any(
        prior.confirmation_event_id == event_id
        for prior in (*p.confirmations.values(), *p.initial_confirmations.values())
    ):
        _fail_replay("replay_mismatch")
    if _confirmation_ledger_identity_conflict(
        p, ledger_uuid=ledger_uuid, ledger_generation=ledger_generation,
        ledger_event_id=ledger_event_id, sequence=sequence,
    ):
        _fail_replay("replay_mismatch")
    record = seal(
        Draft(
            event_id=event_id, event_type="reservation_confirmation", actor="receiver",
            ids={"intent_id": intent_id},
            data={
                "rule": "reservation-confirmation-v3",
                "intent_digest": claimed.intent_digest,
                "ledger_uuid": ledger_uuid, "ledger_generation": ledger_generation,
                "ledger_event_id": ledger_event_id, "sequence": sequence,
                "event_digest": event_digest,
            },
        ), _single_position(p), stamp, schema_version=3,
    )
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    return Plan(records=(record,), charge=charge, outcome=MappingProxyType({
        "intent_id": intent_id, "claim_event_id": event_id,
    }))


def _digest64(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in _UUID_HEX for c in value)


def _known_reservation_ids(p: Projection) -> set[str]:
    """All replayed identities a new Run event or service claim cannot reuse."""
    values = {p.journal_uuid, *p.run_holds.keys()}
    values.update(held.admission_id for held in p.run_holds.values())
    for claim in (*p.intents.values(), *p.initial_intents.values()):
        values.update((
            claim.admission_id, claim.job_id, claim.intent_id, claim.attempt_id,
            claim.reservation_id, claim.run_id, claim.lease_id,
        ))
    for claim in (*p.confirmations.values(), *p.initial_confirmations.values()):
        values.update((
            claim.confirmation_event_id, claim.ledger_uuid, claim.ledger_event_id,
        ))
    return values


def plan_run_intent(
    p: Projection, *, intent_id: str, event_id: str,
    ledger_head_sequence: int, ledger_head_digest: str,
    services: tuple[tuple[str, str, str], ...], stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Plan an outstanding unqualified claim; no ledger verification or writer."""
    if p.head is None or p.bounds is None or p.boot_id != stamp.boot_id:
        _fail_replay("replay_mismatch")
    if p.dispatch_holds or p.run_holds or p.run_intent is not None:
        _fail_replay("replay_mismatch")
    initial = p.initial_intents.get(intent_id)
    confirmation = p.initial_confirmations.get(intent_id)
    if initial is None or confirmation is None or (
        confirmation.intent_digest != initial.intent_digest
        or not initial.committed_at_seq < confirmation.committed_at_seq <= p.head.commit_seq
    ):
        _fail_replay("replay_mismatch")
    members = tuple(sorted(
        fingerprint for fingerprint, entry in p.pending.items()
        if entry.admission_id == initial.admission_id
    ))
    if len(members) != initial.member_count or (
        tagged_digest(INITIAL_INTENT_MEMBERS_TAG, members) != initial.member_digest
    ):
        _fail_replay("replay_mismatch")
    if not _canonical_uuid(event_id) or event_id in _known_reservation_ids(p):
        _fail_replay("replay_mismatch")
    if (type(ledger_head_sequence) is not int
        or not confirmation.sequence <= ledger_head_sequence <= MAX_SEQ
        or not _digest64(ledger_head_digest)
        or (ledger_head_sequence == confirmation.sequence
            and ledger_head_digest != confirmation.event_digest)):
        _fail_replay("replay_mismatch")
    if type(services) is not tuple or not 4 <= len(services) <= 5 or any(
        type(item) is not tuple or len(item) != 3 for item in services
    ):
        _fail_replay("replay_mismatch")
    names = tuple(item[0] for item in services)
    if any(type(name) is not str for name in names) or (
        names != tuple(sorted(names)) or len(set(names)) != len(names)
    ) or not (
        {"anthropic", "jira", "grafana", "kubernetes"} <= set(names)
    ) or set(names) - {"anthropic", "jira", "grafana", "kubernetes", "confluence"}:
        _fail_replay("replay_mismatch")
    if services[0][1] != initial.lease_id or any(
        type(name) is not str or not _canonical_uuid(lease_claim_id)
        or not _digest64(scope_digest)
        for name, lease_claim_id, scope_digest in services
    ):
        _fail_replay("replay_mismatch")
    fresh = (event_id, *(item[1] for item in services[1:]))
    if len(set(fresh)) != len(fresh) or set(fresh) & _known_reservation_ids(p):
        _fail_replay("replay_mismatch")
    ids = {
        "journal_uuid": initial.journal_uuid, "job_id": initial.job_id,
        "admission_id": initial.admission_id, "intent_id": initial.intent_id,
        "attempt_id": initial.attempt_id, "reservation_id": initial.reservation_id,
        "run_id": initial.run_id, "lease_id": initial.lease_id,
    }
    data = {
        "rule": "run-intent-v3", "based_on_commit_seq": p.head.commit_seq,
        "based_on_record_digest": p.head.record_digest,
        "initial_intent_commit_seq": initial.committed_at_seq,
        "intent_digest": initial.intent_digest,
        "confirmation_event_id": confirmation.confirmation_event_id,
        "confirmation_commit_seq": confirmation.committed_at_seq,
        "ledger_uuid": confirmation.ledger_uuid,
        "ledger_generation": confirmation.ledger_generation,
        "ledger_event_id": confirmation.ledger_event_id,
        "sequence": confirmation.sequence,
        "event_digest": confirmation.event_digest,
        "ledger_head": {
            "sequence": ledger_head_sequence, "event_digest": ledger_head_digest,
        },
        "member_count": initial.member_count, "member_digest": initial.member_digest,
        "services": [
            {"service": name, "lease_claim_id": lease_claim_id,
             "scope_digest": scope_digest}
            for name, lease_claim_id, scope_digest in services
        ],
        "work_deadline_seconds": 270, "flush_deadline_seconds": 290,
        "hard_deadline_seconds": 300,
    }
    data["run_intent_digest"] = tagged_digest(RUN_INTENT_TAG, {
        "event_id": event_id, "ids": ids, "data": data,
    })
    record = seal(
        Draft(event_id, "run_intent", "receiver", ids, data),
        _single_position(p), stamp, schema_version=3,
    )
    if len(record.body) > MAX_RUN_INTENT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.ordinary_bytes, p.logical_bytes, charge)
    return Plan(records=(record,), charge=charge, outcome=MappingProxyType({
        "run_intent_id": event_id, "run_intent_digest": data["run_intent_digest"],
        "state": "outstanding_unqualified",
    }))


_SAFE_GRANT_ID = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)


def _safe_grant_id(value: object) -> bool:
    return (type(value) is str and 1 <= len(value) <= MAX_ID_BYTES
            and all(character in _SAFE_GRANT_ID for character in value))


def plan_launch_claim(
    p: Projection, *, event_id: str, forwarder_generation: str,
    barrier_token_digest: str,
    grants: tuple[tuple[str, str, str, str, int], ...], stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Plan a replayed grant mapping claim without grant or launch authority."""
    intent = p.run_intent
    if (p.head is None or p.bounds is None or p.boot_id != stamp.boot_id
        or intent is None or p.launch_claim is not None
        or p.dispatch_holds or p.run_holds
        or p.boot_start_commit_seq is None
        or intent.committed_at_seq < p.boot_start_commit_seq
        or type(stamp.mono_us) is not int
        or not p.last_mono_us <= stamp.mono_us <= MAX_SEQ - 300_000_000):
        _fail_replay("replay_mismatch")
    initial = p.initial_intents.get(intent.intent_id)
    if initial is None or (
        initial.admission_id != intent.admission_id
        or initial.member_count != intent.member_count
        or initial.member_digest != intent.member_digest
    ):
        _fail_replay("replay_mismatch")
    members = tuple(sorted(
        fingerprint for fingerprint, entry in p.pending.items()
        if entry.admission_id == intent.admission_id
    ))
    if (len(members) != intent.member_count
        or tagged_digest(INITIAL_INTENT_MEMBERS_TAG, members) != intent.member_digest):
        _fail_replay("replay_mismatch")
    if (not _canonical_uuid(event_id)
        or event_id in _known_reservation_ids(p)
        or event_id == intent.run_intent_id
        or event_id in {service[1] for service in intent.services}
        or not _safe_grant_id(forwarder_generation)
        or not _digest64(barrier_token_digest)):
        _fail_replay("replay_mismatch")
    if type(grants) is not tuple or len(grants) != len(intent.services) or any(
        type(row) is not tuple or len(row) != 5 for row in grants
    ):
        _fail_replay("replay_mismatch")
    grant_ids: list[str] = []
    for row, service in zip(grants, intent.services, strict=True):
        name, lease_claim_id, scope_digest, grant_id, expiry_us = row
        if ((name, lease_claim_id, scope_digest) != service
            or not _safe_grant_id(grant_id)
            or type(expiry_us) is not int
            or not stamp.mono_us < expiry_us <= stamp.mono_us + 270_000_000):
            _fail_replay("replay_mismatch")
        grant_ids.append(grant_id)
    if len(set(grant_ids)) != len(grant_ids):
        _fail_replay("replay_mismatch")
    ids = {
        "journal_uuid": intent.journal_uuid, "admission_id": intent.admission_id,
        "job_id": intent.job_id, "intent_id": intent.intent_id,
        "attempt_id": intent.attempt_id,
        "reservation_id": intent.reservation_id, "run_id": intent.run_id,
        "lease_id": intent.model_lease_id,
    }
    data = {
        "rule": "launch-claim-v3", "based_on_commit_seq": p.head.commit_seq,
        "based_on_record_digest": p.head.record_digest,
        "run_intent_event_id": intent.run_intent_id,
        "run_intent_digest": intent.run_intent_digest,
        "run_intent_commit_seq": intent.committed_at_seq,
        "receiver_boot_id": p.boot_id,
        "forwarder_generation": forwarder_generation,
        "barrier_token_digest": barrier_token_digest,
        "origin_us": stamp.mono_us,
        "work_deadline_us": stamp.mono_us + 270_000_000,
        "flush_deadline_us": stamp.mono_us + 290_000_000,
        "hard_deadline_us": stamp.mono_us + 300_000_000,
        "grants": [
            {"service": name, "lease_claim_id": claim_id,
             "scope_digest": scope, "grant_id": grant_id,
             "grant_expiry_us": expiry_us}
            for name, claim_id, scope, grant_id, expiry_us in grants
        ],
    }
    data["launch_claim_digest"] = tagged_digest(LAUNCH_CLAIM_TAG, {
        "event_id": event_id, "ids": ids, "data": data,
    })
    record = seal(
        Draft(event_id, "launch_claim", "receiver", ids, data),
        _single_position(p), stamp, schema_version=3,
    )
    if len(record.body) > MAX_LAUNCH_CLAIM_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.ordinary_bytes, p.logical_bytes, charge)
    return Plan(records=(record,), charge=charge, outcome=MappingProxyType({
        "launch_claim_id": event_id, "launch_claim_digest": data["launch_claim_digest"],
        "state": "outstanding_unqualified_launch_claim",
    }))


def _launch_claim_ids(claim: LaunchClaim) -> dict[str, str]:
    return {
        "journal_uuid": claim.journal_uuid, "admission_id": claim.admission_id,
        "job_id": claim.job_id, "intent_id": claim.intent_id,
        "attempt_id": claim.attempt_id, "reservation_id": claim.reservation_id,
        "run_id": claim.run_id, "lease_id": claim.model_lease_id,
    }


def _claim_event_id_ok(p: Projection, event_id: str) -> bool:
    used = _known_reservation_ids(p)
    if p.run_intent is not None:
        used.add(p.run_intent.run_intent_id)
        used.update(service[1] for service in p.run_intent.services)
    if p.launch_claim is not None:
        used.add(p.launch_claim.launch_claim_id)
        used.update(grant[3] for grant in p.launch_claim.grants)
    for claim in (p.spawn_attestation, p.release_intent, p.release_observation):
        if claim is not None:
            used.add(claim.event_id)
    used.update(p.effect_intents)
    used.update(claim.event_id for claim in p.effect_intents.values())
    used.update(claim.event_id for claim in p.effect_receipts.values())
    return _canonical_uuid(event_id) and event_id not in used


def _claim_pre_release(p: Projection, stamp: Stamp) -> LaunchClaim:
    launch = p.launch_claim
    intent = p.run_intent
    if (p.head is None or p.bounds is None or launch is None
        or intent is None or launch.run_intent_id != intent.run_intent_id
        or launch.run_intent_digest != intent.run_intent_digest
        or p.boot_id != stamp.boot_id or launch.receiver_boot_id != stamp.boot_id
        or p.dispatch_holds or p.run_holds
        or p.boot_start_commit_seq is None
        or launch.committed_at_seq < p.boot_start_commit_seq
        or type(stamp.mono_us) is not int
        or not p.last_mono_us <= stamp.mono_us < launch.work_deadline_us):
        _fail_replay("replay_mismatch")
    members = tuple(sorted(
        fingerprint for fingerprint, entry in p.pending.items()
        if entry.admission_id == intent.admission_id
    ))
    if (len(members) != intent.member_count
        or tagged_digest(INITIAL_INTENT_MEMBERS_TAG, members) != intent.member_digest):
        _fail_replay("replay_mismatch")
    return launch


def plan_spawn_attestation(
    p: Projection, *, event_id: str, blocked_ack_digest: str,
    anchor_key_digest: str, witness_kind: str, verifier_version: str,
    witness_locator: str, witness_identity_digest: str,
    registry_entry_digest: str, stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Plan an untrusted blocked-child observation with no spawn authority."""
    launch = _claim_pre_release(p, stamp)
    if (p.spawn_attestation is not None or not _claim_event_id_ok(p, event_id)
        or not all(_digest64(value) for value in (
            blocked_ack_digest, anchor_key_digest, witness_identity_digest,
            registry_entry_digest,
        ))
        or not all(_safe_grant_id(value) for value in (
            witness_kind, verifier_version, witness_locator,
        ))):
        _fail_replay("replay_mismatch")
    ids = _launch_claim_ids(launch)
    data = {
        "rule": "spawn-attestation-v3", "based_on_commit_seq": p.head.commit_seq,
        "based_on_record_digest": p.head.record_digest,
        "launch_claim_event_id": launch.launch_claim_id,
        "launch_claim_digest": launch.launch_claim_digest,
        "launch_claim_commit_seq": launch.committed_at_seq,
        "receiver_boot_id": p.boot_id, "observed_us": stamp.mono_us,
        "blocked_ack_digest": blocked_ack_digest,
        "anchor_key_digest": anchor_key_digest,
        "witness_kind": witness_kind, "verifier_version": verifier_version,
        "witness_locator": witness_locator,
        "witness_identity_digest": witness_identity_digest,
        "registry_entry_digest": registry_entry_digest,
    }
    data["spawn_attestation_digest"] = tagged_digest(
        SPAWN_ATTESTATION_TAG, {"event_id": event_id, "ids": ids, "data": data},
    )
    record = seal(Draft(event_id, "spawn_attestation", "receiver", ids, data),
                  _single_position(p), stamp, schema_version=3)
    if len(record.body) > MAX_SPAWN_ATTESTATION_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.ordinary_bytes, p.logical_bytes, charge)
    return Plan((record,), charge, MappingProxyType({
        "state": "outstanding_unqualified_launch_claim", "claimed_phase": "attested",
    }))


def plan_release_intent(
    p: Projection, *, event_id: str,
    activated_grants: tuple[tuple[str, str, str, int], ...], stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Plan a release-intent claim; do not send a barrier byte."""
    launch = _claim_pre_release(p, stamp)
    attested = p.spawn_attestation
    if (attested is None or p.release_intent is not None
        or not _claim_event_id_ok(p, event_id)
        or attested.receiver_boot_id != stamp.boot_id
        or type(activated_grants) is not tuple
        or len(activated_grants) != len(launch.grants)
        or any(type(row) is not tuple or len(row) != 4 for row in activated_grants)):
        _fail_replay("replay_mismatch")
    activations: list[dict[str, object]] = []
    for row, grant in zip(activated_grants, launch.grants, strict=True):
        name, grant_id, digest, activated_us = row
        if (name != grant[0] or grant_id != grant[3]
            or not _digest64(digest) or type(activated_us) is not int
            or not attested.observed_us <= activated_us <= stamp.mono_us
            or not activated_us < grant[4]):
            _fail_replay("replay_mismatch")
        activations.append({
            "service": name, "grant_id": grant_id,
            "activation_digest": digest, "activation_us": activated_us,
        })
    ids = _launch_claim_ids(launch)
    data = {
        "rule": "release-intent-v3", "based_on_commit_seq": p.head.commit_seq,
        "based_on_record_digest": p.head.record_digest,
        "spawn_attestation_event_id": attested.event_id,
        "spawn_attestation_digest": attested.claim_digest,
        "spawn_attestation_commit_seq": attested.committed_at_seq,
        "receiver_boot_id": p.boot_id,
        "forwarder_generation": launch.forwarder_generation,
        "intended_release_us": stamp.mono_us,
        "activated_grants": activations,
    }
    data["release_intent_digest"] = tagged_digest(
        RELEASE_INTENT_TAG, {"event_id": event_id, "ids": ids, "data": data},
    )
    record = seal(Draft(event_id, "release_intent", "receiver", ids, data),
                  _single_position(p), stamp, schema_version=3)
    if len(record.body) > MAX_RELEASE_INTENT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.ordinary_bytes, p.logical_bytes, charge)
    return Plan((record,), charge, MappingProxyType({
        "state": "outstanding_unqualified_launch_claim", "claimed_phase": "release_intended",
    }))


def plan_release_observation(
    p: Projection, *, event_id: str, ack_digest: str, stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Preserve a claimed acknowledgment, even after a hold or deadline."""
    launch = p.launch_claim
    intended = p.release_intent
    if (p.head is None or p.bounds is None or launch is None or intended is None
        or p.release_observation is not None or not _claim_event_id_ok(p, event_id)
        or p.boot_id != stamp.boot_id or intended.receiver_boot_id != stamp.boot_id
        or type(stamp.mono_us) is not int
        or not max(p.last_mono_us, intended.intended_release_us) <= stamp.mono_us <= MAX_SEQ
        or not _digest64(ack_digest)):
        _fail_replay("replay_mismatch")
    ids = _launch_claim_ids(launch)
    data = {
        "rule": "release-observation-v3", "based_on_commit_seq": p.head.commit_seq,
        "based_on_record_digest": p.head.record_digest,
        "release_intent_event_id": intended.event_id,
        "release_intent_digest": intended.claim_digest,
        "release_intent_commit_seq": intended.committed_at_seq,
        "receiver_boot_id": p.boot_id, "observed_us": stamp.mono_us,
        "ack_digest": ack_digest,
    }
    data["release_observation_digest"] = tagged_digest(
        RELEASE_OBSERVATION_TAG, {"event_id": event_id, "ids": ids, "data": data},
    )
    record = seal(Draft(event_id, "release_observation", "receiver", ids, data),
                  _single_position(p), stamp, schema_version=3)
    if len(record.body) > MAX_RELEASE_OBSERVATION_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    return Plan((record,), charge, MappingProxyType({
        "state": "outstanding_unqualified_launch_claim", "claimed_phase": "release_observed",
    }))


def plan_effect_intent(
    p: Projection, *, event_id: str, operation_id: str, service: str,
    route_id: str, grant_id: str, scope_digest: str, flight_id: str,
    forwarder_receipt_id: str, request_digest: str, target_digest: str,
    expires_us: int, stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Record an untrusted exact-operation claim, never issue a permit."""
    launch = _claim_pre_release(p, stamp)
    if type(service) is not str:
        _fail_replay("replay_mismatch")
    released = p.release_observation
    route_service = EFFECT_ROUTE_SERVICE_V3.get(route_id) if type(route_id) is str else None
    grant = next((row for row in launch.grants if row[0] == service), None)
    used_flights = {claim.flight_id for claim in p.effect_intents.values()}
    used_receipts = {claim.forwarder_receipt_id for claim in p.effect_intents.values()}
    if (released is None or released.receiver_boot_id != stamp.boot_id
        or released.observed_us > stamp.mono_us
        or not _claim_event_id_ok(p, event_id)
        or not _canonical_uuid(operation_id)
        or not _claim_event_id_ok(p, operation_id)
        or operation_id == event_id
        or route_service != service
        or grant is None or not _safe_grant_id(grant_id)
        or not _digest64(scope_digest)
        or grant[3] != grant_id or grant[2] != scope_digest
        or not _safe_grant_id(flight_id) or not _safe_grant_id(forwarder_receipt_id)
        or flight_id == forwarder_receipt_id
        or flight_id in used_flights or forwarder_receipt_id in used_receipts
        or not _digest64(request_digest) or not _digest64(target_digest)
        or type(expires_us) is not int
        or not stamp.mono_us < expires_us <= min(launch.work_deadline_us, grant[4])):
        _fail_replay("replay_mismatch")
    if len(p.effect_intents) >= MAX_EFFECT_CLAIMS:
        return CapacityRefusal(
            "capacity_effect_claims", MAX_EFFECT_CLAIMS, len(p.effect_intents), 1,
        )
    ids = {
        "journal_uuid": launch.journal_uuid, "run_id": launch.run_id,
        "attempt_id": launch.attempt_id, "reservation_id": launch.reservation_id,
        "operation_id": operation_id,
    }
    data = {
        "rule": "effect-intent-v3", "based_on_commit_seq": p.head.commit_seq,
        "based_on_record_digest": p.head.record_digest,
        "release_observation_event_id": released.event_id,
        "release_observation_digest": released.claim_digest,
        "release_observation_commit_seq": released.committed_at_seq,
        "receiver_boot_id": p.boot_id,
        "forwarder_generation": launch.forwarder_generation,
        "service": service, "route_id": route_id, "grant_id": grant_id,
        "scope_digest": scope_digest, "flight_id": flight_id,
        "forwarder_receipt_id": forwarder_receipt_id,
        "request_digest": request_digest, "target_digest": target_digest,
        "observed_us": stamp.mono_us, "expires_us": expires_us,
    }
    data["effect_intent_digest"] = tagged_digest(
        EFFECT_INTENT_TAG, {"event_id": event_id, "ids": ids, "data": data},
    )
    record = seal(Draft(event_id, "effect_intent", "receiver", ids, data),
                  _single_position(p), stamp, schema_version=3)
    if len(record.body) > MAX_EFFECT_INTENT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.ordinary_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.ordinary_bytes, p.logical_bytes, charge)
    return Plan((record,), charge, MappingProxyType({
        "state": "effects_unqualified", "operation_id": operation_id,
    }))


def plan_effect_receipt(
    p: Projection, *, event_id: str, operation_id: str,
    claimed_dispatch_state: str, claimed_reason: str,
    finalized_receipt_digest: str, stamp: Stamp,
) -> Plan | CapacityRefusal:
    """Preserve an untrusted finalized-receipt claim after an exact intent."""
    intent = p.effect_intents.get(operation_id) if type(operation_id) is str else None
    if (p.head is None or p.bounds is None or intent is None
        or operation_id in p.effect_receipts or not _claim_event_id_ok(p, event_id)
        or p.boot_id != stamp.boot_id or intent.receiver_boot_id != stamp.boot_id
        or type(stamp.mono_us) is not int
        or not max(p.last_mono_us, intent.observed_us) <= stamp.mono_us <= MAX_SEQ
        or type(claimed_dispatch_state) is not str
        or type(claimed_reason) is not str
        or claimed_dispatch_state not in EFFECT_CLAIM_REASONS
        or claimed_reason not in EFFECT_CLAIM_REASONS[claimed_dispatch_state]
        or not _digest64(finalized_receipt_digest)):
        _fail_replay("replay_mismatch")
    ids = {
        "run_id": intent.run_id, "attempt_id": intent.attempt_id,
        "operation_id": operation_id,
    }
    data = {
        "rule": "effect-receipt-v3", "based_on_commit_seq": p.head.commit_seq,
        "based_on_record_digest": p.head.record_digest,
        "effect_intent_event_id": intent.event_id,
        "effect_intent_digest": intent.claim_digest,
        "effect_intent_commit_seq": intent.committed_at_seq,
        "receiver_boot_id": p.boot_id, "service": intent.service,
        "grant_id": intent.grant_id, "flight_id": intent.flight_id,
        "forwarder_receipt_id": intent.forwarder_receipt_id,
        "claimed_dispatch_state": claimed_dispatch_state,
        "claimed_reason": claimed_reason,
        "finalized_receipt_digest": finalized_receipt_digest,
        "observed_us": stamp.mono_us,
    }
    data["effect_receipt_digest"] = tagged_digest(
        EFFECT_RECEIPT_TAG, {"event_id": event_id, "ids": ids, "data": data},
    )
    record = seal(Draft(event_id, "effect_receipt", "receiver", ids, data),
                  _single_position(p), stamp, schema_version=3)
    if len(record.body) > MAX_EFFECT_RECEIPT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    charge = len(record.body) + RECORD_OVERHEAD_BYTES
    if p.logical_bytes + charge > p.bounds.total_bytes:
        return CapacityRefusal(_BYTES_CODE, p.bounds.total_bytes, p.logical_bytes, charge)
    return Plan((record,), charge, MappingProxyType({
        "state": "effects_unqualified", "operation_id": operation_id,
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
    if types == ("reservation_intent",):
        return "reservation_intent"
    if types == ("reservation_confirmation",):
        return "reservation_confirmation"
    if types == ("run_intent",):
        return "run_intent"
    if types == ("launch_claim",):
        return "launch_claim"
    if types == ("spawn_attestation",):
        return "spawn_attestation"
    if types == ("release_intent",):
        return "release_intent"
    if types == ("release_observation",):
        return "release_observation"
    if types == ("effect_intent",):
        return "effect_intent"
    if types == ("effect_receipt",):
        return "effect_receipt"
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


def _verify_reservation_intent(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 2:
        _fail_replay("replay_mismatch")
    plan = plan_reservation_intent(
        p, job_id=record.ids["job_id"], admission_id=record.ids["admission_id"],
        intent_id=record.ids["intent_id"], attempt_id=record.ids["attempt_id"],
        reservation_id=record.ids["reservation_id"], run_id=record.ids["run_id"],
        lease_id=record.ids["lease_id"], stamp=record.stamp,
    )
    if isinstance(plan, CapacityRefusal) or (
        plan.records[0].body != record.body
        or plan.records[0].record_digest != record.record_digest
    ):
        _fail_replay("replay_mismatch")
    claim = ReservationIntentClaim(
        journal_uuid=p.journal_uuid, journal_generation=p.generation,
        admission_id=record.ids["admission_id"], job_id=record.ids["job_id"],
        intent_id=record.ids["intent_id"], attempt_id=record.ids["attempt_id"],
        reservation_id=record.ids["reservation_id"], run_id=record.ids["run_id"],
        lease_id=record.ids["lease_id"], intent_digest=record.data["intent_digest"],
        based_on_commit_seq=record.data["based_on_commit_seq"],
        committed_at_seq=commit_seq,
    )
    return Delta(
        head=Head(p.generation, commit_seq, record.position.event_seq, record.record_digest),
        generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + plan.charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, reservation_intent_add=claim,
    )


def _verify_initial_reservation_intent(
    p: Projection, record: Record, commit_seq: int,
) -> Delta:
    if record.schema_version != 3:
        _fail_replay("replay_mismatch")
    plan = plan_initial_reservation_intent(
        p, job_id=record.ids["job_id"], admission_id=record.ids["admission_id"],
        intent_id=record.ids["intent_id"], attempt_id=record.ids["attempt_id"],
        reservation_id=record.ids["reservation_id"], run_id=record.ids["run_id"],
        lease_id=record.ids["lease_id"], stamp=record.stamp,
    )
    if isinstance(plan, CapacityRefusal) or (
        plan.records[0].body != record.body
        or plan.records[0].record_digest != record.record_digest
    ):
        _fail_replay("replay_mismatch")
    claim = InitialReservationIntentClaim(
        journal_uuid=p.journal_uuid, journal_generation=p.generation,
        admission_id=record.ids["admission_id"], job_id=record.ids["job_id"],
        intent_id=record.ids["intent_id"], attempt_id=record.ids["attempt_id"],
        reservation_id=record.ids["reservation_id"], run_id=record.ids["run_id"],
        lease_id=record.ids["lease_id"], member_count=record.data["member_count"],
        member_digest=record.data["member_digest"],
        intent_digest=record.data["intent_digest"],
        based_on_commit_seq=record.data["based_on_commit_seq"],
        committed_at_seq=commit_seq,
    )
    return Delta(
        head=Head(p.generation, commit_seq, record.position.event_seq, record.record_digest),
        generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + plan.charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, initial_reservation_intent_add=claim,
    )


def _verify_reservation_confirmation(
    p: Projection, record: Record, commit_seq: int,
) -> Delta:
    if record.schema_version not in (2, 3):
        _fail_replay("replay_mismatch")
    planner = (
        plan_reservation_confirmation if record.schema_version == 2
        else plan_initial_reservation_confirmation
    )
    plan = planner(
        p, intent_id=record.ids["intent_id"], event_id=record.event_id,
        ledger_uuid=record.data["ledger_uuid"],
        ledger_generation=record.data["ledger_generation"],
        ledger_event_id=record.data["ledger_event_id"],
        sequence=record.data["sequence"], event_digest=record.data["event_digest"],
        stamp=record.stamp,
    )
    if isinstance(plan, CapacityRefusal) or (
        plan.records[0].body != record.body
        or plan.records[0].record_digest != record.record_digest
    ):
        _fail_replay("replay_mismatch")
    claim = ReservationConfirmationClaim(
        intent_id=record.ids["intent_id"], confirmation_event_id=record.event_id,
        intent_digest=record.data["intent_digest"],
        ledger_uuid=record.data["ledger_uuid"],
        ledger_generation=record.data["ledger_generation"],
        ledger_event_id=record.data["ledger_event_id"],
        sequence=record.data["sequence"], event_digest=record.data["event_digest"],
        committed_at_seq=commit_seq,
    )
    return Delta(
        head=Head(p.generation, commit_seq, record.position.event_seq, record.record_digest),
        generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + plan.charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None,
        reservation_confirmation_add=claim if record.schema_version == 2 else None,
        initial_reservation_confirmation_add=claim if record.schema_version == 3 else None,
    )


def _verify_run_intent(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 3 or len(record.body) > MAX_RUN_INTENT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    head = record.data["ledger_head"]
    services = tuple(
        (item["service"], item["lease_claim_id"], item["scope_digest"])
        for item in record.data["services"]
    )
    plan = plan_run_intent(
        p, intent_id=record.ids["intent_id"], event_id=record.event_id,
        ledger_head_sequence=head["sequence"], ledger_head_digest=head["event_digest"],
        services=services, stamp=record.stamp,
    )
    if isinstance(plan, CapacityRefusal) or (
        plan.records[0].body != record.body
        or plan.records[0].record_digest != record.record_digest
    ):
        _fail_replay("replay_mismatch")
    claim = RunIntentClaim(
        run_intent_id=record.event_id,
        journal_uuid=record.ids["journal_uuid"],
        journal_generation=p.generation,
        admission_id=record.ids["admission_id"], job_id=record.ids["job_id"],
        intent_id=record.ids["intent_id"], attempt_id=record.ids["attempt_id"],
        reservation_id=record.ids["reservation_id"], run_id=record.ids["run_id"],
        model_lease_id=record.ids["lease_id"],
        initial_intent_digest=record.data["intent_digest"],
        confirmation_event_id=record.data["confirmation_event_id"],
        ledger_uuid=record.data["ledger_uuid"],
        ledger_generation=record.data["ledger_generation"],
        ledger_event_id=record.data["ledger_event_id"],
        ledger_sequence=record.data["sequence"],
        ledger_event_digest=record.data["event_digest"],
        ledger_head_sequence=head["sequence"], ledger_head_digest=head["event_digest"],
        member_count=record.data["member_count"],
        member_digest=record.data["member_digest"], services=services,
        run_intent_digest=record.data["run_intent_digest"],
        committed_at_seq=commit_seq,
    )
    return Delta(
        head=Head(p.generation, commit_seq, record.position.event_seq, record.record_digest),
        generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + plan.charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, run_intent_add=claim,
    )


def _verify_launch_claim(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 3 or len(record.body) > MAX_LAUNCH_CLAIM_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    grants = tuple(
        (item["service"], item["lease_claim_id"], item["scope_digest"],
         item["grant_id"], item["grant_expiry_us"])
        for item in record.data["grants"]
    )
    plan = plan_launch_claim(
        p, event_id=record.event_id,
        forwarder_generation=record.data["forwarder_generation"],
        barrier_token_digest=record.data["barrier_token_digest"],
        grants=grants, stamp=record.stamp,
    )
    if isinstance(plan, CapacityRefusal) or (
        plan.records[0].body != record.body
        or plan.records[0].record_digest != record.record_digest
        or plan.records[0].ids != record.ids
        or plan.records[0].data != record.data
    ):
        _fail_replay("replay_mismatch")
    claim = LaunchClaim(
        launch_claim_id=record.event_id,
        run_intent_id=record.data["run_intent_event_id"],
        run_intent_digest=record.data["run_intent_digest"],
        journal_uuid=record.ids["journal_uuid"],
        admission_id=record.ids["admission_id"], job_id=record.ids["job_id"],
        intent_id=record.ids["intent_id"], attempt_id=record.ids["attempt_id"],
        reservation_id=record.ids["reservation_id"], run_id=record.ids["run_id"],
        model_lease_id=record.ids["lease_id"],
        receiver_boot_id=record.data["receiver_boot_id"],
        forwarder_generation=record.data["forwarder_generation"],
        barrier_token_digest=record.data["barrier_token_digest"],
        origin_us=record.data["origin_us"],
        work_deadline_us=record.data["work_deadline_us"],
        flush_deadline_us=record.data["flush_deadline_us"],
        hard_deadline_us=record.data["hard_deadline_us"],
        grants=grants, launch_claim_digest=record.data["launch_claim_digest"],
        committed_at_seq=commit_seq,
    )
    return Delta(
        head=Head(p.generation, commit_seq, record.position.event_seq, record.record_digest),
        generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + plan.charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, launch_claim_add=claim,
    )


def _verify_exact_claim_plan(plan: Plan | CapacityRefusal, record: Record) -> Plan:
    if isinstance(plan, CapacityRefusal) or (
        plan.records[0].body != record.body
        or plan.records[0].record_digest != record.record_digest
        or plan.records[0].ids != record.ids
        or plan.records[0].data != record.data
    ):
        _fail_replay("replay_mismatch")
    return plan


def _claim_delta(
    p: Projection, record: Record, commit_seq: int, charge: int, *,
    attestation: SpawnAttestationClaim | None = None,
    intent: ReleaseIntentClaim | None = None,
    observation: ReleaseObservationClaim | None = None,
    effect_intent: EffectIntentClaim | None = None,
    effect_receipt: EffectReceiptClaim | None = None,
) -> Delta:
    return Delta(
        head=Head(p.generation, commit_seq, record.position.event_seq, record.record_digest),
        generation=p.generation, journal_uuid=None, bounds=None,
        boot_id=p.boot_id, last_mono_us=record.stamp.mono_us, new_boot_id=None,
        logical_bytes=p.logical_bytes + charge, admission_count=p.admission_count,
        last_arrival_seq=p.last_arrival_seq, baseline_update=None, pending_updates=(),
        dispatch_hold_add=None, spawn_attestation_add=attestation,
        release_intent_add=intent, release_observation_add=observation,
        effect_intent_add=effect_intent, effect_receipt_add=effect_receipt,
    )


def _verify_spawn_attestation(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 3 or len(record.body) > MAX_SPAWN_ATTESTATION_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    data = record.data
    plan = _verify_exact_claim_plan(plan_spawn_attestation(
        p, event_id=record.event_id,
        blocked_ack_digest=data["blocked_ack_digest"],
        anchor_key_digest=data["anchor_key_digest"],
        witness_kind=data["witness_kind"], verifier_version=data["verifier_version"],
        witness_locator=data["witness_locator"],
        witness_identity_digest=data["witness_identity_digest"],
        registry_entry_digest=data["registry_entry_digest"], stamp=record.stamp,
    ), record)
    claim = SpawnAttestationClaim(
        event_id=record.event_id, claim_digest=data["spawn_attestation_digest"],
        launch_claim_id=data["launch_claim_event_id"], run_id=record.ids["run_id"],
        attempt_id=record.ids["attempt_id"], receiver_boot_id=data["receiver_boot_id"],
        observed_us=data["observed_us"], witness_locator=data["witness_locator"],
        witness_identity_digest=data["witness_identity_digest"],
        committed_at_seq=commit_seq,
    )
    return _claim_delta(p, record, commit_seq, plan.charge, attestation=claim)


def _verify_release_intent(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 3 or len(record.body) > MAX_RELEASE_INTENT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    data = record.data
    activations = tuple(
        (item["service"], item["grant_id"], item["activation_digest"],
         item["activation_us"])
        for item in data["activated_grants"]
    )
    plan = _verify_exact_claim_plan(plan_release_intent(
        p, event_id=record.event_id, activated_grants=activations, stamp=record.stamp,
    ), record)
    claim = ReleaseIntentClaim(
        event_id=record.event_id, claim_digest=data["release_intent_digest"],
        spawn_attestation_id=data["spawn_attestation_event_id"],
        receiver_boot_id=data["receiver_boot_id"],
        intended_release_us=data["intended_release_us"],
        activated_grants=activations, committed_at_seq=commit_seq,
    )
    return _claim_delta(p, record, commit_seq, plan.charge, intent=claim)


def _verify_release_observation(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 3 or len(record.body) > MAX_RELEASE_OBSERVATION_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    data = record.data
    plan = _verify_exact_claim_plan(plan_release_observation(
        p, event_id=record.event_id, ack_digest=data["ack_digest"], stamp=record.stamp,
    ), record)
    claim = ReleaseObservationClaim(
        event_id=record.event_id, claim_digest=data["release_observation_digest"],
        release_intent_id=data["release_intent_event_id"],
        receiver_boot_id=data["receiver_boot_id"], observed_us=data["observed_us"],
        committed_at_seq=commit_seq,
    )
    return _claim_delta(p, record, commit_seq, plan.charge, observation=claim)


def _verify_effect_intent(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 3 or len(record.body) > MAX_EFFECT_INTENT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    data = record.data
    plan = _verify_exact_claim_plan(plan_effect_intent(
        p, event_id=record.event_id, operation_id=record.ids["operation_id"],
        service=data["service"], route_id=data["route_id"],
        grant_id=data["grant_id"], scope_digest=data["scope_digest"],
        flight_id=data["flight_id"],
        forwarder_receipt_id=data["forwarder_receipt_id"],
        request_digest=data["request_digest"], target_digest=data["target_digest"],
        expires_us=data["expires_us"], stamp=record.stamp,
    ), record)
    claim = EffectIntentClaim(
        event_id=record.event_id, claim_digest=data["effect_intent_digest"],
        operation_id=record.ids["operation_id"], run_id=record.ids["run_id"],
        attempt_id=record.ids["attempt_id"], receiver_boot_id=data["receiver_boot_id"],
        forwarder_generation=data["forwarder_generation"],
        service=data["service"], route_id=data["route_id"],
        grant_id=data["grant_id"], scope_digest=data["scope_digest"],
        flight_id=data["flight_id"],
        forwarder_receipt_id=data["forwarder_receipt_id"],
        request_digest=data["request_digest"], target_digest=data["target_digest"],
        observed_us=data["observed_us"], expires_us=data["expires_us"],
        committed_at_seq=commit_seq,
    )
    return _claim_delta(p, record, commit_seq, plan.charge, effect_intent=claim)


def _verify_effect_receipt(p: Projection, record: Record, commit_seq: int) -> Delta:
    if record.schema_version != 3 or len(record.body) > MAX_EFFECT_RECEIPT_RECORD_BYTES:
        _fail_replay("replay_mismatch")
    data = record.data
    plan = _verify_exact_claim_plan(plan_effect_receipt(
        p, event_id=record.event_id, operation_id=record.ids["operation_id"],
        claimed_dispatch_state=data["claimed_dispatch_state"],
        claimed_reason=data["claimed_reason"],
        finalized_receipt_digest=data["finalized_receipt_digest"], stamp=record.stamp,
    ), record)
    claim = EffectReceiptClaim(
        event_id=record.event_id, claim_digest=data["effect_receipt_digest"],
        operation_id=record.ids["operation_id"],
        intent_event_id=data["effect_intent_event_id"],
        receiver_boot_id=data["receiver_boot_id"],
        claimed_dispatch_state=data["claimed_dispatch_state"],
        claimed_reason=data["claimed_reason"],
        finalized_receipt_digest=data["finalized_receipt_digest"],
        observed_us=data["observed_us"], committed_at_seq=commit_seq,
    )
    return _claim_delta(p, record, commit_seq, plan.charge, effect_receipt=claim)


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
    if shape == "reservation_intent":
        if records[0].schema_version == 3:
            return _verify_initial_reservation_intent(p, records[0], commit_seq)
        return _verify_reservation_intent(p, records[0], commit_seq)
    if shape == "reservation_confirmation":
        return _verify_reservation_confirmation(p, records[0], commit_seq)
    if shape == "run_intent":
        return _verify_run_intent(p, records[0], commit_seq)
    if shape == "launch_claim":
        return _verify_launch_claim(p, records[0], commit_seq)
    if shape == "spawn_attestation":
        return _verify_spawn_attestation(p, records[0], commit_seq)
    if shape == "release_intent":
        return _verify_release_intent(p, records[0], commit_seq)
    if shape == "release_observation":
        return _verify_release_observation(p, records[0], commit_seq)
    if shape == "effect_intent":
        return _verify_effect_intent(p, records[0], commit_seq)
    if shape == "effect_receipt":
        return _verify_effect_receipt(p, records[0], commit_seq)
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
    if delta.reservation_intent_add is not None:
        claim = delta.reservation_intent_add
        p.intents[claim.intent_id] = claim
    if delta.reservation_confirmation_add is not None:
        claim = delta.reservation_confirmation_add
        p.confirmations[claim.intent_id] = claim
    if delta.initial_reservation_intent_add is not None:
        claim = delta.initial_reservation_intent_add
        p.initial_intents[claim.intent_id] = claim
    if delta.initial_reservation_confirmation_add is not None:
        claim = delta.initial_reservation_confirmation_add
        p.initial_confirmations[claim.intent_id] = claim
    if delta.run_intent_add is not None:
        p.run_intent = delta.run_intent_add
    if delta.launch_claim_add is not None:
        p.launch_claim = delta.launch_claim_add
    if delta.spawn_attestation_add is not None:
        p.spawn_attestation = delta.spawn_attestation_add
    if delta.release_intent_add is not None:
        p.release_intent = delta.release_intent_add
    if delta.release_observation_add is not None:
        p.release_observation = delta.release_observation_add
    if delta.effect_intent_add is not None:
        claim = delta.effect_intent_add
        p.effect_intents[claim.operation_id] = claim
    if delta.effect_receipt_add is not None:
        claim = delta.effect_receipt_add
        p.effect_receipts[claim.operation_id] = claim
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


def reservation_claims_digest(p: Projection) -> str:
    payload = {
        "intents": [dataclasses.asdict(claim) for _, claim in sorted(p.intents.items())],
        "confirmations": [
            dataclasses.asdict(claim) for _, claim in sorted(p.confirmations.items())
        ],
    }
    return tagged_digest(RESERVATION_CLAIMS_TAG, payload)


def initial_intents_digest(p: Projection) -> str:
    claims = [dataclasses.asdict(claim) for _, claim in sorted(p.initial_intents.items())]
    return tagged_digest(INITIAL_INTENTS_STATE_TAG, claims)


def initial_confirmations_digest(p: Projection) -> str:
    claims = [dataclasses.asdict(claim) for _, claim in sorted(p.initial_confirmations.items())]
    return tagged_digest(INITIAL_CONFIRMATIONS_STATE_TAG, claims)


def run_intent_claim_digest(p: Projection) -> str:
    return tagged_digest(
        RUN_INTENT_STATE_TAG,
        None if p.run_intent is None else dataclasses.asdict(p.run_intent),
    )


def launch_claim_digest(p: Projection) -> str:
    return tagged_digest(
        LAUNCH_CLAIM_STATE_TAG,
        None if p.launch_claim is None else dataclasses.asdict(p.launch_claim),
    )


def spawn_attestation_claim_digest(p: Projection) -> str:
    return tagged_digest(
        SPAWN_ATTESTATION_STATE_TAG,
        None if p.spawn_attestation is None else dataclasses.asdict(p.spawn_attestation),
    )


def release_intent_claim_digest(p: Projection) -> str:
    return tagged_digest(
        RELEASE_INTENT_STATE_TAG,
        None if p.release_intent is None else dataclasses.asdict(p.release_intent),
    )


def release_observation_claim_digest(p: Projection) -> str:
    return tagged_digest(
        RELEASE_OBSERVATION_STATE_TAG,
        None if p.release_observation is None else dataclasses.asdict(p.release_observation),
    )


def effect_intents_claim_digest(p: Projection) -> str:
    claims = [dataclasses.asdict(claim) for _, claim in sorted(p.effect_intents.items())]
    return tagged_digest(EFFECT_INTENTS_STATE_TAG, claims)


def effect_receipts_claim_digest(p: Projection) -> str:
    claims = [dataclasses.asdict(claim) for _, claim in sorted(p.effect_receipts.items())]
    return tagged_digest(EFFECT_RECEIPTS_STATE_TAG, claims)


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
    "EFFECT_INTENTS_STATE_TAG",
    "EFFECT_RECEIPTS_STATE_TAG",
    "FRONT_DOOR_STATE_TAG",
    "INITIAL_CONFIRMATIONS_STATE_TAG",
    "INITIAL_INTENTS_STATE_TAG",
    "LAUNCH_CLAIM_STATE_TAG",
    "MAX_EFFECT_CLAIMS",
    "MAX_RESERVATION_CLAIMS",
    "MAX_RUN_HOLDS",
    "RECORD_OVERHEAD_BYTES",
    "REFUSAL_KEY_TAG",
    "RELEASE_INTENT_STATE_TAG",
    "RELEASE_OBSERVATION_STATE_TAG",
    "REPLAY_ERROR_CODES",
    "RUN_INTENT_STATE_TAG",
    "SPAWN_ATTESTATION_STATE_TAG",
    "Baseline",
    "CapacityRefusal",
    "Delta",
    "EffectIntentClaim",
    "EffectReceiptClaim",
    "InitialReservationIntentClaim",
    "JournalBounds",
    "LaunchClaim",
    "PendingEntry",
    "Plan",
    "Projection",
    "RefusalNotRecorded",
    "ReleaseIntentClaim",
    "ReleaseObservationClaim",
    "ReplayError",
    "ReservationConfirmationClaim",
    "ReservationIntentClaim",
    "RunHold",
    "RunIntentClaim",
    "SpawnAttestationClaim",
    "apply_delta",
    "dispatch_holds",
    "effect_intents_claim_digest",
    "effect_receipts_claim_digest",
    "front_door_digest",
    "group_commits",
    "initial_confirmations_digest",
    "initial_intents_digest",
    "launch_claim_digest",
    "new_projection",
    "pending_digest",
    "pending_entries",
    "plan_admission",
    "plan_capacity_hold",
    "plan_effect_intent",
    "plan_effect_receipt",
    "plan_genesis",
    "plan_ingress_refusal",
    "plan_initial_reservation_confirmation",
    "plan_initial_reservation_intent",
    "plan_launch_claim",
    "plan_operator_resume",
    "plan_release_intent",
    "plan_release_observation",
    "plan_reservation_confirmation",
    "plan_reservation_intent",
    "plan_restart",
    "plan_run_hold",
    "plan_run_intent",
    "plan_spawn_attestation",
    "refusal_key",
    "release_intent_claim_digest",
    "release_observation_claim_digest",
    "replay",
    "reservation_claims_digest",
    "run_holds_digest",
    "run_intent_claim_digest",
    "spawn_attestation_claim_digest",
    "state_digest",
    "verify_commit",
]
