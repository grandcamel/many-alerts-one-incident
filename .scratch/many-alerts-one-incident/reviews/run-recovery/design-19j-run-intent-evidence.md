# 19j: no-writer Run intent and reservation evidence seam

Status: proposed local source design, 2026-09-25. Fixed point: `7e9338f`.
Authority: accepted ADRs 0011–0013 and 0016–0017, tickets 36–38, reviewed
19h/19i designs, and the current v3 journal/negative scanner implementation.
This design creates no Run, ledger reservation, service grant or permit.

## Current evidence and the seam

The journal has a v3 initial intent and an optional confirmation, both
replayable claims. The stopped scanner now verifies both images and truthfully
reports `missing_ledger` for the current Receiver ledger. That ledger has
`population=unknown`, exposes no reservation events and rejects
`reservation_created`. `assess_bridge` is a structural join and holds even on
an exact caller-supplied match. Thus neither the journal confirmation nor a
scanner reason is an admission token.

Keep the future current-reservation qualification in one Receiver-owned
module interface, rather than duplicating ledger checks in a Run writer,
launcher and permit caller. It consumes current, independently verified
journal and ledger heads and an actual replayed, read-back
`reservation_created` event. That event must match the journal intent and
confirmation on journal UUID/generation, admission, intent, attempt,
reservation, Run, model-lease claim, intent digest and exact ledger
UUID/generation/event ID/sequence/digest. It also requires a ledger with no
hold and defensible provider population, charge coverage/lag/finality and
liability U under the operator-approved accounting policy. Its output is a
short-lived, exact-head qualification for one attempt and an explicit hold
otherwise. A verified ledger *head* alone cannot authenticate the claimed
event. It must revalidate under serialized source ownership before a journal
append, at the new committed journal head before grant registration, before
launch and before each effect permit. A stored journal digest or stale
read-only image does not preserve authority across a head change. The present
implementation has no positive output because the opening, reservation and
external evidence gates are unavailable. Do not add a caller-supplied
`verified=True` escape hatch or equate a bridge's structural
`matching_unqualified` with the qualification.

## Proposed no-writer record

Use `(run_intent, schema_version=3)` for a v3 *initial* reservation claim
only. The record is a durable statement of Receiver intent before any
process or grant activation, not evidence that the ledger is still current.
Its exact sanitized fields should bind:

- fresh event ID; existing journal UUID/generation, admission, job, intent,
  attempt, reservation and Run IDs; the replay-available v3 initial-claim
  reference `(intent_id, committed_at_seq, intent_digest)`;
- the matching v3 confirmation event ID and its claimed ledger
  UUID/generation, event ID, sequence and event digest; a distinct
  separately verified ledger head reference captured by the future writer;
- the current pending members for the original admission, with count and
  tagged digest re-derived at planning and replay; they must exactly match
  the v3 initial claim. A newer admission that supersedes any original member
  makes the initial Run ineligible and holds it for a future explicit
  reconciliation or rebase transition. Unrelated newer pending work remains
  separate; no captured command sequence is replayed;
- an exact sorted intended service set with one bounded scope digest per
  service. It includes the four currently mandatory profiles `anthropic`,
  `jira`, `grafana` and `kubernetes`; optional `confluence` needs its separate
  approved scope. The model-service journal lease claim is the v3 accounting
  `lease_id`, while every other service receives a fresh distinct journal
  UUID claim. All mandatory readiness gates are rechecked by the future
  writer; no actual Forwarder grant or sentinel is invented here;
- the fixed 270/290/300-second policy durations, separately tagged record
  digest and current journal basis. `run_intent` is ordinary-class: preflight
  its exact charge against `ordinary_bytes` and retain measured recovery
  headroom for later effect, terminal and containment records. No
  launch origin or absolute deadline is known until a later launch claim.

Pure planning/replay can check current journal basis, exact v3
intent/confirmation links, the original admission's current member
count/digest, canonical and distinct identities, service order and mandatory
membership, scope-digest syntax, one outstanding Run intent for the single
Run slot, and the record/aggregate byte bounds. It cannot authenticate a
provider charge, current ledger head, venue, reference state or grant. The projection and
inspection must describe the record as an **outstanding unqualified intent**;
no field or receipt says `ready`, `confirmed`, `reserved`, `permitted` or
`running`. Earlier v1/v2 and current v3 record bytes and digests stay exact.
Older binaries must hold on the new record version. Existing v2 held-job
claims remain held until a separate replayable reconciliation authorization
defines their next attempt; this record must not treat a historical v2 hold
as an eligible first attempt.

The future writer takes an exact qualification at the pre-append journal and
ledger heads, acquires the ownership required by both stores in a specified
global order, and rechecks both heads and all admission predicates. It then
appends the record durably and reads back its exact new journal head. The
pre-append qualification expires by definition at that new head: a fresh
post-append qualification must match the committed `run_intent` and still
current ledger reservation before any Forwarder grant registration. A failed
or uncertain append latches dispatch. No cross-store atomic snapshot is
claimed. A later ledger change requires fresh qualification; a `run_intent`
alone never authorizes launch or an effect. The launch claim and service grant mapping
remain the separate 19h/19i stage.

## Local implementation sequence and gates

1. Ratify the exact field ceilings and measured recovery headroom against the
   current codec and configured journal reserve. Then add
   validator, pure planner/replay, separate projection digest and stopped
   inspection with no application writer. Test mixed versions, forged
   recomputed data, superseded pending members (must hold), duplicate
   identities, wrong confirmation, absent ledger, capacity and older-binary
   hold.
2. Add the current-reservation qualification module only after a reviewed
   ledger format can supply authenticated reservation events and complete
   population/charge coverage. Test current-head invalidation and
   cross-store crash windows. Do not fabricate a positive fixture as
   production admission evidence.
3. Add the Receiver writer and launch path only after the qualification,
   service scope and Forwarder grant mapping contracts are implemented and
   separately reviewed. Until then, advance the independent test-only
   guarded child and supervision work without a Run caller.

Authoritative opening history, provider charge-line/adjustment identity and
account scope, coverage/lag/finality, liability U, independent continuity,
archive registration, intended-venue durability, native client and tenant
evidence remain external decisions. Provider, native, tenant, paid, venue,
deployment, power-loss and human adjudication are **NOT RUN**.
