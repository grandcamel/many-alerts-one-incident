# Ticket 23 single synthetic Incident store plan

Baseline: f6563c5. Implement a trusted single-threaded in-memory store for the fixed timing
Notification only. This is not live Jira, a native binding, a general Incident database or
persistent recovery. No real OPS fields/permissions or production matching are qualified.

1. Require a retained notification.get response from TimingQueries, sharing its Lifecycle.
   Expose a confirmed empty candidate snapshot initially; permit at most one synthetic
   Incident. Match judgment remains outside this deterministic store.
2. Accept strict create/append payloads with known Notification members, seven Report
   sections, per-Alert explanation inventory and references to retained query responses.
   Validate reference identity/index, not semantic support. Add member labels, preserve a
   fixed unrelated fixture label, ratchet severity/urgency and keep source fixed. Updates
   use an expected revision and append immutable Report content, preserving corrections.
3. Separate admitted dispatch receipt from effect completion and retained effect receipt.
   Allow one pending write; no queue, duplicate request ID, overwrite or blind replay.
   Controller-only fixture completions cover confirmed, definite failure, unknown before
   apply and unknown after apply. Failures/unknowns hold further writes with no clear API.
   Revocation denies new dispatch while allowing completion of the already dispatched work.
4. Bound Report bytes, section/identity/reference sizes and total admitted writes. Read-back
   returns copies with source/digests and scope; restarts lose the store and prove no recovery.
   These receipts are correlation observations, not authenticated transport or cost evidence.
5. Test empty/create/append/read-back, member and revision conflicts, preserved labels/history,
   citation linkage, bounds, stale requests, pending/revoked calls and both uncertain-effect
   windows. Run full suite, independent Standards/Spec and fresh bounded Fable source review.

No Run-visible Skill installation, native adapter, auth, durable journal, real Incident effect,
human scoring, ledger reconciliation, model probe, container or tenant operation is included.
