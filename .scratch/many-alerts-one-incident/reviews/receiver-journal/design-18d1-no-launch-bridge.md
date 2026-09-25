# 18d1: no-launch journal and ledger reconciliation

Status: proposed local design, 2026-09-25. Authority: accepted ADR 0013,
ticket 37's proposed recovery contract, ticket 38's proposed split-store
allowance, and the reviewed 18c non-reserving ledger. This design does not
authorize a production reservation or a Run launch.

## Boundary

The Receiver journal and accounting ledger are separate SQLite/WAL stores.
Neither store's commit implies the other's. The journal has a v2 no-dispatch
`run_hold` projection; it has no reservation intent or confirmation. The
ledger's v1 `reservation_created` shape already names journal origin,
admission, intent, attempt, reservation, Run, lease and an intent digest, but
the Receiver-facing ledger refuses that event while population is unknown.
An 18d join must therefore be three explicit steps:

1. Commit a versioned journal `reservation_intent` bound to an admitted job and
   a fresh attempt/Run/reservation/lease identity. Its stable content digest
   is the ledger's `intent_digest`. This step never launches a process.
2. Append and read back a matching ledger `reservation_created`. The current
   Receiver ledger returns `reservation_unavailable`, so this step is only
   possible in synthetic fixture images until authoritative opening and
   provider evidence are reviewed.
3. Commit a journal `reservation_confirmation` containing the ledger event
   identity, sequence and digest. It is descriptive until independently
   verified against the ledger on recovery.

Crash before step 1 leaves admitted work pending. After step 1 without a
ledger receipt, the attempt is held as reservation-unknown. After step 2
without step 3, the ledger may carry liability but no Run is launched; a
recovery scan may append confirmation only after exact verified read-back.
After step 3, the two stores can still be rolled back independently, so a
fresh scanner must compare their current verified histories before any later
permit. A match is never sufficient by itself: opening population, provider
coverage, liability U, venue, reference, lease and process containment remain
separate gates.

## First local unit

18d1 is a pure, no-launch comparator over bounded, sanitized structural facts
derived from future verified store views. It checks one-to-one intent,
reservation and confirmation identity, origin/generation, immutable attempt
and admission links, intent content digest, ledger event digest and sequence,
an explicit ledger read-back observation, and exact duplicate/conflict
behavior. Every result is a hold with a closed
reason; a structurally matching triple is named `matching_unqualified`, never
`ready` or `permitted`. The result contains no amount, credential, prompt,
provider record or launch token. Arbitrary caller-supplied facts cannot be
promoted to store authority.

The next unit must define v2 journal event validators and replay transitions
for the two new records, then read verified journal and ledger projections
through a read-only adapter. It must test crash images at each commit window,
head rollback/conflict, repeated IDs, stale generation, fixture-only ledger
populations and a real Receiver-facing `reservation_unavailable` result.
No store writer, dispatch gate or launcher may consume the pure 18d1 result as
permission.

## Required external decision

The authoritative opening/billing source, account scope, line identity,
coverage/lag rule, defensible U, continuity witness, archive and repair
policy remain unresolved in [the reservation gate ledger](accounting-reservation-gates.md).
Until those are evidenced and reviewed, a production reservation method and
any permit derived from it stay unavailable. Ticket 38 remains open.
