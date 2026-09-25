# 19c local Run supervision deadline policy plan

Status: source plan, 2026-09-25. Baseline: `6ab54e0`.
Authority: ADR 0012 and ticket 37. This unit is a pure schedule assessment;
it creates no process, sentinel, attempt, reservation or dispatch permit.

1. Add `run_supervision_policy.py` with bounded scalar inputs and an immutable
   output. Require exact scalar types, nonnegative monotonic microseconds on
   one boot, a launch time no later than observation time, and an optional
   observed stop request between launch and observation. Reject overflow and
   cross-boot observations by fixed code. No clock is read inside the module.
2. Derive the work boundary at launch+270s, interrupt/flush end at
   launch+290s, and kill/reap end at launch+300s. For an earlier stop, the
   interrupt end is min(stop+20s, launch+290s) and hard end is
   min(stop+30s, launch+300s). Return only descriptive phase and required
   actions (`revoke_due`, `interrupt_due`, `kill_or_reap_due`). Missing
   observation or containment confirmation cannot be inferred from elapsed
   time; this schedule does not return a dispatch decision.
3. Add focused pure boundary, early-stop, wrong-boot, malformed/overflow and
   no-extension tests. Update `docs/run-outcome.md` and ticket 37 with the
   exact no-authority boundary.
4. Review source and tests independently on Standards and Spec axes, run
   focused checks, Ruff and the full test suite before any code commit.
   Record validation and protected dirty-artifact read-back; stage only
   named 19c files.

This unit does not wire the legacy spawner or journaled front door. A future
supervisor must act on these requests using trusted process-group evidence,
bounded stream draining and persisted observations before any claim of
containment or execution outcome.
