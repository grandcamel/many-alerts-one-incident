"""Pure, synthetic Receiver telemetry-gap bytes for ticket 35.

No queue, transport, native source or trusted Receiver identity is installed
by this codec. It only pins a narrow local record grammar and stable hash.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from datetime import datetime
from types import MappingProxyType

from .forwarder_json import MAX_SAFE_INTEGER, JSONPolicyError, canonical_json, parse_json

MAX_GAP_BYTES = 2_048
GAP_CODES_BY_KIND = MappingProxyType({
    "telemetry_omitted": frozenset({
        "unknown_receiver_shape", "receiver_privacy_rejected",
    }),
    "telemetry_gap": frozenset({
        "projection_sequence_gap", "delivery_unknown",
    }),
})
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z")
_PAYLOAD_FIELDS = frozenset({
    "loss_code", "count", "first_observed_at", "last_observed_at",
    "affected_projection_seq_first", "affected_projection_seq_last",
})
_FIELDS = frozenset({
    "schema_version", "feed", "marker_source_id", "run_id", "rehearsal_id",
    "producer_instance_id", "native_session_id", "projection_generation",
    "projection_seq", "event_kind", "source", "observed_at", "ingested_at",
    "associations", "payload", "loss",
})
_EVENT_ID_TAG = b"maoi.run-gap.v1\x00"


class TelemetryGapError(ValueError):
    """Fixed, non-diagnostic local gap-codec rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclasses.dataclass(frozen=True)
class GapPreflight:
    body: bytes
    byte_count: int
    sha256: str
    projected_event_id: str


def _fail(code: str) -> None:
    raise TelemetryGapError(code) from None


def _keys(value: object, expected: frozenset[str]) -> bool:
    return (
        type(value) is dict
        and len(value) == len(expected)
        and all(type(key) is str for key in value)
        and set(value) == expected
    )


def _uuid4(value: object) -> bool:
    return type(value) is str and _UUID4.fullmatch(value) is not None


def _utc(value: object, *, nullable: bool) -> bool:
    if value is None:
        return nullable
    if type(value) is not str or _UTC.fullmatch(value) is None:
        return False
    valid = True
    try:
        datetime.fromisoformat(value)
    except ValueError:
        valid = False
    return valid


def _seq(value: object, *, positive: bool = False) -> bool:
    return type(value) is int and int(positive) <= value <= MAX_SAFE_INTEGER


def _validate(value: object) -> None:
    if not _keys(value, _FIELDS):
        _fail("telemetry_gap_shape")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        _fail("telemetry_gap_shape")
    if type(value["feed"]) is not str or value["feed"] != "run_gaps":
        _fail("telemetry_gap_shape")
    for key in ("run_id", "rehearsal_id", "projection_generation", "marker_source_id"):
        if not _uuid4(value[key]):
            _fail("telemetry_gap_id")
    if (value["producer_instance_id"] is not None
            or value["native_session_id"] is not None
            or value["associations"] is not None):
        _fail("telemetry_gap_shape")
    if not _seq(value["projection_seq"]):
        _fail("telemetry_gap_shape")
    kind = value["event_kind"]
    if type(kind) is not str or kind not in GAP_CODES_BY_KIND:
        _fail("telemetry_gap_shape")
    source = value["source"]
    if (not _keys(source, frozenset({"class", "version"}))
            or type(source["class"]) is not str or source["class"] != "receiver"
            or type(source["version"]) is not str
            or source["version"] != "receiver_projection_v1"):
        _fail("telemetry_gap_shape")
    if (not _utc(value["observed_at"], nullable=True)
            or not _utc(value["ingested_at"], nullable=False)):
        _fail("telemetry_gap_time")
    payload = value["payload"]
    if not _keys(payload, _PAYLOAD_FIELDS):
        _fail("telemetry_gap_shape")
    code = payload["loss_code"]
    if type(code) is not str or code not in GAP_CODES_BY_KIND[kind]:
        _fail("telemetry_gap_shape")
    loss = value["loss"]
    if type(loss) not in (list, tuple) or len(loss) != 1 or type(loss[0]) is not str:
        _fail("telemetry_gap_shape")
    if loss[0] != code:
        _fail("telemetry_gap_shape")
    count = payload["count"]
    if count is not None and not _seq(count, positive=True):
        _fail("telemetry_gap_shape")
    first_time = payload["first_observed_at"]
    last_time = payload["last_observed_at"]
    if not _utc(first_time, nullable=True) or not _utc(last_time, nullable=True):
        _fail("telemetry_gap_time")
    if first_time is not None and last_time is not None and first_time > last_time:
        _fail("telemetry_gap_time")
    first_seq = payload["affected_projection_seq_first"]
    last_seq = payload["affected_projection_seq_last"]
    if code != "delivery_unknown" and (
        count is None or first_seq is None or last_seq is None
    ):
        _fail("telemetry_gap_shape")
    if (first_seq is None) != (last_seq is None):
        _fail("telemetry_gap_shape")
    if first_seq is not None and (
        not _seq(first_seq) or not _seq(last_seq) or first_seq > last_seq
    ):
        _fail("telemetry_gap_shape")
    if code != "delivery_unknown" and count > last_seq - first_seq + 1:
        _fail("telemetry_gap_shape")


def _event_id(value: dict) -> str:
    identity = (
        value["run_id"],
        value["projection_generation"], value["projection_seq"],
        value["event_kind"],
        value["marker_source_id"],
    )
    return hashlib.sha256(_EVENT_ID_TAG + canonical_json(identity)).hexdigest()


def encode_gap(value: object) -> GapPreflight:
    """Build canonical bytes from an unqualified local Receiver marker draft."""
    _validate(value)
    event_id = _event_id(value)
    body = canonical_json({**value, "projected_event_id": event_id})
    if len(body) > MAX_GAP_BYTES:
        _fail("telemetry_gap_overflow")
    return GapPreflight(body, len(body), hashlib.sha256(body).hexdigest(), event_id)


def decode_gap(data: object) -> GapPreflight:
    """Require exact canonical bytes and a computed stable marker identity."""
    if type(data) is not bytes:
        _fail("telemetry_gap_argument")
    if len(data) > MAX_GAP_BYTES:
        _fail("telemetry_gap_overflow")
    code = None
    try:
        value = parse_json(data, max_bytes=MAX_GAP_BYTES)
    except JSONPolicyError as error:
        code = error.code
    if code is not None:
        raise TelemetryGapError(code) from None
    if (type(value) is not dict or len(value) != len(_FIELDS) + 1
            or any(type(key) is not str for key in value)
            or set(value) != _FIELDS | {"projected_event_id"}):
        _fail("telemetry_gap_shape")
    claimed_id = value.pop("projected_event_id")
    if type(claimed_id) is not str:
        _fail("telemetry_gap_id")
    artifact = encode_gap(value)
    if claimed_id != artifact.projected_event_id:
        _fail("telemetry_gap_id")
    if artifact.body != data:
        _fail("telemetry_gap_noncanonical")
    return artifact
