# Can one DOKS node hold the chart

Type: prototype
Status: resolved
Blocked by: 09

## Question

[Which system, and where it runs](09-which-system-and-where-it-runs.md) chose a
shape nothing has measured. [Can the laptop hold it](08-can-the-laptop-hold-it.md)
measured the **Compose core layer beside an idle kind cluster, on the laptop**.
The chosen venue is the **Helm chart on one DigitalOcean node**, which is a
different deployment of a different component set on different hardware. Ticket
01's figure for the chart — 8,548 Mi of declared limits — is read off a values
file, not measured, and ticket 08 found that Compose limits overstate reality by
about a third.

Stand it up once and measure, on one `s-8vcpu-16gb` node at 1.36.3-do.5, chart
0.41.2 with `agent`, `chatbot`, `mcp` and the four bundled backends disabled and
`kafka`, `accounting`, `fraud-detection` and `load-generator` left enabled:

- What is allocatable on a single 16 GiB DOKS node, and what does the chart
  actually use against it with the load generator running? Ticket 05's "12 GiB
  allocatable" was for two 8 GiB nodes and was never measured either.
- Does everything schedule on one node, and does anything evict or OOM? Ticket 01
  found one upstream report of an OOM loop on a 4 vCPU / 8 GiB node with the
  chart's defaults.
- Add the LGTM stack and one Receiver pod with a Run's 2 GiB cap. What is left?
- Is Grafana usable through `kubectl port-forward` while a Fault fires — the
  75 ms range query ticket 08 measured locally, measured again across the wire?
- What does `failedReadinessProbe` actually produce? Ticket 05's "restart loop
  with a pod-status signal rather than a reliable Event" was about **OOMKill**,
  not this flag, and ticket 01 found this flag wants the chart's
  `kubernetesEvents` preset — so its signal is likely an Event, not a restart
  count. Measure rather than assume: whether a `Warning Unhealthy` Event fires,
  whether the pod leaves the Service's endpoints, whether the restart count moves
  at all, and whether the chart puts a liveness probe on the same endpoint.
  Ticket 10 designs the Cascade off whichever signals are actually there.
- Turn the chart's `kubernetesEvents` preset on and confirm Kubernetes Events
  reach Loki through the Demo's own collector. This is the fog patch ticket 09
  retired on the strength of the preset existing; confirm it works.
- Time and cost `make up` from nothing: how long from `doctl kubernetes cluster
  create` to a Grafana answering, and what did the run cost?

Prerequisites this ticket owns: **`helm` is not installed on this machine**
(`kubectl` and `doctl` 1.162.0 are, and `doctl` is authenticated to the PRSM
SPACE team). Install it here rather than as a ticket of its own.

**This ticket spends money.** A cluster at $0.142860 an hour is about $3.43 a
day. Ask before creating one, say roughly how long it will be up, and destroy it
in the same session — `doctl kubernetes cluster delete` — rather than leaving it
for a later one. Never create without `--ha=false`, `--size` and `--count`: the
high-availability control plane defaults **on** when omitted, at $40 a month,
prorated and irreversible, and `doctl` otherwise defaults to three
`s-1vcpu-2gb-intel` nodes with 1 GiB allocatable each.

The throwaway lives on a `prototype/doks-chart-capacity` branch.

## Answer

**Yes, and not narrowly — but three of the mechanisms the decision rests on do
not work as written, and the first one invalidated this prototype's own first
attempt.**

Measured 2026-09-16 on one `s-8vcpu-16gb` node, nyc3, 1.36.3-do.5, chart 0.41.2,
helm v3.22.0 (installed from the checksum-verified upstream tarball; brew wanted
a source build). Cluster up 2.28 h, **$0.33**, destroyed in the same session,
with no load balancer and no volume left behind. Full detail and every raw stage
file: `prototype/doks-chart-capacity/results/SUMMARY.md` on branch
`prototype/doks-chart-capacity`.

### Capacity — the question the ticket was commissioned for

**Allocatable is 7880m CPU and 13.33 GiB, with a 110-pod cap.** Ticket 05's
"12 GiB allocatable" was for two 8 GiB nodes and was never measured; one node
gives more, in a single scheduling domain.

Everything installed — the chart, LGTM, and a Receiver whose 2 GiB cap was
**genuinely exercised at 1.57 GiB** rather than merely reserved — with a fault
firing: **node working set 5.95 GiB, 9.68 GiB available.** Nothing OOMKilled,
nothing evicted, zero restarts, no pressure conditions, 35/35 pods scheduled on
the one node. **Ticket 01's upstream OOM report did not reproduce.**

Declared limits (12,030 Mi) overstate the node's actual working set by about
**2.2x**. Ticket 08's "about a third" was for Compose and does not transfer —
and the correction runs toward more headroom, not less. The chart's 8,548 Mi
that ticket 01 read off a values file is the *default* set; our shape declares
4,317 Mi across 23 workloads.

CPU under fault: **1.42–1.54 cores of 8 (~19%)**, against the laptop's host load
average of 8.84 on 8 threads that decided the venue in the first place.

Grafana through `kubectl port-forward`, all three datasources a Run reads:
Prometheus 145–170 ms steady and 155–191 ms under fault, Loki 148–180 ms, Tempo
190 ms, health 146 ms. Ticket 08 measured 75 ms locally, so the wire roughly
doubles it and it stays far inside a Run's patience. Prometheus holds **578
metric names against Compose's 240**, 43 of them `k8s_*`/`kube_*` — a signal
class the Compose venue did not have.

### The three that do not work

