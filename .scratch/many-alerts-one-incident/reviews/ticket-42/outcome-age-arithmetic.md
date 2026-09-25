# Ticket 42a local venue age arithmetic outcome

Verdict: local source and tests PASS, 2026-09-25. Ticket 42 remains open.

This change adds deterministic age bounds over caller-supplied claims. The
calculation validates identity and scalar shapes, preserves the prior lower
and upper bounds across same-boot elapsed time or a new boot, and rejects
rollback, lost anchors and overflow. It returns descriptive bounds only.

Independent Standards and Spec reviews both passed after stronger prior-lower
fixtures were added. Focused tests: 19 passed. Ruff: passed. Full suite:
5,341 passed, 39 skipped in 375.37 seconds; see
`full-suite-age-arithmetic.txt`. `git diff --check` passed before the suite.

No provider receipt was authenticated. Provider timestamp placement,
off-cluster persistence, current resource identity, health and cost admission,
protected handoff, deletion, and intended-venue acceptance are unproven.
Native/provider, tenant, venue, paid and power-loss experiments: NOT RUN.
This change grants no Run, Fault, dispatch, creation or teardown permit.
