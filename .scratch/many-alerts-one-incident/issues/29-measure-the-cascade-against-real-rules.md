# Measure the Cascade against real rules

Type: prototype
Status: resolved
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

## Answer, 2026-09-17

**The rules work, the fire edge is three and a half minutes earlier than
projected, and C1's threshold is wrong — on the Fault side, not the baseline
side.** One `s-8vcpu-16gb` DOKS node, 2 h 39 m, **$0.380**, 48 artifacts on
branch `prototype/cascade-timing`. Cluster destroyed in session; no orphans.

### The fire edge (item 1), measured. t+0 is injection.

| Fault | first Alert | last new Alert | assembly | Alerts | firing Notifications → Runs |
| --- | --- | --- | --- | --- | --- |
| `paymentUnreachable` | **t+241 s** (4.0 min) | t+426 s | 185 s | **7** | 4 → 4 |
| `emailMemoryLeak` `1000x` | **t+161 s** (2.7 min) | t+231 s | 70 s | **3** | 3 → 3 |
| `cartFailure` `100%` | **t+105 s** (1.8 min) | t+370 s | 265 s | **2** | 2 → 2 |
| `adFailure` | **t+751 s**, *after the undo* | t+751 s | 0 s | **1** | 1 → 1 |

Ticket 28 projected the live Fault's first Alert at ~t+7.5 min by arithmetic on
measured endpoints. **It is t+241 s.** The projection was right about C2 — that
rule's own first Alert is t+426 s — but C1 fires long before it and nobody had
projected C1 separately.

**Ticket 28's Cascade sizes are exact: 7, 3, 1.** For `paymentUnreachable` the
predicted *composition* is right service by service: C1 on frontend,
frontend-proxy, checkout; C2 on email, accounting, fraud-detection, payment.

**Grafana lagged every condition by exactly its `for` plus one evaluation
interval** — 65 s, 130 s, 60 s, 30 s, 70 s, 80 s, 65 s across seven firings.
No divergence between the rule-state channel and the replayed-query channel
anywhere, and no node errors. The third channel found nothing hiding, which is
the result rather than the absence of one.

### What must change: C1's threshold (item 2, the BLOCKING one)

The re-baseline **vindicates the flags-off side and refutes the fault side.**
30 samples at 60 s on a stack up >13 min:

- worst flags-off reading of any service: **flagd 0.0125/s** → `> 0.1` clears it
  by **8×**. frontend-proxy measures min 0, mean 0.00111, **max 0.00417** — so
  ticket 28's alarming `0.06937/s`, which drove its 1.44× margin, is a single
  instant that 30 samples do not reproduce. It is 16× lower than that in reality.
- C2's `< 0.01/s`: lowest service is payment at **min 0.0833/s**, 8.3×. Ticket 28
  claimed 11.7× off one sample; the true worst case is tighter but safe.

**The fault side is where it fails.** Under the live Fault, checkout ran
min 0.0583 / mean **0.1105** / max 0.1333 and frontend-proxy min 0.0625 / mean
**0.1102** / max 0.1417 — **1.10× the threshold**. At t+792 s and t+852 s both
read **exactly 0.1000**, which is not `> 0.1`, so **both Alerts resolved while
the Fault was still running** and re-fired afterwards. Under ADR 0004 that makes
**7 Alerts into 9 Incidents**, in a demo titled "many alerts, one incident".
Only frontend (mean 0.2218, 2.2×) was safe.

Replaying every recorded sample against candidate thresholds:

| threshold | flags-off false positives (240 samples) | fault-side dips (45 each) |
| --- | --- | --- |
| `> 0.1` | none | **checkout 12/45, frontend-proxy 11/45** |
| `> 0.05` … `> 0.02` | **none** | **none** |
| `> 0.0125` | 4 (flagd) | none |

**A clean band from 0.02 to 0.05. `0.03/s` is its geometric centre** — 2.4×
above the worst flags-off reading and 1.94× below the worst fault-side reading,
the first threshold for this rule with measured separation on *both* sides.

### `adFailure` confirms it from the other side (item 8)

