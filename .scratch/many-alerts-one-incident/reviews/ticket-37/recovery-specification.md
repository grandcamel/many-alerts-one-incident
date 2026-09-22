# Ticket 37 recovery and admission specification

Status: planning-only implementation contract. This document does not change the
Receiver, spawner, Forwarder, Skill, venue, accounting ledger, provider, or OPS.
It separates accepted policy from proposed routine implementation choices. Runtime,
real Receiver/spawner/Forwarder, tenant, model, live OPS, billing, and teardown
acceptance remain NOT RUN.
## Authority and non-negotiable policy

The accepted policy comes from ADR 0012 and ticket 21:

- Execution and external effects are separate. A clean exit, model prose, or a
  success-looking terminal record never proves a Jira/Confluence effect.
- Receiver-observed spawn failure, timeout, cancellation, result error, nonzero
  exit, or containment failure overrides apparent execution success. Missing,
  malformed, conflicting, or duplicate terminal evidence is incomplete. Missing
  usage is unknown, never zero.
- A trusted Forwarder response and required read-back confirm an effect. A failed
  optional Memory or telemetry step does not justify repeating confirmed OPS work.
- A denied mutation may receive one shorter, evidence-backed Report attempt only
  when the denial proves no dispatch. An uncertain dispatch requires
  reconciliation; there is no blind retry, model fallback, permission probing, or
  junk Incident.
- New Run dispatch is held after failed, interrupted, incomplete execution or an
  uncertain required effect. Bounded Notification admission/coalescing continues
  while capacity and durable admission remain available.
- The total Run budget is 300 seconds from launch on a monotonic clock: 270 seconds
  of startup/work, 20 seconds for interruption and local flush, then 10 seconds
  for forced termination and reaping. Cancellation starts cleanup earlier and does
  not extend the deadline. Unconfirmed containment holds dispatch.
- A Receiver-owned recovery journal is separate from Run-written Memory and is
  inaccessible to Runs. It persists across pod/container restart within a
  rehearsal. Restart holds dispatch and invalidates old sentinels. Reset cannot
  erase unresolved uncertainty.
- Ticket 31's successful-admission dedupe baseline is exact
  (fingerprint,status,values) per source group against the latest admitted
  record. Pending reduction is global per Fingerprint and retains the latest
  arrival's source group. Omission is never Resolved.

ADR 0011 supplies scoped Forwarder endpoints, revocable per-service sentinels,
restart invalidation, fixed origins, no direct upstream, and no retry after
uncertain delivery. ADR 0013 requires a durable $3 reservation before each model
attempt, a $150 Monday-Sunday America/New_York weekly model envelope, at most ten
attempts per lifecycle and ten diagnostic attempts, and holds dispatch for unknown
charges or missing accounting. ADR 0016 holds injection and dispatch on venue
readiness, forbids Run launch at cluster age 85 minutes and holds ordinary Fault
injection/model dispatch at age 90 while bounded Notification admission may
continue until protected teardown. ADR 0017 revokes reference admission, cancels exposed Runs
through the bounded path, and holds new dispatch after approved-reference
revocation.
## Identity and state model

The implementation MUST use the following stable identities.

| Identity | Meaning and lifetime |
|---|---|
| journal_generation | Monotonic generation for one rehearsal journal. Restart preserves it; an explicit reset creates the next generation. |
| admission_id | Unique durable identity for one admitted Notification arrival. A repeated HTTP delivery gets a new ingress event but may be suppressed by the latest-admitted baseline. |
| job_id | Stable recovery obligation for the admitted source/effect work. It survives Run retries and is never reused for unrelated work. |
| run_id | One process launch. Every operator retry receives a fresh Run ID and fresh sentinels. |
| attempt_id | One execution attempt, unique across restarts and retries; it links run_id, budget reservation, and terminal evidence. |
| effect_id | One intended external effect, stable while it is being reconciled. It names target, operation kind, Incident identity and sanitized payload digest, never the raw payload. |
| operation_id | One authorized external operation record. A fresh operator retry creates a new operation ID only after reconciliation; confirmed operation IDs are never replayed. |
| intent_id | One durable pre-dispatch intent, written before a Forwarder call. It is unique even when an effect is retried after explicit reconciliation. |
| reservation_id | One accounting reservation for one attempt; unknown reservations remain outstanding until ticket-38 reconciliation. |
| lease_id | One scoped Forwarder sentinel grant. It is revoked at cancellation/work deadline and invalid after restart. |