**1. flagd does not read the ConfigMap.** The chart mounts `flagd-config` only
into an init container that does a one-shot `cp` into an **`emptyDir`**, and the
Deployment carries no `checksum/config` annotation, so a ConfigMap write bumps
`resourceVersion` and changes nothing a service can see. Both fault runs before
this was caught were steady-state samples with every flag `off` inside the pod.
**The working flip is the ConfigMap edit plus `kubectl rollout restart
deploy/flagd`** — verified. `make up` and the presenter's one action must both
own that restart. This re-gates [ticket 25](25-the-change-making-a-faults-cause-citable.md)
rather than killing it: the write is real, and the rollout is a second API event
that emits its own Kubernetes Events.

**2. `failedReadinessProbe` has nothing to fail.** Its own flagd description
names the cart service; the chart **templates no probe on cart**. `readinessProbe`
appears exactly twice in the whole render, both on the collector — 2 containers
of 26. With the flag genuinely on: `ready=true`, `restartCount=0`, EndpointSlice
unchanged, **no `Unhealthy` Event for cart**. This refutes ticket 05's restart
loop and ticket 01's "its signal is an Event" in the same measurement. The
template half is independent of finding 1 and stands alone. **13 fault flags
enabled, 12 usable** for a Kubernetes-visible Cascade.

**3. The `kubernetesEvents` preset is off, and turning it on where the chart puts
the collector does nothing.** It is not in the demo chart at all — it belongs to
collector subchart 0.165.0 and defaults to `false`, so as ADR 0007 describes the
deployment **nothing collects Kubernetes Events**. Enabling it is not enough
either: `daemonsetConfig` omits the `applyKubernetesEventsConfig` call that
`deploymentConfig` makes, and the chart ships `mode: daemonset` — `k8sobjects`
renders **0 times at daemonset, 2 at deployment or statefulset**. It is a
template omission rather than a hard gate (`presets.kubernetesObjects.enabled=true`
renders the same receiver at daemonset with leader election). And it is **not
inert**: the ClusterRole still gains `events.k8s.io`, so the cluster grants
event-read to a collector that reads no events — no error, no warning.
**Fix: `opentelemetry-collector.mode: deployment`**, which on one node costs
nothing (metrics receivers render identically; the logs pipeline gains
`k8sobjects`) but would silently under-collect node-local metrics on a
multi-node cluster, so that line belongs to the one-node decision.

### Kubernetes Events into Loki — works, with four qualifiers

Confirmed end to end, including **`Warning`** events (`Failed`, `BackOff`) from a
deliberately planted `ImagePullBackOff`. The fog patch stays retired, but:
**(a)** the receiver watches rather than lists, so there is **no backfill** — a
Run investigating after the fact sees only what was already being watched;
**(b)** `event_domain` and `k8s_resource_name` are **structured metadata, not
stream labels**, and both select **zero** streams — the only selector that finds
Events is **`{service_name="unknown_service"}`**, which collides with anything
else unlabeled; **(c)** the body is JSON under `scope_name .../k8sobjectsreceiver`;
**(d)** volume is low.

### `span_metrics`, and helm lying about it

Chart defaults: `traces=[otlp_grpc/jaeger, debug, span_metrics]`,
`metrics=[otlp_http/prometheus, debug]`, `logs=[opensearch, debug]`.
`span_metrics` is a **connector** — traces exporter and metrics receiver at once
— so swapping the bundled backends for LGTM means rewriting exporter arrays, and
dropping it crashed every collector pod. Ticket 01 recorded this hazard for
*receiver* arrays; it bites on the *exporter* array, which is the one a venue
swap forces you to touch. Then **`helm upgrade --install --wait --timeout 20m`
exited 0 after 90 seconds with that collector in `CrashLoopBackOff`** — `make up`
cannot treat helm's exit code as proof of health.

### What a Fault looks like — for ticket 10 and ticket 14

`adFailure` is **invisible in logs**; the ad service logged clean request lines
throughout. It appears only in metrics and span metrics: gRPC status 14 at
0.0167/s, and `STATUS_CODE_ERROR` across **five services at once** — ad,
frontend-proxy, flagd, fraud-detection, payment. An Alert rule on log volume
would never fire for this Fault, and the many-to-one shape is already present
before any Grafana grouping change.

### Operational, for `make up`

- **DOKS 1.36.3-do.5 ships no metrics-server**, and the upstream manifest is
  **not sufficient** — it rolls out and still fails. It needs
  **`--kubelet-insecure-tls`**. With that, `kubectl top` works.
- **LGTM climbs ~14 Mi/min** (726 → 1640 Mi over 92 min) against a 4 GiB limit:
  safe for a 30-minute slot, reaches the cap in ~3 h. Leak or cache warm-up is
  unresolved.
- `kubectl get --raw /api/v1/nodes/<node>/proxy/stats/summary` gives node truth
  with nothing installed.

### Timings and cost

`create` 5m48s → chart 1m30s (all image pulls) → LGTM 1m02s → upgrade 20s.
**Cold path ~8m40s; warm ~2m32s.** 2.28 h × $0.142860 = **$0.33**. A demo-day
shape is ~$0.09; left up and forgotten, $3.43/day. Image pulls were a non-issue
in DO's own network, against the VM-disk ceiling that stopped ticket 08.

### Method note

The first fault measurements of this run were wrong, and an adversarial
verification pass over the findings is what caught it. Two harness bugs are
fixed on the branch: `cmd | python3 - <<'PY'` lets the heredoc win stdin, which
killed four inspection scripts; and `lib/kubelet_usage.py` required `{labels}`,
so unlabeled node metrics never matched and every result file reported a node
working set of zero — the container sum is not node usage, and here the gap is
3.39 vs 5.34 GiB.
