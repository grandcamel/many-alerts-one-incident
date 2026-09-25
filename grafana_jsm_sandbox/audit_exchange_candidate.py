"""Content-free, unqualified request/response gap candidate check.

This is not an exchange-v1 writer or source-capture proof. Every result is
capture-unverified, including a pair without structural defects.
"""

from __future__ import annotations

import dataclasses
import re

from .audit_loss import LOSS_CODE_BY_STATE, MAX_LOSS_BYTES, AuditLossError, decode_loss
from .forwarder_json import JSONPolicyError, parse_json

_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_FIELDS = frozenset({
    "audit_bundle_id", "exchange_id", "request_state", "response_state",
    "request_loss", "response_loss",
})
_STATES = frozenset({
    "returned", "empty", "missing", "truncated", "redacted",
    "transport_error", "unknown",
})


class ExchangeCandidateError(ValueError):
    """Fixed, non-diagnostic local candidate rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclasses.dataclass(frozen=True)
class ExchangeCandidatePrecheck:
    defects: tuple[str, ...]
    capture_status: str = "capture_unverified"


def _fail(code: str) -> None:
    raise ExchangeCandidateError(code) from None


def _uuid4(value: object) -> bool:
    return type(value) is str and _UUID4.fullmatch(value) is not None


def _loss_record(value: bytes) -> dict:
    code = None
    try:
        decoded = decode_loss(value)
        record = parse_json(decoded.body, max_bytes=MAX_LOSS_BYTES)
    except (AuditLossError, JSONPolicyError):
        code = "exchange_candidate_loss"
    if code is not None:
        _fail(code)
    return record


def precheck_exchange_candidate(value: object) -> ExchangeCandidatePrecheck:
    """Check caller-supplied state/marker consistency, without capture trust."""
    if (type(value) is not dict or len(value) != len(_FIELDS)
            or any(type(key) is not str for key in value)
            or set(value) != _FIELDS):
        _fail("exchange_candidate_shape")
    if not _uuid4(value["audit_bundle_id"]) or not _uuid4(value["exchange_id"]):
        _fail("exchange_candidate_shape")
    for side in ("request", "response"):
        state = value[f"{side}_state"]
        marker = value[f"{side}_loss"]
        if type(state) is not str or state not in _STATES:
            _fail("exchange_candidate_shape")
        if marker is not None and type(marker) is not bytes:
            _fail("exchange_candidate_shape")
    defects: set[str] = set()
    loss_ids: set[str] = set()
    for side in ("request", "response"):
        state = value[f"{side}_state"]
        marker = value[f"{side}_loss"]
        if marker is None:
            if state in LOSS_CODE_BY_STATE:
                defects.add(f"{side}_loss_missing")
            continue
        record = _loss_record(marker)
        if record["loss_id"] in loss_ids:
            defects.add("loss_identity_duplicate")
        loss_ids.add(record["loss_id"])
        if state not in LOSS_CODE_BY_STATE:
            defects.add(f"{side}_loss_unexpected")
        if (record["audit_bundle_id"] != value["audit_bundle_id"]
                or record["exchange_id"] != value["exchange_id"]
                or record["side"] != side or record["state"] != state):
            defects.add(f"{side}_loss_mismatch")
    return ExchangeCandidatePrecheck(tuple(sorted(defects)))
