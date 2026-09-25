"""Pure v3 execution-claim seam around the pinned v1 record/reducer imports.

No I/O, clock, capture, grant, effect or outcome authority. The adapter keeps
new classifier dependency and exception conversion outside the older A12
record/reducer import boundaries.
"""

from __future__ import annotations

from .forwarder_json import JSONPolicyError, tagged_digest
from .journal_records import Draft, Position, Record, RecordError, Stamp, seal, thaw
from .run_outcome import (
    ExecutionAssessment,
    OutcomeError,
    ProcessFacts,
    TerminalFacts,
    assess_execution,
)


def validate_execution_process(facts: object) -> bool:
    """Use the pure classifier's validation without exposing its exception."""
    valid = True
    try:
        assess_execution(facts, ())
    except OutcomeError:
        valid = False
    return valid


def seal_execution_claim(
    draft: Draft, position: Position, stamp: Stamp,
    *, tag: str, digest_key: str,
) -> Record | None:
    """Build an unqualified private claim, returning no record on bad input."""
    data = thaw(draft.data)
    code: str | None = None
    try:
        data[digest_key] = tagged_digest(
            tag, {"event_id": draft.event_id, "ids": thaw(draft.ids), "data": data},
        )
        record = seal(Draft(draft.event_id, draft.event_type, draft.actor,
                            draft.ids, data), position, stamp, schema_version=3)
    except (JSONPolicyError, RecordError):
        code = "record_field"
    return None if code is not None else record


__all__ = [
    "ExecutionAssessment", "ProcessFacts", "TerminalFacts", "assess_execution",
    "seal_execution_claim", "validate_execution_process",
]
