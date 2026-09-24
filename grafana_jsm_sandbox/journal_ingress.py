"""One raw Grafana Notification HTTP body to a sanitized `SourceRecord`
(ticket 37, unit 16). Refuses whatever the committed record cannot hold.

Pure: no clock, randomness, filesystem, environment, network, logging or
global state. Runs on Python 3.11, because it never touches SQLite. Error
discipline matches `forwarder_json` and `journal_source`: every `except`
body only assigns a local `code` variable, and a fresh error is raised
after the `try` statement with `from None`. Refusals are return values,
never exceptions: no caller-supplied byte, key or value crosses into an
exception, a `repr`, or the refusal summary except through the closed
grammars this module and `journal_source` already enforce.

Validation runs in two phases. Phase 1 is every 400-class check, over the
whole body and every member. Phase 2 is the 422-class checks, in a fixed order,
for a body Grafana's Go encoder could send but the v1 record cannot hold; every
phase-2 refusal names its members. Parser-level refusals come first: a
`json_*` cause that Go can emit (a NUL, a large number, a long array) is 422
even when the rest of the body would have failed phase 1.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import re
from types import MappingProxyType

from .forwarder_json import (
    MAX_JSON_ARRAY_ITEMS,
    MAX_SAFE_INTEGER,
    JSONDecimal,
    JSONPolicyError,
    canonical_json,
    parse_json,
)
from .journal_source import (
    ALERT_STATUSES,
    BODY_TAG,
    HTTP_PROVENANCE,
    MAX_ALERTS,
    MAX_FINGERPRINT_BYTES,
    MAX_REF_ID_BYTES,
    MAX_STARTS_AT_BYTES,
    MAX_TRUNCATED_ALERTS,
    MAX_VALUES,
    SourceAlert,
    SourceError,
    SourceRecord,
    canonical_number,
    source_group_digest,
    validate_source,
)

MAX_INGRESS_BODY_BYTES = 262_144
MAX_INGRESS_STRING_BYTES = MAX_INGRESS_BODY_BYTES  # passed to parse_json
MAX_REFUSAL_MEMBERS = MAX_ALERTS
MAX_REFUSAL_JSON_BYTES = 4_096
GO_ZERO_TIME = "0001-01-01T00:00:00Z"
REFUSED_GROUP_TAG = "rj.refused-group.v1"

# Proposed response classes for the later HTTP seam (Deferred 1); never
# persisted, and never a property of a stored refusal.
INGRESS_HTTP_STATUS = MappingProxyType({
    "ingress_too_large": 413,
    "ingress_json_invalid": 400,
    "ingress_shape": 400,
    "ingress_group_key": 400,
    "ingress_truncated": 400,
    "ingress_fingerprint": 400,
    "ingress_status": 400,
    "ingress_values": 400,
    "ingress_duplicate_fingerprint": 400,
    "ingress_json_unsupported": 422,
    "ingress_group_key_unsupported": 422,
    "ingress_ref_id_unsupported": 422,
    "ingress_too_many_alerts": 422,
    "ingress_too_many_values": 422,
    "ingress_record_too_large": 422,
    "ingress_divergence": 500,
})
INGRESS_REFUSAL_CODES = frozenset(INGRESS_HTTP_STATUS)
INGRESS_ERROR_CODES = frozenset({"ingress_argument"})

# Decided before or at the groupKey check: neither group digest is set yet.
_NO_GROUP_CODES = frozenset({
    "ingress_too_large", "ingress_json_invalid", "ingress_json_unsupported", "ingress_group_key",
})
# Phase-2 refusals: Grafana could send the body, and every member passed
# phase 1, so each of these always carries alerts/resolved/members/omitted.
MEMBER_CODES = frozenset({
    "ingress_group_key_unsupported", "ingress_ref_id_unsupported", "ingress_too_many_alerts",
    "ingress_too_many_values", "ingress_record_too_large",
})

# Total over forwarder_json.JSON_ERROR_CODES (test I8 pins this).
JSON_REFUSAL_CODES = MappingProxyType({
    "json_argument": "ingress_divergence",
    "json_too_large": "ingress_divergence",
    "json_type": "ingress_divergence",
    "json_string_too_long": "ingress_divergence",
    "json_encoding": "ingress_json_invalid",
    "json_syntax": "ingress_json_invalid",
    "json_depth": "ingress_json_invalid",
    "json_duplicate_key": "ingress_json_invalid",
    "json_unicode": "ingress_json_unsupported",
    "json_number": "ingress_json_unsupported",
    "json_array_too_long": "ingress_json_unsupported",
})

# Rebuilt from journal_source's public MAX_* constants: its own patterns are
# private. Test I7 pins parity with validate_source.
_FINGERPRINT_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{MAX_FINGERPRINT_BYTES}}}")
_REF_ID_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{MAX_REF_ID_BYTES}}}")
# [0-9], not \d: \d also matches non-ASCII digits. Grouped for calendar
# validation below; journal_source's grammar is the same shape ungrouped.
_STARTS_AT_PATTERN = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]{1,9})?Z"
)
_HEX = frozenset("0123456789abcdef")


class IngressError(ValueError):
    """A caller-bug error: a non-`bytes` body, or a forged refusal."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail_ingress(code: str) -> None:
    raise IngressError(code) from None


