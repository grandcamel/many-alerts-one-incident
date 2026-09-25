# Unit 19i: first-attempt reservation claim and service lease identities

Status: proposed local source design, 2026-09-25. Fixed point: `953800c`.
Authority: accepted ADRs 0011–0013 and 0016–0017; tickets 36–38; reviewed
18d2 and 19h contracts; current journal, accounting and Forwarder source.
This design adds no reservation, grant, Run, process or dispatch authority.

## The two current mismatches

The v2 `reservation_intent` planner requires a prior `run_hold` for the exact
job and admission. A `run_hold` records an ineligible or recovery obligation;
the only Receiver writer currently creates one under `restart_recovery`.
An ordinary eligible first attempt therefore has no truthful v2 path. Do
not create a synthetic hold just to satisfy this precondition or loosen v2
replay for historical records.

The journal and ledger's `lease_id` is a canonical UUID. Forwarder
`LeaseRegistry.register` mints a different opaque grant ID and a sentinel for
each `(run_id, attempt_id, service)` binding. A Run may need distinct
Anthropic, Jira, Grafana, Kubernetes and optional Confluence grants. The
accounting UUID cannot be silently passed as an actual Forwarder grant or
treated as authority for all routes.

## Proposed initial-claim record

Add a version 3 `reservation_intent` *only for an initial eligible attempt*.
It is one Receiver-authored, ordinary-class record and simultaneously opens
the stable job identity. Pure planning/replay requires a canonical UUID
admission with 1–32 current pending members, no unresolved `run_hold`
anywhere, no outstanding v3 initial claim anywhere, no existing v2/v3 claim
owning that admission, no global journal dispatch hold, and no previous
attempt for the proposed job. Historical v2 holds and v3 initial claims have
no clearing transition today, so a second v3 initial claim remains refused
until a future explicit, replayable terminal/reconciliation disposition
establishes that the earlier job no longer occupies the single Run slot.
A future writer must derive these facts from
the current independently verified journal head and additionally recheck
current accounting, venue, reference, lifecycle/diagnostic limits and other
dispatch predicates under the required locks. Pure replay can validate only
journal facts.

The record binds a new canonical UUID `job_id`, `intent_id`, `attempt_id`,
`reservation_id`, `run_id` and `lease_id`, all pairwise distinct from one
another, the journal/admission identities, and previously committed attempt
identities in this generation. Here `lease_id` is explicitly the *journal
claim for the Anthropic model grant* and remains the UUID cross-store
correlation key in the existing ledger event shape. It is not the Forwarder
grant ID or sentinel. Bind exact `admission_id`, `based_on_commit_seq`,
`member_count`, an ordered digest of current member fingerprints, and a
separately tagged `rj.reservation-intent.v3` digest of every identity and
membership field. No output field says `ready`, `confirmed` or `permitted`.

Replay re-derives the current-member set and every computed field at commit,
then retains the immutable claim even if a later admission supersedes its
pending members. It rejects conflicting ownership, duplicate or reused IDs,
stale membership, changed basis, malformed recomputed records and a second
initial claim for the same admission. It does not turn an old v2 held job
into a new eligible job. A later held-job retry requires its own explicit
operator/reconciliation authorization record and fresh attempt identities;
it cannot reuse this initial-claim path.

Keep v2 record bytes, v2-only replay semantics and digests, and `rj.state.v1`
unchanged. Store v3 initial claims in a
separate projection with a separately tagged digest. Share v2's aggregate
cap of 256 intents and 256 confirmations across both versions and retain
the 2,048-byte canonical record ceiling. The v3 initial intent must fit the
ordinary-byte ceiling, leaving the configured total-minus-ordinary recovery
reserve untouched (16 MiB at current defaults); version-aware capacity
classification is required because the
existing classifier keys on event type. The v3 confirmation is recovery-class,
so a successful ledger event can still be claimed when ordinary admission
capacity is full. Capacity refusal is a no-write hold. A version 3
`reservation_confirmation` can claim the current ledger event for a v3
intent; mixed-history replay must reject reuse of a ledger event ID or
`(ledger_uuid, ledger_generation, sequence)` across *both* v2 and v3
confirmation maps, as well as duplicates within either map, regardless of
which version appears first. A shared cross-version identity index must be
consulted by both replay paths. The v3 confirmation remains
unverified until a fresh, independently verified ledger read-back matches.
The current Receiver ledger still refuses `reservation_created` while its
opening population is unknown. Neither a v3 intent nor a v3 confirmation
can be written as a production positive reservation under that gate.

## Proposed grant mapping at launch

The later `run_intent` binds the verified accounting-linked model claim, an
exact sorted service set and a fresh journal UUID lease claim for every
other intended service. Each service claim is single-use and distinct across
attempts. The Receiver registers one dormant Forwarder grant per intended
service, checks every grant's run, attempt, service, scope digest, boot,
Forwarder generation and expiry against the current intent, and commits a
`launch_claim` before process creation. That record contains an exact sorted
service-to-journal-claim-to-Forwarder-grant mapping; it excludes sentinels.
The model grant maps to the accounting-linked `lease_id` UUID. Each actual
grant ID maps to exactly one service claim and cannot appear under another
Run, attempt or service. Registration failure, missing mandatory service,
changed scope/generation or uncertain read-back revokes every known grant
and holds launch. A registered grant without a committed launch claim is
still dormant and requires revocation on recovery. A committed claim with
no trusted spawn/release observation follows 19h's orphan/Forwarder/effect
inspection rule; mapping alone does not prove child absence or execution.
The effective authority for each service ends at the earlier of its grant
expiry and the Run's origin-plus-270-second work deadline. Because grants
are registered before that origin and current `register` caps expiry at its
own time plus 270 seconds, the design never assumes a full 270 service
seconds after launch. Activation uses a timestamp allowed by the registry's
created-at check; it cannot move the journal Run origin or extend expiry.

At authorization, the Receiver matches the presented *actual* grant ID and
service to this durable mapping, current Forwarder boot/generation and
exact routed request. It does not infer the grant from the UUID, a sentinel,
a stale registry snapshot or a grant for a different service. Every intended
grant is activated only after the guarded spawn attestation and before
barrier release. Revocation/closeout is per grant; all intended grants must
be accounted for before a Run hold can clear.

## Local source order and acceptance

First add v3 validators, pure planner/replay and tagged projection with no
application writer. Check exact v1/v2 bytes/digests, mixed v1/v2/v3 reopen,
older-binary unsupported behavior, forged recomputed records, membership
supersession, duplicate ownership, identity collision, and capacity. Then
extend the no-launch journal/ledger view and comparator to inspect v3
claims without granting reservation. Only after the external accounting
gate can a Receiver writer create positive current reservations. Separately
specify and implement `run_intent`/`launch_claim` record bounds and grant
mapping, then the guarded caller and permit path. Run independent Standards
and Spec reviews and the full local test suite before any code commit.

Provider opening and charge identity, coverage/lag/finality, liability U,
independent continuity/retention, native client, tenant/OPS, paid, venue,
deployment and human adjudication evidence remain unrun external gates.
