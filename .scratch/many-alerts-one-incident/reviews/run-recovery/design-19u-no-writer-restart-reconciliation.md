# 19u: no-writer reconciliation observation after Receiver restart

Status: proposed local design, 2026-09-25. Fixed point: 19t pending.
Authority: accepted ADR 0012 and ticket 37. This extends 19t's Jira OPS
read-back **claim history**, not effect settlement, operator disposition,
hold clearance, retry or a live OPS read.

## Restart boundary

19t deliberately accepts only the original launch boot. A Receiver restart
holds dispatch and invalidates old sentinels, but outstanding effects still
need a fresh OPS read. The journal already replays the prior effect intent,
the `restart_recovery` commit, `boot_start_commit_seq`, recovered predecessor
head and current boot. A new no-writer record family can preserve a later
claimed read without treating the original boot's authority as current.

Add private v3 recovery record `restart_reconciliation_observation`, actor
`receiver`, bound to the existing Jira mutation effect intent/operation,
current journal/Run/attempt, current Receiver boot, exact predecessor head,
restart commit sequence and its durable record digest, and the recovered
pre-restart head. The reducer must retain the boot-start record digest from
verified genesis/restart replay without changing the v1 state digest. Require
`restart_recovery` as this boot's start, the `restart_recovery` dispatch hold
still active, and the referenced effect intent committed in an earlier boot.
The newest verified restart record and boot-start digest anchor the claim;
the active hold's stored origin commit may be from an earlier restart and is
not required to equal this boot's restart sequence.
No old grant or permit is revived. A fresh read-back writer remains absent.

Use 19t's closed Jira OPS mutation route map and issue/comment read-back
source kinds. Store a closed reported state `confirmed`, `absent`, `conflict`
or `unavailable`, source-evidence digest, effect target digest and nullable
version digest with 19t's matrix. Every state is `reconciliation_unqualified`.
`absent` is never proof of no prior write. Record each observation in an
append-only per-operation sequence and show the boot boundary explicitly;
never choose the last value as the external truth.

Allow at most four restart observations per operation across **all** new
boots, not four per boot. At the 64-operation cap and a 3,072-byte body plus
384-byte overhead, the additional recovery obligation is at most 884,736
bytes. Exhaustion holds the effect for operator review; it cannot erase an
uncertain write or authorize reset. This is additive to 19t's original-boot
622,592-byte obligation. An actual writer must preflight both.

## Local acceptance and remaining gate

Test restart binding, prior-boot intent requirement, active restart hold,
claim disagreement, exact predecessor/recomputed forgery, cap/bytes,
multiple restarts, mixed-version reopen and old-decoder refusal. Pure
inspection labels all states unqualified. No writer, new attempt, fresh
operation, operator identity, effect truth or disposition is inferred.
Native, provider, paid, tenant, venue, power-loss and human acceptance are
NOT RUN. A positive reconciliation/authorization transition still requires
a trusted current OPS source, route/tenant grants, actor authentication,
read-back identity/version semantics and human decision.