Execution state and effects are never collapsed into one enum.

Execution state is one of ADMITTED, HELD, LAUNCHING, RUNNING, INTERRUPTING,
FLUSHING, TERMINATING, SUCCEEDED, FAILED, CANCELLED, INCOMPLETE,
NEVER_STARTED, or CONTAINMENT_FAILED. NEVER_STARTED is terminal only for a
pre-dispatch refusal or a trusted spawn failure with no process created. A
budget or venue hold remains HELD and does not consume a new Run attempt.

Effect state is one of NOT_REQUIRED, JUSTIFIED_NOOP, NOT_DISPATCHED,
INTENT_RECORDED, DISPATCHED_UNKNOWN, PARTIAL, CONFIRMED, or
RECONCILIATION_REQUIRED. A successful execution may still have
DISPATCHED_UNKNOWN; an execution failure may still have CONFIRMED or PARTIAL
effects.

The derived lifecycle disposition is computed with this precedence:

1. CONTAINMENT_FAILED or an unconfirmed process group is containment failure.
2. Receiver timeout or cancellation is cancelled/interrupted, regardless of result.
3. Result error, error terminal reason, nonzero exit, or spawn failure is failed.
4. Missing, malformed, conflicting, or duplicate terminal evidence is incomplete.
5. A recognized non-error success result plus clean exit is execution success only
   when no earlier rule applies.
6. Effects are reported separately. Any required DISPATCHED_UNKNOWN or PARTIAL
   keeps the recovery gate held even when execution succeeded.

A missing usage field is shown as unknown. A model-reported success or textual
claim cannot move an effect to CONFIRMED.

### Typed record requirements

Each record declares supported `schema_version`/`event_type`, bounded canonical
size, and a digest. Unknown versions/enums, wrong scalar types, oversized fields,
non-monotonic `event_seq`, or a duplicate `event_id` with a different digest
hold the journal; an exact duplicate ID/digest is idempotently ignored. IDs are
opaque ASCII <=128 bytes, sequence numbers nonnegative bounded integers, wall
time UTC RFC3339, and monotonic time nonnegative bounded integers. The full
schema remains proposed until Receiver and ticket-38 owners ratify it.

`terminal_observation` has subtype enum, exact boolean `is_error`, bounded
nullable reason, exact boolean `exit_observed`, signed 32-bit exit code or
signal 1--64 when observed, `usage_state` (`known`, `absent`, `malformed`), and
evidence digest. Raw result/prompt/tool bodies are excluded; missing required
fields are rejected. `spawn_observation` has accepted/failed status, bounded
positive process/group IDs, monotonic start, exit/reaped/pipe flags, exit code or
signal, and containment (`contained`, `pending`, `failed`, `unknown`). Accepted
spawn without a trusted group is containment unknown, never proof of absence.

`effect_receipt` has fixed service, effect/operation/intent IDs, status
(`confirmed`, `failed`, `unknown`, `partial`), opaque provider ID, optional HTTP
class 100--599, read-back (`confirmed`, `absent`, `conflict`, `unavailable`),
target identity/version, response digest, and receipt time. Exclude credentials,
auth headers, and raw responses. Missing correlation/read-back is unknown;
conflicting receipts are retained and held, never last-write-wins.

Terminal validation is deterministic before classification: accept exactly one
recognized terminal record; require an exact boolean error indicator, a recognized
subtype, and an explicit process exit observation. Preserve a separately named
terminal reason and usage state. A second terminal, an unknown subtype, a
non-boolean error indicator, a missing exit, malformed encoding, or conflicting
terminal fields produces INCOMPLETE. The reported terminal and the Receiver's
derived disposition are both journaled; normalization never silently repairs a
contradiction.

