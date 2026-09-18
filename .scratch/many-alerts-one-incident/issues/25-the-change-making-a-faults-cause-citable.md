# The Change: making a Fault's cause citable

Type: grilling
Status: resolved
Blocked by: 09

## Question

[Can the laptop hold it](08-can-the-laptop-hold-it.md) measured that a flipped
fault flag leaves **no retrievable trace**. With `adFailure` on and traffic
running: Prometheus held 240 metric names and none matched flag, impression or
feature; flagd emitted only span metrics and `target_info`; flagd's stdout never
reached Loki; and a Loki search across every service for the flag file,
`configuration_change` or `adFailure` returned zero matches. The symptom is
rich, the cause is absent.

Two standing preferences collide with that. The **Ground truth rule** judges a
Report by whether its Suggested root cause names the Fault's documented Ground
truth. The **Citation rule** requires every claim in a Report's root-cause
section to cite evidence the Run *retrieved*. A Run that cannot retrieve the
flip can only infer it — and an inference dressed as a citation is exactly the
failure Haiku 4.5 produced in
[Does a high-effort Run fit the slot](11-does-a-high-effort-run-fit-the-slot.md),
where it claimed two services healthy it had never queried.

So: **what makes a Fault's cause citable, and is that in the spec?**

- Is the Change a first-class thing the simulation emits, or does the Run reason
  from symptoms alone and the Ground truth rule soften to "names the failing
  component" rather than "names the cause"?
- If it is emitted: ticket 01 sketched a ~30-line watcher on flagd's event
  stream posting a Grafana annotation and an OTLP log record. Which of those
  does a Run actually retrieve through Eyes — an annotation, a log record, a
  metric, or more than one? Grafana annotations are not a Loki or Prometheus
  query; can the Run reach them at all?
- What does a Change record carry: flag name, variant, who flipped it, when, and
  what the Ground truth says it breaks? How much of the Ground truth may the
  Change reveal before a Report naming it is cheating rather than diagnosing?
  This is the same tension [Scoring a Report against ground
  truth](24-scoring-a-report-against-ground-truth.md) is weighing.
- Does the same mechanism cover the non-flag Faults — a Kubernetes restart loop
  has a real Kubernetes Event, so is that already a Change, and does one shape
  cover both?
- Where does the watcher live — beside the demo's collector on Compose, in the
  cluster, or in the Forwarder — and does that change if the venue is cloud?
  This is why the ticket waits on
  [Which system, and where it runs](09-which-system-and-where-it-runs.md).

The answer feeds the simulation spec directly: if the Change is in, it is a
build the spec must describe, and the fourth signal ("structured events") gains
its Compose-side member.

## What ticket 09 settled, 2026-09-16

The venue is one DigitalOcean node running Helm chart 0.41.2 (ADR 0007), which
answers this ticket's last bullet and adds a lead to its second.

- **Where the watcher would live**: in the cluster. There is no Compose arm to
  serve — the spec describes the DOKS venue only.
- **The lead**: on the chart, flagd's flag configuration is a **ConfigMap**
  (`mountedConfigMaps`, with `existingConfigMap` or inline `data`). So the
  presenter's flip is a Kubernetes API write with a real resource-version change,
  not an invisible edit to a file inside a container. If the chart's
  `kubernetesEvents` preset carries ConfigMap updates — unverified — a Run could
  retrieve the Change from Loki with no watcher at all, and the ~30-line build
  ticket 01 sketched drops out of the simulation spec. If it does not, the
  watcher is still needed and now has a Kubernetes-shaped source of truth.
  [Ticket 26](26-can-one-doks-node-hold-the-chart.md) turns that preset on; its
  result is worth having before this ticket is worked.

## Correction from ticket 26, 2026-09-16

