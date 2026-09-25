"""The recovery journal record envelope: canonical encoding, digests and
transaction-numbering fields (ticket 37, unit 15, module 1).

The bounded sanitized source record lives in the sibling ``journal_source``
module (split out past this module's ~520-line trigger, same owner and
public API as originally specified); this module imports only the two names
its own per-type validation needs from it.

Pure: no clock, randomness, filesystem or state. Stamps, IDs and positions are
always inputs. Every validation failure raises ``RecordError`` with a fixed
code; nothing echoes caller or stored content in an error, a ``repr`` or a
chained exception. Error discipline matches ``forwarder_json``: every
``except`` body only assigns a local ``code`` variable, and a fresh error is
raised after the ``try`` statement with ``from None``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from types import MappingProxyType

from .forwarder_json import JSONPolicyError, canonical_json, parse_json, tagged_digest
from .journal_source import MAX_FINGERPRINT_BYTES, source_from_json

# --- Format constants -------------------------------------------------------

SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 16_384
MAX_ID_BYTES = 128
MAX_COMMIT_RECORDS = 8
MAX_SEQ = 2**53 - 1
MAX_GENERATION = 2**31 - 1
ZERO_DIGEST = "0" * 64

V1_BOUND_CEILINGS = MappingProxyType({
    "max_admissions": 10_000,
    "max_pending_fingerprints": 1_024,
    "ordinary_bytes": 112 * 2**20,
    "total_bytes": 128 * 2**20,
})

EVENT_TYPES = (
    "journal_genesis", "restart_recovery", "capacity_hold", "admission", "dedupe_decision",
)
# The front door's two record types (unit 17). EVENT_TYPES stays the unit-15
# five-tuple: F3 replays a journal holding only those and asserts the set.
FRONT_DOOR_EVENT_TYPES = ("ingress_refusal", "operator_action")
RUN_EVENT_TYPES_V2 = ("run_hold",)
RUN_EVENT_TYPES_V3 = ("run_intent", "launch_claim")
SPAWN_EVENT_TYPES_V3 = ("spawn_attestation", "release_intent", "release_observation")
EFFECT_EVENT_TYPES_V3 = ("effect_intent", "effect_receipt")
SUPERVISION_ACTION_EVENT_TYPES_V3 = (
    "supervision_action_intent", "supervision_action_result",
)
EXECUTION_EVENT_TYPES_V3 = (
    "process_observation", "terminal_observation", "execution_assessment",
)
RECONCILIATION_EVENT_TYPES_V3 = ("reconciliation_observation",)
REGISTERED_EVENT_TYPES = EVENT_TYPES + FRONT_DOOR_EVENT_TYPES
RECORD_CLASS = MappingProxyType({
    "journal_genesis": "recovery",
    "restart_recovery": "recovery",
    "capacity_hold": "recovery",
    "admission": "ordinary",
    "dedupe_decision": "ordinary",
    "ingress_refusal": "ordinary",
    "operator_action": "recovery",
})
RUN_RECORD_CLASS_V2 = MappingProxyType({"run_hold": "recovery"})
RUN_RECORD_CLASS_V3 = MappingProxyType({
    "run_intent": "ordinary", "launch_claim": "ordinary",
})
SPAWN_RECORD_CLASS_V3 = MappingProxyType({
    "spawn_attestation": "ordinary", "release_intent": "ordinary",
    "release_observation": "recovery",
})
EFFECT_RECORD_CLASS_V3 = MappingProxyType({
    "effect_intent": "ordinary", "effect_receipt": "recovery",
})
SUPERVISION_ACTION_RECORD_CLASS_V3 = MappingProxyType({
    "supervision_action_intent": "recovery",
    "supervision_action_result": "recovery",
})
EXECUTION_RECORD_CLASS_V3 = MappingProxyType({
    "process_observation": "recovery", "terminal_observation": "recovery",
    "execution_assessment": "recovery",
})
RECONCILIATION_RECORD_CLASS_V3 = MappingProxyType({
    "reconciliation_observation": "recovery",
})
RESERVATION_RECORD_CLASS_V2 = MappingProxyType({
    "reservation_intent": "recovery",
    "reservation_confirmation": "recovery",
})
RESERVATION_RECORD_CLASS_V3 = MappingProxyType({
    "reservation_intent": "ordinary",
    "reservation_confirmation": "recovery",
})

ACTORS = ("receiver", "spawner", "forwarder", "operator")

IDENTITY_KEYS = (
    "admission_id", "job_id", "run_id", "attempt_id", "effect_id",
    "operation_id", "intent_id", "reservation_id", "lease_id",
)

DEDUPE_RULE = "latest-admitted-v1"
DEDUPE_RESULTS = ("admitted", "suppressed", "pending_reduced")
ADMISSION_DECISIONS = ("admitted", "held")

CAPACITY_CODES = ("capacity_admissions", "capacity_pending", "capacity_bytes")
DISPATCH_HOLD_CODES = CAPACITY_CODES + ("restart_recovery",)

RECORD_TAG = "rj.record.v1"
CONTENT_TAG = "rj.content.v1"

# --- Front-door constants (unit 17), restated because A12 pins the imports:
# journal_records may not import journal_ingress, so the values it enforces
# here are independent copies, held in step by parity test A5. ------------

REFUSAL_RULE = "first-per-membership-v1"
MAX_REFUSAL_RECORDS = 256
REFUSAL_RESOLVED_RESERVE = 64
INGRESS_REFUSAL_CODES_V1 = tuple(sorted((
    "ingress_too_large", "ingress_json_invalid", "ingress_shape", "ingress_group_key",
    "ingress_truncated", "ingress_fingerprint", "ingress_status", "ingress_values",
    "ingress_duplicate_fingerprint", "ingress_json_unsupported", "ingress_group_key_unsupported",
    "ingress_ref_id_unsupported", "ingress_too_many_alerts", "ingress_too_many_values",
    "ingress_record_too_large", "ingress_divergence",
)))
OPERATOR_ACTIONS = ("resume",)
RESUME_RULE = "resume-at-open-v1"
RESUMABLE_HOLDS = ("restart_recovery",)
RUN_HOLD_REASONS_V2 = (
    "accounting_unavailable", "restart_recovery", "venue_unready",
    "reference_revoked", "operator_review", "required_effect_unknown",
)
MAX_RUN_HOLD_RECORD_BYTES = 2_048
MAX_RUN_INTENT_RECORD_BYTES = 4_096
MAX_LAUNCH_CLAIM_RECORD_BYTES = 6_144
MAX_SPAWN_ATTESTATION_RECORD_BYTES = 4_096
MAX_RELEASE_INTENT_RECORD_BYTES = 4_096
MAX_RELEASE_OBSERVATION_RECORD_BYTES = 2_048
MAX_EFFECT_INTENT_RECORD_BYTES = 4_096
MAX_EFFECT_RECEIPT_RECORD_BYTES = 2_048
MAX_SUPERVISION_ACTION_INTENT_RECORD_BYTES = 4_096
MAX_SUPERVISION_ACTION_RESULT_RECORD_BYTES = 2_048
MAX_PROCESS_OBSERVATION_RECORD_BYTES = 4_096
MAX_TERMINAL_OBSERVATION_RECORD_BYTES = 4_096
MAX_EXECUTION_ASSESSMENT_RECORD_BYTES = 2_048
MAX_RECONCILIATION_OBSERVATION_RECORD_BYTES = 2_048

# Private copies of journal_ingress/journal_source vocabulary the strict
# refusal-summary checker needs; never imported (A12's import pin).
_MEMBER_CODES = frozenset({
    "ingress_group_key_unsupported", "ingress_ref_id_unsupported", "ingress_too_many_alerts",
    "ingress_too_many_values", "ingress_record_too_large",
})
_NO_GROUP_CODES = frozenset({
    "ingress_too_large", "ingress_json_invalid", "ingress_json_unsupported", "ingress_group_key",
})
_ALERT_STATUSES = ("firing", "resolved")
_MAX_ALERTS = 32
_MAX_REFUSAL_MEMBERS = 32
_MAX_JSON_ARRAY_ITEMS = 256
_MAX_REFUSAL_JSON_BYTES = 4_096
_MAX_INGRESS_BODY_BYTES = 262_144

RECORD_ERROR_CODES = frozenset({
    "record_argument", "record_digest", "record_json", "record_not_canonical",
    "record_too_large", "record_unsupported", "record_field", "record_type",
    "record_id", "record_time",
})

_HEX = frozenset("0123456789abcdef")
_MAX_DISPATCH_HOLDS = 8
_MAX_SUPERSEDED = 32
# canonical_json's depth cap: nothing deeper could ever be encoded.
_MAX_THAW_DEPTH = 16

_ID_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{MAX_ID_BYTES}}}")
# The same grammar journal_source applies to a source record's fingerprints.
_FINGERPRINT_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{MAX_FINGERPRINT_BYTES}}}")
_UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# [0-9], not \d: \d also matches non-ASCII digits.
_WALL_TIME_PATTERN = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})\.([0-9]{6})Z"
)


class RecordError(ValueError):
    """A fixed, non-diagnostic envelope/registry rejection; never embeds caller data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail_record(code: str) -> None:
    raise RecordError(code) from None


# --- Value types --------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Head:
    generation: int
    commit_seq: int
    event_seq: int
    record_digest: str


@dataclasses.dataclass(frozen=True)
class Stamp:
    boot_id: str
    wall_time: str
    mono_us: int


@dataclasses.dataclass(frozen=True)
class WalFound:
    size: int
    digest: str


@dataclasses.dataclass(frozen=True)
class Position:
    journal_generation: int
    event_seq: int
    commit_seq: int
    commit_index: int
    commit_size: int
    prev_record_digest: str


