# 19v: fence v1 restart resume on unresolved private claims

Status: proposed local safety design, 2026-09-25. Fixed point: 19u pending.
Authority: accepted ADR 0012 and the v1 `resume-at-open-v1` contract. This
unit does not add a positive disposition, retry, effect settlement or
operator decision.

## Demonstrated source gap

A local pure replay with a v3 Jira effect intent, then `restart_recovery`,
then `operator_action=resume` passes today and clears the sole
`restart_recovery` dispatch hold while the effect intent remains. The v1
resume rule checks immediate position, inspected head, pending digest and
operator fields, but has no predicate for later v2/v3 reservation, Run,
launch, effect or recovery claims. In the sampled source state this changes
`dispatch_holds` from `{'restart_recovery': 11}` to `{}` with one unresolved
effect intent still projected. No tenant or native action was run; this is a
local pure replay counterexample.

## Fail-closed repair

Keep `resume-at-open-v1` limited to a journal prefix with no private
reservation/Run/effect/recovery claim. Add one pure predicate for private
outstanding state: v2 reservation intents/confirmations or Run holds; v3
initial intents/confirmations, Run intent, launch/spawn/release, effects,
supervision actions, process/terminal/assessment, original/new-boot
reconciliation claims. The predicate is conservative because none of these
families has a positively authenticated terminal disposition transition.
It must not infer that a claimed `NOT_DISPATCHED`, `succeeded`, `absent` or
`confirmed` resolves the obligation. Ordinary pending admissions alone
remain under the original v1 resume rule.

The pure planner refuses to create a resume record when the predicate is
true; replay refuses a forged or historical v1 resume at that prefix. The
`open_recovery_journal` resume-at-open shell sees the predicate before
planning and leaves `restart_recovery` held without a resume receipt. It
must not mislabel this as capacity exhaustion, erase claims, or crash.
An existing journal with an old invalidating resume after private claims
fails verified open rather than silently adopting a now-unsafe state.

Test the demonstrated effect counterexample, representative reservation
and Run-only prefixes, the still-valid v1 clean restart resume, and the
live open path on a stored private-claim history. Preserve A12/B11 import,
exception and v1 state-digest boundaries. A future authenticated,
versioned disposition/resume transition may release a hold only after fresh
effect/accounting reconciliation and the accepted human/operator gates.
Native, provider, paid, tenant, venue and human acceptance are NOT RUN.

## Implementation sequence

1. Add the pure private-claim predicate to `journal_reducer.py` and apply it
   at both resume planning and replay verification. Run focused reducer tests.
2. Use the same predicate in `recovery_journal.py` before the resume shell
   mints an ID or reads a clock. Run focused live-front-door tests.
3. Add a targeted effect-intent replay counterexample and real-store resume
   test, then update the older Run-hold test to the safe held outcome. Run
   these tests and the existing clean v1 resume tests.
4. Obtain independent standards and specification reviews, check lint and
   the protected working tree, run the full test suite, then commit only the
   named 19v files. No push or external experiment.
