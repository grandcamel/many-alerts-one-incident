# Unit 19g durable restart Run-hold writer

Status: **PASS_LOCAL_NO_LAUNCH_WRITER**, 2026-09-25. Fixed point: `923a003`.

`RecoveryJournal.record_restart_run_hold` writes one v2 per-job hold for a
currently pending admission only when its replayed global `restart_recovery`
hold is active. The reason is fixed by the journal. An exact retry returns the
committed hold without another record, including after an operator resume
clears the global hold. A second job claiming that admission latches
`journal_divergence`; a new unrelated hold without an active restart hold is
refused without a write. Capacity, clock, ID and append uncertainty latch a
process hold. The writer creates no attempt, reservation, Run, effect, permit
or process.

The [plan](implementation-plan-19g-restart-run-hold-writer.md) and independent
Standards and Spec reviews pass after two idempotency/ownership ordering
corrections. Nine focused real SQLite/WAL tests and changed-file Ruff pass.
The full local suite passes **5,443**, skips **39**, in 392.65 seconds. Tests
cover fresh-create refusal, exact retry, operator resume, later admission,
conflicting identity, absent admission, clock/ID faults, uncertain append,
capacity refusal, reopen and verify-only inspection.

No application caller, admission-to-job allocation, verified external reason
binding, positive accounting reservation, effect record, dispatch permit,
worker containment or guarded launcher was added. The Receiver-facing v1
accounting ledger still has `population=unknown` and rejects reservation
events. Native, provider, tenant, paid, venue, deployment, power-loss and
human adjudication are **NOT RUN**. Ticket 37 stays open. No push, publication,
provider experiment or credential change occurred.
