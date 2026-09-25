# 18d2 source review

Status: independent read-only Standards and Spec reviews of the 18d2 local
diff against `f107120`, 2026-09-25. Reviewers made no edits or test runs.
Parent validation is recorded separately.

## Standards

The reviewer found a correctness blocker: the first planner checked that at
least one member of the held admission was still pending, so a partially
superseded job could form a stale reservation intent. The planner now compares
the sorted current member digest to the committed `run_hold.member_digest`;
a two-member partial-supersession regression verifies the hold. The reviewer
rechecked this correction and found no remaining blocker. A separate v2
recovery-class map now describes both claim record pairs. The broader journal
tests also exposed the reducer's exact import allowlist; replacing the new
`re` import with a fixed-position UUID check restored that pin.

## Spec

The reviewer found no implementation blocker. The source keeps the v1 public
registry and digest contract exact, replays only the private v2 pairs,
recomputes the intent digest, rejects stale membership, enforces identity and
claimed ledger reuse, charges bounded recovery bytes and leaves the Run hold
unchanged. Its suggested test gaps were closed with every intent identity
pair, confirmation/ledger collisions, pre-intent and intent-only committed
images, restart between claims and a re-signed false intent in a real store.
The reviewer re-read the expanded tests and found no remaining blocker.

## Authority boundary

The confirmation is a journal claim. It cannot authenticate a current ledger
event. No application writer or permit uses these records, and the
Receiver-facing accounting ledger still refuses production reservation.
Actual execution with an older binary is **NOT RUN**; the current tests pin
v1 registry compatibility and classify unknown future pairs as a process
hold. Native, provider, tenant, venue, paid, power-loss and human Report
adjudication remain **NOT RUN**.
