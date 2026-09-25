# Unit 19i1 no-writer first-attempt intent outcome

Status: **PASS_LOCAL_NO_WRITER**, 2026-09-25. Fixed point: `508887e`.

The private v3 `reservation_intent` record opens a stable first-attempt job
from current pending admission membership without fabricating a v2 hold. Its
planner/replay binds canonical identities, membership count/digest, the
ordinary-byte ceiling and a separately tagged projection digest. It refuses
global holds, unresolved v2 holds or v3 jobs, ownership conflicts, reused
identities, stale membership and recomputed-field forgeries. A later v2
`run_hold` may attach to the exact same job/admission but cannot create a
second job for that admission. V1 public registry, v2-only replay/digests
and stored bytes remain unchanged.

Snapshot, verify-only inspection and the stopped claim view expose a v3
count/digest and explicit outstanding status or typed claim. They do not
confirm a ledger reservation or grant dispatch. The reviewed
[implementation plan](implementation-plan-19i1-first-intent.md) and
independent Standards/Spec source reviews pass after the ownership and
visibility corrections. Focused journal tests: **79 passed**; changed-file
Ruff passes. The full local suite: **5,473 passed, 39 skipped** in 385.84s.
The reopened SQLite/WAL test verifies mixed v1/v2/v3 history and a simulated
older decoder's `journal_schema_unsupported` process hold.

There is no application writer, v3 confirmation, positive accounting
reservation, service grant mapping, Run, process or permit. The v2 hold
planner still needs current pending members, so a superseded v3 job requires
a later versioned recovery-obligation transition. The Receiver ledger remains
at `population=unknown` and rejects reservation events. Native, provider,
tenant, paid, venue, deployment, power-loss and human adjudication are
**NOT RUN**. Tickets 37 and 38 stay open.
