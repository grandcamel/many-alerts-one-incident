# Can the laptop hold it

Type: prototype
Status: open
Blocked by: 01, 05, 18

## Question

Bring up the OpenTelemetry Demo's core layer (its `compose.yaml` alone, with the load generator, flagd UI and docs container removed, chained into LGTM through the documented extras files, at a pinned version), the cheapest laptop Kubernetes from "Where a real Kubernetes could run", and the LGTM stack, on this laptop with Docker Desktop's allocation at 12 GiB or the ceiling the upgrade task found, the Demo's bundled Jaeger, Prometheus, Grafana and OpenSearch turned off, and measure. Does it fit with headroom for one Claude container? Does one fault flag fire and show in Grafana? Is Grafana usable while it runs? Record the numbers, the allocation used, and what broke. The throwaway lives on a `prototype/laptop-capacity` branch.