**The ConfigMap lead is re-gated, not dead — but its premise was wrong one level
up.** flagd does **not** read the ConfigMap. The chart mounts `flagd-config`
only into an init container that does a one-shot `cp` into an `emptyDir`, and
the Deployment carries no `checksum/config` annotation, so writing the ConfigMap
bumps `resourceVersion` and changes nothing a service can see. Verified: with
`adFailure` written to the ConfigMap, the pod still served `off`.

**The flip that works is the ConfigMap edit plus `kubectl rollout restart
deploy/flagd`** (verified: `adFailure = on` in-pod afterwards). That is *better*
for this ticket than the original lead, because it produces **two** citable API
writes — the ConfigMap's `resourceVersion` change and a Deployment rollout that
emits its own Kubernetes Events. The alternative path, the flagd-ui sidecar on
port 4000, writes the same `emptyDir` and leaves **no Kubernetes API trace at
all**, so the presenter's action must be the restart path if the Change is to be
citable.

**The no-watcher branch now has a measured answer.** Kubernetes Events do reach
Loki, but only at `opentelemetry-collector.mode: deployment` — the preset is off
by default and skipped entirely in the chart's shipped daemonset mode. Even
then, three limits bear on whether a Run can cite a Change from Loki alone:
the receiver **watches rather than lists, so there is no backfill**; there is
**no isolating stream selector** (`{event_domain="k8s"}` returns zero streams —
only `{service_name="unknown_service"}` finds them); and whether `k8sobjects`
is configured to watch **ConfigMap** updates at all, as opposed to `events`, is
still unverified — the preset's rendered config watches `events.k8s.io` only.

**The non-flag-Fault bullet's premise does not hold.** There is no non-flag
Fault on this menu, and the one Kubernetes-shaped candidate,
`failedReadinessProbe`, produced `restartCount=0` and zero `Unhealthy` Events,
so there is no restart-loop Event shape for a single Change record to also cover.

## What ticket 10 settled, 2026-09-17

**The tension this ticket was built around is resolved, and in the Change's favour.**
ADR 0008 splits the Ground truth into Mechanism and Trigger and scores only the Mechanism.
So **a Change may name the Trigger freely** — flag, variant, who flipped it, when — because
a Run retrieving a flag flip is citing evidence, not copying an answer. The bullet asking
"how much of the Ground truth may the Change reveal before a Report naming it is cheating"
is answered: all of it, as long as the Mechanism is what gets scored.

Also settled or narrowed:

- **The non-flag-Fault bullet is dead.** All three chosen Faults are flag flips; there is
  no second shape for one Change record to cover.
- **`OOMKilled` emits no Kubernetes Event**, so even the memory Fault has no Event-shaped
  cause record. Its Kubernetes evidence is pod status via read-only `kubectl`.
- **The presenter's action is fixed** for all three: ConfigMap edit plus
  `kubectl rollout restart deploy/flagd`, then confirm one real symptom before starting the
  clock. The flagd-ui path writes the same emptyDir and leaves no Kubernetes API trace, and
  flagd v0.16.0 is distroless so `kubectl exec ... cat` fails — use `-c flagd-ui` or OFREP
  on `:8016` after `rollout status` returns.
- **A new problem for the Change to solve.** The flagd rollout emits *identical* Events for
  injection and for remediation, and it briefly zeroes every flag as providers fall back to
  code defaults. A Run investigating after recovery sees two indistinguishable rollouts, so
  a Change record has to disambiguate what a Kubernetes Event cannot.

## Correction from ticket 27, 2026-09-17

**A Fault's cause IS citable at this venue, from traces, with no watcher.** This
ticket — and the map's standing fact behind it — rests on
[Can the laptop hold it](08-can-the-laptop-hold-it.md)'s finding at the **Compose**
venue: 240 metric names, none `feature_flag*`, and flagd's stdout never reaching
Loki, therefore "the Change watcher is load-bearing for the Citation rule, not
optional". Measured on the **chart-on-DOKS** venue, one third of that holds.

