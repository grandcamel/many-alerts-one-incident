# The OpenTelemetry Demo as the system under simulation

Type: research
Status: resolved
Resolved: 2026-09-15, by a research subagent
Blocked by: none

## Question

Is the OpenTelemetry Demo the system this effort simulates, and what would it cost to run it beside the LGTM stack? Facts a later grilling needs:

- Its footprint on Docker Compose and on Kubernetes: CPU, memory, number of images, as documented and as reported on small machines.
- The feature flags it ships that inject faults: each flag, what it breaks, and which signals (logs, metrics, traces, Events) show the breakage.
- How it is pointed at an external collector or LGTM stack (the `grafana/otel-lgtm` image, or Grafana Alloy) instead of its bundled collector, Prometheus, Jaeger and Grafana.
- Whether its services carry Kubernetes-shaped resource attributes when run on Compose, and what they carry on Kubernetes.
- Whether a flag flip can be recorded as a Change: does `flagd` or the demo emit anything on a flip, and how could one be turned into a Grafana annotation or an OpenTelemetry log event.
- What a minimal subset of its services looks like if the whole thing is too big, and whether the demo supports running a subset.

Primary sources: opentelemetry.io demo docs, the `open-telemetry/opentelemetry-demo` repository, and the `grafana/docker-otel-lgtm` README.

## Answer

Findings: `docs/research/otel-demo-as-the-system-2026-09.md` on branch `research/otel-demo-as-the-system` (commit 668afa2), cited to the demo's docs, its repository files and the Helm chart. Nothing was run.

- **Yes, it is the system.** Twenty-one services in twelve languages, all traced, fourteen with OTLP logs; fifteen fault flags on `main` (fourteen in release 3.0.0), all default off, flipped at runtime through `src/flagd/demo.flagd.json` or the UI at `:8080/feature`. Flag evaluations are already in the telemetry: Python span events, .NET counters, and flagd's `feature_flag.flagd.impression{variant}` metric. The Run can see the cause in the same data as the symptoms.
- **The default does not fit the laptop.** `make start` is 28 containers and 7,899 MB of declared limits (docs say 6 GB RAM, 14 GB disk) against a Docker Desktop VM exposing 4 CPUs and 7.8 GiB. `compose.yaml` alone (`start-minimal-no-o11y`) is 20 containers and 4,155 MB; removing the load generator (1,500 MB), the flagd UI and the docs container leaves about 2.4 GB. `start-minimal` at 6,819 MB is out.
- **The Helm chart (0.41.2) is the DigitalOcean shape**, 8,548 Mi of limits with no requests, and `agent`, `chatbot` and `mcp` on by default at 500 Mi each; one open report of an OOM loop on a 4 vCPU / 8 GiB node. Turn those three and the four bundled backends off.
- **Wiring into LGTM is a documented seam**: `otelcol-config-extras.yml` plus `compose.extras.yaml` on Compose, adding an `otlp_http` exporter at `lgtm:4318`, keeping the `span_metrics` connector (the collector crashes without it), and repeating receiver arrays because a merge replaces them; on Helm, `jaeger`, `prometheus`, `grafana` and `opensearch` set to disabled. Chain the demo's own collector into LGTM rather than bypassing it: the RED metrics, the Docker and PostgreSQL receivers and the redaction transforms live there.
- **Resource attributes**: on Compose, `service.*`, `host.name` and `os.type`, with `container.*` only on `docker_stats` metrics and no `k8s.*` at all; on Helm, the `k8sattributes` preset adds about two dozen `k8s.*` and `container.*` attributes.
- **A flip is not yet a Change.** flagd emits only a gRPC `configuration_change` event and one uncollected log line. A Change record is a watcher of about thirty lines on flagd's event stream that posts a Grafana annotation and an OTLP log record. The flag file is the Change's source of truth.
- **Two flags need the bigger deployments**: `kafkaQueueProblems` needs the Kafka layer (+1,080 MB); `failedReadinessProbe` needs Kubernetes with the chart's `kubernetesEvents` preset turned on. The other thirteen work in the core layer.
- **Pin a version and say which.** Release 3.0.0 shipped k6 as the load generator; `main` reverted to Locust on 2026-09-01 and added `productCatalogLockContention` on 2026-09-08. The docs and the chart describe 3.0.0, and `latest` images come from the same workflow as version tags.

What this settles for the map: the system question in "Which system, and where it runs" narrows to where and in what shape, since the Demo fits the story and its faults are documented. "Can the laptop hold it" has a precise recipe: the core layer with three containers removed, chained into LGTM, inside a 7.8 GiB VM. "Faults and their Cascades" starts from the fifteen flags and the two that need the bigger deployments. The Change is a small build the simulation spec must include.

Could not verify: what the `latest` images currently are; any measured memory locally; LGTM's own memory use; whether the local Compose is v2 on Engine 20.10.8; the Envoy fault route and cart readiness code beyond the docs; whether Tempo's metrics generator could replace `span_metrics`.
