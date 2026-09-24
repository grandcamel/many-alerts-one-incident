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
full suite reports 3799 passed, 38 skipped. The admission transaction (15b),
Receiver integration, Run and effect records, accounting, reset and
reconstruction remain open, as do venue durability and isolation from Runs.
This ticket stays open.
