# Can the laptop hold it

Type: prototype
Status: open
Blocked by: 01, 05, 18

## Question

Bring up the OpenTelemetry Demo's core layer (its `compose.yaml` alone, with the load generator, flagd UI and docs container removed, chained into LGTM through the documented extras files, at a pinned version), the cheapest laptop Kubernetes from "Where a real Kubernetes could run", and the LGTM stack, on this laptop with Docker Desktop's allocation at 12 GiB or the ceiling the upgrade task found, the Demo's bundled Jaeger, Prometheus, Grafana and OpenSearch turned off, and measure. Does it fit with headroom for one Claude container? Does one fault flag fire and show in Grafana? Is Grafana usable while it runs? Record the numbers, the allocation used, and what broke. The throwaway lives on a `prototype/laptop-capacity` branch.

## Premise improved, 2026-09-16

[Upgrade Docker Desktop](18-upgrade-docker-desktop.md) landed, and this ticket's starting
conditions are better than they were written:

- **8 CPUs, not 4**, and **11.68 GiB to containers, not 7.8** — the 12 GiB allocation is
  set and the slider would allow 16 GiB if it ever came to that.
- **No laptop Kubernetes needs installing.** Docker Desktop 4.91.0 ships the **kind**
  provisioner built in and already selected (`docker desktop kubernetes status` reports
  `Mode: kind`, `Version: 1.36.1`, currently disabled). So "the cheapest laptop Kubernetes
  from 'Where a real Kubernetes could run'" is now just enabling what is already there;
  kind mode pulls four images against kubeadm's ten.
- **The VM is faster**: off HyperKit onto the Apple Virtualization Framework with VirtioFS,
  which should matter for the bind mounts and for container start-up across 20-odd services.
- Enable, reset and diagnose are all driveable from `docker desktop kubernetes ...`, so this
  prototype does not need a human at the Dashboard.

The measurement question is unchanged and is now the only one left: how much of the 11.68 GiB
a kind cluster leaves for the Demo's core layer, LGTM and one Claude container.