@dataclasses.dataclass(frozen=True)
class Draft:
    event_id: str
    event_type: str
    actor: str
    ids: Mapping[str, str]
    data: Mapping[str, object]


@dataclasses.dataclass(frozen=True)
class Record:
    position: Position
    stamp: Stamp
    event_id: str
    event_type: str
    schema_version: int
    actor: str
    ids: Mapping[str, str]
    data: Mapping[str, object]
    body: bytes
    record_digest: str


# --- Small structural predicates (no side effects, no exceptions) -----------


def _hex64_ok(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in _HEX for c in value)


def _enum_ok(value: object, choices: tuple[str, ...]) -> bool:
    return type(value) is str and value in choices


def _exact_keys_ok(value: object, keys: frozenset) -> bool:
    return type(value) is dict and value.keys() == keys


def validate_id(value: object) -> str:
    if type(value) is not str or not _ID_PATTERN.fullmatch(value):
        _fail_record("record_id")
    return value


# --- Frozen <-> plain conversion ----------------------------------------------


def thaw(value: object) -> object:
    return _thaw(value, 1)


def _thaw(value: object, depth: int) -> object:
    is_mapping = isinstance(value, Mapping)
    if not is_mapping and type(value) is not tuple:
        return value
    if depth > _MAX_THAW_DEPTH:  # also ends a cycle
        _fail_record("record_field")
    if is_mapping:
        return {key: _thaw(item, depth + 1) for key, item in value.items()}
    return tuple(_thaw(item, depth + 1) for item in value)


def _freeze(value: object) -> object:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is tuple or type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


# --- Wall time -----------------------------------------------------------------


def format_wall_time(epoch_ns: int) -> str:
    if type(epoch_ns) is not int or epoch_ns < 0:
        _fail_record("record_time")
    seconds, nanoseconds = divmod(epoch_ns, 1_000_000_000)
    code: str | None = None
    # The import allowlist pins `timezone`, not the `UTC` alias ruff would prefer.
    try:
        stamp = datetime.fromtimestamp(seconds, tz=timezone.utc)  # noqa: UP017
    except (OverflowError, OSError, ValueError):
        code = "record_time"
    if code is not None:
        _fail_record(code)
    if not 2000 <= stamp.year <= 9999:
        _fail_record("record_time")
    microseconds = nanoseconds // 1_000
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{microseconds:06d}Z"


def _require_wall_time(value: object) -> str:
    if type(value) is not str or len(value) != 27:
        _fail_record("record_time")
    match = _WALL_TIME_PATTERN.fullmatch(value)
    if match is None:
        _fail_record("record_time")
    year = int(match.group(1))
    if not 2000 <= year <= 9999:
        _fail_record("record_time")
    code: str | None = None
    try:
        datetime(
            year, int(match.group(2)), int(match.group(3)),
            int(match.group(4)), int(match.group(5)), int(match.group(6)),
            int(match.group(7)), tzinfo=timezone.utc,  # noqa: UP017
        )
    except ValueError:
        code = "record_time"
    if code is not None:
        _fail_record(code)
    return value


# --- Envelope and per-type validation -----------------------------------------

_ENVELOPE_KEYS = frozenset({
    "schema_version", "journal_generation", "event_id", "event_seq", "commit_seq",
    "commit_index", "commit_size", "event_type", "actor", "boot_id", "wall_time",
    "mono_us", "ids", "data", "prev_record_digest",
})
_EMPTY_KEYS: frozenset = frozenset()
_ADMISSION_IDS_KEYS = frozenset({"admission_id"})

_GENESIS_DATA_KEYS = frozenset({"format", "journal_uuid", "bounds"})
_BOUNDS_KEYS = frozenset({
    "max_admissions", "max_pending_fingerprints", "ordinary_bytes", "total_bytes",
})
_RESTART_DATA_KEYS = frozenset({
    "previous_boot_id", "recovered", "anchor_lag", "wal_found", "dispatch_hold", "prior_leases",
})
_RECOVERED_KEYS = frozenset({"commit_seq", "event_seq", "record_digest"})
_WAL_FOUND_KEYS = frozenset({"size", "digest"})
_CAPACITY_DATA_KEYS = frozenset({
    "code", "limit", "observed", "requested", "refused_source_digest", "action",
})
_ADMISSION_DATA_KEYS = frozenset({
    "arrival_seq", "decision", "dispatch_holds", "source", "source_digest",
})
_DEDUPE_DATA_KEYS = frozenset({
    "rule", "result", "source_group", "dedupe_key", "baseline_before", "baseline_after",
    "superseded", "pending_count_after",
})
_BASELINE_KEYS = frozenset({"admission_id", "complete", "dedupe_key"})
_SUPERSEDED_ENTRY_KEYS = frozenset({"admission_id", "fingerprint"})

