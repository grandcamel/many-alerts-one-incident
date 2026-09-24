# Unit 18a outcome

Status: PASS_LOCAL_PURE_ACCOUNTING_POLICY, 2026-09-24.
Baseline: `1d04b7dc1174924de52a8927059f9eb6cbaca3a3`.

Implemented [accounting_policy.py](../../../../grafana_jsm_sandbox/accounting_policy.py)
and [its tests](../../../../tests/test_accounting_policy.py), documented in
[accounting-policy.md](../../../../docs/accounting-policy.md). All existing
source, tests, goldens and prior 17b records are unchanged.

The component validates exact USD microdollars, computes explicit New York
week boundaries, derives retained liabilities/counts from hypothetical history,
and evaluates fixed reservation ceilings. Retries count once weekly/lifetime
and against both buckets. Unknown/stale/conflicted history refuses; settled
hypothetical actuals do not erase counters. Outputs are immutable proposals or
closed refusals, with no application caller, receipt, state mutation or dispatch.

The [exact plan](implementation-plan-18a.md) was critiqued before coding;
[review](review-18a.md) records independent Standards/Spec/fresh final review
and the repaired identity finding. Production module: 413 lines, within the
600-line bound. Six deliberate policy mutants were killed.

- Full suite: **5062 passed, 39 skipped**, 381.23s.
- Focused suite: **123 passed**, no non-loopback attempts.
- Ruff, E501, whitespace and baseline/protected hashes: PASS.
- [Validation and hashes](validation-18a.json).

The ticket-38 durable reservation seam remains unmet. Stored history,
configuration, profile, reconciliation and complete-coverage inputs are explicit
hypothetical assumptions. This does not authenticate them or enforce provider U.
Semantic misclassification of failed work, cross-week retry, refunds/import,
apply/replay, persistence, reconstruction, concurrency and archive capacity are
not implemented. Provider/native/tenant/venue/paid execution and human Report
adjudication: **NOT RUN**. Ticket 38 and Run lifecycle remain open.

Next local work is a separately reviewed accounting transition/durability
unit: settle its scope and physical-storage/identity/migration or cross-store
handshake design before implementation. It must preserve complete lifetime
history, serialized re-evaluation and no-launch recovery. An 18a proposal cannot
be substituted for a durable receipt. Continue from this outcome alongside the
[existing queue](../../execution-backlog.md); its 17b hash-bound record remains
historically intact. No push/publication or C2 retry occurred.
