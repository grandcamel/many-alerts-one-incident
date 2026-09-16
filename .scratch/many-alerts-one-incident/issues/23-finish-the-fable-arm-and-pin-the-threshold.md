# Finish the Fable arm and pin the denial threshold

Type: task
Status: open
Blocked by: none

## Question

Two measurements from the timing prototype are unfinished, both because the account ran
out of its seven-day allowance mid-experiment, not because they were judged unnecessary.
The allowance resets at **2026-09-19 19:00 local**; do this after that.

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