@dataclasses.dataclass(frozen=True)
class IngressRefusal:
    code: str
    body_bytes: int
    body_digest: str | None
    source_group: str | None
    refused_group: str | None
    alerts: int | None
    resolved: int | None
    members: tuple[tuple[str, str], ...]
    members_omitted: int


@dataclasses.dataclass(frozen=True)
class IngressOutcome:
    source: SourceRecord | None
    refusal: IngressRefusal | None
    starts_at_dropped: tuple[str, ...]


def body_digest(body: bytes) -> str:
    if type(body) is not bytes:
        _fail_ingress("ingress_argument")
    return hashlib.sha256(BODY_TAG.encode("ascii") + b"\x00" + body).hexdigest()


# --- Refusal construction -----------------------------------------------------


def _member_key(member: tuple[str, str]) -> tuple[bool, str]:
    return (member[1] != "resolved", member[0])  # Resolved first, then Fingerprint


def _refusal(
    code: str,
    size: int,
    digest: str | None = None,
    group: str | None = None,
    refused: str | None = None,
    members: list[tuple[str, str]] | None = None,
) -> IngressRefusal:
    count = resolved = None
    listed: tuple[tuple[str, str], ...] = ()
    omitted = 0
    if members is not None:
        ordered = sorted(members, key=_member_key)
        count = len(ordered)
        resolved = sum(1 for member in ordered if member[1] == "resolved")
        listed = tuple(ordered[:MAX_REFUSAL_MEMBERS])
        omitted = count - len(listed)
    return IngressRefusal(
        code=code, body_bytes=size, body_digest=digest, source_group=group,
        refused_group=refused, alerts=count, resolved=resolved, members=listed,
        members_omitted=omitted,
    )


def _refuse(
    code: str,
    size: int,
    digest: str | None = None,
    group: str | None = None,
    refused: str | None = None,
    members: list[tuple[str, str]] | None = None,
) -> IngressOutcome:
    refusal = _refusal(code, size, digest, group, refused, members)
    return IngressOutcome(source=None, refusal=refusal, starts_at_dropped=())


def oversize_refusal(declared_length: int) -> IngressRefusal:
    if (
        type(declared_length) is not int
        or not MAX_INGRESS_BODY_BYTES < declared_length <= MAX_SAFE_INTEGER
    ):
        _fail_ingress("ingress_argument")
    return _refusal("ingress_too_large", declared_length)


# --- startsAt (provenance only; D5) -------------------------------------------


def _starts_at(value: object) -> tuple[str | None, bool]:
    """(stored starts_at, dropped?). Never refuses the Notification."""
    if value is None or value == GO_ZERO_TIME:
        return None, False
    if type(value) is not str or len(value) > MAX_STARTS_AT_BYTES:
        return None, True
    match = _STARTS_AT_PATTERN.fullmatch(value)
    if match is None:
        return None, True
    valid = True
    try:
        datetime.datetime(*(int(part) for part in match.groups()), tzinfo=datetime.UTC)
    except ValueError:
        valid = False
    return (value, False) if valid else (None, True)


# --- Per-member checks ---------------------------------------------------------


def _member_code(value: object) -> str | None:
    """Phase-1 (400-class) checks for one element of `alerts`."""
    if type(value) is not dict:
        return "ingress_shape"
    fingerprint = value.get("fingerprint")
    if type(fingerprint) is not str or not _FINGERPRINT_PATTERN.fullmatch(fingerprint):
        return "ingress_fingerprint"
    status = value.get("status")
    if type(status) is not str or status not in ALERT_STATUSES:
        return "ingress_status"
    values = value.get("values")
    if values is not None and type(values) is not dict:
        return "ingress_values"
    for number in (values or {}).values():
        if number is not None and type(number) is not int and type(number) is not JSONDecimal:
            return "ingress_values"
    return None


