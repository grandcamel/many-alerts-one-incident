# Where a real Kubernetes could run

Type: research
Status: resolved
Resolved: 2026-09-15, by a research subagent
Blocked by: none

## Question

What does a real Kubernetes cost on this laptop, and on DigitalOcean, for a demo that needs a cluster, a multi-service system, the LGTM stack and one Claude container? Facts:

- Docker Desktop's built-in Kubernetes versus kind on an Intel Mac with 8 cores and 16 GB: overhead of each, whether Docker Desktop's allocation can be raised from 8 GB to 12 GB and what is left for the workload.
- DigitalOcean Kubernetes: the smallest viable cluster, its price per hour and per month, the `doctl` steps to create and destroy one, and whether a single droplet running k3s is cheaper for a demo that is up for a day.
- How Kubernetes Events get into Loki: Grafana Alloy's `loki.source.kubernetes_events`, the OpenTelemetry Collector's `k8sobjects` or `k8s_events` receiver, and `kubernetes-event-exporter`; which the `grafana/otel-lgtm` image can ingest from directly.
- Read-only RBAC for a `kubectl` a Run may execute: the ClusterRole, the service account, and how the kubeconfig would be held so that the Run never holds the cluster credential (the chapter-one Forwarder pattern, ADR 0002).
- Whether the LGTM stack and the Receiver container would live inside the cluster or beside it on Compose, and what each choice does to "one command brings everything up".

Primary sources: Docker Desktop, kind, DigitalOcean, Grafana Alloy, OpenTelemetry Collector contrib, and Kubernetes RBAC documentation.

## Answer

Findings: `docs/research/where-a-real-kubernetes-could-run-2026-09.md` on branch `research/where-a-real-kubernetes-could-run` (commit bf89ecf), cited to Docker, kind, DigitalOcean, Grafana, OpenTelemetry Collector and Kubernetes documentation, with the LGTM idle figure measured here.

- **The laptop, corrected.** The CPU is 4 physical cores and 8 threads, not 8 cores. Docker Desktop is 4.0.0 from 2021 on Engine 20.10.8 and HyperKit; the kind provisioner appears by 4.43.0 and became the default at 4.65.0, the Kubernetes view in the Dashboard is 4.51 and later, and the current release is 4.91.0. Upgrading is step one before any capacity prototype.
- **The workload before Kubernetes** is about 8.7 GiB: the OpenTelemetry Demo's documented 6 GiB, the LGTM image at 650 MiB idle as measured, the demo container's 2 GiB cap. A control plane on top is unsized by any Docker or kind page. 12 GiB of Docker allocation is the floor and leaves macOS, a browser and screen sharing 4 GiB. Verdict: rehearsal-capable with the Demo's bundled Jaeger, Prometheus, Grafana and OpenSearch turned off; not the live venue.
- **Cheapest DigitalOcean**: two `s-4vcpu-8gb` DOKS nodes at $48 a month each, $0.0714 an hour, about $3.43 a day, 12 GiB allocatable, control plane free with `--ha=false`. Two traps: on every DOKS version offered (1.36+) the high-availability control plane defaults on when omitted, $40 a month prorated and irreversible; and `doctl` defaults to three `s-1vcpu-2gb-intel` nodes with 1 GiB allocatable each. A single 16 GiB k3s droplet is $3.00 a day, not meaningfully cheaper. Four rehearsal days and the demo come to under $20.
- **Kubernetes Events into Loki**: the `grafana/otel-lgtm` image ingests OTLP only; port 3100 is not exposed. Recommendation: the Collector's `k8sobjects` receiver (beta) inside the Demo's own collector, watching `events.k8s.io` and pods, exported to `lgtm:4318`. OOMKilled is a pod status, not a reliable Event, so pods must be watched too; the kubelet restarts the container, so the Fault presents as a restart loop and the Alerts that fire are whatever the restart count and the service's latency do. The `k8s_events` receiver is alpha and carries no deprecation notice.
- **Read-only kubectl without a credential in the Run**: a custom ClusterRole with get, list and watch on pods, events, deployments and nodes; the Receiver runs `kubectl proxy --reject-methods='POST,PUT,PATCH,DELETE'` with a bound service-account-token kubeconfig behind the Forwarder; the Run's `kubectl` points at `--server=http://127.0.0.1:<forwarder>` with the sentinel as its bearer token. ADR 0002 is unchanged in shape.
- **A runbook rule**: never run `doctl kubernetes cluster create` without `--ha=false`, `--size` and `--count`.

What this settles for the map: "Can the laptop hold it" gains a prerequisite task, upgrading Docker Desktop, and a precise experiment: 12 GiB, backends off. "Which system, and where it runs" has its cloud arm priced. "Eyes" has its kubectl shape. "Faults and their Cascades" knows that the Kubernetes-native Fault is a restart loop with a pod-status signal. The seed task's tree gains a `k8s/` layout: the LGTM image as a manifest, the Demo chart with a values file, a Kustomization for the Receiver, `make up` and `make down` wrapping `doctl` and `kubectl`.

Could not verify: Docker Desktop's memory ceiling on this machine, which is read off the Resources pane; idle overhead of a kind or Docker Desktop cluster; kind on Engine 20.10.8; Loki's bind address inside the image; kind pods resolving `host.docker.internal`; kubectl against an http proxy with no user entry, implied by the docs rather than stated; the proration basis of the HA charge; the Demo's memory with its backends off; Helm 3.14 and later versus 4.0.
