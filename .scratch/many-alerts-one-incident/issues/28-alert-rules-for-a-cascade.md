# Alert rules for a Cascade

Type: grilling
Status: resolved
Blocked by: 10, 27

Unblocked 2026-09-17: ticket 27 has reported.

## Question

Graduated from the map's fog on 2026-09-17, once
[Faults and their Cascades](10-faults-and-their-cascades.md) fixed the Faults and the
alertable conditions each one raises. That ticket owns **what is true of the system when a
Fault fires**; this one owns **when we agree to call it an Alert**.

So: for each of the three Faults, what are the actual Grafana rules — thresholds, `for`
durations, labels, and the grouping that makes a Cascade arrive together?

- **Thresholds.** The conditions are written; the numbers are not. Several are already
  known to be delicate: cart's error ratio straddles 0.05 and needs an absolute rate
  against a measured baseline instead; the email memory rule had to move off 90%/`for:1m`
  because 90 → 100 MiB takes 56 s; frontend-proxy's ratio has a denominator nobody has
  measured. [Verify the signal surface](27-verify-the-signal-surface-and-settle-the-fault-gates.md)
  supplies the baselines — do not pick numbers before it reports.
- **NoData is the real decision, not the threshold.** Every `> 0` rule here is written on
  an error-only series that does not exist at steady state, and Grafana puts an empty
  vector in **NoData**, not Normal. Whether the Cascade misses entirely or fires before
  injection is decided by NoData handling and by whether each rule wraps in `or vector(0)`.
- **Instantiation is where the breadth comes from.** Two to four conditions with
  `by (service_name)` should give six to nine Alerts, each with its own Fingerprint. Which
  label set does each rule carry, and does every Alert still carry what ADR 0004's
  Fingerprint label and the Skill expect?
- **Grouping.** Grafana groups by `grafana_folder` and `alertname` with a 10 s group wait
  and a 1 m repeat, so a Cascade of N rules is N Notifications today. Widening that is
  [Many-to-one under a Cascade](14-many-to-one-under-a-cascade.md)'s decision, not this
  one — but this ticket must hand it a rule set whose labels make the intended grouping
  expressible.
- **Resolution.** Each Fault's undo restarts a service. What does the Resolved edge look
  like, and does a rule that goes NoData on recovery ever send a Resolved at all?

Every query these rules are built on is **proposed, not verified**, until
[Verify the signal surface](27-verify-the-signal-surface-and-settle-the-fault-gates.md)
runs. The trap list in [Faults and their Cascades](10-faults-and-their-cascades.md) —
the `service_namespace` selector, cross-language metric families, `span_kind` on ratio
denominators, `collector_instance_id` cardinality, gauge-versus-counter on restarts — is
this ticket's checklist, not background reading.

## Answer

Resolved 2026-09-17 by a grilling session, against six candidate rule sets drafted per
design dimension and then adversarially refuted rule by rule. **Every rule as first
drafted was refuted.** What follows is the repaired set, and the repairs changed the
outcome twice: the error condition is not the one ticket 10 wrote, and the email memory
condition would have minted five OPS Incidents from one Fault.

The rules live on branch `rules/cascade`, loadable, with every threshold cited to an
artifact inline: [`rules/cascade/`](../../../rules/cascade/README.md) —
`alerting/cascade-rules.yaml`, plus the ConfigMap builder, the `lgtm.yaml` volume patch
and the pre-flight check.

### The decision that shaped every other one

**The rules describe the system, not the Faults.** One standing set of six, in folder
`demo`, instantiated `by (service_name)`. Any Fault lights up whichever services it
touches, so `adFailure` — the designated fallback — gets a Cascade without a fourth rule
set, and nobody can say the alerting was built to recognise the failure being demoed.
This is the map's own "breadth comes from instantiation, not rule count" taken to its
conclusion.

Three of the six still name a service. **Both times that was forced, and measured:**

- **C3** — the generic form, working set over `k8s_container_memory_limit_bytes`, is
  refuted: **checkout runs at 18 Mi of a 20 Mi limit, 90% of its limit at steady state**,
  above any threshold that would catch email's climb with margin.
- **C5, C6** — a generic severity-based log rule is impossible. `severity_text` and
  `detected_level` are **structured metadata, not stream labels**; the authoritative
  eight are in `capture/01-loki-stream-labels.json`.

`C4` (container restarting) *is* generic, over every container.

### The six rules

