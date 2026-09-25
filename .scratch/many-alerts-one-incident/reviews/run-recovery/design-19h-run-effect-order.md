# Unit 19h: Run and effect record order at the guarded barrier

Status: proposed local source design, 2026-09-25. Fixed point: `77a8f20`.
Authority: accepted ADRs 0011–0013, 0016–0017, ticket 37's proposed
recovery contract, the reviewed 19b and 19d designs, and current journal,
accounting, Forwarder and supervision source. This document selects no
provider/tenant fact and authorizes no process or external mutation.

## Current gate

The current Receiver accounting ledger has `population=unknown` and rejects
`reservation_created`. A v2 journal `reservation_confirmation` is a replayed
claim; it cannot authenticate the separate ledger. The stopped-image 18d3
scanner therefore holds every reservation, and no `run_intent`, launch claim,
dispatch permit, process or effect writer can be exercised by a production
caller. Source work may add versioned record validation and replay under a
no-writer boundary, but no journal field named `confirmed` or `ready` may
stand in for the current, independently verified ledger relation.

## Record families and partial order

The following is a proposed v2 extension dependency order, not a single
timeline: supervision and individual effects occur while a Run is active,
and terminal assessment normally follows them. Each new record must have
an exact validator, pure planner, replay transition, bound, separately tagged
projection digest, mixed-version reopen coverage and older-binary
`journal_schema_unsupported` behavior before any writer is exposed. The v1
registry, records and `rj.state.v1` digest remain byte-for-byte stable.

1. **`run_intent`**, before any process creation. Bind a current eligible
   pending admission and stable job identity, or a held job with an explicit
   replayable reconciliation/authorization transition, to immutable intent,
   attempt, reservation and Run IDs, the exact journal reservation claim,
   and a separately verified current accounting reservation receipt/head.
   Record the requested bounded service lease scopes and the *policy
   durations* 270/290/300 seconds. It must not invent actual launch time or
   deadlines. A future writer checks journal,
   ledger and other dispatch predicates again while holding their required
   locks; replay alone can check only internal identity and order. No second
   run intent may reuse an attempt, Run or reservation ID. The current v2
   `reservation_intent` planner requires an existing `run_hold`, so it cannot
   serve an ordinary eligible first attempt. Its `lease_id` is a canonical
   UUID claim, while the current Forwarder mints a distinct `lease_...` grant
   ID *per service*. Preserve that v2 record and its replay meaning; a future
   versioned first-attempt intent and service-specific claim-to-grant mapping
   need source review before a `run_intent` writer. The existing v2 UUID has
   no service discriminator or enforceable grant mapping. A future versioned
   mapping must explicitly designate the accounting-linked claim for the
   model-service grant and separately claim/bind other routed services. Keep
   existing v2 images held until that mapping is recorded and replayed;
   neither ID is silently substituted for the other, and one grant cannot
   authorize every service.
2. **`launch_claim`, then guarded child and `spawn_attestation`.** To retain
   ticket 37's claim-before-process rule, the Receiver first registers the
   intended dormant, revocable Forwarder grants per service and reads back
   each Forwarder-issued lease ID, scope and boot/generation binding. It
   samples a same-boot monotonic origin and commits the launch claim with the
   journal service-lease claims and actual Forwarder grant identities, a fresh
   barrier token and absolute 270/290/300-second deadlines. The claim maps each fresh journal
   service lease identity, including the accounting-linked model lease claim,
   to exactly one grant for that service. This origin is at or before process
   creation; queue wait ends there, and barrier/attestation time consumes the
   Run budget. A grant registered before this origin may expire before the
   270-second work deadline: its effective service deadline is the earlier
   of its registered expiry and origin plus 270 seconds. No activation or
   retry extends that expiry; insufficient remaining authority holds launch
   or denies that route. The Forwarder activation timestamp must satisfy its
   own created-at rule and is not substituted for the journal Run origin.
   The child is then created behind an inherited fail-closed barrier. It
   cannot run client code or make an external call while the
   Receiver verifies stable containment identity and commits a separate
   `spawn_attestation` bound to the claim and observed group. Only after
   attestation, activation of the intended grants and a final
   same-boot/deadline check may the barrier release. A failure revokes all
   installed grants, contains and reaps the blocked child where identity is
   verified, and appends a failed-pre-release/blocked-child containment
   observation. If that record
   or containment proof is unavailable, state remains unknown and dispatch
   held. The barrier must close on parent loss;
   `start_new_session=True` alone does not prove this ordering. The barrier
   token is a correlation value, not proof of absence. A crash after claim or
   creation but before attestation requires a fail-closed child plus an
   independently verified orphan/absence inspection before retry; an absent
   attestation cannot imply that no child existed.
