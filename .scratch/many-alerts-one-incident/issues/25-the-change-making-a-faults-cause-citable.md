# The Change: making a Fault's cause citable

Type: grilling
Status: open
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