def _build_alert(raw: dict) -> tuple[str | None, SourceAlert | None, bool]:
    """Phase-2 build for one member: (divergence code, alert, startsAt dropped)."""
    raw_values = raw.get("values")
    values = None
    if raw_values is not None:
        items: list[tuple[str, str | None]] = []
        for ref_id in sorted(raw_values):
            number = raw_values[ref_id]
            text: str | None = None
            if number is not None:
                code: str | None = None
                try:
                    text = canonical_number(number)
                except (SourceError, JSONPolicyError):
                    code = "ingress_divergence"
                if code is not None:
                    return code, None, False
            items.append((ref_id, text))
        values = tuple(items)
    starts_at, dropped = _starts_at(raw.get("startsAt"))
    alert = SourceAlert(
        fingerprint=raw["fingerprint"], status=raw["status"], values=values, starts_at=starts_at,
    )
    return None, alert, dropped


# --- The sanitizer -------------------------------------------------------------


def sanitize_notification(body: bytes) -> IngressOutcome:
    if type(body) is not bytes:
        _fail_ingress("ingress_argument")
    size = len(body)
    if size > MAX_INGRESS_BODY_BYTES:
        return IngressOutcome(source=None, refusal=oversize_refusal(size), starts_at_dropped=())
    digest = body_digest(body)
    code: str | None = None
    try:
        root = parse_json(
            body, max_bytes=MAX_INGRESS_BODY_BYTES, numbers="finite",
            max_string_bytes=MAX_INGRESS_STRING_BYTES,
        )
    except JSONPolicyError as error:
        code = JSON_REFUSAL_CODES.get(error.code, "ingress_divergence")
    if code is not None:
        return _refuse(code, size, digest)

    # --- Phase 1: every 400-class check, over the whole body and every member
    if type(root) is not dict:
        return _refuse("ingress_shape", size, digest)
    group_key = root.get("groupKey")
    if type(group_key) is not str or not group_key:
        return _refuse("ingress_group_key", size, digest)
    group: str | None = None
    refused: str | None = None
    code = None
    try:
        group = source_group_digest(group_key)
    except SourceError:
        code = "unsupported"
    except JSONPolicyError:
        code = "ingress_divergence"
    if code == "ingress_divergence":
        return _refuse(code, size, digest)
    if group is None:
        refused = hashlib.sha256(
            REFUSED_GROUP_TAG.encode("ascii") + b"\x00" + group_key.encode("utf-8")
        ).hexdigest()
    truncated = root.get("truncatedAlerts")
    if truncated is not None and (
        type(truncated) is not int or not 0 <= truncated <= MAX_TRUNCATED_ALERTS
    ):
        return _refuse("ingress_truncated", size, digest, group, refused)
    raw_alerts = root.get("alerts")
    if type(raw_alerts) is not tuple or not raw_alerts:
        return _refuse("ingress_shape", size, digest, group, refused)
    for raw in raw_alerts:
        code = _member_code(raw)
        if code is not None:
            return _refuse(code, size, digest, group, refused)
    members = [(raw["fingerprint"], raw["status"]) for raw in raw_alerts]
    fingerprints = [member[0] for member in members]
    if len(set(fingerprints)) != len(fingerprints):
        return _refuse("ingress_duplicate_fingerprint", size, digest, group, refused)

    # --- Phase 2: 422-class checks; every refusal names its members ----------
    if group is None:
        return _refuse("ingress_group_key_unsupported", size, digest, None, refused, members)
    for raw in raw_alerts:
        if any(not _REF_ID_PATTERN.fullmatch(ref_id) for ref_id in raw.get("values") or {}):
            return _refuse("ingress_ref_id_unsupported", size, digest, group, None, members)
    if len(members) > MAX_ALERTS:
        return _refuse("ingress_too_many_alerts", size, digest, group, None, members)
    if sum(len(raw.get("values") or {}) for raw in raw_alerts) > MAX_VALUES:
        return _refuse("ingress_too_many_values", size, digest, group, None, members)
    alerts: list[SourceAlert] = []
    dropped: list[str] = []
    for raw in raw_alerts:
        code, alert, was_dropped = _build_alert(raw)
        if code is not None:
            return _refuse(code, size, digest, group, None, members)
        alerts.append(alert)
        if was_dropped:
            dropped.append(alert.fingerprint)
    alerts.sort(key=lambda alert: alert.fingerprint)
    record = SourceRecord(
        source_group=group, alerts=tuple(alerts), truncated_alerts=truncated,
        body_digest=digest, provenance=HTTP_PROVENANCE,
    )
    code = None
    try:
        validate_source(record)
    except SourceError as error:
        code = (
            "ingress_record_too_large" if error.code == "source_too_large" else "ingress_divergence"
        )
    except JSONPolicyError:
        code = "ingress_divergence"
    if code is not None:
        return _refuse(code, size, digest, group, None, members)
    return IngressOutcome(source=record, refusal=None, starts_at_dropped=tuple(sorted(dropped)))


# --- The refusal summary --------------------------------------------------------


def _hex64_ok(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in _HEX for c in value)