3. **`spawn_observation` and supervision observations**, after release, a
   trusted failed-before-process path, or a failed-pre-release blocked-child
   path. A Receiver-owned writer binds each
   sanitized observation to the immutable attempt/Run/service grants and
   monotonic boot. Spawn acceptance, root exit/reap, stable group
   identity/absence,
   actual stdout/stderr EOF, capture completeness, per-grant revocation and
   current Forwarder closeout are distinct facts. A callback or signal
   attempt is durably marked *before* it is invoked and its result is
   appended afterward. A crash between the two leaves the action unknown;
   the reducer cannot silently issue it again. If the pre-action append
   fails at a deadline or cancellation boundary, the Receiver still attempts
   bounded best-effort revocation and containment. Journal uncertainty
   latches dispatch and cannot become a clean closeout. A lost control session or
   stale closeout cannot become `closed` on replay. No observation alone
   clears the per-job Run hold.
4. **Per-operation `effect_intent` then `effect_receipt`**, interleaved with
   active supervision and usually before terminal assessment. A Run calls the
   scoped Forwarder route; it cannot write the Receiver journal. After route
   and pure connector preparation, the Forwarder presents the registered
   route-specific grant/attempt, route, canonical *prepared-request* digest
   and sanitized target/plan to the Receiver over authenticated control. The Receiver
   resolves these to its admitted logical operation ID, rechecks the current
   journal/accounting/gates, and durably commits an `effect_intent` bound to
   that exact route, request digest, operation, attempt and target before
   Forwarder upstream admission/connect, then returns a one-use permit.
   This refines ticket 37's proposed phrase "before the Forwarder call": the
   inbound Run-to-Forwarder request must be parsed first to bind its actual
   routed digest, while the durable intent still precedes any upstream
   connection or write. If native-client request identity cannot be
   resolved, deny. The Forwarder consumes the permit at L1 admission, then
   re-verifies that consumed permit, route-specific grant, digest, target and
   deadline at L2 immediately before the first possible upstream byte. Current permit
   routes remain denied; neither exchange nor receipt ledger yet supplies
   this handshake. Missing or late approval denied before L1 is
   NOT_DISPATCHED and may qualify for ADR 0012's one shorter Report attempt
   if its other evidence gates hold. A denial after L1 but before L2 is
   `FAILED` with zero application bytes and a consumed permit; it does not
   qualify for that shorter Report path or revive the same operation. A crash
   without trusted L1/L2 and zero-byte evidence, or after L2, is
   dispatch-unknown until correlated receipt and required OPS read-back.
   A missing response, timeout, stale session or conflicting read-back
   cannot be promoted to confirmation. Confirmed OPS effects survive optional
   Memory or telemetry failure. No path automatically reissues the request.
5. **`terminal_observation` and `execution_assessment`**, after bounded
   parsing and containment observation. Preserve the recognized terminal
   subtype, exact boolean error indicator, bounded nullable sanitized reason
   code (closed vocabulary; never freeform native text), usage
   state and evidence digest without raw output. Record the Receiver process
   facts separately. Replay re-derives `run_outcome.assess_execution`; a
   claimed derived result that disagrees holds. Missing, duplicate or
   malformed terminal *evidence* is incomplete, while Receiver-observed
   containment failure, timeout and cancellation retain their higher
   precedence in the derived outcome. Missing usage remains unknown.
   Execution success is separate from effect confirmation and accounting
   settlement.