_INGRESS_REFUSAL_DATA_KEYS = frozenset({"rule", "summary", "refusal_key", "refusal_seq"})
_REFUSAL_SUMMARY_KEYS = frozenset({
    "alerts", "body_bytes", "body_digest", "code", "members", "members_omitted",
    "refused_group", "resolved", "source_group",
})
_OPERATOR_ACTION_DATA_KEYS = frozenset({
    "action", "rule", "hold", "since_commit_seq", "inspected", "pending_digest",
    "operator", "reason",
})
_INSPECTED_KEYS = frozenset({"commit_seq", "event_seq", "record_digest"})
_RUN_HOLD_IDS_KEYS = frozenset({"job_id", "admission_id"})
_RUN_HOLD_DATA_KEYS = frozenset({
    "rule", "reason", "based_on_commit_seq", "pending_digest",
    "member_count", "member_digest",
})
_RESERVATION_INTENT_IDS_KEYS = frozenset({
    "job_id", "admission_id", "intent_id", "attempt_id", "reservation_id",
    "run_id", "lease_id",
})
_RESERVATION_INTENT_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "intent_digest",
})
_RESERVATION_INTENT_V3_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "intent_digest", "member_count", "member_digest",
})
_RESERVATION_CONFIRMATION_IDS_KEYS = frozenset({"intent_id"})
_RESERVATION_CONFIRMATION_DATA_KEYS = frozenset({
    "rule", "intent_digest", "ledger_uuid", "ledger_generation",
    "ledger_event_id", "sequence", "event_digest",
})
_RUN_INTENT_IDS_KEYS = _RESERVATION_INTENT_IDS_KEYS | {"journal_uuid"}
_RUN_INTENT_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "initial_intent_commit_seq", "intent_digest", "confirmation_event_id",
    "confirmation_commit_seq", "ledger_uuid", "ledger_generation",
    "ledger_event_id", "sequence", "event_digest", "ledger_head",
    "member_count", "member_digest", "services", "work_deadline_seconds",
    "flush_deadline_seconds", "hard_deadline_seconds", "run_intent_digest",
})
_RUN_INTENT_LEDGER_HEAD_KEYS = frozenset({"sequence", "event_digest"})
_RUN_INTENT_SERVICE_KEYS = frozenset({"service", "lease_claim_id", "scope_digest"})
_RUN_INTENT_MANDATORY_SERVICES = frozenset({"anthropic", "jira", "grafana", "kubernetes"})
_RUN_INTENT_ALLOWED_SERVICES = _RUN_INTENT_MANDATORY_SERVICES | {"confluence"}
_LAUNCH_CLAIM_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "run_intent_event_id", "run_intent_digest", "run_intent_commit_seq",
    "receiver_boot_id", "forwarder_generation", "barrier_token_digest",
    "origin_us", "work_deadline_us", "flush_deadline_us",
    "hard_deadline_us", "grants", "launch_claim_digest",
})
_LAUNCH_CLAIM_GRANT_KEYS = frozenset({
    "service", "lease_claim_id", "scope_digest", "grant_id", "grant_expiry_us",
})
_SPAWN_ATTESTATION_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "launch_claim_event_id", "launch_claim_digest", "launch_claim_commit_seq",
    "receiver_boot_id", "observed_us", "blocked_ack_digest", "anchor_key_digest",
    "witness_kind", "verifier_version", "witness_locator", "witness_identity_digest",
    "registry_entry_digest", "spawn_attestation_digest",
})
_RELEASE_INTENT_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "spawn_attestation_event_id", "spawn_attestation_digest",
    "spawn_attestation_commit_seq", "receiver_boot_id", "forwarder_generation",
    "intended_release_us", "activated_grants", "release_intent_digest",
})
_RELEASE_ACTIVATION_KEYS = frozenset({
    "service", "grant_id", "activation_digest", "activation_us",
})
_RELEASE_OBSERVATION_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "release_intent_event_id", "release_intent_digest", "release_intent_commit_seq",
    "receiver_boot_id", "observed_us", "ack_digest", "release_observation_digest",
})
_EFFECT_INTENT_IDS_KEYS = frozenset({
    "journal_uuid", "run_id", "attempt_id", "reservation_id", "operation_id",
})
_EFFECT_INTENT_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "release_observation_event_id", "release_observation_digest",
    "release_observation_commit_seq", "receiver_boot_id",
    "forwarder_generation", "service", "route_id", "grant_id", "scope_digest",
    "flight_id", "forwarder_receipt_id", "request_digest", "target_digest",
    "observed_us", "expires_us", "effect_intent_digest",
})
_EFFECT_RECEIPT_IDS_KEYS = frozenset({"run_id", "attempt_id", "operation_id"})
_EFFECT_RECEIPT_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "effect_intent_event_id", "effect_intent_digest", "effect_intent_commit_seq",
    "receiver_boot_id", "service", "grant_id", "flight_id",
    "forwarder_receipt_id", "claimed_dispatch_state", "claimed_reason",
    "finalized_receipt_digest", "observed_us", "effect_receipt_digest",
})
_SUPERVISION_ACTION_IDS_KEYS = frozenset({
    "journal_uuid", "run_id", "attempt_id", "action_id",
})
_SUPERVISION_ACTION_RESULT_IDS_KEYS = frozenset({
    "run_id", "attempt_id", "action_id",
})
_SUPERVISION_ACTION_INTENT_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "launch_claim_event_id", "launch_claim_digest", "receiver_boot_id",
    "forwarder_generation", "action_kind", "phase", "phase_event_id",
    "phase_digest", "service", "grant_id", "attestation_event_id",
    "attestation_digest", "witness_locator", "witness_identity_digest",
    "prior_revoke_action_ids", "observed_us", "action_intent_digest",
})
_SUPERVISION_ACTION_RESULT_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "action_intent_event_id", "action_intent_digest",
    "action_intent_commit_seq", "receiver_boot_id", "action_kind",
    "claimed_outcome", "observed_us", "action_result_digest",
})
_EXECUTION_IDS_KEYS = frozenset({"journal_uuid", "run_id", "attempt_id"})
_OBSERVATION_BASE_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "launch_claim_event_id", "launch_claim_digest", "receiver_boot_id",
    "observed_us",
})
_PROCESS_OBSERVATION_DATA_KEYS = _OBSERVATION_BASE_KEYS | frozenset({
    "spawn_state", "exit_observed", "exit_code", "exit_signal", "timed_out",
    "cancelled", "containment", "source_digest", "process_observation_digest",
})
_TERMINAL_OBSERVATION_DATA_KEYS = _OBSERVATION_BASE_KEYS | frozenset({
    "process_event_id", "process_digest", "process_commit_seq",
    "count_class", "quality", "invalidity_code", "subtype", "is_error",
    "reason_code", "usage_state", "source_digest", "terminal_observation_digest",
})
_EXECUTION_ASSESSMENT_DATA_KEYS = _OBSERVATION_BASE_KEYS | frozenset({
    "process_event_id", "process_digest", "process_commit_seq",
    "terminal_event_id", "terminal_digest", "terminal_commit_seq",
    "state", "reasons", "usage", "never_started", "execution_assessment_digest",
})
_RECONCILIATION_IDS_KEYS = frozenset({
    "journal_uuid", "run_id", "attempt_id", "operation_id",
})
_RECONCILIATION_DATA_KEYS = frozenset({
    "rule", "based_on_commit_seq", "based_on_record_digest",
    "launch_claim_event_id", "launch_claim_digest",
    "effect_intent_event_id", "effect_intent_digest", "effect_intent_commit_seq",
    "receiver_boot_id", "observed_us", "observation_index", "source_kind",
    "reported_state", "source_evidence_digest", "target_digest",
    "version_digest", "reconciliation_observation_digest",
})
RECONCILIATION_SOURCE_BY_ROUTE = MappingProxyType({
    "jira.issue.create": "jira_issue_readback",
    "jira.issue.update": "jira_issue_readback",
    "jira.transition": "jira_issue_readback",
    "jira.comment.add": "jira_comment_readback",
})
RECONCILIATION_REPORTED_STATES = frozenset({
    "confirmed", "absent", "conflict", "unavailable",
})
TERMINAL_REASON_CODES = frozenset({
    "reported_error", "provider_unavailable", "interrupted", "runtime_error",
    "unknown_error",
})
TERMINAL_INVALIDITY_CODES = frozenset({
    "parse_invalid", "shape_invalid", "field_invalid", "contradictory",
})
_EXECUTION_STATES = frozenset({
    "succeeded", "failed", "cancelled", "containment_failed", "incomplete",
})
_EXECUTION_REASONS = frozenset({
    "containment_failed", "containment_unknown", "timeout", "cancelled",
    "spawn_failed", "spawn_unknown", "exit_missing", "signaled_exit",
    "nonzero_exit", "missing_terminal", "duplicate_terminal", "terminal_invalid",
    "result_error", "usage_malformed",
})
# A closed syntax copy of the current Forwarder receipt state/reason pairs.
# It validates a claim's shape; it does not authenticate its source or facts.
EFFECT_CLAIM_REASONS = MappingProxyType({
    "NOT_DISPATCHED": frozenset({
        "request_rejected", "lease_denied", "route_denied", "permit_denied",
        "deadline", "abandoned",
    }),
    "FAILED": frozenset({"connect_failed", "upstream_tls_failed"}),
    "DISPATCHED_UNKNOWN": frozenset({
        "write_failed", "receive_failed", "malformed_response", "abandoned", "deadline",
    }),
    "PARTIAL": frozenset({"response_incomplete", "response_overflow"}),
    "TRANSPORT_CONFIRMED": frozenset({"ok", "response_policy_rejected"}),
})
SUPERVISION_ACTION_OUTCOMES = MappingProxyType({
    "revoke_grant": frozenset({"acknowledged", "failed", "unknown"}),
    "signal_interrupt": frozenset({"requested", "failed", "unknown"}),
    "signal_kill": frozenset({"requested", "failed", "unknown"}),
})
SUPERVISION_ACTION_PHASES = frozenset({
    "pre_attestation", "blocked_pre_release", "release_unknown",
    "released_observed",
})


# The per-type validators below share a handful of two-line "check shape or
# fail with a fixed code" patterns often enough to earn one-line helpers.
def _require_bound_int(value: object, lo: int, hi: int, field_code: str) -> int:
    if type(value) is not int:
        _fail_record("record_type")
    if not lo <= value <= hi:
        _fail_record(field_code)
    return value


def _require_keys(value: object, keys: frozenset) -> dict:
    if not _exact_keys_ok(value, keys):
        _fail_record("record_field")
    return value


def _require_hex64(value: object) -> str:
    if not _hex64_ok(value):
        _fail_record("record_field")
    return value


def _require_uuid(value: object) -> str:
    if type(value) is not str or not _UUID_PATTERN.fullmatch(value):
        _fail_record("record_field")
    return value


def _require_literal(value: object, literal: str, code: str) -> str:
    if type(value) is not str or value != literal:
        _fail_record(code)
    return value


def _require_enum(value: object, choices: tuple[str, ...]) -> str:
    if not _enum_ok(value, choices):
        _fail_record("record_field")
    return value


def _require_empty_ids(ids: object) -> None:
    _require_keys(ids, _EMPTY_KEYS)


def _require_admission_id(ids: object) -> str:
    ids = _require_keys(ids, _ADMISSION_IDS_KEYS)
    return validate_id(ids["admission_id"])


def _validate_baseline(value: object) -> None:
    value = _require_keys(value, _BASELINE_KEYS)
    validate_id(value["admission_id"])
    if type(value["complete"]) is not bool:
        _fail_record("record_type")
    _require_hex64(value["dedupe_key"])


def _validate_journal_genesis(ids: object, data: object, event_id: str) -> None:
    _require_empty_ids(ids)
    data = _require_keys(data, _GENESIS_DATA_KEYS)
    _require_literal(data["format"], "rj.journal.v1", "record_unsupported")
    journal_uuid = data["journal_uuid"]
    if type(journal_uuid) is not str or not _UUID_PATTERN.fullmatch(journal_uuid):
        _fail_record("record_field")
    bounds = _require_keys(data["bounds"], _BOUNDS_KEYS)
    for key in sorted(_BOUNDS_KEYS):
        _require_bound_int(bounds[key], 1, V1_BOUND_CEILINGS[key], "record_field")
    if bounds["ordinary_bytes"] > bounds["total_bytes"]:
        _fail_record("record_field")


def _validate_restart_recovery(ids: object, data: object, event_id: str) -> None:
    _require_empty_ids(ids)
    data = _require_keys(data, _RESTART_DATA_KEYS)
    validate_id(data["previous_boot_id"])
    recovered = _require_keys(data["recovered"], _RECOVERED_KEYS)
    _require_bound_int(recovered["commit_seq"], 1, MAX_SEQ, "record_field")
    _require_bound_int(recovered["event_seq"], 1, MAX_SEQ, "record_field")
    _require_hex64(recovered["record_digest"])
    _require_bound_int(data["anchor_lag"], 0, 1, "record_field")
    wal_found = data["wal_found"]
    if wal_found is not None:
        wal_found = _require_keys(wal_found, _WAL_FOUND_KEYS)
        _require_bound_int(wal_found["size"], 0, MAX_SEQ, "record_field")
        _require_hex64(wal_found["digest"])
    _require_literal(data["dispatch_hold"], "restart_recovery", "record_field")
    _require_literal(data["prior_leases"], "invalid", "record_field")


def _validate_capacity_hold(ids: object, data: object, event_id: str) -> None:
    _require_empty_ids(ids)
    data = _require_keys(data, _CAPACITY_DATA_KEYS)
    _require_enum(data["code"], CAPACITY_CODES)
    _require_bound_int(data["limit"], 0, MAX_SEQ, "record_field")
    _require_bound_int(data["observed"], 0, MAX_SEQ, "record_field")
    _require_bound_int(data["requested"], 1, MAX_SEQ, "record_field")
    _require_hex64(data["refused_source_digest"])
    _require_literal(data["action"], "set", "record_field")


def _validate_admission(ids: object, data: object, event_id: str) -> None:
    admission_id = _require_admission_id(ids)
    if admission_id != event_id:
        _fail_record("record_field")
    data = _require_keys(data, _ADMISSION_DATA_KEYS)
    _require_bound_int(data["arrival_seq"], 1, MAX_SEQ, "record_field")
    _require_enum(data["decision"], ADMISSION_DECISIONS)
    holds = data["dispatch_holds"]
    if type(holds) is not tuple or len(holds) > _MAX_DISPATCH_HOLDS:
        _fail_record("record_field")
    for code in holds:
        _require_enum(code, DISPATCH_HOLD_CODES)
    if list(holds) != sorted(set(holds)):
        _fail_record("record_field")
    # A SourceError from a malformed embedded source propagates as-is: the
    # sanitized source record owns its own closed vocabulary.
    source_from_json(data["source"])
    _require_hex64(data["source_digest"])


