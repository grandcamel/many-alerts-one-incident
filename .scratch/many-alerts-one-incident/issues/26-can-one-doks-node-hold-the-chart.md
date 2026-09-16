# Can one DOKS node hold the chart

Type: prototype
Status: open
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
- Does `failedReadinessProbe` behave as ticket 05 predicted: a restart loop with
  a pod-status signal rather than a reliable Kubernetes Event?
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
