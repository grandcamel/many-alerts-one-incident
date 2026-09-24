"""The bounded sanitized source record and canonical numbers (ticket 37, unit
15, module 1; split out of ``journal_records`` past its ~520-line trigger,
same owner and API).

Pure: no clock, randomness, filesystem or state. Every validation failure
raises ``SourceError`` with a fixed code; nothing echoes caller or stored
content in an error, a ``repr`` or a chained exception. Error discipline
matches ``forwarder_json``: every ``except`` body only assigns a local
``code`` variable, and a fresh error is raised after the ``try`` statement
with ``from None``.
"""

from __future__ import annotations

import dataclasses
import math
import re

from .forwarder_json import (
    MAX_JSON_NUMBER_CHARS,
    MAX_SAFE_INTEGER,
    JSONDecimal,
    canonical_json,
    tagged_digest,
)

ALERT_STATUSES = ("firing", "resolved")
PROVENANCE_KINDS = ("http",)

MAX_ALERTS = 32
MAX_VALUES = 64
MAX_SOURCE_RECORD_BYTES = 4_096
MAX_FINGERPRINT_BYTES = 64
MAX_REF_ID_BYTES = 32
MAX_GROUP_KEY_BYTES = 1_024
MAX_STARTS_AT_BYTES = 30
MAX_TRUNCATED_ALERTS = 2**31 - 1

SOURCE_TAG = "rj.source.v1"
SOURCE_GROUP_TAG = "rj.source-group.v1"
DEDUPE_KEY_TAG = "rj.dedupe-key.v1"
# Computed by the (deferred) ingress unit; documented here, never by this module.
BODY_TAG = "rj.body.v1"

SOURCE_ERROR_CODES = frozenset({
    "source_argument", "source_shape", "source_group", "source_fingerprint",
    "source_duplicate_fingerprint", "source_order", "source_status", "source_values",
    "source_number", "source_too_many_alerts", "source_too_many_values",
    "source_too_large", "source_starts_at", "source_truncated", "source_body_digest",
    "source_provenance",
})

_HEX = frozenset("0123456789abcdef")

_FINGERPRINT_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{MAX_FINGERPRINT_BYTES}}}")
_REF_ID_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{MAX_REF_ID_BYTES}}}")
# [0-9], not \d: \d also matches non-ASCII digits.
_STARTS_AT_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z"
)
# JSON's own number grammar (RFC 8259): what a legitimate JSONDecimal.text holds.
_JSON_NUMBER_LEXEME = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")
# The canonical *output* grammar: explicit exponent sign, no leading zeros.
_CANONICAL_NUMBER_PATTERN = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?(e[+-][0-9]+)?")