def _validate_dedupe_decision(ids: object, data: object, event_id: str) -> None:
    _require_admission_id(ids)
    data = _require_keys(data, _DEDUPE_DATA_KEYS)
    _require_literal(data["rule"], DEDUPE_RULE, "record_unsupported")
    _require_enum(data["result"], DEDUPE_RESULTS)
    _require_hex64(data["source_group"])
    _require_hex64(data["dedupe_key"])
    baseline_before = data["baseline_before"]
    if baseline_before is not None:
        _validate_baseline(baseline_before)
    _validate_baseline(data["baseline_after"])
    superseded = data["superseded"]
    if type(superseded) is not tuple or len(superseded) > _MAX_SUPERSEDED:
        _fail_record("record_field")
    previous: str | None = None
    for entry in superseded:
        entry = _require_keys(entry, _SUPERSEDED_ENTRY_KEYS)
        validate_id(entry["admission_id"])
        fingerprint = entry["fingerprint"]
        if type(fingerprint) is not str or not _FINGERPRINT_PATTERN.fullmatch(fingerprint):
            _fail_record("record_field")
        if previous is not None and fingerprint <= previous:
            _fail_record("record_field")
        previous = fingerprint
    _require_bound_int(data["pending_count_after"], 0, MAX_SEQ, "record_field")


def _int_in(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _refusal_groups_ok(summary: dict) -> bool:
    """Port of ``journal_ingress._groups_ok`` (A5, A6 pin the parity)."""
    source_group, refused_group = summary["source_group"], summary["refused_group"]
    if not all(v is None or _hex64_ok(v) for v in (source_group, refused_group)):
        return False
    count = (source_group is not None) + (refused_group is not None)
    code = summary["code"]
    if code in _NO_GROUP_CODES:
        return count == 0
    if code == "ingress_group_key_unsupported":
        return source_group is None and refused_group is not None
    if code in _MEMBER_CODES or (code == "ingress_divergence" and summary["alerts"] is not None):
        return source_group is not None and refused_group is None
    if code in ("ingress_shape", "ingress_divergence"):
        return count <= 1
    return count == 1


def _refusal_members_ok(summary: dict) -> bool:
    """Port of ``journal_ingress._members_ok`` (A5, A6 pin the parity)."""
    alerts_count, resolved = summary["alerts"], summary["resolved"]
    members, omitted, code = summary["members"], summary["members_omitted"], summary["code"]
    if alerts_count is None:
        return (
            resolved is None and type(members) is tuple and not members
            and omitted == 0 and code not in _MEMBER_CODES
        )
    if code not in _MEMBER_CODES and code != "ingress_divergence":
        return False
    if not (_int_in(alerts_count, 1, _MAX_JSON_ARRAY_ITEMS) and _int_in(resolved, 0, alerts_count)):
        return False
    # The alert-count check runs before the value and record checks.
    if code == "ingress_too_many_alerts":
        if alerts_count <= _MAX_ALERTS:
            return False
    elif code in (
        "ingress_too_many_values", "ingress_record_too_large", "ingress_divergence",
    ) and alerts_count > _MAX_ALERTS:
        return False
    if type(members) is not tuple or len(members) != min(alerts_count, _MAX_REFUSAL_MEMBERS):
        return False
    if omitted != alerts_count - len(members):
        return False
    for member in members:
        if not (
            type(member) is tuple and len(member) == 2
            and type(member[0]) is str and _FINGERPRINT_PATTERN.fullmatch(member[0])
            and type(member[1]) is str and member[1] in _ALERT_STATUSES
        ):
            return False
    keys = [(member[1] != "resolved", member[0]) for member in members]
    if any(keys[index] >= keys[index + 1] for index in range(len(keys) - 1)):
        return False
    if len({member[0] for member in members}) != len(members):
        return False
    listed_resolved = sum(1 for member in members if member[1] == "resolved")
    return listed_resolved == min(resolved, len(members))


def _check_refusal_summary(value: object) -> None:
    """Strict refusal-summary checker (critic 4): the v1 convention only,
    ``members`` a tuple of 2-tuples. Called at seal and at decode alike.
    """
    if not _exact_keys_ok(value, _REFUSAL_SUMMARY_KEYS):
        _fail_record("record_field")
    code = value["code"]
    if type(code) is not str or code not in INGRESS_REFUSAL_CODES_V1:
        _fail_record("record_field")
    # refusal_to_json's own type gate: the member checks below only compare
    # values, and a bool there would pass them yet change the refusal key.
    if type(value["members_omitted"]) is not int:
        _fail_record("record_field")
    if code == "ingress_too_large":
        body_ok = (
            _int_in(value["body_bytes"], _MAX_INGRESS_BODY_BYTES + 1, MAX_SEQ)
            and value["body_digest"] is None
        )
    else:
        body_ok = (
            _int_in(value["body_bytes"], 0, _MAX_INGRESS_BODY_BYTES)
            and _hex64_ok(value["body_digest"])
        )
    if not body_ok:
        _fail_record("record_field")
    if not _refusal_groups_ok(value):
        _fail_record("record_field")
    if not _refusal_members_ok(value):
        _fail_record("record_field")
    json_code: str | None = None
    try:
        encoded = canonical_json(value, ascii_only=True)
    except JSONPolicyError:
        json_code = "record_field"
    if json_code is not None:
        _fail_record(json_code)
    if len(encoded) > _MAX_REFUSAL_JSON_BYTES:
        _fail_record("record_field")


def refusal_summary_data(summary: object) -> dict:
    """The normalizer (critic 4): accepts ``members`` as a list or tuple of
    lists or tuples (``refusal_to_json``'s own output shape), rebuilds a new
    dict with tuples, checks it strictly, and returns it. Called only by
    ``RecoveryJournal.record_refusal`` before sealing, so the sealed
    ``Record.data`` equals what a normalized, already-tupled summary decodes
    to (J2-OF-7).
    """
    if type(summary) is not dict or summary.keys() != _REFUSAL_SUMMARY_KEYS:
        _fail_record("record_field")
    members = summary["members"]
    if type(members) is not list and type(members) is not tuple:
        _fail_record("record_field")
    normalized_members = []
    for member in members:
        if (type(member) is not list and type(member) is not tuple) or len(member) != 2:
            _fail_record("record_field")
        normalized_members.append((member[0], member[1]))
    normalized = dict(summary, members=tuple(normalized_members))
    _check_refusal_summary(normalized)
    return normalized


def _validate_ingress_refusal(ids: object, data: object, event_id: str) -> None:
    _require_empty_ids(ids)
    if type(data) is not dict or "rule" not in data:
        _fail_record("record_field")
    _require_literal(data["rule"], REFUSAL_RULE, "record_unsupported")
    _require_keys(data, _INGRESS_REFUSAL_DATA_KEYS)
    _check_refusal_summary(data["summary"])
    _require_hex64(data["refusal_key"])
    _require_bound_int(data["refusal_seq"], 1, MAX_REFUSAL_RECORDS, "record_field")


def _validate_operator_action(ids: object, data: object, event_id: str) -> None:
    _require_empty_ids(ids)
    if type(data) is not dict or "rule" not in data:
        _fail_record("record_field")
    _require_literal(data["rule"], RESUME_RULE, "record_unsupported")
    _require_keys(data, _OPERATOR_ACTION_DATA_KEYS)
    _require_enum(data["action"], OPERATOR_ACTIONS)
    _require_enum(data["hold"], RESUMABLE_HOLDS)
    _require_bound_int(data["since_commit_seq"], 2, MAX_SEQ, "record_field")
    inspected = _require_keys(data["inspected"], _INSPECTED_KEYS)
    _require_bound_int(inspected["commit_seq"], 1, MAX_SEQ, "record_field")
    _require_bound_int(inspected["event_seq"], 1, MAX_SEQ, "record_field")
    _require_hex64(inspected["record_digest"])
    _require_hex64(data["pending_digest"])
    # The ID grammar, but as data fields: record_field, not validate_id's record_id.
    for key in ("operator", "reason"):
        if type(data[key]) is not str or not _ID_PATTERN.fullmatch(data[key]):
            _fail_record("record_field")


def _validate_run_hold_v2(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RUN_HOLD_IDS_KEYS)
    validate_id(ids["job_id"])
    validate_id(ids["admission_id"])
    data = _require_keys(data, _RUN_HOLD_DATA_KEYS)
    _require_literal(data["rule"], "run-hold-v2", "record_unsupported")
    _require_enum(data["reason"], RUN_HOLD_REASONS_V2)
    _require_bound_int(data["based_on_commit_seq"], 1, MAX_SEQ, "record_field")
    _require_hex64(data["pending_digest"])
    _require_bound_int(data["member_count"], 1, 32, "record_field")
    _require_hex64(data["member_digest"])


def _validate_reservation_intent_v2(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RESERVATION_INTENT_IDS_KEYS)
    validate_id(ids["job_id"])
    for key in (
        "admission_id", "intent_id", "attempt_id", "reservation_id", "run_id", "lease_id",
    ):
        _require_uuid(ids[key])
    if ids["intent_id"] != event_id or len(set(ids.values())) != len(ids):
        _fail_record("record_field")
    data = _require_keys(data, _RESERVATION_INTENT_DATA_KEYS)
    _require_literal(data["rule"], "reservation-intent-v2", "record_unsupported")
    _require_bound_int(data["based_on_commit_seq"], 1, MAX_SEQ, "record_field")
    _require_hex64(data["intent_digest"])


def _validate_reservation_intent_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RESERVATION_INTENT_IDS_KEYS)
    for key in _RESERVATION_INTENT_IDS_KEYS:
        _require_uuid(ids[key])
    if ids["intent_id"] != event_id or len(set(ids.values())) != len(ids):
        _fail_record("record_field")
    data = _require_keys(data, _RESERVATION_INTENT_V3_DATA_KEYS)
    _require_literal(data["rule"], "reservation-intent-v3", "record_unsupported")
    _require_bound_int(data["based_on_commit_seq"], 1, MAX_SEQ, "record_field")
    _require_bound_int(data["member_count"], 1, 32, "record_field")
    _require_hex64(data["member_digest"])
    _require_hex64(data["intent_digest"])


