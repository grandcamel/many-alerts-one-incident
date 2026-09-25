"""Read-only, no-launch scan of two independently verified stopped images.

The current Receiver ledger stores no reservation events. Every outcome is a
hold; this shell cannot reserve money, confirm a journal claim or issue a
dispatch permit. The two inspections are not an atomic cross-store snapshot.
"""

from dataclasses import dataclass
from pathlib import Path

from .accounting_store import LedgerStore
from .recovery_journal import inspect_reservation_claim_view
from .reservation_bridge import (
    BridgeAssessment,
    BridgeError,
    JournalConfirmation,
    JournalIntent,
    assess_bridge,
)

SCAN_REASONS = frozenset({
    'bridge_invalid', 'journal_unverified', 'ledger_unverified',
    'ledger_unsupported', 'missing_intent', 'missing_ledger',
    'identity_conflict', 'scan_invariant',
})
_CURRENT_BRIDGE_REASONS = frozenset({
    'missing_intent', 'missing_ledger', 'identity_conflict',
})


@dataclass(frozen=True, slots=True)
class ScanAssessment:
    reason: str

    @property
    def hold(self) -> bool:
        return True


def _intent_fact(claim) -> JournalIntent:
    return JournalIntent(
        journal_uuid=claim.journal_uuid,
        journal_generation=claim.journal_generation,
        admission_id=claim.admission_id,
        intent_id=claim.intent_id,
        attempt_id=claim.attempt_id,
        reservation_id=claim.reservation_id,
        run_id=claim.run_id,
        lease_id=claim.lease_id,
        intent_digest=claim.intent_digest,
    )


def _confirmation_fact(claim) -> JournalConfirmation:
    return JournalConfirmation(
        intent_id=claim.intent_id,
        ledger_uuid=claim.ledger_uuid,
        ledger_generation=claim.ledger_generation,
        event_id=claim.ledger_event_id,
        sequence=claim.sequence,
        event_digest=claim.event_digest,
    )


def scan_reservation(
    journal_directory: Path, ledger_directory: Path, target_intent_id: str,
) -> ScanAssessment:
    """Observe verified negative v1 evidence and always hold the attempt."""
    preflight = None
    try:
        preflight = assess_bridge(target_intent_id, (), (), ())
    except BridgeError:
        return ScanAssessment('bridge_invalid')
    if type(preflight) is not BridgeAssessment or (
        preflight.hold is not True or preflight.reason != 'missing_intent'
    ):
        return ScanAssessment('scan_invariant')

    journal = inspect_reservation_claim_view(journal_directory)
    if journal.state != 'ready':
        return ScanAssessment('journal_unverified')
    ledger = LedgerStore.inspect_reservation_view(ledger_directory)
    if ledger.state != 'ready':
        return ScanAssessment('ledger_unverified')
    if ledger.population != 'unknown' or ledger.reservations != ():
        return ScanAssessment('ledger_unsupported')

    intents = tuple(_intent_fact(claim) for claim in journal.intents)
    confirmations = tuple(_confirmation_fact(claim) for claim in journal.confirmations)
    result = None
    try:
        result = assess_bridge(target_intent_id, intents, (), confirmations)
    except BridgeError:
        return ScanAssessment('bridge_invalid')
    if type(result) is not BridgeAssessment or result.hold is not True or (
        result.reason not in _CURRENT_BRIDGE_REASONS
    ):
        return ScanAssessment('scan_invariant')
    return ScanAssessment(result.reason)


__all__ = ['SCAN_REASONS', 'ScanAssessment', 'scan_reservation']