class SourceError(ValueError):
    """A fixed, non-diagnostic sanitized-source-record rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail_source(code: str) -> None:
    raise SourceError(code) from None


# --- Small structural predicates (no side effects, no exceptions) -----------


def _hex64_ok(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in _HEX for c in value)


def _enum_ok(value: object, choices: tuple[str, ...]) -> bool:
    return type(value) is str and value in choices


def _exact_keys_ok(value: object, keys: frozenset) -> bool:
    return type(value) is dict and value.keys() == keys


# --- Value types --------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Provenance:
    kind: str
    path: str
    line: int | None


HTTP_PROVENANCE = Provenance("http", "/notification", None)


@dataclasses.dataclass(frozen=True)
class SourceAlert:
    fingerprint: str
    status: str
    values: tuple[tuple[str, str | None], ...] | None
    starts_at: str | None


@dataclasses.dataclass(frozen=True)
class SourceRecord:
    source_group: str
    alerts: tuple[SourceAlert, ...]
    truncated_alerts: int | None
    body_digest: str
    provenance: Provenance


# --- Canonical numbers --------------------------------------------------------


def canonical_number(value: int | JSONDecimal) -> str:
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            _fail_source("source_number")
        return str(value)
    if type(value) is not JSONDecimal:
        _fail_source("source_number")
    text = value.text
    if type(text) is not str:
        _fail_source("source_number")
    if len(text) > MAX_JSON_NUMBER_CHARS or not _JSON_NUMBER_LEXEME.fullmatch(text):
        _fail_source("source_number")
    code: str | None = None
    try:
        parsed = float(text)
    except (OverflowError, ValueError):
        code = "source_number"
    if code is not None:
        _fail_source(code)
    if not math.isfinite(parsed):
        _fail_source("source_number")
    if parsed.is_integer() and abs(parsed) <= MAX_SAFE_INTEGER:
        return str(int(parsed))
    return repr(parsed)


def is_canonical_number(text: object) -> bool:
    if type(text) is not str or len(text) > MAX_JSON_NUMBER_CHARS:
        return False
    if not _CANONICAL_NUMBER_PATTERN.fullmatch(text):
        return False
    lexeme: object = JSONDecimal(text) if ("." in text or "e" in text) else int(text)
    matches = False
    try:
        matches = canonical_number(lexeme) == text
    except SourceError:
        matches = False
    return matches


# --- Source group and the sanitized source record ----------------------------


def source_group_digest(group_key: str) -> str:
    if (
        type(group_key) is not str
        or not 1 <= len(group_key) <= MAX_GROUP_KEY_BYTES
        or any(character < "\x20" or character > "\x7e" for character in group_key)
    ):
        _fail_source("source_group")
    return tagged_digest(SOURCE_GROUP_TAG, {"group_key": group_key})


_SOURCE_JSON_KEYS = frozenset({
    "alerts", "body_digest", "provenance", "source_group", "truncated_alerts",
})
_ALERT_JSON_KEYS = frozenset({"fingerprint", "starts_at", "status", "values"})
_PROVENANCE_JSON_KEYS = frozenset({"kind", "line", "path"})


def _alert_to_json(alert: object) -> dict[str, object]:
    if type(alert) is not SourceAlert:
        _fail_source("source_shape")
    fingerprint = alert.fingerprint
    if type(fingerprint) is not str:
        _fail_source("source_fingerprint")
    status = alert.status
    if type(status) is not str:
        _fail_source("source_status")
    starts_at = alert.starts_at
    if starts_at is not None and type(starts_at) is not str:
        _fail_source("source_starts_at")
    values = alert.values
    values_json: dict[str, object] | None
    if values is None:
        values_json = None
    else:
        if type(values) is not tuple:
            _fail_source("source_values")
        values_json = {}
        for pair in values:
            if type(pair) is not tuple or len(pair) != 2:
                _fail_source("source_values")
            ref_id, number = pair
            if type(ref_id) is not str:
                _fail_source("source_values")
            values_json[ref_id] = number
    return {
        "fingerprint": fingerprint, "starts_at": starts_at, "status": status, "values": values_json,
    }


def source_to_json(source: SourceRecord) -> dict[str, object]:
    if type(source) is not SourceRecord:
        _fail_source("source_argument")
    alerts = source.alerts
    if type(alerts) is not tuple:
        _fail_source("source_shape")
    alerts_json = tuple(_alert_to_json(alert) for alert in alerts)
    provenance = source.provenance
    if type(provenance) is not Provenance:
        _fail_source("source_provenance")
    kind, path, line = provenance.kind, provenance.path, provenance.line
    if (
        type(kind) is not str or type(path) is not str
        or (line is not None and type(line) is not int)
    ):
        _fail_source("source_provenance")
    body_digest = source.body_digest
    if type(body_digest) is not str:
        _fail_source("source_body_digest")
    source_group = source.source_group
    if type(source_group) is not str:
        _fail_source("source_group")
    truncated_alerts = source.truncated_alerts
    if truncated_alerts is not None and type(truncated_alerts) is not int:
        _fail_source("source_truncated")
    return {
        "alerts": alerts_json,
        "body_digest": body_digest,
        "provenance": {"kind": kind, "line": line, "path": path},
        "source_group": source_group,
        "truncated_alerts": truncated_alerts,
    }


def _parse_provenance(value: object) -> Provenance:
    if not _exact_keys_ok(value, _PROVENANCE_JSON_KEYS):
        _fail_source("source_provenance")
    kind, path, line = value["kind"], value["path"], value["line"]
    if type(kind) is not str or kind not in PROVENANCE_KINDS or type(path) is not str:
        _fail_source("source_provenance")
    if line is not None and type(line) is not int:
        _fail_source("source_provenance")
    provenance = Provenance(kind=kind, path=path, line=line)
    if provenance != HTTP_PROVENANCE:
        _fail_source("source_provenance")
    return provenance


def _parse_values(value: object, budget: list[int]) -> tuple[tuple[str, str | None], ...] | None:
    if value is None:
        return None
    if type(value) is not dict:
        _fail_source("source_values")
    items: list[tuple[str, str | None]] = []
    for ref_id, number in value.items():
        if type(ref_id) is not str or not _REF_ID_PATTERN.fullmatch(ref_id):
            _fail_source("source_values")
        # A stored body lists object keys in canonical (sorted) order, so only
        # sorted values replay to the same tuple; never re-sorted here.
        if items and ref_id <= items[-1][0]:
            _fail_source("source_order")
        if number is not None and (type(number) is not str or not is_canonical_number(number)):
            _fail_source("source_values")
        items.append((ref_id, number))
    budget[0] += len(items)
    if budget[0] > MAX_VALUES:
        _fail_source("source_too_many_values")
    return tuple(items)


def _parse_alert(value: object, budget: list[int]) -> SourceAlert:
    if not _exact_keys_ok(value, _ALERT_JSON_KEYS):
        _fail_source("source_shape")
    fingerprint = value["fingerprint"]
    if type(fingerprint) is not str or not _FINGERPRINT_PATTERN.fullmatch(fingerprint):
        _fail_source("source_fingerprint")
    status = value["status"]
    if not _enum_ok(status, ALERT_STATUSES):
        _fail_source("source_status")
    starts_at = value["starts_at"]
    if starts_at is not None and (
        type(starts_at) is not str
        or len(starts_at) > MAX_STARTS_AT_BYTES
        or not _STARTS_AT_PATTERN.fullmatch(starts_at)
    ):
        _fail_source("source_starts_at")
    values = _parse_values(value["values"], budget)
    return SourceAlert(fingerprint=fingerprint, status=status, values=values, starts_at=starts_at)


def source_from_json(value: object) -> SourceRecord:
    if not _exact_keys_ok(value, _SOURCE_JSON_KEYS):
        _fail_source("source_shape")
    alerts_raw = value["alerts"]
    if type(alerts_raw) is not tuple or len(alerts_raw) < 1:
        _fail_source("source_shape")
    if len(alerts_raw) > MAX_ALERTS:
        _fail_source("source_too_many_alerts")
    budget = [0]
    alerts = tuple(_parse_alert(item, budget) for item in alerts_raw)
    previous: str | None = None
    for alert in alerts:
        if previous is not None and alert.fingerprint <= previous:
            duplicate = alert.fingerprint == previous
            _fail_source("source_duplicate_fingerprint" if duplicate else "source_order")
        previous = alert.fingerprint
    truncated_alerts = value["truncated_alerts"]
    if truncated_alerts is not None and (
        type(truncated_alerts) is not int or not 0 <= truncated_alerts <= MAX_TRUNCATED_ALERTS
    ):
        _fail_source("source_truncated")
    body_digest = value["body_digest"]
    if not _hex64_ok(body_digest):
        _fail_source("source_body_digest")
    provenance = _parse_provenance(value["provenance"])
    source_group = value["source_group"]
    if not _hex64_ok(source_group):
        _fail_source("source_group")
    record = SourceRecord(
        source_group=source_group, alerts=alerts, truncated_alerts=truncated_alerts,
        body_digest=body_digest, provenance=provenance,
    )
    if len(canonical_json(source_to_json(record), ascii_only=True)) > MAX_SOURCE_RECORD_BYTES:
        _fail_source("source_too_large")
    return record


def validate_source(source: object) -> SourceRecord:
    if type(source) is not SourceRecord:
        _fail_source("source_argument")
    reconstructed = source_from_json(source_to_json(source))
    if reconstructed != source:
        _fail_source("source_shape")
    return reconstructed


def source_digest(source: SourceRecord) -> str:
    return tagged_digest(SOURCE_TAG, source_to_json(source))


def dedupe_key(source: SourceRecord) -> str:
    json_value = source_to_json(source)
    rows = tuple(
        (alert["fingerprint"], alert["status"], alert["values"]) for alert in json_value["alerts"]
    )
    return tagged_digest(DEDUPE_KEY_TAG, rows)


__all__ = [
    "ALERT_STATUSES",
    "BODY_TAG",
    "DEDUPE_KEY_TAG",
    "HTTP_PROVENANCE",
    "MAX_ALERTS",
    "MAX_FINGERPRINT_BYTES",
    "MAX_GROUP_KEY_BYTES",
    "MAX_REF_ID_BYTES",
    "MAX_SOURCE_RECORD_BYTES",
    "MAX_STARTS_AT_BYTES",
    "MAX_TRUNCATED_ALERTS",
    "MAX_VALUES",
    "PROVENANCE_KINDS",
    "SOURCE_ERROR_CODES",
    "SOURCE_GROUP_TAG",
    "SOURCE_TAG",
    "Provenance",
    "SourceAlert",
    "SourceError",
    "SourceRecord",
    "canonical_number",
    "dedupe_key",
    "is_canonical_number",
    "source_digest",
    "source_from_json",
    "source_group_digest",
    "source_to_json",
    "validate_source",
]
