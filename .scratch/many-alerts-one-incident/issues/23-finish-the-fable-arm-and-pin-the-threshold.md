# Finish the Fable arm and pin the denial threshold

Type: task
Status: open
Blocked by: none

## Historical question — execution claims superseded below

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

## Current execution boundary after ticket 22

The commands and model availability above are historical, not runnable-now evidence or authorization. Ticket 22 refutes independent per-model balances as an established fact; a top-up is not an accepted remedy. ADR 0013 requires metered API billing, mediated credentials, budget preflight and separately authorized execution. Redesign these probes against that contract and ADR 0012's 300-second total bound before any future run; the historical 900-second command is not an approved current Run budget. No paid probe or credential change is authorized.

## Source preparation, 2026-09-21

The [redesign packet](../reviews/ticket-23/source-redesign.md) records the pinned historical
harness gaps, revised timing/length contracts, inert fixtures and implementation
acceptance gates. The [measurement card](../reviews/ticket-23/execution-card.md) remains
**CLOSED**. Source preparation can proceed independently of ticket 19's C2 provider
block; paid execution still requires reviewed implementation, mediated-client and
budget readiness, then separate one-attempt authorization. No new measurement or
qualification result is claimed; this ticket remains open.

## Offline implementation continuation

The [offline implementation outcome](../reviews/ticket-23/implementation-outcome.md)
records the new replay core, adversarial regressions and remaining native integrations.
No paid timing/length probe ran. The measurement card stays closed and this ticket stays
open; offline receipts, ledger snapshots and containment observations do not establish
the corresponding host/provider boundaries.

The next [fixed-process harness outcome](../reviews/ticket-23/process-outcome.md) adds real
host fixture evidence for scheduling, cancellation, process-group cleanup, pipe EOF,
bounded output and attempt collisions. It does not admit a native model client or prove
adversarial isolation. Ticket 23 remains open; paid execution remains closed.

The [synthetic diagnostic ledger outcome](../reviews/ticket-23/ledger-outcome.md) adds
durable reservation/launch claims, exact receipt reconciliation and concurrent/crash
tests around fixed local fixtures. Inputs and allocation amounts are synthetic; no real
accounting ledger or paid probe is admitted. This diagnostic slice does not complete
ticket 38's lifecycle/Receiver integration. Ticket 23 remains open; native launch remains
closed.

The [fixture closeout outcome](../reviews/ticket-23/closeout-outcome.md) adds bounded
retained output, exclusive publication and digest/linkage read-back. Byte integrity does
not establish semantic acceptance, production audit custody or a launch-to-durable-closeout
deadline. Closeout failures preserve unresolved ledger claims. Paid execution remains closed.

The [inert length-record outcome](../reviews/ticket-23/length-record-outcome.md) adds
five-case snapshots with command digests, virtual times and separate issued/supplied
receipt observations. Synthetic permission labels and opaque references do not establish
native permission or authenticated dispatch. Ticket 23 remains open.

The [timing text outcome](../reviews/ticket-23/timing-text-outcome.md) adds reviewed source
drafts for the prompt, diagnostic Skill and operator-only human rubric. Historical inputs
are pinned; legacy flag-name grading is excluded. Human Mechanism/rubric freeze and the
native adapter/executable binding remain pending. No Skill was installed and no probe ran.

The [pinned query outcome](../reviews/ticket-23/query-outcome.md) adds a read-only in-process
fixture API with exact input hashes, bounded queries, explicit truncation and correlated
response read-back. Native transport, authenticated receipts and synthetic Incident writes
remain unimplemented; the timing measurement card remains closed.
