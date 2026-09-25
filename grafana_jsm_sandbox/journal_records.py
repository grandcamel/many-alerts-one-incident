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


_TYPE_VALIDATORS = MappingProxyType({
    ("journal_genesis", 1): _validate_journal_genesis,
    ("restart_recovery", 1): _validate_restart_recovery,
    ("capacity_hold", 1): _validate_capacity_hold,
    ("admission", 1): _validate_admission,
    ("dedupe_decision", 1): _validate_dedupe_decision,
    ("ingress_refusal", 1): _validate_ingress_refusal,
    ("operator_action", 1): _validate_operator_action,
})
_V2_TYPE_VALIDATORS = MappingProxyType({("run_hold", 2): _validate_run_hold_v2})
TYPE_ACTORS = MappingProxyType({
    ("journal_genesis", 1): "receiver",
    ("restart_recovery", 1): "receiver",
    ("capacity_hold", 1): "receiver",
    ("admission", 1): "receiver",
    ("dedupe_decision", 1): "receiver",
    ("ingress_refusal", 1): "receiver",
    ("operator_action", 1): "operator",
})
_V2_TYPE_ACTORS = MappingProxyType({("run_hold", 2): "receiver"})
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
        ) not in _V2_TYPE_VALIDATORS:
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
    ):
        _fail_record("record_unsupported")
    actor = envelope["actor"]
    expected_actor = (
        TYPE_ACTORS[type_key] if type_key in TYPE_ACTORS else _V2_TYPE_ACTORS[type_key]
    )
    if type(actor) is not str or actor not in ACTORS or actor != expected_actor:
        _fail_record("record_field")
    validate_id(envelope["boot_id"])
    _require_wall_time(envelope["wall_time"])
    _require_bound_int(envelope["mono_us"], 0, MAX_SEQ, "record_field")
    prev_digest = _require_hex64(envelope["prev_record_digest"])
    if (event_seq == 1) != (prev_digest == ZERO_DIGEST):
        _fail_record("record_field")
    validator = (
        _TYPE_VALIDATORS[type_key] if type_key in _TYPE_VALIDATORS
        else _V2_TYPE_VALIDATORS[type_key]
    )
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
    if schema_version == 2 and len(body) > MAX_RUN_HOLD_RECORD_BYTES:
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
    if envelope["schema_version"] == 2 and len(body) > MAX_RUN_HOLD_RECORD_BYTES:
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
    "EVENT_TYPES",
    "FRONT_DOOR_EVENT_TYPES",
    "IDENTITY_KEYS",
    "INGRESS_REFUSAL_CODES_V1",
    "MAX_COMMIT_RECORDS",
    "MAX_GENERATION",
    "MAX_ID_BYTES",
    "MAX_RECORD_BYTES",
    "MAX_REFUSAL_RECORDS",
    "MAX_RUN_HOLD_RECORD_BYTES",
    "MAX_SEQ",
    "OPERATOR_ACTIONS",
    "RECORD_CLASS",
    "RECORD_ERROR_CODES",
    "RECORD_TAG",
    "REFUSAL_RESOLVED_RESERVE",
    "REFUSAL_RULE",
    "REGISTERED_EVENT_TYPES",
    "RESUMABLE_HOLDS",
    "RESUME_RULE",
    "RUN_EVENT_TYPES_V2",
    "RUN_HOLD_REASONS_V2",
    "RUN_RECORD_CLASS_V2",
    "SCHEMA_VERSION",
    "SCHEMA_VERSIONS",
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
