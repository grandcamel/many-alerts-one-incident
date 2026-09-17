# Eyes

Type: grilling
Status: open
Blocked by: 03, 09, 17, 19

## Question

Which tools may a Run execute to read telemetry, and what does the allow list say? How does the sentinel pattern extend to a Grafana service account? The Forwarder's shape itself (one or one per site, and what it speaks on loopback) is decided in "The Forwarder's growth"; this ticket takes that answer as given. Is read-only `kubectl` an Eye when the cluster is real, and how is its credential held so the Run never sees it? What changes in Grafana: anonymous access off, a Viewer service account minted at startup, Loki, Tempo and Prometheus bound to loopback so that Grafana is the only door (the research found all three answer the demo container with no credential today). Whether the tool is `mcp-grafana` or a standard-library `eyes` CLI, decided on what the prototype "mcp-grafana behind the sentinel" showed and what the allow list and the Skill can say plainly. Produces an ADR extending ADRs 0002 and 0003.

## What ticket 09 settled, 2026-09-16

ADR 0007 puts Grafana, LGTM, the Receiver and each Run inside one DigitalOcean
cluster, with **nothing exposed publicly** — no ingress, no load balancer, the
presenter reaching Grafana through `kubectl port-forward`. So this ticket's
Grafana question is unconstrained by any audience requirement: anonymous access
goes away and no human-facing exception has to be carved out for viewers. The
cluster is real, so read-only `kubectl` is a live option rather than a
hypothetical, and a Run's Eyes queries stay inside the cluster.

## Input from ticket 26, 2026-09-16

**All three datasources a Run reads are usable across the wire.** Through
`kubectl port-forward` on the real venue: Prometheus `query_range` 145–170 ms
(155–191 ms under fault), Loki `query_range` 148–180 ms, Tempo `/api/search`
190 ms, Grafana `/api/health` 146 ms. Ticket 08 measured 75 ms for the same
Prometheus query locally on Compose, so the wire roughly doubles it and it stays
far inside a Run's patience. Grafana knows four datasources by uid: `prometheus`,
`loki`, `tempo`, `pyroscope`.

**Prometheus holds 578 metric names against Compose's 240**, 43 of them
`k8s_*`/`kube_*` — a signal class this venue adds and the laptop did not have.

**Two constraints on what Eyes must be able to express.**

1. **Kubernetes Events have no isolating stream selector in Loki.**
   `event_domain` and `k8s_resource_name` are **structured metadata, not stream
   labels**, and both select zero streams. The only selector that finds Events is
   `{service_name="unknown_service"}`, which collides with anything else
   unlabeled. Whatever Eyes is, it has to let a Run write that query — and the
   Run has to know to.
2. **A Fault can be invisible in logs.** `adFailure` produced no error lines at
   all; it was visible only in metrics and span metrics. Eyes that reaches logs
   well and metrics poorly would miss this Fault entirely.

**Read-only `kubectl` is load-bearing, not one option among several.** Pod
status, endpoints and restart counts have no other carrier here: Events reach
Loki only at `mode: deployment`, watch-only with no backfill, so anything that
happened before the collector started is unreachable from Loki by construction.

## Correction from ticket 10, 2026-09-16

**Point 2 above is false, and it is the stronger of two versions of a claim that was
never measured.** [Can one DOKS node hold the chart](26-can-one-doks-node-hold-the-chart.md)
said the ad service "logged clean request lines throughout" — an observation about one
service's log. This ticket restated that as "`adFailure` produced no error lines at all",
a claim about the whole telemetry system, and that stronger version is now driving the
Eyes design.

Neither version was measured. **No Loki query for ad logs exists anywhere in that
prototype**, and no Loki access occurred at any time while the flag was on; see the
correction appended to that ticket. Meanwhile [Can the laptop hold it](08-can-the-laptop-hold-it.md)
did retrieve `GetAds Failed with status Status{code=UNAVAILABLE}` from Loki on the same
`3.0.0-ad` image, and the ad Deployment sets `OTEL_LOGS_EXPORTER: otlp`.

So the premise "a Fault can be invisible in logs, therefore Eyes must reach metrics
well" loses this example. **The conclusion still holds, on better examples**: resolving
[Faults and their Cascades](10-faults-and-their-cascades.md) found two faults that are
genuinely log-silent at source — `paymentUnreachable` (all 34 `logger.*` calls read; the
failure branch is `status.Errorf` with no logging) and `productCatalogFailure`
(`span.SetStatus` and `span.AddEvent` only, in a service that demonstrably exports OTLP
logs). Rewrite point 2 against those.

**Two facts Eyes needs that this ticket does not yet carry:**

- **No application service's logs have ever been retrieved from this venue's Loki, and
  Tempo has never been queried at this venue for anything.** Every log and trace
  capability this ticket assumes is source-derived, not measured. The confirmed stream
  labels are `k8s_container_name`, `k8s_deployment_name`, `k8s_namespace_name`,
  `k8s_pod_name`, `k8s_replicaset_name`, `service_instance_id`, `service_name`,
  `service_namespace`.
- **`service_namespace="otel-demo"` on an application selector returns zero streams
  forever.** All 22 demo pod templates carry
  `resource.opentelemetry.io/service.namespace: opentelemetry-demo`, and the collector
  runs `k8s_attributes` with `otel_annotations: true`, which overwrites the
  namespace-derived value. `"otel-demo"` is correct **only** for Kubernetes Event streams,
  which come from the collector pod — the one pod carrying no such annotation. Eyes must
  steer a Run to a bare `{service_name="…"}`.

**Read-only `kubectl` is more load-bearing than this ticket already says.**
`OOMKilled` emits **no Kubernetes Event** — it is a
`containerStatuses[].lastState.terminated.reason`, carried by neither Loki nor
Prometheus. Pod status via `kubectl` is the *only* carrier for it.
