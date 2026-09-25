# Run recovery and admission specification

Type: task
Status: open
Blocked by: 16, 21, 22, 36

## Question

Produce an implementation-ready specification for [ADR 0012](../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md), not runtime code. Define the execution/effect state model, terminal schema validation and precedence, trusted operation receipts, justified no-ops, visible unknown usage and operator controls. Integrate the planning-only [refusal contract](../reviews/ticket-21/refusal-recovery-contract.md) with ticket 16's compact Report and ADR 0011's Forwarder enforcement; the model's prose is not a receipt.

Specify the Receiver-owned durable journal's schema, storage/mount/access boundary, admission-before-ack ordering, mutation-intent-before-dispatch ordering, dedupe baseline and failed/pending merge. Cover crash windows between dispatch, upstream effect and local confirmation, restart-held dispatch, reconciliation after an Incident ages out, explicit reset disposition and bounded queue/journal capacity. Keep OPS authoritative; no raw prompt/tool bodies, credentials or Ground truth in the journal. Integrate tickets 32/35/36 without making their implementation a prerequisite for writing this specification.

Specify 270s work + 20s interrupt/flush + 10s kill/reap within the 300s total, early cancellation, sentinel lease/revocation timing, and containment failure without falsely declaring cleanup complete. Extend ticket 31's offline fixture contract with false-success terminal records, nonzero exits, missing/malformed/duplicate results, confirmed and uncertain writes, pre-dispatch denial and one compact retry, optional secondary failure, silent work, parent exit with descendants holding pipes, journal failures/full capacity, failed A plus newer B/A, repeated dedupe during recovery, restart and operator retry/resume.

Require real Receiver/spawner/Forwarder boundaries for offline acceptance; do not present stubbed Match or model outcomes as real diagnosis/CLI behavior. Record separate model-signal, host containment, intended-venue storage and live OPS acceptance requirements. No model, cluster, demo, live write or runtime implementation is authorized by this planning task.

ADR 0013 adds budget admission holds and durable spend reservations. Integrate ticket 38's accounting interface without making ticket 38 a prerequisite for this specification: reserve before model launch, retain pending work on budget hold, count every retry, and never reset weekly spend or unknown charges with a rehearsal reset. Keep effect reconciliation required even when no paid Run may start.

## Accepted venue input from ticket 30

ADR 0016 holds new dispatch on venue-readiness failure and forbids Run launch at or after cluster age 85 minutes. Retain bounded Notification admission/pending work while active Runs keep their existing deadlines; age 90 holds admissions rather than deleting resources. Specify verified off-cluster handoff of unresolved effects and explicit operator ownership before source destruction; handoff is not effect confirmation.

## Accepted Confluence input from ticket 33

ADR 0017 adds reference-revocation cancellation: track delivered page/version identity, cancel exposed active Runs under the existing bounded deadline and hold new dispatch for operator review. Unknown exposure conservatively includes active Runs admitted to that manifest. Reconcile confirmed/uncertain effects and mark affected outputs for review; retry remains explicit and budgeted with fresh context. Cancellation does not undo OPS writes or erase read context.

## Specification progress, 2026-09-22

The [proposed implementation contract](../reviews/ticket-37/recovery-specification.md)
now records the concrete state, persistence, integration and acceptance requirements.
Accepted ADR policy remains distinct from proposed implementation choices. See the
[cross-ticket review](../reviews/recovery-accounting-audit-integration.md).
This planning artifact is not runtime, model, billing, tenant or venue acceptance;
the ticket remains open for its unresolved inputs and final integration.

## Local implementation progress, 2026-09-23

The reviewed [journal implementation plan](../reviews/recovery-journal/implementation-plan.md)
chooses SQLite in WAL mode plus a separately synced anchor file. Every storage
setting, limit and v1 semantic in it is a proposal awaiting ratification. Unit
[15a](../reviews/recovery-journal/outcome-15a.md) adds the sanitized source
record, the digest-chained record envelope, and a store that acknowledges only
after the COMMIT and the anchor sync. Verified integrity failures persist as
durable holds; transient failures never do. Independent review passes; the
full suite reports 3799 passed, 38 skipped.

Unit [15b](../reviews/recovery-journal/outcome-15b.md) adds the pure reducer
(ticket-31 dedupe, pending reduction, capacity and restart decisions, and
identical replay) and the shell. The shell's open verifies the whole chain,
adopts at most one unanchored commit and persists every verified integrity
failure; its admission receipt follows the COMMIT and the anchor sync. Crash
images cover the in-scope windows of spec L249-253. Independent review passes;
the full suite reports 4012 passed, 38 skipped. Receiver integration, Run and
effect records, accounting, reset and reconstruction remain open, as do venue
durability and isolation from Runs.

Unit [16](../reviews/journal-ingress/outcome.md) adds the raw ingress
sanitizer: one Grafana Notification body becomes a journal `SourceRecord` or a
closed-code refusal. Every 400-class check runs before any member-level 422, and
each 422 names its lost members, Resolved first. All 115 captures admit, and the
full suite reports 4443 passed, 38 skipped. Receiver integration with operator
resume, refusal persistence, Run and effect records, accounting, reset and
reconstruction remain open.