def _validate_reservation_confirmation_v2(
    ids: object, data: object, event_id: str,
) -> None:
    ids = _require_keys(ids, _RESERVATION_CONFIRMATION_IDS_KEYS)
    _require_uuid(ids["intent_id"])
    _require_uuid(event_id)
    data = _require_keys(data, _RESERVATION_CONFIRMATION_DATA_KEYS)
    _require_literal(data["rule"], "reservation-confirmation-v2", "record_unsupported")
    _require_hex64(data["intent_digest"])
    _require_uuid(data["ledger_uuid"])
    _require_bound_int(data["ledger_generation"], 1, MAX_GENERATION, "record_field")
    _require_uuid(data["ledger_event_id"])
    _require_bound_int(data["sequence"], 1, MAX_SEQ, "record_field")
    _require_hex64(data["event_digest"])
    if len({ids["intent_id"], event_id, data["ledger_uuid"], data["ledger_event_id"]}) != 4:
        _fail_record("record_field")


def _validate_reservation_confirmation_v3(
    ids: object, data: object, event_id: str,
) -> None:
    ids = _require_keys(ids, _RESERVATION_CONFIRMATION_IDS_KEYS)
    _require_uuid(ids["intent_id"])
    _require_uuid(event_id)
    data = _require_keys(data, _RESERVATION_CONFIRMATION_DATA_KEYS)
    _require_literal(data["rule"], "reservation-confirmation-v3", "record_unsupported")
    _require_hex64(data["intent_digest"])
    _require_uuid(data["ledger_uuid"])
    _require_bound_int(data["ledger_generation"], 1, MAX_GENERATION, "record_field")
    _require_uuid(data["ledger_event_id"])
    _require_bound_int(data["sequence"], 1, MAX_SEQ, "record_field")
    _require_hex64(data["event_digest"])
    if len({ids["intent_id"], event_id, data["ledger_uuid"], data["ledger_event_id"]}) != 4:
        _fail_record("record_field")


def _validate_run_intent_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RUN_INTENT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    data = _require_keys(data, _RUN_INTENT_DATA_KEYS)
    _require_literal(data["rule"], "run-intent-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "initial_intent_commit_seq", "confirmation_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "intent_digest", "event_digest",
                "member_digest", "run_intent_digest"):
        _require_hex64(data[key])
    for key in ("confirmation_event_id", "ledger_uuid", "ledger_event_id"):
        _require_uuid(data[key])
    _require_bound_int(data["ledger_generation"], 1, MAX_GENERATION, "record_field")
    _require_bound_int(data["sequence"], 1, MAX_SEQ, "record_field")
    _require_bound_int(data["member_count"], 1, 32, "record_field")
    head = _require_keys(data["ledger_head"], _RUN_INTENT_LEDGER_HEAD_KEYS)
    _require_bound_int(head["sequence"], 1, MAX_SEQ, "record_field")
    _require_hex64(head["event_digest"])
    if head["sequence"] < data["sequence"] or (
        head["sequence"] == data["sequence"] and head["event_digest"] != data["event_digest"]
    ):
        _fail_record("record_field")
    for key, value in (("work_deadline_seconds", 270), ("flush_deadline_seconds", 290),
                       ("hard_deadline_seconds", 300)):
        _require_bound_int(data[key], value, value, "record_field")
    services = data["services"]
    if type(services) not in (list, tuple) or not 4 <= len(services) <= 5:
        _fail_record("record_field")
    names: list[str] = []
    lease_claims: list[str] = []
    for item in services:
        item = _require_keys(item, _RUN_INTENT_SERVICE_KEYS)
        name = item["service"]
        if type(name) is not str or name not in _RUN_INTENT_ALLOWED_SERVICES:
            _fail_record("record_field")
        names.append(name)
        lease_claims.append(_require_uuid(item["lease_claim_id"]))
        _require_hex64(item["scope_digest"])
    if (names != sorted(names) or len(set(names)) != len(names)
        or not _RUN_INTENT_MANDATORY_SERVICES.issubset(names)):
        _fail_record("record_field")
    if services[0]["lease_claim_id"] != ids["lease_id"]:
        _fail_record("record_field")
    identities = (
        *ids.values(), event_id, data["confirmation_event_id"], data["ledger_uuid"],
        data["ledger_event_id"], *lease_claims[1:],
    )
    if len(set(identities)) != len(identities):
        _fail_record("record_field")


def _validate_launch_claim_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RUN_INTENT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    data = _require_keys(data, _LAUNCH_CLAIM_DATA_KEYS)
    _require_literal(data["rule"], "launch-claim-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "run_intent_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "run_intent_digest",
                "barrier_token_digest", "launch_claim_digest"):
        _require_hex64(data[key])
    _require_uuid(data["run_intent_event_id"])
    validate_id(data["receiver_boot_id"])
    validate_id(data["forwarder_generation"])
    origin = _require_bound_int(data["origin_us"], 0, MAX_SEQ - 300_000_000,
                                "record_field")
    for key, offset in (("work_deadline_us", 270_000_000),
                        ("flush_deadline_us", 290_000_000),
                        ("hard_deadline_us", 300_000_000)):
        if _require_bound_int(data[key], 0, MAX_SEQ, "record_field") != origin + offset:
            _fail_record("record_field")
    grants = data["grants"]
    if type(grants) not in (list, tuple) or not 4 <= len(grants) <= 5:
        _fail_record("record_field")
    names: list[str] = []
    grant_ids: list[str] = []
    for item in grants:
        item = _require_keys(item, _LAUNCH_CLAIM_GRANT_KEYS)
        name = item["service"]
        if type(name) is not str or name not in _RUN_INTENT_ALLOWED_SERVICES:
            _fail_record("record_field")
        names.append(name)
        _require_uuid(item["lease_claim_id"])
        _require_hex64(item["scope_digest"])
        grant_ids.append(validate_id(item["grant_id"]))
        expiry = _require_bound_int(item["grant_expiry_us"], 0, MAX_SEQ,
                                    "record_field")
        if not origin < expiry <= origin + 270_000_000:
            _fail_record("record_field")
    if (names != sorted(names) or len(set(names)) != len(names)
        or not _RUN_INTENT_MANDATORY_SERVICES.issubset(names)
        or len(set(grant_ids)) != len(grant_ids)):
        _fail_record("record_field")
    if len({*ids.values(), event_id, data["run_intent_event_id"]}) != len(ids) + 2:
        _fail_record("record_field")


def _validate_spawn_attestation_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RUN_INTENT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    data = _require_keys(data, _SPAWN_ATTESTATION_DATA_KEYS)
    _require_literal(data["rule"], "spawn-attestation-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "launch_claim_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "launch_claim_digest", "blocked_ack_digest",
                "anchor_key_digest", "witness_identity_digest", "registry_entry_digest",
                "spawn_attestation_digest"):
        _require_hex64(data[key])
    _require_uuid(data["launch_claim_event_id"])
    for key in ("receiver_boot_id", "witness_kind", "verifier_version", "witness_locator"):
        validate_id(data[key])
    _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")
    if len({*ids.values(), event_id, data["launch_claim_event_id"]}) != len(ids) + 2:
        _fail_record("record_field")


def _validate_release_intent_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RUN_INTENT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    data = _require_keys(data, _RELEASE_INTENT_DATA_KEYS)
    _require_literal(data["rule"], "release-intent-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "spawn_attestation_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "spawn_attestation_digest",
                "release_intent_digest"):
        _require_hex64(data[key])
    _require_uuid(data["spawn_attestation_event_id"])
    validate_id(data["receiver_boot_id"])
    validate_id(data["forwarder_generation"])
    _require_bound_int(data["intended_release_us"], 0, MAX_SEQ, "record_field")
    grants = data["activated_grants"]
    if type(grants) not in (list, tuple) or not 4 <= len(grants) <= 5:
        _fail_record("record_field")
    names: list[str] = []
    grant_ids: list[str] = []
    for item in grants:
        item = _require_keys(item, _RELEASE_ACTIVATION_KEYS)
        name = item["service"]
        if type(name) is not str or name not in _RUN_INTENT_ALLOWED_SERVICES:
            _fail_record("record_field")
        names.append(name)
        grant_ids.append(validate_id(item["grant_id"]))
        _require_hex64(item["activation_digest"])
        _require_bound_int(item["activation_us"], 0, MAX_SEQ, "record_field")
    if (names != sorted(names) or len(set(names)) != len(names)
        or not _RUN_INTENT_MANDATORY_SERVICES.issubset(names)
        or len(set(grant_ids)) != len(grant_ids)):
        _fail_record("record_field")
    if len({*ids.values(), event_id, data["spawn_attestation_event_id"]}) != len(ids) + 2:
        _fail_record("record_field")