| # | Rule | Query core | Threshold | for | sev |
| --- | --- | --- | --- | --- | --- |
| C1 | Service error rate is elevated | `sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))` | `> 0.1` | 1m | critical |
| C2 | Service request rate has dropped to zero | `sum by (service_name) (rate(traces_span_metrics_calls_total[5m]))` | `< 0.01` | 2m | warning |
| C3 | Container memory is approaching its limit | 3-node, `max_over_time(…{k8s_container_name="email"}[5m])` latch | `> 73400320` | 1m | warning |
| C4 | Container is restarting | `max by (k8s_container_name) (changes(k8s_container_restarts[10m]))` | `> 0` | 0s | critical |
| C5 | Checkout cannot deliver order confirmations | Loki `count_over_time({service_name="checkout"} \|= "failed to send order confirmation" [10m])` | `> 0` | 1m | warning |
| C6 | Cart cannot reach its data store | Loki `count_over_time({service_name="cart"} \|= "Wasn't able to connect to redis" [5m])` | `> 0` | 1m | warning |

**Cascades:** `paymentUnreachable` **7 Alerts** (3 + 4, inside the six-to-nine target) ·
`emailMemoryLeak` **3** · `cartFailure` at `100%` **1**. The last two are correctly
narrow: both Ground truths say no customer sees an error, and padding them to reach a
number would manufacture the alert fatigue the demo argues against.

### The error condition is an absolute rate, not a ratio

Ticket 10's ratio is **refuted twice over**, both against `capture/faultprobe-paymentUnreachable-on.json`,
which ran that exact by-service query:

1. **It inverts.** frontend-proxy's ratio under the Fault is `0.00705`; with every flag
   off it is `0.00808` (`capture/05-baseline-span-metrics.json`). The fault-time ratio is
   *lower* than a measured no-fault ratio.
2. **Its only extra instances are `NaN`** — accounting, fraud-detection and payment,
   whose denominators collapse, and which the absence rule already owns.

It yields **1 Alert, not 3**: frontend `0.01594` and frontend-proxy `0.00705` sit 3.1×
and 7.1× below a 5% threshold. `span_kind="SPAN_KIND_SERVER"` does not rescue it — it
saturates checkout's ratio at `1.0000`, which would freeze every repeat-Firing trend
comment at "unchanged", since the Skill posts `values.A`.

The absolute rate separates cleanly: `0.35000` / `0.18333` / `0.17500 /s`, with the next
service down at `0.01131/s` — an **8.8× gap** — and four more at the one-error-per-`[5m]`
quantum of `0.00417/s`, 24× below.

**Two costs written down rather than rounded away.** The worst fault-side margin is
**1.17×** (frontend-proxy at `0.1167/s` in the timestamped capture), and the threshold
clears the worst no-fault reading ever recorded by only **1.44×**. And it is
**traffic-dependent**: valid only because `make up` pins `loadGeneratorVUs` once.

### The email memory rule would have minted five Incidents from one Fault

An instantaneous `> 70Mi` rule goes Firing→Resolved→Firing **five times in 1181 s**: the
container drops to 47 Mi after each kill and stays below 70 Mi for **67, 119, 118 and
243 s** across the four measured cycles (`capture/podwatch-emailMemoryLeak-window.jsonl`).
Under ADR 0004 a resolved-then-refired Alert **deliberately gets a new Incident** — so the
rehearsal rule of a demo titled *many alerts, one incident* yields five.

The fix is a three-node rule latched on `max_over_time([5m])`, clearing the worst dip by
57 s, with refId A left as the **live** working set so `values.A` carries the real
sawtooth — which is the Ground truth Mechanism. A `[10m]` latch was recomputed from the
same 58 samples and goes **flat at 98.0 Mi for 11.7 minutes across two kills**.

`keepFiringFor` would express this directly and is **not available**: Grafana 12.0.1's
file-provisioning input struct `AlertRuleV1` has no such field — it exists in the model
and the HTTP API only. The constraint picked the better condition for us.

### Invariants, each bought with a refutation

- **`[5m]` is the floor** on every span-metrics rate; the collector pushes every 60 s.
- **Never `or vector(0)` on a `by (...)` rule.** A third case ticket 27 did not reach:
  `vector(0)` returns an **unlabelled** series, so its Fingerprint differs from the firing
  Alert's and **the Resolved can never Match the Incident**. (It remains separately fatal
  on an absence rule, for the reason ticket 27 gave.)
