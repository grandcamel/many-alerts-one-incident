# 39b outcome: content-free exchange candidate precheck

Status: reviewed local source and synthetic verification, 2026-09-25.
The [design](design-39b-exchange-candidate-precheck.md) adds a pure check
that compares claimed request/response states with canonical 39a loss
markers. Gap states require a marker with matching bundle, exchange, side
and state; `empty` and `returned` require no marker. Request and response
loss records cannot reuse one loss ID. Every result is
`capture_unverified`, including a pair with no structural defects.

Independent Standards and Spec source reviews pass. The Spec review found
that two markers could reuse one loss ID; a fixed defect and distinct
normal-fixture IDs resolved it, with a passing re-review. The focused 39a
and 39b suites passed **48 tests**; Ruff and `git diff --check` passed.
The full local suite passed **5,773 tests, 39 skipped in 419.43s**.

This candidate has no trusted capture hook, returned response bytes,
source scope/order, provenance, redaction, private storage, retention,
human support review or `exchange-v1` authority. Native, provider, paid,
tenant, venue and human acceptance are **NOT RUN**. Ticket 39 remains open.
