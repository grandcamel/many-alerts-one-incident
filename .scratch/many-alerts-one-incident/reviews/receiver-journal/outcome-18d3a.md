# Unit 18d3a verified reservation views

Status: **PASS_LOCAL_VERIFIED_VIEWS**, 2026-09-25. Fixed point: `a6830a8`.

The journal now exposes immutable reservation intent and confirmation claims
only after a verify-only full replay with an exact anchored head. WAL absence,
one-commit anchor lag, a store finding, and detectable close failure return no
facts. WAL presence is rechecked after taking the store lock and before
SQLite opens, then checked from the opened store's observation. The existing
public `inspect_recovery_journal` report keeps its count/digest shape and
one-commit reanchor description.

The v1 accounting store now exposes a separate query-only view of its
verified Receiver/`unknown` identity and head with an **empty** reservation
tuple. The current store rejects fixture genesis and every
`reservation_created` event on create and replay. The view cannot return a
positive durable reservation or authenticate a journal confirmation. Both
views describe stopped images separately; neither writes a claim, reserves
money, joins the stores, permits dispatch or launches a Run.

The [design](design-18d3a-verified-views.md),
[plan](implementation-plan-18d3a.md), [plan review](review-18d3a-plan.md),
[source review](review-18d3a-source.md) and
[validation record](validation-18d3a.json) bind this local checkpoint.
Independent Standards and Spec source re-reviews pass after the locked WAL
guard and direct custody/corruption regressions. The guarded store/journal
block passed **352**, skipped **2**; changed-file Ruff and whitespace checks
passed. The full local repository suite passed **5260**, skipped **39**, in
371.20 seconds with demo flags unset.

Production reservation remains gated on authoritative opening history,
provider charge-line identity/coverage/lag, defensible liability U, an
independent continuity witness, and archive/repair policy. A matching
cross-store triple is not available in the v1 ledger. The next local unit
may scan verified negative cases but must remain a hold. Native/provider,
tenant, venue, paid, power-loss, older-binary execution and human Report
adjudication are **NOT RUN**. Tickets 37 and 38 stay open. No push,
publication, C2 retry or provider/model call occurred.
