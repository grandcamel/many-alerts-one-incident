# 18d2: replayable reservation claims in the Receiver journal

Status: accepted local source design, 2026-09-25. Baseline: `d871a63`.
Authority: ADR 0013, tickets 37 and 38, the 19b versioning design, and the
18d1 hold-only comparator. This unit supplies journal evidence only. A
journal claim is not an accounting receipt, production reserve or launch
permit.

## Existing boundary

The v1 public registry, schema set, encodings, goldens and state digest are
pinned by existing tests. The v2 `run_hold` pair lives in a separate private
registry. The accounting store is a different SQLite/WAL history, and its
Receiver wrapper rejects `reservation_created` from the unknown population.
Therefore 18d2 adds no Receiver writer or ledger call. It only makes two
versioned journal records replayable, so the later verified adapter can
compare current histories at every restart.

## Exact record order

`reservation_intent` v2 is a single Receiver record after a committed
`run_hold` for the same job/admission and current pending membership. Its
`event_id` equals `intent_id`. The existing `job_id` retains the journal ID
grammar and must match the committed hold. The existing `admission_id` also
retains its v1 grammar for historical replay, but a new reservation intent
requires a canonical UUID admission because the ledger and 18d1 comparator
require it. Older non-UUID admissions remain valid and held; they are never
silently converted. Journal origin and new intent, attempt, reservation, Run
and lease IDs are canonical UUIDs. Journal UUID, admission ID, job ID, intent
ID, attempt ID, reservation ID, Run ID and lease ID are pairwise distinct.
The new attempt, reservation, Run and lease IDs cannot be reused by another
intent in this generation. The data includes `rule=reservation-intent-v2`,
`based_on_commit_seq` and `intent_digest`. That digest is the tagged canonical
digest `rj.reservation-intent.v2` of an exact object with keys
`journal_uuid`, `journal_generation`, `admission_id`, `job_id`, `intent_id`,
`attempt_id`, `reservation_id`, `run_id`, `lease_id` and
`based_on_commit_seq`. Replay recomputes it;
it is only an immutable cross-store comparison key, never an authorization.

`reservation_confirmation` v2 is a single Receiver record after exactly one
matching intent. Its journal `event_id` is a fresh canonical UUID, distinct
from every intent identity and the claimed ledger UUID and event ID. The
claimed ledger UUID and event ID are canonical UUIDs and are distinct from
all eight intent identities and from each other. Its data includes
`rule=reservation-confirmation-v2`, the same `intent_digest`, and claimed
ledger UUID/generation/event ID/sequence/event digest. Replay rejects a
second confirmation for one intent, or reuse of a claimed ledger event ID or
`(ledger_uuid, ledger_generation, sequence)` by another intent. The journal
can validate exact shape and claim linkage, but cannot authenticate the
claimed ledger fields by itself. The later adapter must compare them with a
freshly verified ledger history. A confirmation with no ledger counterpart
remains held.

The replay projection retains immutable intent and confirmation facts, with a
separately tagged digest `rj.reservation-claims.v2`. Its exact canonical JSON
input is an object with `intents` and `confirmations` arrays. Intents sort by
`intent_id` and each entry has exactly `journal_uuid`, `journal_generation`,
`admission_id`, `job_id`, `intent_id`, `attempt_id`, `reservation_id`, `run_id`,
`lease_id`, `intent_digest`, `based_on_commit_seq` and `committed_at_seq`.
Confirmations sort by `intent_id` and each entry has exactly `intent_id`,
`confirmation_event_id`, `intent_digest`, `ledger_uuid`,
`ledger_generation`, `ledger_event_id`, `sequence`, `event_digest` and
`committed_at_seq`. Here `committed_at_seq` is the journal commit sequence.
The v1 state digest and the v2 `run_hold` digest remain
unchanged. No projection field is named
`ready`, `reserved` or `permitted`. The records are recovery-class, with at
most 256 intents and 256 confirmations per journal generation and at most
2048 canonical body bytes each. At that cap, body plus 384-byte overhead is
at most 1,245,184 bytes. A cap or byte refusal is a no-write hold; it cannot
be interpreted as a successful intent or confirmation. No operation clears
or overwrites an existing claim or the job's `run_hold`. An intent or
confirmation does not make that job dispatch-eligible. A newer admission may
supersede the held job's pending members; the older hold remains a recovery
obligation, and an intent requiring current membership cannot attach to the
newer admission or implicitly clear the older hold.

## Crash and compatibility contract

Before intent commit, no journal attempt claim exists. The scanner must still
check independently verified ledger history for orphan events and hold them;
journal absence cannot prove zero liability. Intent without confirmation is
reservation-unknown: a ledger may have liability. Confirmation does not
make the pair verified, because either store can be rolled back separately.
Only exact replayed journal facts may be passed to the future 18d comparator.
Mixed v1/v2 reopen and verify-only inspection must work. Older binaries must
return a non-persisted `journal_schema_unsupported` process hold on either
new pair. Unsupported future pairs remain unsupported. No existing v1 record
or public registry is rewritten.

The next 18d3 unit will read independently verified current journal and
ledger histories, make immutable comparator facts and test all three commit
windows. It may inspect synthetic complete ledgers, but must not expose a
production reserve or launch method. The external opening/billing, liability,
continuity and archive decisions in `accounting-reservation-gates.md` remain
required before production reservation.