def _int_in(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _groups_ok(refusal: IngressRefusal) -> bool:
    if not all(v is None or _hex64_ok(v) for v in (refusal.source_group, refusal.refused_group)):
        return False
    count = (refusal.source_group is not None) + (refusal.refused_group is not None)
    if refusal.code in _NO_GROUP_CODES:
        return count == 0
    if refusal.code == "ingress_group_key_unsupported":
        return refusal.source_group is None and refusal.refused_group is not None
    # Every later member code runs after the group key was accepted.
    if refusal.code in MEMBER_CODES or (
        refusal.code == "ingress_divergence" and refusal.alerts is not None
    ):
        return refusal.source_group is not None and refusal.refused_group is None
    if refusal.code in ("ingress_shape", "ingress_divergence"):
        return count <= 1
    return count == 1


def _members_ok(refusal: IngressRefusal) -> bool:
    if refusal.alerts is None:
        return (
            refusal.resolved is None and type(refusal.members) is tuple and not refusal.members
            and refusal.members_omitted == 0
            and refusal.code not in MEMBER_CODES
        )
    if refusal.code not in MEMBER_CODES and refusal.code != "ingress_divergence":
        return False
    if not (
        _int_in(refusal.alerts, 1, MAX_JSON_ARRAY_ITEMS)
        and _int_in(refusal.resolved, 0, refusal.alerts)
    ):
        return False
    # The alert-count check runs before the value and record checks.
    if refusal.code == "ingress_too_many_alerts":
        if refusal.alerts <= MAX_ALERTS:
            return False
    elif refusal.code in (
        "ingress_too_many_values", "ingress_record_too_large", "ingress_divergence",
    ) and refusal.alerts > MAX_ALERTS:
        return False
    members = refusal.members
    if type(members) is not tuple or len(members) != min(refusal.alerts, MAX_REFUSAL_MEMBERS):
        return False
    if refusal.members_omitted != refusal.alerts - len(members):
        return False
    for member in members:
        if not (
            type(member) is tuple and len(member) == 2
            and type(member[0]) is str and _FINGERPRINT_PATTERN.fullmatch(member[0])
            and type(member[1]) is str and member[1] in ALERT_STATUSES
        ):
            return False
    keys = [_member_key(member) for member in members]
    if any(keys[index] >= keys[index + 1] for index in range(len(keys) - 1)):
        return False
    if len({member[0] for member in members}) != len(members):
        return False
    listed_resolved = sum(1 for member in members if member[1] == "resolved")
    return listed_resolved == min(refusal.resolved, len(members))


def refusal_to_json(refusal: IngressRefusal) -> dict[str, object]:
    ok = (
        type(refusal) is IngressRefusal
        and type(refusal.code) is str and refusal.code in INGRESS_REFUSAL_CODES
        and type(refusal.members_omitted) is int
    )
    if ok:
        oversize = refusal.code == "ingress_too_large"
        ok = (
            (_int_in(refusal.body_bytes, MAX_INGRESS_BODY_BYTES + 1, MAX_SAFE_INTEGER) if oversize
             else _int_in(refusal.body_bytes, 0, MAX_INGRESS_BODY_BYTES))
            and (refusal.body_digest is None if oversize else _hex64_ok(refusal.body_digest))
            and _groups_ok(refusal)
            and _members_ok(refusal)
        )
    if not ok:
        _fail_ingress("ingress_argument")
    summary = {
        "alerts": refusal.alerts,
        "body_bytes": refusal.body_bytes,
        "body_digest": refusal.body_digest,
        "code": refusal.code,
        "members": [list(member) for member in refusal.members],
        "members_omitted": refusal.members_omitted,
        "refused_group": refusal.refused_group,
        "resolved": refusal.resolved,
        "source_group": refusal.source_group,
    }
    code = None
    try:
        encoded = canonical_json(summary, ascii_only=True)
    except JSONPolicyError:
        code = "ingress_argument"
    if code is None and len(encoded) > MAX_REFUSAL_JSON_BYTES:
        code = "ingress_argument"
    if code is not None:
        _fail_ingress(code)
    return summary


__all__ = [
    "GO_ZERO_TIME",
    "INGRESS_ERROR_CODES",
    "INGRESS_HTTP_STATUS",
    "INGRESS_REFUSAL_CODES",
    "JSON_REFUSAL_CODES",
    "MAX_INGRESS_BODY_BYTES",
    "MAX_INGRESS_STRING_BYTES",
    "MAX_REFUSAL_JSON_BYTES",
    "MAX_REFUSAL_MEMBERS",
    "MEMBER_CODES",
    "REFUSED_GROUP_TAG",
    "IngressError",
    "IngressOutcome",
    "IngressRefusal",
    "body_digest",
    "oversize_refusal",
    "refusal_to_json",
    "sanitize_notification",
]