Lease lifecycle is explicit: register a scoped sentinel before launch and
activate it only for the admitted run. Controller time records boot/clock
identity; persisted monotonic values from another boot cannot extend deadlines.
Hard validity ends at the earliest cancellation, 270-second work deadline,
venue/reference revocation, or containment failure. Grace is
`min(cancel+20s, launch+290s)` then kill/reap `min(cancel+30s, launch+300s)`;
neither extends the allowance. Revoke before interrupt; restart invalidates all
leases. Already-dispatched work may finish unknown, but no new request may use
an expired lease.
## Durable journal

A single Receiver-owned transactional store is the preferred implementation.
Journal tables and the ticket-38 accounting tables have separate purposes and
access controls but share a transaction for admission, reservation intent and
dispatch gating where practical. If accounting is a separate store, use an
explicit reservation_intent -> reservation_confirmed|reservation_unknown
handshake and recovery scan; never assume two stores commit atomically.

Every record has these common fields: schema_version, journal_generation,
event_id, monotonic event_seq, event_type, wall and monotonic timestamps, actor
(receiver, spawner, forwarder, or operator), and applicable identity fields from
the table above. Records are append-only. A durable commit means the store's
configured WAL/sync acknowledgement, not an in-memory callback. An optional
hash predecessor and record digest support corruption detection.

The bounded sanitized source record contains source_group, Fingerprint, status,
bounded numeric values, source event time if supplied, arrival sequence, canonical
digest, and provenance path/line. It contains no raw HTTP body, prompt, tool body,
credential, repository Ground truth, or unbounded model text.

The required record types are:

- admission: validated source record and admitted or held decision.
- dedupe_decision: latest baseline key, source group, and admitted, suppressed, or
  pending_reduced result.
- run_hold: dispatch gate, hold reasons, pending source IDs, and capacity,
  budget, or venue references.
- reservation_intent and reservation_receipt: amount, envelope,
  lifecycle/diagnostic bucket, reservation ID, policy reservation `R`,
  defensible liability `U`, coverage status, accounting-summary reference, and
  accounting status; no billing secret. Unknown/partial charges retain `U` or
  an indeterminate accounting hold, never a guessed zero.
- run_intent: input admission IDs, job/attempt/run IDs, lease scope, work and
  hard deadlines, and reservation ID, written before spawn.
- spawn_observation: process-group identity, accepted/failed observation,
  containment handle and bounded exit metadata; no command body or credential.
- terminal_observation: normalized subtype, error indicator, terminal reason,
  exit status, usage-known flag and evidence digest.
- effect_intent: effect/operation/intent IDs, target service, operation kind,
  target OPS identity, payload schema and digest, written before Forwarder
  dispatch.
- effect_receipt: trusted Forwarder receipt identity, response class, read-back
  identity/version and digest, and confirmed, failed, unknown, or partial state.
- reconciliation: operator, time, evidence references, observed external state,
  disposition and whether a fresh operation is authorized.
- operator_action: cancel, inspect, reconcile, retry, resume, abandon, or reset,
  with actor and reason.
- capacity_hold, restart_recovery, handoff_manifest, and reset_commit: explicit
  lifecycle transitions, never implicit cleanup.

### Transaction ordering

1. Validate and bound ingress. In one durable transaction append admission, its
   latest-admitted baseline update, and a dedupe decision. Commit before the
   Receiver acknowledges successful admission. If this commit fails, return
   retryable backpressure/hold and do not claim admission.
2. If a run is ineligible, append `run_hold` only; do not create an attempt,
   launch intent, sentinel, or process. If eligible, durably confirm a budget
   reservation with valid R/U coverage and no accounting hold, append and commit
   run_intent, then register the lease and commit the launch claim before
   creating a process. A held Notification remains retained and coalescible.
3. Record spawn acceptance/failure immediately after the real spawner observation.
   No model result can substitute for a spawn receipt.
4. Before every external mutation, append and commit effect_intent. Only then
   call the real Forwarder with the scoped sentinel. Append the trusted receipt
   and read-back before marking the effect confirmed.
5. At cancellation/work deadline revoke the lease first, then interrupt the
   process group. Permit only bounded local flush and evidence writes. Append
   terminal, containment, reservation and effect states before releasing or
   holding dispatch.
