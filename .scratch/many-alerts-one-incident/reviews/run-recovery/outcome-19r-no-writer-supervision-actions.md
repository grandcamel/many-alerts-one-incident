# 19r outcome: unqualified supervision-action replay

Date: 2026-09-25. Fixed point: `f8682ad`.

The reviewed [design](design-19r-no-writer-supervision-actions.md) and
[implementation plan](implementation-plan-19r-no-writer-supervision-actions.md)
add private v3 recovery-capacity intent/result claims for per-grant revoke,
SIGINT and SIGKILL. Replay binds each to the current launch and, for signal
claims, the prior attestation witness fields and all grant-revoke intents.
It records blocked-pre-release, release-unknown and release-observed phases
without inferring whether the barrier byte crossed. Cleanup can be journaled
after a dispatch hold; a result may preserve history after the deadline.
The first cleanup intent stops new release-intent and effect-intent claims,
while an already intended release may still get a historical observation.
One revoke per grant and one of each signal bound the family to at most
seven intents/results and 48,384 worst-case recovery bytes. There is no
escrow or writer.

Independent Standards and Spec design/plan/source reviews pass after
correcting the held-cleanup, release-unknown, witness, boot, duplicate-action
and maximal-body edges. Ten direct 19r tests and 104 focused journal tests
pass; changed-file Ruff and `git diff --check` pass. The full local suite
passes **5,597 tests, 39 skipped in 397.23s**.

The records are replayable **claims**, not proof of a callback, actual
revocation, signal delivery, stable group identity/absence, Forwarder
closeout, early-stop trigger or due-time compliance. No process, grant,
permit, effect writer, durable reservation or production Run was added.
The ledger remains `population=unknown`. Native, provider, paid, tenant,
venue, power-loss and human acceptance are **NOT RUN**. Ticket 37 remains
open with the accounting and intended-venue gates.
