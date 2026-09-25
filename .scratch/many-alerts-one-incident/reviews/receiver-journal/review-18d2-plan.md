# 18d2 design and plan review

Status: **ACCEPT_LOCAL_18D2_CLAIM_PLAN**, 2026-09-25. Fixed point:
`d871a63`. Independent Standards and Spec reviewers read the local design,
implementation plan, accepted ADR 0013, tickets 37 and 38, the 19b versioning
design and current journal/accounting contracts. They made no edits and ran no
tests. This verdict authorizes only local claim-record source work.

## Standards

The first draft did not require every ID that 18d1 validates to be pairwise
distinct. The revised design requires distinct journal origin, admission,
job, intent, attempt, reservation, Run and lease IDs, and the plan tests
collisions with historical IDs. The reviewer re-read the fix and found no
remaining blocker. A final scan of confirmation identity, ledger event reuse,
digest ordering and superseded holds found no new Standards issue.

## Spec

The first draft overconstrained existing v1 admission/job IDs as UUIDs and
could imply journal absence meant no ledger liability. The revision leaves
historical non-UUID IDs replayable but held for a new intent, requires a
verified scanner to find orphan ledger events, keeps the older held job after
pending supersession, and freezes a fresh confirmation ID, claimed ledger
event uniqueness and the exact sorted claims digest. The reviewer re-read all
five corrections and found no remaining claim-only plan blocker.

## Scope

No source or tests changed in this planning checkpoint. Full and focused
tests are **NOT RUN** for this docs-only commit. The future source review must
check replay, identity, capacity, crash windows, v1 compatibility and the
absence of a permit. Production reservation, verified-store adapter, Run
launch, native/provider/tenant/venue/paid execution, power-loss durability
and human Report adjudication remain **NOT RUN**.