def _validate_release_observation_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _RUN_INTENT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    data = _require_keys(data, _RELEASE_OBSERVATION_DATA_KEYS)
    _require_literal(data["rule"], "release-observation-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "release_intent_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "release_intent_digest", "ack_digest",
                "release_observation_digest"):
        _require_hex64(data[key])
    _require_uuid(data["release_intent_event_id"])
    validate_id(data["receiver_boot_id"])
    _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")
    if len({*ids.values(), event_id, data["release_intent_event_id"]}) != len(ids) + 2:
        _fail_record("record_field")


def _validate_effect_intent_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _EFFECT_INTENT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    data = _require_keys(data, _EFFECT_INTENT_DATA_KEYS)
    _require_literal(data["rule"], "effect-intent-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "release_observation_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "release_observation_digest",
                "scope_digest", "request_digest", "target_digest", "effect_intent_digest"):
        _require_hex64(data[key])
    _require_uuid(data["release_observation_event_id"])
    for key in ("receiver_boot_id", "forwarder_generation", "route_id", "grant_id",
                "flight_id", "forwarder_receipt_id"):
        validate_id(data[key])
    if type(data["service"]) is not str or data["service"] not in _RUN_INTENT_ALLOWED_SERVICES:
        _fail_record("record_field")
    observed = _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")
    expiry = _require_bound_int(data["expires_us"], 0, MAX_SEQ, "record_field")
    if expiry <= observed or len({*ids.values(), event_id,
                                  data["release_observation_event_id"]}) != len(ids) + 2:
        _fail_record("record_field")


