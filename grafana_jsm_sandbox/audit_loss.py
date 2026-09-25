"""Pure, unqualified audit-loss bytes for ticket 39.

This codec records a gap shape only. It does not capture evidence, persist a
bundle, grant provenance, or decide whether a Report is supported.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from datetime import datetime
from types import MappingProxyType

from .forwarder_json import JSONPolicyError, canonical_json, parse_json

MAX_LOSS_BYTES = 1_024
LOSS_CODE_BY_STATE = MappingProxyType({
    "missing": "expected_record_missing",
    "truncated": "capture_truncated",
    "redacted": "support_removed",
    "transport_error": "transport_failed",
    "unknown": "unclassified_gap",
})
_FIELDS = frozenset({
    "schema_version", "record_kind", "loss_id", "audit_bundle_id",
    "exchange_id", "report_revision_id", "side", "state", "loss_code",
    "source", "detected_phase", "observed_at",
})
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z")


class AuditLossError(ValueError):
    """Fixed, non-diagnostic local codec rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclasses.dataclass(frozen=True)
class LossPreflight:
    body: bytes
    byte_count: int
    sha256: str


def _fail(code: str) -> None:
    raise AuditLossError(code) from None


def _uuid4(value: object) -> bool:
    return type(value) is str and _UUID4.fullmatch(value) is not None


def _utc(value: object) -> bool:
    if value is None:
        return True
    if type(value) is not str or _UTC.fullmatch(value) is None:
        return False
    valid = True
    try:
        datetime.fromisoformat(value)
    except ValueError:
        valid = False
    return valid


def _validate(value: object) -> None:
    if (type(value) is not dict or len(value) != len(_FIELDS)
            or any(type(key) is not str for key in value)
            or set(value) != _FIELDS):
        _fail("audit_loss_shape")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        _fail("audit_loss_shape")
    if type(value["record_kind"]) is not str or value["record_kind"] != "audit_loss":
        _fail("audit_loss_shape")
    if not _uuid4(value["loss_id"]) or not _uuid4(value["audit_bundle_id"]):
        _fail("audit_loss_id")
    side = value["side"]
    if type(side) is not str or side not in ("request", "response", "report"):
        _fail("audit_loss_shape")
    if side == "report":
        if value["exchange_id"] is not None or not _uuid4(value["report_revision_id"]):
            _fail("audit_loss_id")
    elif not _uuid4(value["exchange_id"]) or value["report_revision_id"] is not None:
        _fail("audit_loss_id")
    state = value["state"]
    if type(state) is not str or state not in LOSS_CODE_BY_STATE:
        _fail("audit_loss_shape")
    if type(value["loss_code"]) is not str or value["loss_code"] != LOSS_CODE_BY_STATE[state]:
        _fail("audit_loss_shape")
    if type(value["source"]) is not str or value["source"] != "unqualified_local":
        _fail("audit_loss_shape")
    phase = value["detected_phase"]
    if type(phase) is not str or phase not in ("before_persistence", "after_persistence"):
        _fail("audit_loss_shape")
    if not _utc(value["observed_at"]):
        _fail("audit_loss_time")


def encode_loss(value: object) -> LossPreflight:
    """Encode a content-free local loss claim to canonical UTF-8 bytes."""
    _validate(value)
    body = canonical_json(value)
    if len(body) > MAX_LOSS_BYTES:
        _fail("audit_loss_overflow")
    return LossPreflight(body, len(body), hashlib.sha256(body).hexdigest())


def decode_loss(data: object) -> LossPreflight:
    """Require an exact canonical local loss claim with no body or grade."""
    if type(data) is not bytes:
        _fail("audit_loss_argument")
    if len(data) > MAX_LOSS_BYTES:
        _fail("audit_loss_overflow")
    code = None
    try:
        value = parse_json(data, max_bytes=MAX_LOSS_BYTES)
    except JSONPolicyError as error:
        code = error.code
    if code is not None:
        raise AuditLossError(code) from None
    artifact = encode_loss(value)
    if artifact.body != data:
        _fail("audit_loss_noncanonical")
    return artifact