- **Traces: fully citable.** Services emit a **`feature_flag.evaluation` span
  event** carrying `feature_flag.key`, **`feature_flag.result.variant`**,
  `feature_flag.result.value`, `feature_flag.result.reason` and
  `feature_flag.provider.name`. Observed on **checkout** (`paymentUnreachable`),
  **cart** (`cartFailure`) and **product-catalog** (`productCatalogFailure`).
  The TraceQL filter genuinely discriminates:
  `{event.feature_flag.key="paymentUnreachable"}` returns traces,
  `{event.feature_flag.key="thisFlagDoesNotExist"}` returns **0**.
- **Metrics: not citable.** Four `feature_flag_evaluation_*` metrics **do** exist
  here (the map says none), but they carry **no `key` label** and come from
  `service_name="cart"` only, so they identify no flag.
- **Logs: not citable.** flagd's stdout still never reaches Loki —
  `{service_name="flagd"}`, `{k8s_deployment_name="flagd"}` and
  `{k8s_container_name="flagd"}` all return 0 streams. Unchanged.

**`emailMemoryLeak` emits no `feature_flag.evaluation` event at all** (0 traces),
so the three Faults are **asymmetric**: Faults 1 and 3 have a citable Trigger in
traces, Fault 2 does not.

This re-gates the ticket rather than closing it. A watcher may still be wanted for
a Grafana annotation, for a Change the audience can see, or to cover Fault 2 — but
**the Citation rule can already be satisfied from Tempo for two of three Faults**,
which changes what the watcher is *for*.

It does not collide with ADR 0008 — a Report is scored on the **Mechanism**, and
naming the Trigger is not a diagnosis — but it raises the stakes on that scoring
rule, since a Run can now name the Trigger cheaply and must not be credited for it.

Also relevant: **`badhost` appears in no log line anywhere**. The bad hostname —
the literal cause — exists only in the flag config and the evaluation span event.

## Work in progress

Claimed after ticket 24 was committed. Offline evidence review and planning only; no cluster, model or demo runs. ADRs 0008/0014 permit supported causal inference and score the Mechanism, so absence of a directly retrieved Trigger does not itself violate the Citation rule. The Change design must record operational facts without importing adjudication Ground truth.

[Offline facts](../reviews/ticket-25/facts.md) separate the Compose implementation, historical intended-venue observations and the missing Change recorder. The earlier phrase “all of it” about Ground truth is restricted to Trigger facts: repository Mechanism/scoring material remains excluded under ADRs 0008/0014. [Round 1](../reviews/ticket-25/round-1.md) records accepted producer/coverage, truthful stages, retrieval and partial-failure policy. The human accepted all four recommendations. [Round 2](../reviews/ticket-25/round-2.md) records accepted ordering, durability, deadlines, authority and recovery details; all five second-round recommendations were accepted.

## Answer

Both rounds are accepted in [ADR 0015](../../../docs/adr/0015-changes-record-operator-actions-and-observed-stages.md). An operator-controlled in-cluster coordinator records injection and undo as stable, staged Changes; config acceptance, rollout, served value, application evaluation and symptom recovery remain distinct claims. Runs retain read-only access through a dedicated Loki Change stream and Eyes/Forwarder. Optional annotations are audience views, never another authority.

Actions are globally serialized with durable intent and reconciliation before uncertain retries. The journal is 100 MiB with 10 MiB for recovery; journal and Change stream retention is seven days, with unresolved-state handoff before expiry/reset/destruction. Actuation has a 180-second bound and stage queryability a 30-second bound; failed delivery allows three sends per authorized attempt, not mutation replay. Separate operator grants, safe identity, restricted alternative editing and emergency undo preserve control without giving Runs mutation authority. Gaps/uncertain actions exclude clean qualification, and Incident completion still follows Alert/member rules.

[Ticket 41](41-change-coordinator-and-retrieval-specification.md) specifies the implementation and offline/live acceptance boundaries. No coordinator, Skill, collector, cluster or model work was executed. Historical traced Trigger evidence remains useful; absent direct Trigger evidence does not prohibit an explicitly supported causal inference under ADR 0014.
