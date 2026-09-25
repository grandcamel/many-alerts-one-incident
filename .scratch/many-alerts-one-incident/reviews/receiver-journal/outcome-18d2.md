# Unit 18d2 journal claim outcome

Status: **PASS_LOCAL_CLAIM_REPLAY**, 2026-09-25. Fixed point: `f107120`.

The journal now accepts and replays private v2 `reservation_intent` and
`reservation_confirmation` records. A pure planner requires a current pending
membership digest matching a committed `run_hold`, canonical cross-store IDs,
fresh attempt identities and bounded recovery capacity. A confirmation
stores only a claimed ledger event identity. Replay rejects duplicate or
cross-intent reuse and retains the original Run hold after admission
supersession or restart. Verify-only inspection exposes count and a separately
tagged claims digest, without claim contents or a permit. There is no
application writer.

The [design](design-18d2-journal-claims.md), [plan](implementation-plan-18d2.md),
[plan review](review-18d2-plan.md), [source review](review-18d2-source.md)
and [validation record](validation-18d2.json) bind this local gate. Both
independent source reviews pass after a partial-supersession fix. The guarded
journal block passed **218** tests with `NON_LOOPBACK_ATTEMPTS []`; Ruff,
line and whitespace checks passed. The full repository suite passed **5255**
tests with **39 skipped**.

No verified ledger adapter, production reservation, Run intent, effect
record, dispatch permit or launch path is present. The Receiver-facing ledger
still refuses `reservation_created` while its population is unknown. Actual
older-binary execution is **NOT RUN**; current tests pin v1 compatibility
and classify unknown future pairs. Trusted opening history, provider line
identity/coverage/lag, liability U, continuity witness and archive/repair
policy remain unresolved. Native, provider, tenant, venue, paid execution,
power-loss durability and human Report adjudication were **NOT RUN**. Tickets
37 and 38 remain open. No push, publication, C2 retry or provider/model call
occurred.
