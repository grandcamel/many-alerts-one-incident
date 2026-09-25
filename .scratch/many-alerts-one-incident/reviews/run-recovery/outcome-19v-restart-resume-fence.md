# 19v outcome: v1 restart resume stays held over private claims

Status: reviewed local source and real-store verification, 2026-09-25.
Authority: accepted ADR 0012 and the v1 resume-at-open contract. The
[design](design-19v-restart-resume-fence.md) recorded the demonstrated
effect-intent counterexample and file-by-file implementation sequence.

The reducer now rejects a v1 operator resume at planning and verified replay
whenever a v2/v3 reservation, Run, launch, effect, supervision, execution or
reconciliation claim exists. The real open path checks the same predicate
before minting an ID or reading a clock. It retains `restart_recovery`, records
no `operator_action`, and returns no resume receipt. A persisted unsafe resume
fails verified open with `journal_replay_mismatch`. Ordinary v1-only resume
remains eligible; neither a claimed success nor an absence settles a private
obligation.

Independent Standards and Spec source reviews passed. The focused front-door,
Run-hold and fence suite passed **356 tests**. Ruff and `git diff --check`
passed. The full local suite passed **5,628 tests, 39 skipped in 402.00s**.
The four protected dirty/untracked files and 76-file panel were not edited or
staged; their hashes were rechecked before the commit.

This repair does not add a positive disposition, effect writer, authenticated
permit, stable containment witness, child, or production Run. Native,
provider, paid, tenant, venue, power-loss and human acceptance remain
**NOT RUN**. Tickets 36-38 remain open.
