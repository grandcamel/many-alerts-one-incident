"""Pure structural join for a future two-store reservation handshake.

Facts are caller supplied. Even an exact match is unqualified and held; this
module cannot authenticate either store, reserve money or permit Run launch.
"""

import re
from dataclasses import dataclass

_UUID = re.compile(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')
_DIGEST = re.compile(r'[0-9a-f]{64}\Z')
_MAX_FACTS = 1_024
_MAX_GENERATION = 2**31 - 1
_MAX_SEQUENCE = 2**53 - 1


class BridgeError(ValueError):
    """Fixed rejection code without caller values."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class JournalIntent:
    journal_uuid: str
    journal_generation: int
    admission_id: str
    intent_id: str
    attempt_id: str
    reservation_id: str
    run_id: str
    lease_id: str
    intent_digest: str


@dataclass(frozen=True, slots=True)
class LedgerReservation:
    journal_uuid: str
    journal_generation: int
    admission_id: str
    intent_id: str
    attempt_id: str
    reservation_id: str
    run_id: str
    lease_id: str
    intent_digest: str
    ledger_uuid: str
    ledger_generation: int
    event_id: str
    sequence: int
    event_digest: str
    read_back: bool


@dataclass(frozen=True, slots=True)
class JournalConfirmation:
    intent_id: str
    ledger_uuid: str
    ledger_generation: int
    event_id: str
    sequence: int
    event_digest: str


@dataclass(frozen=True, slots=True)
class BridgeAssessment:
    hold: bool
    reason: str


def _invalid() -> None:
    raise BridgeError('bridge_invalid') from None


def _uuid(value: object) -> bool:
    return type(value) is str and _UUID.fullmatch(value) is not None


def _digest(value: object) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _generation(value: object) -> bool:
    return type(value) is int and 1 <= value <= _MAX_GENERATION


def _sequence(value: object) -> bool:
    return type(value) is int and 1 <= value <= _MAX_SEQUENCE


def _valid_intent(value: object) -> bool:
    keys = (
        'journal_uuid', 'admission_id', 'intent_id', 'attempt_id',
        'reservation_id', 'run_id', 'lease_id',
    )
    return (
        type(value) is JournalIntent
        and all(_uuid(getattr(value, key)) for key in keys)
        and len({getattr(value, key) for key in keys}) == len(keys)
        and _generation(value.journal_generation)
        and _digest(value.intent_digest)
    )


def _valid_ledger(value: object) -> bool:
    keys = (
        'journal_uuid', 'admission_id', 'intent_id', 'attempt_id',
        'reservation_id', 'run_id', 'lease_id', 'ledger_uuid', 'event_id',
    )
    return (
        type(value) is LedgerReservation
        and all(_uuid(getattr(value, key)) for key in keys)
        and len({getattr(value, key) for key in keys}) == len(keys)
        and _generation(value.journal_generation)
        and _generation(value.ledger_generation)
        and _sequence(value.sequence)
        and _digest(value.intent_digest)
        and _digest(value.event_digest)
        and type(value.read_back) is bool
    )


def _valid_confirmation(value: object) -> bool:
    return (
        type(value) is JournalConfirmation
        and _uuid(value.intent_id)
        and _uuid(value.ledger_uuid)
        and _generation(value.ledger_generation)
        and _uuid(value.event_id)
        and len({value.intent_id, value.ledger_uuid, value.event_id}) == 3
        and _sequence(value.sequence)
        and _digest(value.event_digest)
    )


def _checked_family(values: object, item_type: type, valid) -> tuple:
    if type(values) is not tuple or len(values) > _MAX_FACTS:
        _invalid()
    if any(type(value) is not item_type or not valid(value) for value in values):
        _invalid()
    return tuple(set(values))


def _intent_link(value: JournalIntent | LedgerReservation) -> tuple:
    return (
        value.journal_uuid, value.journal_generation, value.admission_id,
        value.intent_id, value.attempt_id, value.reservation_id,
        value.run_id, value.lease_id, value.intent_digest,
    )


def _ledger_link(value: LedgerReservation | JournalConfirmation) -> tuple:
    return (
        value.intent_id, value.ledger_uuid, value.ledger_generation,
        value.event_id, value.sequence, value.event_digest,
    )


def _reused_attempt(target: JournalIntent, intents: tuple, ledger: tuple) -> bool:
    target_ids = {target.attempt_id, target.reservation_id, target.run_id, target.lease_id}
    for value in (*intents, *ledger):
        if value.intent_id == target.intent_id:
            continue
        ids = {value.attempt_id, value.reservation_id, value.run_id, value.lease_id}
        if target_ids & ids:
            return True
    return False


def _reused_ledger_event(
    target: LedgerReservation, ledger: tuple, confirmations: tuple,
) -> bool:
    for value in (*ledger, *confirmations):
        if value.intent_id != target.intent_id and (
            value.event_id == target.event_id
            or (value.ledger_uuid, value.ledger_generation, value.sequence) == (
                target.ledger_uuid, target.ledger_generation, target.sequence,
            )
        ):
            return True
    return False


def assess_bridge(
    target_intent_id: str,
    intents: tuple[JournalIntent, ...],
    ledger: tuple[LedgerReservation, ...],
    confirmations: tuple[JournalConfirmation, ...],
) -> BridgeAssessment:
    """Return only a closed hold reason, even for an exact structural match."""
    if not _uuid(target_intent_id):
        _invalid()
    intents = _checked_family(intents, JournalIntent, _valid_intent)
    ledger = _checked_family(ledger, LedgerReservation, _valid_ledger)
    confirmations = _checked_family(
        confirmations, JournalConfirmation, _valid_confirmation,
    )
    selected_intents = tuple(v for v in intents if v.intent_id == target_intent_id)
    selected_ledger = tuple(v for v in ledger if v.intent_id == target_intent_id)
    selected_confirmations = tuple(v for v in confirmations if v.intent_id == target_intent_id)
    if len(selected_intents) > 1 or len(selected_ledger) > 1 or (
        len(selected_confirmations) > 1
    ):
        reason = 'identity_conflict'
    elif not selected_intents:
        reason = 'orphan_ledger' if selected_ledger else 'missing_intent'
    elif _reused_attempt(selected_intents[0], intents, ledger):
        reason = 'identity_conflict'
    elif not selected_ledger:
        reason = 'missing_ledger'
    elif (
        _intent_link(selected_intents[0]) != _intent_link(selected_ledger[0])
        or _reused_ledger_event(selected_ledger[0], ledger, confirmations)
        or (
            selected_confirmations
            and _ledger_link(selected_ledger[0]) != _ledger_link(selected_confirmations[0])
        )
    ):
        reason = 'identity_conflict'
    elif not selected_ledger[0].read_back:
        reason = 'ledger_unverified'
    elif not selected_confirmations:
        reason = 'missing_confirmation'
    else:
        reason = 'matching_unqualified'
    return BridgeAssessment(hold=True, reason=reason)


__all__ = [
    'BridgeAssessment', 'BridgeError', 'JournalConfirmation', 'JournalIntent',
    'LedgerReservation', 'assess_bridge',
]