6. A journal commit failure puts the affected path into a visible hold. It never
   triggers a blind external retry.
## Dedupe, failed work, and recovery merge

Exact duplicate suppression compares the canonical source tuple to the latest
admitted tuple in the same source group. Thus failed A, newer B, and newer A
are all admitted when each differs from the current latest tuple; a repeated A
after the final A is suppressed. Cross-group equal records are not suppressed by
this rule.

While a job is held or running, pending reduction retains only the latest arrival
per Fingerprint plus its source group, but stores every admission identity and
arrival order in the journal. Reduction never deletes a failed effect obligation.
For failed A/new B/A:

1. Keep failed A's job_id/effect_id and its effect state.
2. Admit B and then A because each differs from the latest admitted tuple.
3. On recovery, reconcile A's prior effect before any new dispatch.
4. Derive fresh work from the outstanding obligation plus the newest admitted A,
   applying current Match eligibility and source provenance. Never replay an old
   command list.
5. A confirmed prior effect is not reissued. An unknown or partial effect stays
   held until trusted read-back or an explicit operator disposition.
6. One operator retry creates fresh run/attempt/reservation/intent IDs. A second
   failure holds dispatch again.

A suppressed repeat during recovery remains visible as a dedupe event and cannot
settle, delete, or downgrade the failed obligation. Incident aging out changes
Match eligibility for a new operation; it does not erase reconciliation duty.
## Crash, restart, and uncertainty

Recovery validates the complete durable journal chain before applying any prefix.
Corruption, truncation, an event-ID conflict, or an unverified tail is a
durable recovery hold: it cannot silently discard acknowledged admissions or
effects. Resume requires an authoritative reconstruction or handoff manifest
with digest/read-back agreement. Only then are incomplete transactions classified
according to these windows:

| Crash window | Recovery result |
|---|---|
| Before admission commit | No acknowledged admission; a repeat is safe to validate anew. |
| After admission commit before ACK | Admission is retained and deduped; ACK/replay is idempotent. |
| After ACK before run intent | Pending admission remains held. |
| After run intent before spawn observation | No process absence is proved; mark launch/containment unknown, inspect the process group, and hold. NEVER_STARTED is unavailable without a trusted no-process observation. |
| Spawn accepted before observation | Containment/spawn state is unknown; inspect the process group before retry. |
| Effect intent committed before Forwarder result | Effect is dispatched-unknown until trusted receipt/read-back; never retry blindly. |
| Receipt/read-back committed before process crash | Effect remains confirmed/partial independently of execution state. |
| Terminal result before local journal commit | Execution is incomplete/unknown; effect records remain authoritative. |

On Receiver, Forwarder, or spawner restart, old sentinels are invalid and all new
model dispatch is held. Reconcile process groups, journal intents, reservations
and external effects before operator resume. A fresh rehearsal generation cannot
adopt unresolved state by title or treat missing records as no effect.

Resolution order is trusted Forwarder receipt, then current OPS read-back with
identity/version checks, then operator disposition. “No response”, process exit,
or a missing receipt is not proof of absence. Confirmed OPS state is preserved
when optional Memory/export delivery fails. Unresolved state is exported in a
private handoff manifest before destructive reset; the handoff is not effect
confirmation.
## Bounds, retention, reset, and holds

The following are explicit proposed implementation limits, pending capacity
measurement: 128 MiB journal per rehearsal with a reserved 16 MiB recovery
region; 10,000 admissions; 1,024 retained pending source records; 128 recovery
jobs; one active Run with pending coalescing; 4,096 effect obligations; 4 KiB
canonical source record; 64 numeric values per source record. The implementation
must reject or hold before crossing a bound and expose the exact hold reason. It
must never evict unresolved effects to admit newer work.

After terminal resolution and with no unresolved effect, retain records for a
proposed 30 days, then compact to a digest/identity manifest. Retain unresolved
or operator-abandoned obligations until explicit reconciliation or a verified
handoff. Capacity exhaustion, failed durable writes, corruption, or overdue
retention holds new model dispatch and reports the affected records; it does not
drop admitted Notifications.

