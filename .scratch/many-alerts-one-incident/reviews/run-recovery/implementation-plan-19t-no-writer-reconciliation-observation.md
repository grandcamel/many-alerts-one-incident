# 19t implementation plan: unqualified Jira reconciliation claims

Fixed point `d2a4067`; reviewed design
[19t](design-19t-no-writer-reconciliation-observation.md). This is a
multi-file local source change with no OPS read, writer, effect settlement,
retry, disposition or hold clearance.

1. Extend the private v3 record codec with a recovery-class
   `reconciliation_observation` and a 2,048-byte body cap. Closed route and
   source-kind mapping, reported state, digest/null matrix and exact types
   must reject unrelated model/read-only/Confluence effects.
2. Add pure planner/replay in the reducer. Bind the current Jira mutation
   intent, launch, target digest, predecessor, original boot and monotonic
   observation. Permit at most four observations per operation; preserve all
   claims in append order, including conflict, without deriving a winner.
   Charge recovery bytes; reject new intent/event/capacity mismatches.
3. Add live/stopped read-only inspection of counts, digest and reported
   per-operation sequences, always `reconciliation_unqualified`. No writer
   method or positive effect classification.
4. Test codec/replay, mismatched route/source/target, forged predecessor,
   competing observations, count and byte caps, late same-boot append,
   restart refusal, mixed-version reopen and old decoder. Obtain independent
   Standards and Spec source reviews, run Ruff and `git diff --check`, then
   the full suite before a named-path local commit. Recheck the protected
   ticket-19/planning/C2/panel baseline before committing.

Native, provider, tenant, venue, paid, power-loss and human acceptance are
NOT RUN. Post-restart reconciliation needs a separate contract.
