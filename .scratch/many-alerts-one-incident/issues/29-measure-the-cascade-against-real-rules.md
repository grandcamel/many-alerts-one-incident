# Measure the Cascade against real rules

Type: prototype
Status: claimed
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

## What ticket 28 hands this ticket, 2026-09-17

**The rules exist and are loadable**, on branch `rules/cascade`: six rules in
`alerting/cascade-rules.yaml`, plus the ConfigMap builder, the `lgtm.yaml` volume
patch and `preflight.sh`. Load them with the ConfigMap at
`/otel-lgtm/grafana/conf/provisioning/alerting` — it must carry all three files,
because the mount replaces the whole directory.

Expected Cascades to measure against: `paymentUnreachable` **7 Alerts** (3 error
+ 4 absence), `emailMemoryLeak` **3**, `cartFailure` at `100%` **1**.

**Run `preflight.sh` before every clock.** Every rule sets `execErrState: OK`, so
a rule whose query model is wrong is forced to Normal and vanishes silently. That
risk is not hypothetical: **no Loki-datasource alert rule has ever been
provisioned at this venue**, and two of the six are Loki rules.

### The brief, ranked by damage. Item 2 is BLOCKING.

1. **The fire edge** — the thing this ticket exists for. Projected by arithmetic
   on measured endpoints: C2 crosses `0.01` at ~t+5.2–5.5 min, first Alert
   ~t+7.5 min with the `for: 2m`. Never observed.
2. **Which baseline is the baseline — BLOCKING; the thresholds are not settled
   until this reports.** The two flags-off captures disagree by `0.069/s` on
   frontend-proxy, and the `> 0.1/s` threshold clears the worse of them by only
   **1.44×** while its worst fault-side margin is **1.17×**. There is currently
   **exactly one instant sample per service in the entire capture set** — no
   repeated sampling, no variance, anywhere. Measure 30 flags-off minutes at
   60 s on a stack up longer than 13 minutes, reporting min/mean/max/stddev per
   service.
3. **Whether a Loki-datasource rule provisions here at all.** Two of six rules at
   stake, silently. Settle `noDataState: KeepLast` while there.
4. **Whether `container_memory_working_set_bytes` ever reads ≥ 70 Mi on a *live*
   email pod.** The threshold is calibrated on `kubectl top`, a different
   instrument; the only ≥70 Prometheus reading is on the **deleted** pod.
5. **The Resolved edge for anything that is not cart** — including whether a
   `count_over_time` log rule going Firing→NoData→Normal emits a Resolved at all,
   and whether the Firing and Resolved carry the same `fingerprint`.
6. **Cross-Fault contamination.** The by-service sweep was run for
   `paymentUnreachable` only. Run C1 and C2 at t+6 min under the other two Faults.
7. **Sample cadence of the kubeletstats family.** 60 s is measured for the
   span-metrics connector only. If that series gaps, `noDataState: OK` POSTs a
   Resolved mid-Fault.
8. **`adFailure`, the designated fallback, has never been measured at this
   venue** — every number about it is from the Compose venue. The system-shaped
   rules mean it should raise a Cascade with no rule set of its own. Worth one
   injection to find out, since discovering otherwise under time pressure is
   exactly what a fallback exists to prevent.
9. **`label_replace` and Grafana annotation templating at this venue** — C1, C2
   and C4 depend on `label_replace` supplying the `service` label, and it has
   never been run here.
10. **Whether a multi-Alert Notification works end to end.** The Receiver has
    never been handed one carrying 3 or 4 Alerts, and ticket 11 measured Opus 5
    at high taking 370 s against a seven-Alert Cascade.
