# Unit 19g: durable restart Run-hold writer plan

Status: local implementation plan, 2026-09-25. Fixed point: `923a003`.

## Scope and order

1. Add a public `RecoveryJournal.record_restart_run_hold(job_id,
   admission_id)` method. Require a ready journal whose replayed
   `restart_recovery` dispatch hold is active, plus a currently pending
   admission. The method supplies `reason=restart_recovery` itself, so no
   caller claim can invent the reason. It invokes the existing v2 planner and
   the sole `_commit` path; it creates no attempt, reservation, lease, Run,
   effect, permit or process.
2. Return a frozen receipt carrying the replayed job/admission/reason,
   `since_commit_seq`, member digest and `recorded` or `already_recorded`.
   An exact same-job retry reads the existing projection and writes nothing;
   a conflicting job/admission or failed required commit latches a process
   hold. A missing active restart hold is a closed no-write refusal.
3. Preserve recovery capacity rules. A planner capacity refusal or any
   uncertain append latches the journal; no absent hold is presented as
   durable. Do not change the v1 registry, record bytes, state digest or
   front-door HTTP semantics.
4. Test through real create/open/reopen SQLite/WAL histories: fresh-create
   refusal, restart-held pending admission, exact retry, later admissions,
   conflicting IDs, capacity, clock/ID fault, append failure and reopen
   retention. Verify the existing journaled front door remains admission-only.
5. Run focused tests, Ruff, independent Standards and Spec source reviews,
   then the full suite before code commit. Update ticket 37 with local evidence
   and leave accounting, permit, process and external gates open.

This writer can truthfully claim only the journal's own restart reason.
Accounting, venue, reference and effect reasons need their own independently
verified evidence bindings before public writers are added.
