# Faults and their Cascades

Type: grilling
Status: open
Blocked by: 09, 26

## Question

Which Faults can the simulation inject, including the one Kubernetes-native Fault the story needs? For each: its Ground truth, the Cascade of Alerts it should raise, the signals that show it (which logs, metrics, traces, Kubernetes Events and Changes), and its timing inside the slot from injection to the last Alert. Which Fault the live demo uses, and which are rehearsal-only. Every Fault added here writes its Ground truth, per the map's standing rule.

Start from the Demo's fifteen fault flags (two need the Kafka layer or Kubernetes). Decide here how each Fault's injection becomes a Change: the research found a flip emits nothing collectable, so a small watcher on flagd's event stream posting a Grafana annotation and an OTLP log record is the candidate, with the flag file as the source of truth. Ticket 05's finding that a Fault presents as a restart loop with a pod-status signal rather than a reliable Kubernetes Event was about **OOMKill**, not about `failedReadinessProbe`; ticket 01 found that flag wants the chart's `kubernetesEvents` preset, which points the other way. What it actually produces is [ticket 26](26-can-one-doks-node-hold-the-chart.md)'s to measure, and this ticket's Cascade waits on that answer rather than assuming a restart count.

## What ticket 09 settled, 2026-09-16

The venue is one DigitalOcean node running the Helm chart, not the Compose core
layer (ADR 0007). That changes this ticket's starting menu:

- **All 13 fault flags are usable**, not 11. `kafka` stays enabled, so
  `kafkaQueueProblems` is in; the cluster is real, so `failedReadinessProbe` is
  the Kubernetes-native Fault the story wanted rather than a synthesized one.
- **The load generator stays on**, so a Fault produces symptoms the moment it is
  flipped and `traffic.sh` is retired. Timing "from injection to the last Alert"
  is measurable rather than dependent on a stopgap driving traffic.
- **The flip is a ConfigMap write**, not a file edit. How that becomes a Change
  is [ticket 25](25-the-change-making-a-faults-cause-citable.md)'s to decide, but
  the presenter's action for each Fault is shaped by it.
- This ticket now also waits on
  [Can one DOKS node hold the chart](26-can-one-doks-node-hold-the-chart.md), so
  the menu is not written against a deployment that has not stood up.
