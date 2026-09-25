# 19u implementation plan: post-restart reconciliation claims

Fixed point `5cd58c8`; reviewed
[design](design-19u-no-writer-restart-reconciliation.md). This is a
multi-file local source change. It makes no OPS read or positive decision.

1. Retain the verified boot-start record digest in the pure projection when
   genesis or restart commits replay. Keep v1 `state_digest` unchanged. Add
   a private v3 recovery-class `restart_reconciliation_observation` codec
   capped at 3,072 bytes, with closed fields, digest/null matrix and exact
   UUID/sequence/type checks.
2. Add a pure planner/replayer for prior-boot Jira mutation intents. Bind
   the latest verified restart commit/digest and recovered head, current
   boot, exact predecessor, effect intent/target and active restart hold.
   The hold's origin may be older than this boot's restart commit. Bound
   four observations per operation across all recovery boots, charge
   recovery bytes, preserve conflicting claims in append order.
3. Add read-only live/stopped inspection with boot-labeled reported states,
   always `reconciliation_unqualified`. No writer, effect settlement, retry,
   hold clearance or operator disposition.
4. Test prior-boot and hold predicates, latest restart binding across two
   restarts, forged fields, conflicts, count/byte caps, late observation,
   mixed-version reopen and old decoder. Obtain independent Standards and
   Spec source reviews, run Ruff, `git diff --check`, then the full suite
   before a named-path local commit. Verify protected preexisting paths and
   panel manifest before committing.

Native, provider, paid, tenant, venue, power-loss and human acceptance are
NOT RUN. Positive reconciliation and resume remain externally gated.
