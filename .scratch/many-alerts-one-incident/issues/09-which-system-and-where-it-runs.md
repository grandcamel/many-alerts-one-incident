# Which system, and where it runs

Type: grilling
Status: resolved
Resolved: 2026-09-16, by a grilling session
Blocked by: 08

## Question

Given the research and the capacity prototype: the research settled the system as the OpenTelemetry Demo and the laptop as a rehearsal venue at best, so the questions left are which layer of the Demo (core, with Kafka, with Kubernetes), which pinned version, and whether it runs on the laptop for rehearsal only, on DigitalOcean, or split, with the cluster in the cloud and the LGTM stack and the Receiver on the laptop? What does the choice do to "one command brings everything up" and to sharing the demo with people who are not in the room? Produces an ADR: the deployment target carries lock-in.

## Answer

ADR: [0007 — The demo runs on one DigitalOcean node, with everything inside the
cluster](../../../docs/adr/0007-one-digitalocean-node-with-everything-in-the-cluster.md).
Decided across three grilling rounds on 2026-09-16.

**One `s-8vcpu-16gb` DOKS node at 1.36.3-do.5, Helm chart 0.41.2, everything
in-cluster, nothing public.**

- **The venue turns on the host, not the VM.** [Can the laptop hold
  it](08-can-the-laptop-hold-it.md) proved the laptop holds the simulation with
  8.39 GiB of 11.68 GiB spare, so the standing preference's gate ("Kubernetes is
  real, gated by the capacity prototype") passed and the synthesized-Events
  fallback is not forced. What decides the venue is the other half of that
  prototype: host load average 8.84 on 8 threads while the VM idled at 215.8% of
  800%. The laptop has headroom for the simulation and none for presenting it.
- **One node, not two, at identical cost.** Ticket 05 priced two
  `s-4vcpu-8gb` nodes at $0.071430/hr each. One `s-8vcpu-16gb` is
  **$0.142860/hr — the same total to the cent** — and gives one 16 GiB, 8-vCPU
  scheduling domain instead of 12 GiB allocatable split in two, with 320 GB of
  disk against the laptop's hand-raised 102 G. About $3.43 a day; four rehearsal
  days and the demo come in under $20. `doctl` 1.162.0 is authenticated to the
  PRSM SPACE team; `kubectl` is installed; **`helm` is not**.
- **The layer is the chart's defaults minus four.** `agent`, `chatbot`, `mcp`
  and the four bundled backends off. `kafka`, `accounting` and `fraud-detection`
  **stay**, reversing the round-1 answer once the chart turned out to ship them
  enabled: on Helm, removing them is the work. All **13 fault flags** are usable
  where the Compose core layer left 11.
- **The load generator stays on**, which retires `traffic.sh` and dissolves the
  "how is the system driven" fog: it was dropped on the laptop for memory, and
  that reason is gone.
- **The pin is free here.** Chart 0.41.2 carries `appVersion: 3.0.0` and its
  image tag defaults to that appVersion from `ghcr.io/open-telemetry/demo`, so
  ticket 08's `DEMO_VERSION=latest` trap — telemetry lying about itself — is
  **Compose-only** and cannot occur. The spec sets the tag explicitly anyway so
  the pin survives a chart bump. 3.0.0 (published 2026-07-24) is still the latest
  release; `main` is the only thing ahead of it and was not chosen.
- **The Receiver and each Run move into the cluster.** With Grafana in the cloud,
  a laptop Receiver would need Grafana to reach *inward* through a tunnel, and
  ticket 15's Run telemetry would need LGTM's OTLP endpoint exposed publicly.
  In-cluster, every path points outward — Atlassian and the Anthropic API — and
  the Transcript renders through `kubectl logs -f`. The cost is that both
  credentials become Kubernetes Secrets, created from environment at `make up`.
  ADR 0002's Forwarder becomes a sidecar; ADR 0001 is unchanged, a pod being
  still one container. The image publishes to `ghcr.io` publicly.
- **"One command" survives, qualified.** `make up` stays one idempotent command,
  but cluster creation requires `CREATE_CLUSTER=1` and otherwise fails loudly;
  ticket 05's `doctl` rule is enforced inside that path rather than remembered.
  `make down` is in the spec, because an undestroyed cluster is the only way this
  demo costs real money.
- **Sharing needs nothing built.** The Incident's Atlassian URL already works for
  anyone with site access, the repo is public, and the Transcript is a recorded
  fixture. Grafana is not exposed — no ingress, no load balancer, `kubectl
  port-forward` for the presenter — which also keeps "anonymous Grafana access
  goes away" intact, since an anonymous audience Grafana would hand a Run a way
  around its own sentinel.
- **The spec describes this venue only**, with a one-paragraph pointer to
  `prototype/laptop-capacity` as the measured offline record.

### What this hands the rest of the map

- **A gap, ticketed.** The chart has never been stood up on a DOKS node — ticket
  08 measured Compose on the laptop. [Can one DOKS node hold the
  chart](26-can-one-doks-node-hold-the-chart.md) carries that risk, installs
  `helm`, and now blocks [Faults and their Cascades](10-faults-and-their-cascades.md)
  so the Fault menu is not written against a deployment that has not run.
- **A lead for [The Change](25-the-change-making-a-faults-cause-citable.md).**
  flagd's flag config is a ConfigMap on the chart, so the presenter's flip is a
  Kubernetes API write with a real resource-version change — possibly citable
  without the ~30-line watcher. Ticket 25's call, not this one's.
- **Kubernetes Events have their home**: the chart's own collector with the
  `kubernetesEvents` preset, verified by ticket 26. The fog patch is retired.
- **Provisioning is not a separate task.** It lives inside `make up` and is first
  exercised by ticket 26. That fog patch is retired too.

### Not decided here

Region (the spec takes the one nearest the presenter), the cluster's exact
values file, and whether a DigitalOcean billing alert backs up `make down`.