- **Name the metric literally, never a `__name__` regex.** A regex over
  `container_memory.*` matched two families and `max` returned the **limit**, not the
  usage (`capture/faultprobe-emailMemoryLeak-on.json`).
- **Aggregate container rules by `k8s_container_name`, never `k8s_pod_name`** — a
  pod-keyed query returns the **deleted** pod at 75.26 Mi beside the new one, so every
  undo mints a new Fingerprint.
- **Severity is `critical` or `warning` and nothing else** — the Skill maps only those
  two and anything else lands **silently** on Sev-3/Medium. Graded, not uniform, because
  ticket 10's Ground truths say payment "stays perfectly healthy" and that for Fault 2
  "no customer ever sees an error and no order is lost".
- **The label key set is frozen** at `{severity, service, cascade}` plus Grafana's
  `alertname` and `grafana_folder` and the one varying query label. Adding a key later
  re-Fingerprints every Alert of that rule and **orphans every open Incident carrying the
  old `fp-` label, with nothing reporting an error.**
- **Annotations are static, never templated, and never name a Fault or flag** — a Run
  copies them verbatim into OPS, and ADR 0008 keeps the Ground truth out of the Run's world.

### `noDataState: OK`, `execErrState: OK`, and where the loudness went instead

Both `OK` on all six, keeping chapter one's reason: a Notification about no-data or a
broken rule would start a Run, and that is not an Incident. The cost is real — **no
Loki-datasource rule has ever been provisioned at this venue**, and if either refId-A
model is wrong the threshold node errors, is forced to Normal, and **two of the six rules
vanish with nothing reporting it.**

So the loudness moved outside the rule, into `rules/cascade/preflight.sh`: assert every
rule is Normal and not Error before the clock starts. It is the mirror image of ticket
10's "confirm one real symptom before starting the clock".

**A named limit, documented rather than patched:** C2 detects *a service nobody calls*,
not *a service that emits nothing*. A service that stops producing spans leaves the
result set — a retired dimension, not a firing Alert — and no `noDataState` patches that,
because NoData needs the *whole* query empty. None of the three Faults reaches that state;
the `absent()` fix would hand-code the blast radius the demo exists to discover.

### How the rules reach Grafana

A **ConfigMap mounted at `/otel-lgtm/grafana/conf/provisioning/alerting`**, carrying all
three files — the mount replaces the whole directory, so shipping only the rules leaves
Grafana with no contact point. The path is verified three ways: `docker-compose.yml:39`
bind-mounts it for the same image, `tests/test_container.py:67` asserts it, and Grafana's
startup log prints it. Datasources are a **sibling** directory and survive; the only file
shadowed is the stock `sample.yaml`, which reduces to `apiVersion: 1`. kubelet's `..data`
symlink farm is skipped by extension filter, so no duplicate-UID error.

The alternative — `POST /api/v1/provisioning/alert-rules` — accepts every field but writes
to an **ephemeral SQLite DB with no PVC**, so a pod restart loses the rules. This ticket
*names* the mechanism; `make up` implements it. `lgtm.yaml` today has **no `volumes` and
no `volumeMounts` at all**.

### Handoffs

- **[Many-to-one under a Cascade](14-many-to-one-under-a-cascade.md)** gets the constant
  `cascade: otel-demo` label and two constraints: `group_by` must never contain `service`
  or `service_name`, and **only the global policy can drop `alertname`** — per-rule
  `notification_settings` always prepends `grafana_folder` and `alertname`
  (`NormalizedGroupBy()`), so it makes grouping finer, never coarser.
- **The Skill changes, the rules do not bend.** A `sum by (service_name)` series carries
  no `instance` and no `service`; `label_replace` supplies `service`, and the Summary must
  stop reading `instance` rather than fake one — presenting a service as an instance would
  be a lie the Run copies into OPS. A spec requirement, not a new decision.
- **[Measure the Cascade against real rules](29-measure-the-cascade-against-real-rules.md)**
  gets the ranked unmeasured brief below, with the re-baseline **blocking**.

### What is unmeasured — ticket 29's brief, ranked by damage

`prototype/signal-surface/results/SUMMARY.md`: *"No Grafana Alert rules existed, by
design."* **Nothing here has ever been evaluated by Grafana at the venue.**

1. **The fire edge.** Every landing time in this ticket is arithmetic on measured
   endpoints. Projected: C2 crosses at ~t+5.2–5.5 min, first Alert ~t+7.5 min. Never observed.