**At `> 0.1/s` the designated fallback raises no Cascade at all.** Measured at
t+275 s: frontend **0.0642/s**, frontend-proxy **0.0333/s**, ad **0.0202/s** —
every one below. Its single measured Alert fired at t+751 s, **144 s after the
undo**, caused by the `rollout restart deploy/ad` that *remediates* it. The Fault
is silent to the alerting; switching it off is not. At `0.03/s` it raises two.

Also measured here, correcting ticket 10's refutation pass: `adFailure` produces
**0 matching log lines** at this venue against 5 errored traces. Ticket 10
rehabilitated it on the grounds that its "invisible in logs" finding had never
been measured and ticket 08 *had* retrieved the line — but ticket 08 is the
**Compose** venue. At the chart-on-DOKS venue it really is invisible in logs.

### Grouping does not collapse across rules (items 10, 14)

**7 Alerts arrived as 4 firing Notifications, not the 2 ticket 28 predicted.**
`group_by: [grafana_folder, alertname]` collapses instances of one rule that are
*simultaneous*; C1's members joined over 120 s (frontend at t+241 s,
frontend-proxy and checkout at t+361–366 s), so C1 notified **twice** — once
carrying one Alert, once carrying three. `emailMemoryLeak`'s 3 Alerts are 3
different alertnames and **cannot collapse at all**: 3 Notifications, 3 Runs.

Getting "many alerts, one incident" therefore cannot come from grouping. It has
to come from the Run's Match against open Incidents, or from dropping
`alertname` from the **global** policy — which ticket 28 established is the only
place it can be dropped.

Multi-Alert Notifications work: 22 of 26 deliveries carried 3 or 4 Alerts. One
delivery at t+790 s carried **checkout resolved and frontend firing in the same
payload** with `status: firing` — so the Skill must complete one Incident and
update another from a single Notification.

**The Fingerprint is unique per (rule, label-set), not per Incident.**
`5e8d72dc87b1ff35` is frontend/C1 in *both* the `paymentUnreachable` run and the
`adFailure` run 90 minutes later. Two different Faults lighting the same service
on the same rule produce the same Fingerprint, so a Run would Match the later
Alert to the earlier Fault's Incident if it were still open.

### The Resolved edge (item 5) and NoData (item 3)

**Every fingerprint that fired also resolved, under the same Fingerprint** — 7 of
7 for the live Fault. Grafana resolved 5.3, 6.9 and 7.0 minutes after the undo
for `emailMemoryLeak`'s three rules.

**Item 3 is answered twice over.** A Loki-datasource rule *does* provision here —
all six rules present, both Loki rules `health=ok` — and C5 and C6 both
**evaluated and fired**, the first time either has happened at this venue.

**But `noDataState: KeepLast` would break both of them.** Loki returns an **empty
vector**, not `0`, when no line matches, so C5 and C6 can *only* resolve through
`OK`: the measured C5 resolution is an empty evaluation at t+1512 s, 411 s after
the undo, as the last log line aged out of its `[10m]` window. Under `KeepLast`
they would hold Alerting forever and the Incident would never complete. **Keep
`OK` on the Loki rules.** This reverses the suggestion in this ticket's own brief.

For C1, `noDataState` is doing nothing at all: its vector is **never empty** —
8 services carry an error series at steady state, all reading 0.0 — so the rule
sits in Normal, not NoData. Ticket 28's stated justification for `OK` on C1
("the error series does not exist at steady state") is **wrong at this venue**.
The setting is harmless; its reason is not a fact.

### C4 is cluster-wide, and it fired on something nobody injected (item 6)

C4 carries **37 series including kube-system containers** — `cilium-agent`,
`coredns`, `csi-do-plugin`, `konnectivity-agent`, `do-node-agent`,
`metrics-server` — because `k8s_container_restarts` is not namespace-scoped.

It fired for real. **The `load-generator` was OOMKilled** (`exitCode 137`) after
116 minutes, mid-`cartFailure`, raising a **critical** Alert labelled
`service=load-generator`. So cart's Cascade is 2 Alerts, one of which is
contamination: under one-Run-per-Notification it starts a Run investigating a
container the presenter never touched. Two consequences:

- **the load generator OOMs at ~116 min.** Fine for a thirty-minute slot, fatal
  for a cluster left up across a rehearsal day.
- **C4 needs a namespace matcher**, or the Skill needs to handle a `service`
  label naming a CNI daemon.