Reset is operator-only. It requires ordinary admission and dispatch held, no
active process groups, every effect confirmed/justified or explicitly handed
off, accounting reservations reconciled or carried in the handoff, a private
manifest exported and read back with digest equality, and all old sentinels
revoked. Reset increments journal_generation, invalidates old IDs for dispatch,
and records reset_commit. It cannot reset ADR 0013 weekly spend, unknown
charges, or unresolved external effects.
## Budget, venue, references, and revocation gates

The dispatch gate is the conjunction of durable journal health, capacity, a
confirmed ticket-38 reservation with valid R/U coverage and accounting summary,
no accounting hold, mandatory Forwarder readiness, venue readiness, operator
resume, and no unresolved recovery hold. A budget hold retains and coalesces
bounded Notifications; it never silently discards them. Every retry reserves
again and unknown provider charges retain U or an indeterminate hold.

Venue readiness includes ADR 0016's five-minute healthy baseline and freshness
checks. At cluster age 85 no new Run launches. At age 90 ordinary Fault
injections and Run dispatch are held; bounded Notification admission may continue
until protected teardown explicitly stops it. Active admitted work retains its
existing 300-second bounds. Export preserves obligations and does not authorize
resume.

If ADR 0017 revokes an approved reference, stop new reads, mark exposed Runs
affected, cancel them through the same bounded path, and hold dispatch until
review. Track exact page/version delivery; unknown exposure is conservatively
affected. Reconciliation and review precede any fresh-context retry.
## Acceptance matrix and evidence boundary

Acceptance must exercise real seams; deterministic adapters may control timing and
provider-free outcomes but cannot replace the boundary under test.

| Gate | Required acceptance | Does not prove |
|---|---|---|
| Receiver admission | Real HTTP Notification endpoint: durable admission before ACK, latest-group dedupe, A/B/A, capacity/backpressure, and restart replay. | Live Grafana scheduling or model quality. |
| Spawner/containment | Real Receiver spawner and process group: spawn failure, SIGINT window, descendants holding pipes, kill/reap, containment failure and lease revocation. | Universal OS isolation without intended-venue evidence. |
| Forwarder effects | Real scoped Forwarder endpoint: intent-before-dispatch, trusted response/read-back, timeout/disconnect unknown, no direct route, revocation and one retry only after reconciliation. | Provider billing or live tenant authorization. |
| Journal restart | Kill/restart Receiver around every crash window; inspect durable records, held dispatch, invalid sentinels and no replay of confirmed effects. | Durability after cluster destruction. |
| Accounting/venue | Ticket-38 reservation/unknown-charge seam plus real venue readiness/age inputs; prove holds preserve pending work. | Current prices, cloud billing, or a safe lifetime beyond accepted gates. |
| Reference revocation | Revoke a page/version after delivery; prove cancellation, affected marking and fresh-context hold. | Human publication or Confluence tenant grants. |
| Operator controls | Real operator-only cancel, inspect/reconcile, retry, resume, abandon and reset with audit identities. | A prompt/model following policy without enforcement. |

The acceptance harness may use a deterministic local process, but it must drive
real Receiver/spawner/Forwarder boundaries and label model signal, containment,
venue storage, and live OPS evidence separately. Stubbed Match, synthetic
terminal lines, and adapter-only mutation are not runtime acceptance.
## Source basis and remaining gaps

Primary sources: ADRs 0011, 0012, 0013, 0016, 0017; issues 37
(`.scratch/many-alerts-one-incident/issues/37-run-recovery-and-admission-specification.md`),
21, 31; ticket-21 reviews `round-1.md`, `round-2.md`,
`refusal-recovery-contract.md`; ticket-31 `fixture-spec.md`, `source-checks.md`.

The accepted sources do not choose physical database technology, exact journal
capacity/retention, an accounting transaction boundary, a process-spawner API,
Forwarder receipt schema, operator authentication syntax, or native tenant
read-back fields. The limits, field names, WAL/transaction recommendation and
30-day compaction period above are proposed routine choices and require review.
Ticket 38 owns accounting persistence/attribution; tickets 36 and 39 own
Forwarder/integration details. Real Receiver, spawner, Forwarder, OPS,
Confluence, venue, provider and crash/restart acceptance remain NOT RUN.