2. **Which baseline is the baseline — BLOCKING.** The two flags-off captures disagree by
   `0.069/s` on frontend-proxy. There is currently **exactly one instant sample per
   service in the entire capture set** — no repeated sampling, no variance, anywhere.
   Measure 30 flags-off minutes at 60 s, reporting min/mean/max/stddev.
3. **Whether a Loki-datasource rule provisions here at all.** Two of six rules at stake,
   silently. Settle `noDataState: KeepLast` while there.
4. **Whether `container_memory_working_set_bytes` ever reads ≥ 70 Mi on a *live* email
   pod.** The threshold is calibrated on `kubectl top`, a different instrument; the only
   ≥70 Prometheus reading is on the **deleted** pod.
5. **The Resolved edge for anything that is not cart**, including whether a
   `count_over_time` log rule going Firing→NoData→Normal emits a Resolved at all.
6. **Cross-Fault contamination.** The by-service sweep was run for `paymentUnreachable`
   only. Run C1 and C2 under the other two Faults.
7. **Sample cadence of the kubeletstats family.** Measured 60 s for the span-metrics
   connector only. If that series gaps, `noDataState: OK` POSTs a Resolved mid-Fault.
8. **`cartFailure` below `100%`** — pinned at 100%, so this is only a risk if that changes.
9. **`label_replace` and Grafana annotation templating at this venue** — never run here.
10. **Whether a multi-Alert Notification works end to end.** The Receiver has never been
    handed one carrying 3 or 4 Alerts.

### Corrections this ticket made to the record

- **`capture/symptom-paymentUnreachable.json`'s `never_fired` list and its t+7 s "first
  symptom" are `[1m]` artifacts, not findings about a `[5m]` rule.** Settled against
  `git show 5194d38 -- prototype/signal-surface/lib/symptom.py`: that watch ran at `[1m]`,
  and the commit changing the window to `[5m]` landed **eighteen minutes after the watch
  ended**. Two independent verifiers built high-confidence kills on that file without
  checking it; taking the majority would have killed **both of the live Fault's
  conditions**. This is the exact failure mode this effort's first rule exists to prevent,
  committed by the verification layer itself.
- **The Kubernetes signal class does produce a usable `Warning` Event — just not the one
  anyone looked for.** `BackOff` — *"Back-off restarting failed container email"* —
  reaches Loki from **t+219 s**, `deprecatedCount` rising to 5. Ticket 27's "eight Events,
  all `Normal`" was measured after **one** restart, before any back-off could exist.
  `OOMKilled` still emits no Event. **No fourth rule** — it is the same fact as the restart
  count; it belongs in the Skill's query guide as corroborating evidence.
- **Ticket 27's trap 4 is half right.** `Wasn't able to connect to redis` carries
  `severity_text: "Error"` / `severity_number: 17`; only the separate
  `Grpc.AspNetCore.Server.ServerCallHandler` template line carries `"Information"`. The
  conclusion survives for a **different** reason: `severity_text` is structured metadata
  and is not selectable as a stream label at all.
- **The venue's Grafana is 12.0.1**, with Prometheus 3.4.1, Tempo 2.7.2, Loki 3.5.1 and
  collector 0.127.0 (`otel-lgtm:0.11.4`). The map's "the LGTM image's Prometheus is 3.9.1"
  matches **neither** 0.11.4 nor current `latest` (3.14.0) — it was true of whatever
  `latest` resolved to on the day it was measured, on the retired Compose venue.
  `docker-compose.yml:25` still pins `:latest` and should be pinned to `0.11.4`.
- **`results/SUMMARY.md` over-claims its own file** with "every service reads 0.0000/s
  error rate": the `error` map has four entries and `server_error` two; checkout and
  thirteen others appear in **neither**, which is a different and stronger statement. Its
  "~2–5 min" timing row cites no capture file.
- **cart never restarts during Fault 3.** `capture/window-cartFailure-100%.log` shows
  `restarts=0 ready=True` at every sample; the pod change is the undo's own
  `rollout restart`.

### The Notification count, which the ticket's own framing had wrong

This ticket said "a Cascade of N rules is N Notifications today." With
`group_by: [grafana_folder, alertname]` Grafana already collapses *instances of one rule*,
so Fault 1's **7 Alerts arrive as two Notifications** — one carrying 3, one carrying 4 —
and start **2 Runs, not 7**. The Receiver hands one whole Notification to one Run
(`grafana_jsm_sandbox/notification.py`), and the Skill handles every Alert inside it.
Ticket 14 inherits 2 Runs, and the demo's opening claim should be stated accordingly.