Traffic recovered within ~60 s and **C2 did not fire** during the gap — the
`[5m]` window did not drain far enough. A useful robustness result for the
absence rule.

### Items 4 and 7, settled

- **item 4** — the **live** email pod (`Running`, **0 restarts**, 77 min old)
  reads **84.1 MiB**. The concern that only a *deleted* pod ever read ≥70 MiB is
  refuted; C3's 70 MiB threshold is calibrated on the right instrument. Steady
  state is 55.25 MB mean / 55.98 MB max (σ 463 KB), 17.4 MiB of clearance.
- **item 7** — sample cadence is **exactly 60/60/60 s, σ 0**, for *both* the
  kubeletstats family and the span-metrics connector, with **no gaps**. So
  `noDataState: OK` cannot post a spurious Resolved from a scrape gap.

### C3's latch is vindicated (and its timing warned of, confirmed)

**Zero flaps across 18.4 minutes.** Ticket 28 chose `max_over_time([5m])` because
the naive `> 70Mi` form went Firing→Resolved five times in 1181 s, which under
ADR 0004 is five Incidents from one Fault. The latch held.

This ticket's own warning is confirmed to the second: C3's `for: 1m` fires at
**t+220 s** and the container was OOM-killed at **the same instant**. All three
of `emailMemoryLeak`'s conditions became true in the same 10-second tick; they do
not cascade, they arrive together.

### Ticket 10's timing budgets, corrected in place

Injection → flagd ready: **6 s** (ConfigMap 2 s + rollout 4 s), against a
budgeted 20–45 s. Injection → first symptom: **102 s** for `paymentUnreachable`
(errored checkout trace), **~25 s** for `cartFailure` (C6's condition true at
t+24.7 s, against ticket 27's t+53 s first line), **~100 s** for
`emailMemoryLeak` (C3's condition true at t+100.5 s).

### Defects in the instrument, found before and during the run

An adversarial review over five lenses raised 30 findings and **19 survived
refutation**, almost all *silent* — a harness that completes and reports numbers
that are not what they claim. Four would have corrupted the answer: the sink's
log is cumulative so Fault 2's Notification count would have included Fault 1's
(21 deliveries over 47 min against a true 6 and 2); the watcher appended, so a
re-run would report the first run's fire edge as the second's; a failed poll was
written as a quiet instant; and the clock kept only the first return to Normal,
so a flapping rule read as "still firing".

**Ticket 28's `preflight.sh` could not fail.** Its rule-health loop was the body
of a pipeline, so bash ran it in a subshell and `bad=1` never reached the parent.
The check that exists to catch a silently broken rule would have passed silently
over one. Rewritten; against a deliberately broken venue it now catches all six
planted faults and exits 1.

**Ticket 28's contact point named a Compose service** (`http://demo:8080/…`),
which does not resolve in-cluster — item 10 could not have been measured at all.

Three more were found by running it: the uptime gate queried
`process_start_time_seconds`, **which does not exist at this venue**, and
degraded to a warning that waved through an 8-minute-old stack; the symptom gate
*ran* the 600-second watch instead of testing set membership; and the watcher's
log stayed empty for a whole Fault because Python block-buffers stdout to a file.
A gate that cannot measure now refuses rather than warning.

### Recommended edits to `rules/cascade`

1. **C1: `> 0.1` → `> 0.03`.** Blocking. Without it the live Fault produces 9
   Incidents instead of 7 and the fallback Fault produces none.
2. **C4: add a namespace matcher**, or accept Alerts labelled `service=cilium-agent`.
3. **Keep `noDataState: OK` everywhere.** `KeepLast` would strand both Loki rules.
4. C2, C3, C5, C6 and every `for` are confirmed as written. No other change.

### What this ticket does not settle

- **Grouping.** [Many-to-one under a Cascade](14-many-to-one-under-a-cascade.md)
  owns it and now has its input: grouping cannot collapse across rules, so the
  collapse is the Run's job or the global policy's.
- **The Receiver.** The sink is a tape recorder. Nothing here starts a Run, so
  ticket 11's 370 s against a seven-Alert Cascade is still the only figure for
  what a Run does with one.
- **`0.03/s` is measured but not yet run.** It is a threshold chosen against two
  measured distributions, not one observed firing.