Unit [17a](../reviews/receiver-journal/outcome-17a.md) adds the journal side of
the Receiver integration, which the user chose to make opt-in:
- durable `ingress_refusal` records under the flood rule `first-per-membership-v1`;
- `operator_action` resume at open, which clears only `restart_recovery`;
- a verify-only inspect.

Replay re-derives every field of both new records. The full suite reports
4786 passed, 38 skipped. The body spool, the journaled front door (unit 17b),
Run and effect records, accounting, reset and reconstruction remain open. This
ticket stays open.

## Local implementation progress, 2026-09-24: unit 17b

Unit [17b](../reviews/receiver-journal/outcome-17b.md) completes the opt-in
admission front door, body spool and operator CLI. File and directory sync
precede journal admission, which precedes the 202. Bounded HTTP handling
records refusal summaries and reports health; verify-only inspect surveys
spool consistency, and startup resume remains tied to the inspected head.
The separate command starts no Run. Legacy modules, existing tests and the
17a journal modules/goldens remain unchanged.

Independent source/test review, mutation regressions and fresh hash-bound
review pass. Focused: 1645 passed, 30 skipped with the loopback guard clean.
Full suite: 4939 passed, 39 skipped. [Validation](../reviews/receiver-journal/validation-17b.json)
records hashes and limits. No provider, tenant, native-client, paid or deployment
qualification is claimed, and nothing is pushed.

Run/effect lifecycle still requires the durable ticket-38 reservation seam.
The next design starts with a pure accounting-policy prerequisite, without
launch authority or a no-reservation profile. Accounting, reset, retention,
reconstruction and other operator controls remain open. This ticket stays open.

## Local implementation progress, 2026-09-24: unit 19a

Unit [19a](../reviews/run-recovery/outcome-19a.md) adds a pure execution-outcome
classifier for bounded, sanitized process and terminal facts. It preserves
ADR 0012 precedence and reports missing usage as unknown. It has no application
caller and no effect, billing, reservation or launch authority. Independent
Standards and Spec source reviews found no remaining concrete blocker after a
conflicting-success-reason regression was added. The full local suite passed
5183 tests with 39 skipped. Versioned journal Run/effect records and replay,
Receiver provenance, Forwarder receipts, process containment and cross-store
dispatch remain open. This ticket stays open.

## Local implementation progress, 2026-09-25: unit 19b1

Unit [19b1](../reviews/run-recovery/outcome-19b1.md) adds an explicit v2
`run_hold` record and replay projection for a current pending admission. The
v1 registry, encodings, and goldens remain exact. A held job survives a newer
admission and a committed mixed-version store reopens and inspects locally.
The bounded per-job projection has no application writer and is separate from
the global dispatch hold. Independent Standards and Spec reviews pass after
the exact v1 registry correction; the full suite passed 5193 tests with 39
skipped. Reservation/ledger confirmation, attempt and effect records, a
writer that latches failed holds, and the permit gate remain open. This ticket
stays open.

## Local implementation progress, 2026-09-25: unit 18d2

Unit [18d2](../reviews/receiver-journal/design-18d2-journal-claims.md)
adds versioned journal reservation intent and confirmation claims with pure
planners, replay and count/digest inspection. A committed `run_hold` remains
held, including after partial pending supersession. The confirmation cannot
authenticate the separate accounting ledger. Independent
[source review](../reviews/receiver-journal/review-18d2-source.md) found no
remaining blocker. There is no application writer, Run intent, dispatch
permit, launch or Forwarder effect path. The ticket remains open.

## Local verification progress, 2026-09-25: unit 18d3a

Unit [18d3a](../reviews/receiver-journal/outcome-18d3a.md) adds a read-only
journal claim view that releases replayed intent/confirmation facts only from
an exact anchored head. It withholds facts on one-commit lag, WAL absence,
custody/replay findings and detectable close failure; the original public
inspection report is unchanged. A locked WAL recheck closes the observed
preflight/open disappearance window. Independent Standards and Spec reviews
pass; the full local suite passed 5260 tests with 39 skipped. There is no
application writer, reservation, Run/effect record, dispatch permit or launch
path. The ticket remains open.

## Local no-launch scan progress, 2026-09-25: unit 18d3b

Unit [18d3b](../reviews/receiver-journal/outcome-18d3b.md) reads the
independently verified journal and v1 ledger views for one intent and always
returns a hold. No claim, intent-only, and journal-confirmed stopped images
are covered by real SQLite tests; the current ledger contains no verified
reservation. The scanner neither writes an effect/Run record nor issues a
dispatch permit. Independent source reviews pass; the full local suite
passed 5274 tests with 39 skipped. Run/effect recovery, supervision and a
guarded launcher remain local work, and external accounting gates remain
unresolved. The ticket stays open.
