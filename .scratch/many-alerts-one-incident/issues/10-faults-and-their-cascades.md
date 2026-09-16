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

## Correction from ticket 26, 2026-09-16

Measured on the real venue. Three things this ticket carries as settled are
wrong, and two of them would have shaped the Fault menu around signals that do
not exist.

**`failedReadinessProbe` is not the Kubernetes-native Fault.** A real cluster was
never sufficient: chart 0.41.2 templates **no readinessProbe on cart**, the
service the flag names. `readinessProbe` appears twice in the entire render,
both on the collector — 2 containers of 26. With the flag genuinely on, cart held
`ready=true` and `restartCount=0`, its EndpointSlice never changed, and no
`Unhealthy` Event fired. So the adjudication this ticket was waiting for has **no
winner**: ticket 05's restart loop and ticket 01's Event are both wrong. Pick a
different Kubernetes-native Fault, or accept that the Kubernetes signal class
comes from elsewhere. **13 flags enabled, 12 usable.**

**"Start from the Demo's fifteen fault flags" counts two knobs as faults.**
Chart 0.41.2 ships 15 flags, but `loadGeneratorTraffic` and `loadGeneratorVUs`
are load knobs. The menu starts from **13**, and one of those is inert, so **12**.

**A Fault can be invisible in logs.** `adFailure`, genuinely firing, produced
clean `Targeted ad request received` lines and nothing else in the ad service's
log. It was visible only in metrics and span metrics — gRPC status 14 at
0.0167/s, and `STATUS_CODE_ERROR` on **five services at once**: ad,
frontend-proxy, flagd, fraud-detection, payment. **An Alert rule written on log
volume would never fire for this Fault.** Per-Fault, this ticket has to name
which signal class actually carries it rather than assuming logs do.

That five-service spread is also the many-to-one shape **already present** with
no Grafana grouping change, which is an input to ticket 14.

**Flipping a flag requires a pod restart.** flagd reads an `emptyDir` populated
once by an init container, not the ConfigMap. The presenter's one action is the
ConfigMap edit **plus `kubectl rollout restart deploy/flagd`**, which adds a
rollout delay between the action and the first symptom — size the Cascade window
accordingly.

**Kubernetes Events are available but awkward.** They reach Loki only at
`mode: deployment`, watch-only with **no backfill**, and with **no isolating
stream selector**: `{event_domain="k8s"}` and `{k8s_resource_name="events"}`
both return zero streams, because those are structured metadata. The only
selector that finds them is `{service_name="unknown_service"}`.
