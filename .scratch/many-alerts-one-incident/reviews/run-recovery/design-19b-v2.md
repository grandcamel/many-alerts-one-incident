# Unit 19b design: versioned Run and effect journal records

Status: proposed local design, 2026-09-24. Source: accepted ADRs 0011, 0012,
0013, 0016 and 0017; ticket 37's proposed recovery specification; the
reviewed v1 journal and 18c accounting store. This document is a source plan,
not an authorization to launch a Run or dispatch an OPS mutation.

## Current seam

`journal_records.py` registers exact `(event_type, schema_version)` pairs. All
stored records are version 1. `seal` currently writes version 1 only, and the
reducer accepts a closed set of commit shapes. The storage layer verifies raw
bytes, chain, columns, framing and replay in order. A new event name alone is
not sufficient: unless the reducer understands its transition, replay rejects
it. The v1 genesis, admission and front-door encodings and their validators
must remain byte-for-byte stable. An older binary that encounters a new pair
must return the non-persisted `journal_schema_unsupported` process hold; it
must not turn an intentional format extension into a durable corruption hold.

The accounting ledger is a separate Receiver-owned store. A journal event
cannot assert that a reservation exists merely because it carries an ID. The
18d handshake requires a ledger receipt and an independently replayed journal
confirmation, with any missing/conflicting counterpart held on recovery.

## Record families and order

Use explicit version 2 for every new Run/effect pair; retain the version 1
validators unchanged. Version 2 is per record type in the existing canonical
envelope and digest chain. Mixing v1 admission records and v2 Run records is
allowed only after whole-chain replay supports both. No implicit migration of
old events or state digest is allowed. An extension must retain the old
`rj.state.v1` calculation for v1-only consumers and add a separately named
digest for the extended projection.

Implement in bounded units, with a full source and replay review at each
storage-visible step:

1. **19b1, no-dispatch recovery obligations.** Define and replay a v2
   `run_hold` record, with a stable job ID bound to committed admission IDs.
   The projection retains the obligation and newest pending source without
   erasing an older uncertain effect. Public journal methods may append these
   records, but create no attempt, reservation, lease, process or operation.
   A restart holds dispatch before any external action. Exhausted capacity
   yields a closed hold/backpressure outcome; recovery reserve is not silently
   spent on ordinary work.
2. **19b2, attempt and cross-store reservation.** Define v2
   `reservation_intent`, `reservation_confirmation` and `run_intent`. A
   separate 18d scanner compares committed journal records to ledger
   receipts and holds every unmatched pair. `run_intent` is eligible only
   after a valid, current ledger reservation confirmation and all other
   gates. The first implementation remains no-launch; it emits no permit.
3. **19b3, process and terminal observations.** Define v2
   `spawn_observation` and `terminal_observation` with Receiver provenance,
   sanitized digest references and reported versus derived outcome stored
   separately. Replay re-derives the 19a classification and holds on a
   mismatch. Trusted pre-process absence is distinct from an observation gap.
4. **19b4, effects and reconciliation.** Define v2 `effect_intent`,
   `effect_receipt` and `reconciliation`. An intent is committed before
   Forwarder dispatch. A receipt records the exact Forwarder identity and
   required OPS read-back; conflict or unavailable read-back is unknown.
   After a crash between intent and receipt, do not replay the mutation.
   Operator retry has a fresh operation/intent identity only after an
   explicit reconciliation disposition. A confirmed effect is never
   reissued because execution or an optional step failed.

No unit may publish a new v2 record that its replay path cannot validate and
project. Each uses the existing store commit/anchor acknowledgement and a
whole-history reopen test. Records are bounded, canonical and free of raw
prompt, tool, response, credential or Ground truth text. Every identity is
validated against the journal's closed ID grammar. The schema must reserve
enough recovery capacity for terminal, receipt, containment and handoff
evidence after ordinary admission capacity fills.

## Acceptance and deferred authority

Before a 19b source commit: write an exact multi-file plan, preserve the v1
goldens, add mixed-version replay and crash images, test unknown future pairs
as process holds, review both Standards and Spec axes, run focused checks and
the full suite. Verify that the legacy admission-only front door still cannot
launch a Run. For 19b2 and later, verify the counterpart scanner against
committed SQLite images, not only mock objects.

This design does not choose a production opening balance, provider coverage
window, charge identity, `U` estimate, archive policy or rollback witness.
Those remain the exact external decision gate recorded in
`../receiver-journal/accounting-reservation-gates.md`. Native/provider/tenant,
OPS, intended-venue, paid and human adjudication evidence remain unrun.
