# Measure the Cascade against real rules

Type: prototype
Status: open
Blocked by: 28

## Question

Graduated from [Verify the signal surface and settle the Fault gates](27-verify-the-signal-surface-and-settle-the-fault-gates.md)
on 2026-09-17. That ticket owned the timing budget and could measure only half of
it, because the other half is a property of a Fault **and a rule**, and the rules
did not exist. It measured **injection → flagd ready → first symptom** for all
three Faults. This one measures **first Alert → last Alert**.

Ticket 27's own text said to do this "once [Alert rules for a Cascade](28-alert-rules-for-a-cascade.md)
has thresholds to measure against" — but 28 is blocked by 27, so the work could
not happen in the same session. It becomes its own ticket rather than a claim
ticket 27 pretends to have closed.

So: with 28's rule set loaded into Grafana, inject each Fault once and measure

- **injection → first Alert firing**, and → the last Alert of the Cascade.
- **how many Alerts actually instantiate**, against ticket 27's measured
  prediction of **7** for `paymentUnreachable` (3 error-ratio + 4 absence) and
  **2–3** for `emailMemoryLeak`. Each Alert's Fingerprint, and whether every one
  carries what ADR 0004 and the Skill expect.
- **the Resolved edge.** Ticket 27 measured the underlying series: it returns to
  a genuine **0**, not NoData, about **4 minutes** after the undo, so Resolved
  should fire. Confirm Grafana actually sends it, and how long it takes.
- **the NoData edge before injection.** The error series does not exist at steady
  state, so every `> 0` rule starts in NoData. Confirm the chosen NoData handling
  does not fire the Cascade before the Fault.
- **correct ticket 10's timing budgets in place** with whatever this measures.

Watch the traps ticket 27 found: an absence rule on a window shorter than `[2m]`
reads a confident 0 forever, and `emailMemoryLeak` crosses 70 Mi only ~60 s
before the kill, so a `for: 1m` fires about when the container dies.

**This spends money.** Same discipline: ask before creating, never without
`--ha=false`, `--size` and `--count`, destroy in the same session. Ticket 27's
harness on `prototype/signal-surface` brings the cluster up in ~9 minutes and
already does the flip, the flagd rollout and the symptom confirmation; it needs
only the rules and an Alert-side watcher. A run costs about **$0.20**.