def _validate_effect_receipt_v3(ids: object, data: object, event_id: str) -> None:
    ids = _require_keys(ids, _EFFECT_RECEIPT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    data = _require_keys(data, _EFFECT_RECEIPT_DATA_KEYS)
    _require_literal(data["rule"], "effect-receipt-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "effect_intent_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "effect_intent_digest",
                "finalized_receipt_digest", "effect_receipt_digest"):
        _require_hex64(data[key])
    _require_uuid(data["effect_intent_event_id"])
    for key in ("receiver_boot_id", "grant_id", "flight_id", "forwarder_receipt_id"):
        validate_id(data[key])
    if type(data["service"]) is not str or data["service"] not in _RUN_INTENT_ALLOWED_SERVICES:
        _fail_record("record_field")
    state, reason = data["claimed_dispatch_state"], data["claimed_reason"]
    if type(state) is not str or type(reason) is not str or (
        state not in EFFECT_CLAIM_REASONS or reason not in EFFECT_CLAIM_REASONS[state]
    ):
        _fail_record("record_field")
    _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")
    if len({*ids.values(), event_id, data["effect_intent_event_id"]}) != len(ids) + 2:
        _fail_record("record_field")


def _validate_supervision_action_intent_v3(
    ids: object, data: object, event_id: str,
) -> None:
    ids = _require_keys(ids, _SUPERVISION_ACTION_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    if event_id in ids.values():
        _fail_record("record_field")
    data = _require_keys(data, _SUPERVISION_ACTION_INTENT_DATA_KEYS)
    _require_literal(data["rule"], "supervision-action-intent-v3", "record_unsupported")
    _require_bound_int(data["based_on_commit_seq"], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "launch_claim_digest", "phase_digest",
                "action_intent_digest"):
        _require_hex64(data[key])
    for key in ("launch_claim_event_id", "phase_event_id"):
        _require_uuid(data[key])
    for key in ("receiver_boot_id", "forwarder_generation"):
        validate_id(data[key])
    _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")
    kind, phase = data["action_kind"], data["phase"]
    if (type(kind) is not str or kind not in SUPERVISION_ACTION_OUTCOMES
        or type(phase) is not str or phase not in SUPERVISION_ACTION_PHASES):
        _fail_record("record_field")
    prior = data["prior_revoke_action_ids"]
    if type(prior) not in (list, tuple) or len(prior) > 5:
        _fail_record("record_field")
    for action_id in prior:
        _require_uuid(action_id)
    if len(set(prior)) != len(prior):
        _fail_record("record_field")
    attestation_fields = (
        "attestation_event_id", "attestation_digest", "witness_locator",
        "witness_identity_digest",
    )
    if phase == "pre_attestation":
        if any(data[key] is not None for key in attestation_fields):
            _fail_record("record_field")
    else:
        _require_uuid(data["attestation_event_id"])
        for key in ("attestation_digest", "witness_identity_digest"):
            _require_hex64(data[key])
        validate_id(data["witness_locator"])
    if kind == "revoke_grant":
        if (type(data["service"]) is not str
            or data["service"] not in _RUN_INTENT_ALLOWED_SERVICES
            or prior):
            _fail_record("record_field")
        validate_id(data["grant_id"])
    elif (data["service"] is not None or data["grant_id"] is not None
          or phase == "pre_attestation" or not 4 <= len(prior) <= 5):
        _fail_record("record_field")


def _validate_supervision_action_result_v3(
    ids: object, data: object, event_id: str,
) -> None:
    ids = _require_keys(ids, _SUPERVISION_ACTION_RESULT_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    if event_id in ids.values():
        _fail_record("record_field")
    data = _require_keys(data, _SUPERVISION_ACTION_RESULT_DATA_KEYS)
    _require_literal(data["rule"], "supervision-action-result-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "action_intent_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "action_intent_digest",
                "action_result_digest"):
        _require_hex64(data[key])
    _require_uuid(data["action_intent_event_id"])
    validate_id(data["receiver_boot_id"])
    kind, outcome = data["action_kind"], data["claimed_outcome"]
    if (type(kind) is not str or kind not in SUPERVISION_ACTION_OUTCOMES
        or type(outcome) is not str
        or outcome not in SUPERVISION_ACTION_OUTCOMES[kind]):
        _fail_record("record_field")
    _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")


def _validate_execution_base(ids: object, data: object, event_id: str,
                             keys: frozenset[str], rule: str, digest_key: str) -> dict:
    ids = _require_keys(ids, _EXECUTION_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    if event_id in ids.values():
        _fail_record("record_field")
    data = _require_keys(data, keys)
    _require_literal(data["rule"], rule, "record_unsupported")
    _require_bound_int(data["based_on_commit_seq"], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "launch_claim_digest", digest_key):
        _require_hex64(data[key])
    _require_uuid(data["launch_claim_event_id"])
    validate_id(data["receiver_boot_id"])
    _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")
    return data


def _validate_process_observation_v3(ids: object, data: object, event_id: str) -> None:
    data = _validate_execution_base(
        ids, data, event_id, _PROCESS_OBSERVATION_DATA_KEYS,
        "process-observation-v3", "process_observation_digest",
    )
    _require_hex64(data["source_digest"])
    if (type(data["spawn_state"]) is not str
        or data["spawn_state"] not in ("accepted", "failed_before_process", "unknown")
        or type(data["containment"]) is not str
        or data["containment"] not in ("confirmed", "failed", "unknown")
        or any(type(data[key]) is not bool for key in
               ("exit_observed", "timed_out", "cancelled"))):
        _fail_record("record_field")
    code, signal = data["exit_code"], data["exit_signal"]
    if data["exit_observed"]:
        valid_code = type(code) is int and -(2**31) <= code < 2**31 and signal is None
        valid_signal = type(signal) is int and 1 <= signal <= 64 and code is None
        if not (valid_code or valid_signal):
            _fail_record("record_field")
    elif code is not None or signal is not None:
        _fail_record("record_field")
    if (data["spawn_state"] == "failed_before_process"
        and (data["exit_observed"] or data["containment"] == "failed")):
        _fail_record("record_field")


def _validate_terminal_observation_v3(ids: object, data: object, event_id: str) -> None:
    data = _validate_execution_base(
        ids, data, event_id, _TERMINAL_OBSERVATION_DATA_KEYS,
        "terminal-observation-v3", "terminal_observation_digest",
    )
    _require_uuid(data["process_event_id"])
    _require_hex64(data["process_digest"])
    _require_bound_int(data["process_commit_seq"], 1, MAX_SEQ, "record_field")
    count = data["count_class"]
    parsed = ("subtype", "is_error", "reason_code", "usage_state")
    if type(count) is not str or count not in ("none", "one", "multiple"):
        _fail_record("record_field")
    if count == "none":
        if any(data[key] is not None for key in
               ("quality", "invalidity_code", "source_digest", *parsed)):
            _fail_record("record_field")
        return
    _require_hex64(data["source_digest"])
    if count == "multiple":
        if any(data[key] is not None for key in ("quality", "invalidity_code", *parsed)):
            _fail_record("record_field")
        return
    quality = data["quality"]
    if quality == "invalid":
        if (type(data["invalidity_code"]) is not str
            or data["invalidity_code"] not in TERMINAL_INVALIDITY_CODES
            or any(data[key] is not None for key in parsed)):
            _fail_record("record_field")
        return
    if quality != "recognized" or data["invalidity_code"] is not None:
        _fail_record("record_field")
    subtype, is_error, reason = (data[key] for key in
                                  ("subtype", "is_error", "reason_code"))
    if (type(subtype) is not str or subtype not in ("success", "error")
        or type(is_error) is not bool or (subtype == "error") != is_error
        or (reason is not None and
            (type(reason) is not str or reason not in TERMINAL_REASON_CODES))
        or (subtype == "success" and reason is not None)
        or type(data["usage_state"]) is not str
        or data["usage_state"] not in ("known", "absent", "malformed")):
        _fail_record("record_field")


def _validate_execution_assessment_v3(ids: object, data: object, event_id: str) -> None:
    data = _validate_execution_base(
        ids, data, event_id, _EXECUTION_ASSESSMENT_DATA_KEYS,
        "execution-assessment-v3", "execution_assessment_digest",
    )
    for prefix in ("process", "terminal"):
        _require_uuid(data[f"{prefix}_event_id"])
        _require_hex64(data[f"{prefix}_digest"])
        _require_bound_int(data[f"{prefix}_commit_seq"], 1, MAX_SEQ, "record_field")
    reasons = data["reasons"]
    if (type(data["state"]) is not str or data["state"] not in _EXECUTION_STATES
        or type(data["usage"]) is not str or data["usage"] not in ("known", "unknown")
        or type(data["never_started"]) is not bool
        or type(reasons) not in (tuple, list)
        or any(type(reason) is not str or reason not in _EXECUTION_REASONS
               for reason in reasons)):
        _fail_record("record_field")
    if tuple(reasons) != tuple(sorted(set(reasons))):
        _fail_record("record_field")


def _validate_reconciliation_observation_v3(
    ids: object, data: object, event_id: str,
) -> None:
    ids = _require_keys(ids, _RECONCILIATION_IDS_KEYS)
    for value in ids.values():
        _require_uuid(value)
    _require_uuid(event_id)
    if event_id in ids.values():
        _fail_record("record_field")
    data = _require_keys(data, _RECONCILIATION_DATA_KEYS)
    _require_literal(data["rule"], "reconciliation-observation-v3", "record_unsupported")
    for key in ("based_on_commit_seq", "effect_intent_commit_seq"):
        _require_bound_int(data[key], 1, MAX_SEQ, "record_field")
    for key in ("based_on_record_digest", "launch_claim_digest",
                "effect_intent_digest", "source_evidence_digest", "target_digest",
                "reconciliation_observation_digest"):
        _require_hex64(data[key])
    for key in ("launch_claim_event_id", "effect_intent_event_id"):
        _require_uuid(data[key])
    validate_id(data["receiver_boot_id"])
    _require_bound_int(data["observed_us"], 0, MAX_SEQ, "record_field")
    _require_bound_int(data["observation_index"], 1, 4, "record_field")
    if (type(data["source_kind"]) is not str
        or data["source_kind"] not in RECONCILIATION_SOURCE_BY_ROUTE.values()
        or type(data["reported_state"]) is not str
        or data["reported_state"] not in RECONCILIATION_REPORTED_STATES):
        _fail_record("record_field")
    version = data["version_digest"]
    if data["reported_state"] in ("confirmed", "conflict"):
        _require_hex64(version)
    elif version is not None:
        _fail_record("record_field")


_TYPE_VALIDATORS = MappingProxyType({
    ("journal_genesis", 1): _validate_journal_genesis,
    ("restart_recovery", 1): _validate_restart_recovery,
    ("capacity_hold", 1): _validate_capacity_hold,
    ("admission", 1): _validate_admission,
    ("dedupe_decision", 1): _validate_dedupe_decision,
    ("ingress_refusal", 1): _validate_ingress_refusal,
    ("operator_action", 1): _validate_operator_action,
})
_V2_TYPE_VALIDATORS = MappingProxyType({
    ("run_hold", 2): _validate_run_hold_v2,
    ("reservation_intent", 2): _validate_reservation_intent_v2,
    ("reservation_confirmation", 2): _validate_reservation_confirmation_v2,
})
_V3_TYPE_VALIDATORS = MappingProxyType({
    ("reservation_intent", 3): _validate_reservation_intent_v3,
    ("reservation_confirmation", 3): _validate_reservation_confirmation_v3,
    ("run_intent", 3): _validate_run_intent_v3,
    ("launch_claim", 3): _validate_launch_claim_v3,
    ("spawn_attestation", 3): _validate_spawn_attestation_v3,
    ("release_intent", 3): _validate_release_intent_v3,
    ("release_observation", 3): _validate_release_observation_v3,
    ("effect_intent", 3): _validate_effect_intent_v3,
    ("effect_receipt", 3): _validate_effect_receipt_v3,
    ("supervision_action_intent", 3): _validate_supervision_action_intent_v3,
    ("supervision_action_result", 3): _validate_supervision_action_result_v3,
    ("process_observation", 3): _validate_process_observation_v3,
    ("terminal_observation", 3): _validate_terminal_observation_v3,
    ("execution_assessment", 3): _validate_execution_assessment_v3,
    ("reconciliation_observation", 3): _validate_reconciliation_observation_v3,
})
TYPE_ACTORS = MappingProxyType({
    ("journal_genesis", 1): "receiver",
    ("restart_recovery", 1): "receiver",
    ("capacity_hold", 1): "receiver",
    ("admission", 1): "receiver",
    ("dedupe_decision", 1): "receiver",
    ("ingress_refusal", 1): "receiver",
    ("operator_action", 1): "operator",
})
_V2_TYPE_ACTORS = MappingProxyType({
    ("run_hold", 2): "receiver",
    ("reservation_intent", 2): "receiver",
    ("reservation_confirmation", 2): "receiver",
})
_V3_TYPE_ACTORS = MappingProxyType({
    ("reservation_intent", 3): "receiver",
    ("reservation_confirmation", 3): "receiver",
    ("run_intent", 3): "receiver",
    ("launch_claim", 3): "receiver",
    ("spawn_attestation", 3): "receiver",
    ("release_intent", 3): "receiver",
    ("release_observation", 3): "receiver",
    ("effect_intent", 3): "receiver",
    ("effect_receipt", 3): "receiver",
    ("supervision_action_intent", 3): "receiver",
    ("supervision_action_result", 3): "receiver",
    ("process_observation", 3): "receiver",
    ("terminal_observation", 3): "receiver",
    ("execution_assessment", 3): "receiver",
    ("reconciliation_observation", 3): "receiver",
})
SCHEMA_VERSIONS = frozenset(version for _event_type, version in _TYPE_VALIDATORS)


def _validate_envelope(envelope: object) -> None:
    if type(envelope) is not dict or envelope.keys() != _ENVELOPE_KEYS:
        _fail_record("record_field")
    schema_version = envelope["schema_version"]
    if type(schema_version) is not int:
        _fail_record("record_type")
    if schema_version not in SCHEMA_VERSIONS:
        proposed_type = envelope["event_type"]
        if type(proposed_type) is not str or (
            proposed_type, schema_version
        ) not in _V2_TYPE_VALIDATORS and (
            proposed_type, schema_version
        ) not in _V3_TYPE_VALIDATORS:
            _fail_record("record_unsupported")
    _require_bound_int(envelope["journal_generation"], 1, MAX_GENERATION, "record_field")
    event_id = validate_id(envelope["event_id"])
    event_seq = _require_bound_int(envelope["event_seq"], 1, MAX_SEQ, "record_field")
    _require_bound_int(envelope["commit_seq"], 1, MAX_SEQ, "record_field")
    commit_size = _require_bound_int(envelope["commit_size"], 1, MAX_COMMIT_RECORDS, "record_field")
    commit_index = envelope["commit_index"]
    if type(commit_index) is not int:
        _fail_record("record_type")
    if not 0 <= commit_index < commit_size:
        _fail_record("record_field")
    event_type = envelope["event_type"]
    type_key = (event_type, schema_version)
    if type(event_type) is not str or (
        type_key not in _TYPE_VALIDATORS and type_key not in _V2_TYPE_VALIDATORS
        and type_key not in _V3_TYPE_VALIDATORS
    ):
        _fail_record("record_unsupported")
    actor = envelope["actor"]
    if type_key in TYPE_ACTORS:
        expected_actor = TYPE_ACTORS[type_key]
    elif type_key in _V2_TYPE_ACTORS:
        expected_actor = _V2_TYPE_ACTORS[type_key]
    else:
        expected_actor = _V3_TYPE_ACTORS[type_key]
    if type(actor) is not str or actor not in ACTORS or actor != expected_actor:
        _fail_record("record_field")
    validate_id(envelope["boot_id"])
    _require_wall_time(envelope["wall_time"])
    _require_bound_int(envelope["mono_us"], 0, MAX_SEQ, "record_field")
    prev_digest = _require_hex64(envelope["prev_record_digest"])
    if (event_seq == 1) != (prev_digest == ZERO_DIGEST):
        _fail_record("record_field")
    if type_key in _TYPE_VALIDATORS:
        validator = _TYPE_VALIDATORS[type_key]
    elif type_key in _V2_TYPE_VALIDATORS:
        validator = _V2_TYPE_VALIDATORS[type_key]
    else:
        validator = _V3_TYPE_VALIDATORS[type_key]
    validator(envelope["ids"], envelope["data"], event_id)


# --- Encode, digest, decode ----------------------------------------------------


def _record_digest(body: bytes) -> str:
    return hashlib.sha256(RECORD_TAG.encode("ascii") + b"\x00" + body).hexdigest()


def _build_record(
    envelope: dict, position: Position, stamp: Stamp, body: bytes, digest: str,
) -> Record:
    return Record(
        position=position, stamp=stamp, event_id=envelope["event_id"],
        event_type=envelope["event_type"], schema_version=envelope["schema_version"],
        actor=envelope["actor"],
        ids=_freeze(envelope["ids"]), data=_freeze(envelope["data"]),
        body=body, record_digest=digest,
    )


def seal(
    draft: Draft, position: Position, stamp: Stamp, *, schema_version: int = SCHEMA_VERSION,
) -> Record:
    if type(draft) is not Draft or type(position) is not Position or type(stamp) is not Stamp:
        _fail_record("record_argument")
    envelope = {
        "schema_version": schema_version,
        "journal_generation": position.journal_generation,
        "event_id": draft.event_id,
        "event_seq": position.event_seq,
        "commit_seq": position.commit_seq,
        "commit_index": position.commit_index,
        "commit_size": position.commit_size,
        "event_type": draft.event_type,
        "actor": draft.actor,
        "boot_id": stamp.boot_id,
        "wall_time": stamp.wall_time,
        "mono_us": stamp.mono_us,
        "ids": thaw(draft.ids),
        "data": thaw(draft.data),
        "prev_record_digest": position.prev_record_digest,
    }
    _validate_envelope(envelope)
    code: str | None = None
    try:
        body = canonical_json(envelope, ascii_only=True)
    except JSONPolicyError:
        code = "record_field"
    if code is not None:
        _fail_record(code)
    if len(body) > MAX_RECORD_BYTES:
        _fail_record("record_too_large")
    private_cap = {
        ("run_intent", 3): MAX_RUN_INTENT_RECORD_BYTES,
        ("launch_claim", 3): MAX_LAUNCH_CLAIM_RECORD_BYTES,
        ("spawn_attestation", 3): MAX_SPAWN_ATTESTATION_RECORD_BYTES,
        ("release_intent", 3): MAX_RELEASE_INTENT_RECORD_BYTES,
        ("release_observation", 3): MAX_RELEASE_OBSERVATION_RECORD_BYTES,
        ("effect_intent", 3): MAX_EFFECT_INTENT_RECORD_BYTES,
        ("effect_receipt", 3): MAX_EFFECT_RECEIPT_RECORD_BYTES,
        ("supervision_action_intent", 3): MAX_SUPERVISION_ACTION_INTENT_RECORD_BYTES,
        ("supervision_action_result", 3): MAX_SUPERVISION_ACTION_RESULT_RECORD_BYTES,
        ("process_observation", 3): MAX_PROCESS_OBSERVATION_RECORD_BYTES,
        ("terminal_observation", 3): MAX_TERMINAL_OBSERVATION_RECORD_BYTES,
        ("execution_assessment", 3): MAX_EXECUTION_ASSESSMENT_RECORD_BYTES,
        ("reconciliation_observation", 3): MAX_RECONCILIATION_OBSERVATION_RECORD_BYTES,
    }.get((draft.event_type, schema_version), MAX_RUN_HOLD_RECORD_BYTES)
    if schema_version in (2, 3) and len(body) > private_cap:
        _fail_record("record_too_large")
    return _build_record(envelope, position, stamp, body, _record_digest(body))


def verify_body(body: bytes, record_digest: str) -> dict:
    if type(body) is not bytes or type(record_digest) is not str:
        _fail_record("record_argument")
    if _record_digest(body) != record_digest:
        _fail_record("record_digest")
    code: str | None = None
    try:
        parsed = parse_json(body, max_bytes=MAX_RECORD_BYTES, numbers="integer", ascii_only=True)
    except JSONPolicyError as error:
        code = "record_too_large" if error.code == "json_too_large" else "record_json"
    if code is not None:
        _fail_record(code)
    return parsed


def decode_record(envelope: dict, body: bytes, record_digest: str) -> Record:
    if type(body) is not bytes or type(record_digest) is not str:
        _fail_record("record_argument")
    if type(envelope) is not dict:
        _fail_record("record_field")
    code: str | None = None
    try:
        canonical_body = canonical_json(envelope, ascii_only=True)
    except JSONPolicyError:
        code = "record_field"
    if code is not None:
        _fail_record(code)
    if canonical_body != body:
        _fail_record("record_not_canonical")
    _validate_envelope(envelope)
    private_cap = {
        ("run_intent", 3): MAX_RUN_INTENT_RECORD_BYTES,
        ("launch_claim", 3): MAX_LAUNCH_CLAIM_RECORD_BYTES,
        ("spawn_attestation", 3): MAX_SPAWN_ATTESTATION_RECORD_BYTES,
        ("release_intent", 3): MAX_RELEASE_INTENT_RECORD_BYTES,
        ("release_observation", 3): MAX_RELEASE_OBSERVATION_RECORD_BYTES,
        ("effect_intent", 3): MAX_EFFECT_INTENT_RECORD_BYTES,
        ("effect_receipt", 3): MAX_EFFECT_RECEIPT_RECORD_BYTES,
        ("supervision_action_intent", 3): MAX_SUPERVISION_ACTION_INTENT_RECORD_BYTES,
        ("supervision_action_result", 3): MAX_SUPERVISION_ACTION_RESULT_RECORD_BYTES,
        ("process_observation", 3): MAX_PROCESS_OBSERVATION_RECORD_BYTES,
        ("terminal_observation", 3): MAX_TERMINAL_OBSERVATION_RECORD_BYTES,
        ("execution_assessment", 3): MAX_EXECUTION_ASSESSMENT_RECORD_BYTES,
        ("reconciliation_observation", 3): MAX_RECONCILIATION_OBSERVATION_RECORD_BYTES,
    }.get((envelope["event_type"], envelope["schema_version"]),
          MAX_RUN_HOLD_RECORD_BYTES)
    if envelope["schema_version"] in (2, 3) and len(body) > private_cap:
        _fail_record("record_too_large")
    position = Position(
        journal_generation=envelope["journal_generation"],
        event_seq=envelope["event_seq"],
        commit_seq=envelope["commit_seq"],
        commit_index=envelope["commit_index"],
        commit_size=envelope["commit_size"],
        prev_record_digest=envelope["prev_record_digest"],
    )
    stamp = Stamp(
        boot_id=envelope["boot_id"], wall_time=envelope["wall_time"], mono_us=envelope["mono_us"],
    )
    return _build_record(envelope, position, stamp, body, record_digest)


def open_record(body: bytes) -> Record:
    if type(body) is not bytes:
        _fail_record("record_argument")
    digest = _record_digest(body)
    envelope = verify_body(body, digest)
    return decode_record(envelope, body, digest)


def content_digest(record: Record) -> str:
    if type(record) is not Record:
        _fail_record("record_argument")
    payload = {
        "schema_version": record.schema_version,
        "journal_generation": record.position.journal_generation,
        "event_id": record.event_id,
        "event_type": record.event_type,
        "actor": record.actor,
        "ids": thaw(record.ids),
        "data": thaw(record.data),
    }
    return tagged_digest(CONTENT_TAG, payload)


__all__ = [
    "ACTORS",
    "ADMISSION_DECISIONS",
    "CAPACITY_CODES",
    "CONTENT_TAG",
    "DEDUPE_RESULTS",
    "DEDUPE_RULE",
    "DISPATCH_HOLD_CODES",
    "EFFECT_CLAIM_REASONS",
    "EFFECT_EVENT_TYPES_V3",
    "EFFECT_RECORD_CLASS_V3",
    "EVENT_TYPES",
    "EXECUTION_EVENT_TYPES_V3",
    "EXECUTION_RECORD_CLASS_V3",
    "FRONT_DOOR_EVENT_TYPES",
    "IDENTITY_KEYS",
    "INGRESS_REFUSAL_CODES_V1",
    "MAX_COMMIT_RECORDS",
    "MAX_EFFECT_INTENT_RECORD_BYTES",
    "MAX_EFFECT_RECEIPT_RECORD_BYTES",
    "MAX_EXECUTION_ASSESSMENT_RECORD_BYTES",
    "MAX_GENERATION",
    "MAX_ID_BYTES",
    "MAX_LAUNCH_CLAIM_RECORD_BYTES",
    "MAX_PROCESS_OBSERVATION_RECORD_BYTES",
    "MAX_RECONCILIATION_OBSERVATION_RECORD_BYTES",
    "MAX_RECORD_BYTES",
    "MAX_REFUSAL_RECORDS",
    "MAX_RELEASE_INTENT_RECORD_BYTES",
    "MAX_RELEASE_OBSERVATION_RECORD_BYTES",
    "MAX_RUN_HOLD_RECORD_BYTES",
    "MAX_RUN_INTENT_RECORD_BYTES",
    "MAX_SEQ",
    "MAX_SPAWN_ATTESTATION_RECORD_BYTES",
    "MAX_SUPERVISION_ACTION_INTENT_RECORD_BYTES",
    "MAX_SUPERVISION_ACTION_RESULT_RECORD_BYTES",
    "MAX_TERMINAL_OBSERVATION_RECORD_BYTES",
    "OPERATOR_ACTIONS",
    "RECONCILIATION_EVENT_TYPES_V3",
    "RECONCILIATION_RECORD_CLASS_V3",
    "RECONCILIATION_REPORTED_STATES",
    "RECONCILIATION_SOURCE_BY_ROUTE",
    "RECORD_CLASS",
    "RECORD_ERROR_CODES",
    "RECORD_TAG",
    "REFUSAL_RESOLVED_RESERVE",
    "REFUSAL_RULE",
    "REGISTERED_EVENT_TYPES",
    "RESERVATION_RECORD_CLASS_V2",
    "RESERVATION_RECORD_CLASS_V3",
    "RESUMABLE_HOLDS",
    "RESUME_RULE",
    "RUN_EVENT_TYPES_V2",
    "RUN_EVENT_TYPES_V3",
    "RUN_HOLD_REASONS_V2",
    "RUN_RECORD_CLASS_V2",
    "RUN_RECORD_CLASS_V3",
    "SCHEMA_VERSION",
    "SCHEMA_VERSIONS",
    "SPAWN_EVENT_TYPES_V3",
    "SPAWN_RECORD_CLASS_V3",
    "SUPERVISION_ACTION_EVENT_TYPES_V3",
    "SUPERVISION_ACTION_OUTCOMES",
    "SUPERVISION_ACTION_PHASES",
    "SUPERVISION_ACTION_RECORD_CLASS_V3",
    "TERMINAL_INVALIDITY_CODES",
    "TERMINAL_REASON_CODES",
    "TYPE_ACTORS",
    "V1_BOUND_CEILINGS",
    "ZERO_DIGEST",
    "Draft",
    "Head",
    "Position",
    "Record",
    "RecordError",
    "Stamp",
    "WalFound",
    "content_digest",
    "decode_record",
    "format_wall_time",
    "open_record",
    "refusal_summary_data",
    "seal",
    "thaw",
    "validate_id",
    "verify_body",
]
