# Finish the Fable arm and pin the denial threshold

Type: task
Status: open
Blocked by: none

## Question

Two measurements from the timing prototype are unfinished. They are **not equally
blocked**, which an earlier version of this ticket got wrong:

- The **length probe is runnable now**. It is driven by Haiku 4.5, and Haiku 4.5 and
  Opus 5 were both confirmed working right after the arms.
- The **Fable arm is blocked on usage credits**, not on a weekly window. `claude-fable-5-1`
  is refused with "You're out of usage credits"; the remedy is topping the balance up at
  claude.ai/settings/usage, a human-in-the-loop step, and then it can run immediately.

On branch `prototype/run-timing`:

1. **The Fable 5.1 arm.** `python3 measure.py run fable51-high --model claude-fable-5-1
   --budget 3 --wait 900`, then `python3 measure.py report` and `python3 score.py
   fable51-high`. It is the one comparison the ticket asked for that has no number.
   Chapter one's recorded Transcript ran on Fable 5.1, so this is also the "what chapter
   one would have done" arm.
2. **The denial threshold.** `probe/` holds five ready command files at 9,500, 11,000,
   12,000, 13,000 and 14,000 characters and a `PROBE.md` telling a Run to run each
   verbatim and report ran-or-denied. Drive it with Haiku 4.5 to keep it cheap. The
   natural experiment bounds the threshold between 9,417 accepted and 11,313 denied;
   this pins it.

This ticket does work; it decides nothing and produces no ADR. It is here so the frontier
carries it rather than a reviewer's memory. The answer records the Fable numbers, its
grade against the Ground truth, and the threshold, and appends all three to
`prototype/run-timing/results/measurements-2026-09.md`.