6. **Reconciliation and disposition**, operator-only and append-only. A
   fresh OPS read reconciles an uncertain effect even if its Incident has
   aged out of ordinary admission. An operator may authorize one fresh
   operation ID only after the previous effect's external state is resolved;
   the same intent/operation is never reissued. Abandoning unprocessed
   Notification work does not settle an unknown external write. A retry uses
   new attempt, Run, reservation and sentinels and remains in the same
   lifecycle/diagnostic and weekly limits.

## Permit and recovery invariants

`AuthorizeDispatch` is a one-use, exact routed-request exchange from the
Forwarder to the Receiver before L1 admission. It requires a verified current
journal head, an independently verified
accounting reservation relation, the committed launch claim and live
route-specific grant, the intended target/scope, deadline, venue/reference
readiness, no global
dispatch hold and an explicit authorized state for this job. Historical
`run_hold` records are never erased; their presence alone neither grants nor
permanently forbids a later explicitly reconciled attempt. The permit is
bound to the canonical prepared-request digest, exact operation and grant.
L1 consumes it once; L2 re-verifies it before first write without consuming
it again. A Receiver-side snapshot is insufficient. A consumed but unwritten
permit is not reusable. The permit does not make an upstream effect
reversible. The current product issues no such permit.

On restart, all old leases are invalid and dispatch is held before recovery
inspection. A `run_intent` without a launch claim predates process creation
under this contract; registered but unclaimed grants still need revocation.
A launch claim without a verified spawn attestation
does not prove whether a blocked child was created or contained; inspect
the barrier/orphan state. An attestation without a subsequent durable
spawn/release observation proves identity only: a crash before or just after
release leaves child execution unknown. Hold dispatch and inspect the orphan,
Forwarder and effect state before classifying or retrying; never infer
`NEVER_STARTED` from attestation alone. An effect intent without a receipt requires
trusted Forwarder L1/L2 and zero-byte evidence to distinguish a pre-L1
NOT_DISPATCHED denial, a post-L1 unwritten `FAILED` request and
dispatch-unknown. A terminal
record without a journaled containment and current Forwarder closeout cannot
release the hold. A confirmation claim without a current ledger counterpart
remains accounting-unknown. Any uncertain journal append latches the process
and may not return a positive receipt.

At ordinary journal capacity, reserve bounded recovery space for action
results, terminal/containment observations, effect receipts, reconciliation
and handoff. An exhausted recovery reserve holds new dispatch and preserves
the original source and effect obligation; no `finally` cleanup may discard
the only evidence. Exact per-record and active-attempt caps must be measured
against the current journal bounds before source implementation, rather than
borrowed from a model Run estimate. Raw prompt, tool/response body, token,
account identity, scoring data and Ground truth stay outside these records.

## Local implementation and acceptance order

First resolve the local v2 held-job/eligible-first-attempt and journal lease
claim/Forwarder service-grant mismatches above with a reviewed versioned
contract. Then ratify record fields and capacity against real current codecs and
stores. Implement no-writer `run_intent`/`launch_claim` replay only after a
verified reservation relation can be represented without granting dispatch;
then add Receiver writers with exact current-head checks. Independently,
exercise a closed synthetic child through a test-only startup barrier and
supervisor adapter; keep native/provider/OPS routes absent. Add actual
Forwarder effect-intent/receipt wiring only after a current permit gate and
service-grant/fence relation exist. At each storage-visible step, test mixed
version reopen, every crash boundary above, exact retry/conflict, capacity,
forged recomputed records, read-back and old-binary refusal; review Standards and
Spec and run the full local suite before a code commit.

Provider opening/billing identity, coverage/lag/finality, liability U,
independent continuity, archive registration/retention, native client,
tenant/OPS, paid, intended-venue isolation/durability and human adjudication
remain separate unrun gates. No local fixture can clear them.
