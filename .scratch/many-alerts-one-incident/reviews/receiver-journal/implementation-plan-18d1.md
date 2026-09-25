# 18d1 implementation plan: pure cross-store relation

Status: proposed source-only plan, 2026-09-25. Baseline: `b27ed04`.
Decision: `design-18d1-no-launch-bridge.md`. No existing journal, ledger,
Receiver, Forwarder or launcher file changes in this first unit.

1. Add `tests/test_reservation_bridge.py` first. Use immutable, synthetic
   structural facts to cover: no intent, intent-only, ledger-only, ledger
   without journal confirmation, exact triple, duplicate exact evidence,
   duplicate conflict, different journal generation/admission/attempt/Run/
   reservation/lease, wrong intent digest, ledger event digest/sequence
   mismatch and malformed values. Assert every result is a hold and no result
   has a permit, spend availability or launch method.
2. Add `grafana_jsm_sandbox/reservation_bridge.py` as a pure module. Inputs
   are frozen records: `JournalIntent`, `LedgerReservation`, and
   `JournalConfirmation`. They carry only UUID/sequence/digest/correlation
   facts needed for a join. Validate exact scalar types and bounded tuple
   lengths, reject malformed inputs with one fixed code, and return a frozen
   `BridgeAssessment(hold=True, reason=<closed code>)`.
   A matching triple returns `matching_unqualified`; it does not encode a
   separate ready state. No filesystem, clock, socket, provider, journal or
   ledger import is permitted.
3. Add `docs/reservation-bridge.md` defining the descriptive API and the
   verified-view integration still required. Review both Standards and Spec
   axes against the 18c gate and accepted ADR. Run focused tests, Ruff,
   line/whitespace checks, then the full repository suite before the local
   code commit. Record hashes, protected uncommitted read-back, reviewer
   verdicts and all `NOT RUN` boundaries.

The interface is deliberately incapable of asserting a production reserve.
Future 18d2 work must bind its inputs to independently verified journal and
ledger histories, extend the journal with v2 intent/confirmation records,
and test actual crash ordering. Current production population remains unknown.

Input schema for the first unit:

- `JournalIntent`: journal UUID/generation, admission ID, intent ID, attempt
  ID, reservation ID, Run ID, lease ID, and intent content digest.
- `LedgerReservation`: the same correlation fields, plus ledger UUID,
  generation, event ID, sequence and event digest from a read-back receipt.
- `JournalConfirmation`: intent ID plus the ledger UUID/generation/event
  ID/sequence/digest that the journal claims to have observed.
- `assess_bridge(target_intent_id, intents, ledger, confirmations)` accepts
  tuples of at most 1024 facts per family. Exact identical records are
  idempotent. A conflicting duplicate or counterpart mismatch is a conflict
  hold; orphan ledger evidence is never discarded. Closed reasons are
  `missing_intent`, `orphan_ledger`, `missing_ledger`,
  `missing_confirmation`, `identity_conflict`, and
  `matching_unqualified`. All are holds. Malformed input raises a fixed
  `bridge_invalid` error with no echoed values.
