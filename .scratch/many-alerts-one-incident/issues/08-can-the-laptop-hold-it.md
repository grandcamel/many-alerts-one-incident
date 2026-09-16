# Can the laptop hold it

Type: prototype
Status: resolved
Resolved: 2026-09-16, by a prototype on branch `prototype/laptop-capacity`
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
  prototype does not need a human at the Dashboard to *operate*. It does need one to
  **consent**: enabling Kubernetes claims several GiB of the 12 GiB allocation, pulls four
  images, and leaves the laptop running a cluster and twenty-odd containers for as long as
  the measurement takes. Ask before enabling it, say roughly how long the machine will be
  busy, and know the way back is `docker desktop kubernetes reset-cluster` plus turning it
  off again. Do not treat "the CLI can do it" as permission to do it.

The measurement question is unchanged and is now the only one left: how much of the 11.68 GiB
a kind cluster leaves for the Demo's core layer, LGTM and one Claude container.

## Answer

Prototype: branch `prototype/laptop-capacity` (commits 702d7eb, e26d809), harness
and per-stage numbers under `prototype/laptop-capacity/`. Summary in
`results/SUMMARY.md`, the six surprises in `results/00-blockers-found.txt`.

The `/prototype` skill offers two branches, a logic-model HTML file and UI
variations. Neither fits a capacity measurement, so this followed the skill's
shared rules instead: throwaway and marked so, one command, no polish, state
surfaced at every step, captured to a branch with the answer here.

**Yes, the laptop holds it, and not narrowly.** Docker Desktop 4.91.0 at 8 CPUs
and 11.68 GiB, the demo pinned at `DEMO_VERSION=3.0.0`:

| Stage | Containers | VM MemAvailable |
|---|---|---|
| Docker idle | 0 | 11.03 GiB |
| + kind cluster | — | 10.31 GiB |
| + LGTM | 1 | 9.78 GiB |
| + demo core layer | 20 | 8.56 GiB |
| + Claude container (2g cap) | 21 | 8.57 GiB |
| under load, fault on | 21 | **8.39 GiB** |

The whole stack costs about **2.6 GiB** of 11.68 GiB. **An idle kind cluster is
~735 MiB** — the figure ticket 05 said no Docker or kind page supplies. LGTM is
429 MiB idle and 742 MiB working, against ticket 05's estimated 650 MiB. The 20
demo containers declare 2,655 MB of limits and use 1,827 MiB under load, so
limits overstate reality by about a third.

**Grafana is comfortably usable**: health in 4 ms, search 37–46 ms under load,
and a Run-shaped PromQL range query over ten minutes in **75 ms**, all while the
fault was firing. Four datasources live: Loki, Prometheus, Tempo, Pyroscope.

**A fault flag fires and is visible.** `adFailure` on gave 12 errors in 140
requests against a clean 92-of-92 baseline, with `GetAds Failed with status
Status{code=UNAVAILABLE}` in Loki; flipping it off restored 92 of 92, so the
presenter's undo works.

**The constraint is not memory.** Three things bind before RAM does:

1. **VM disk.** The first ceiling hit was 58.4 G with 7.1 G free against the
   demo's ~14 G of images. Tickets 05 and 18 costed CPU and RAM only. Raised to
   102 G by hand. Any venue decision must budget disk.
2. **The host, not the VM.** Containers used 215.8% of 800% of VM CPU, but host
   load average hit **8.84 on 8 threads**. The VM has headroom; the laptop does
   not. Screen sharing and a browser compete with this during a live demo.
3. **Report size**, already the tightest constraint per ticket 11, is untouched
   by any of this.

### What this costs the map, beyond the fit question

**The cause of a Fault is invisible in the telemetry.** Ticket 01 claimed flag
evaluations are already in the telemetry via `feature_flag.flagd.impression`.
Measured: Prometheus holds 240 metric names and **none** match flag, impression
or feature; flagd emits only span metrics and `target_info`; flagd's stdout
never reaches Loki (0 streams); and a Loki search across all services for the
flag file, `configuration_change` or `adFailure` returns **0 matches**. The
symptom is rich, the cause is absent.

That collides with two standing preferences. The Ground truth rule judges a
Report by whether its Suggested root cause names the Fault's Ground truth; the
Citation rule requires every root-cause claim to cite evidence the Run
*retrieved*. With no retrievable evidence of the flip, a Run can infer the flag
but never cite it. **The ~30-line Change watcher ticket 01 sketched is
load-bearing, not optional** — it is what makes the citation rule satisfiable
for flag-injected Faults, and the simulation spec cannot omit it.

### Corrections to the map

- `compose.yaml` at 3.0.0 is **3,167 MB** of limits across 20 services, not
  ticket 01's 4,155 MB. The load generator is 512 M, not 1,500 MB. The trim to
  17 is 2,355 MB, which does match ticket 01's "about 2.4 GB".
- `compose.yaml` alone carries **no** Jaeger, Prometheus, Grafana or OpenSearch
  — they live in `compose.observability.yaml`. There is nothing to turn off.
- **The 3.0.0 git tag does not pin the images.** The demo's `.env` at that tag
  sets `IMAGE_VERSION=3.0.0` *and* `DEMO_VERSION=latest`, and `compose.yaml`
  interpolates the latter. A clean clone runs `latest` code while reporting
  `service.version=3.0.0` — telemetry lying about itself — with flagd's config
  mounted from the 3.0.0 tree against newer service code. The spec must pin
  **`DEMO_VERSION`** by name. `3.0.0-*` tags do exist on ghcr.io.
- **`docker desktop` cannot enable Kubernetes.** It offers only `status`,
  `images` and `reset-cluster`. Ticket 18's "does not need a human at the
  Dashboard to operate" is wrong for enabling; a human or a write to
  `settings-store.json` is required. Reset and status are driveable.
- **The core layer cannot be trimmed by naming services.** `frontend-proxy`
  depends on `flagd-ui` and `telemetry-docs`, so 20 containers start, not 18.
  Dropping them needs an override that rewrites that `depends_on`.
- 3.0.0 ships **fifteen** flags, not fourteen. Two are load knobs
  (`loadGeneratorTraffic`, `loadGeneratorVUs`); with `kafkaQueueProblems`
  needing Kafka and `failedReadinessProbe` needing Kubernetes, the core layer
  leaves **11 usable Faults**.
- Removing the load generator removes all traffic, so a Fault produces nothing
  until something drives the system. `traffic.sh` on the branch is the stopgap;
  the spec needs a deliberate answer.

### Not measured

The Demo deployed **on** Kubernetes via Helm — the shape the story's
Kubernetes-native Fault actually needs. This measured Compose beside an idle
kind cluster, as the ticket asked and as decided on 2026-09-16. The sum fits
with ~6.4 GiB spare, so the Helm arm is not obviously blocked, but it is
unproven. Also unmeasured: whether the other ten services emit OTLP logs, since
this traffic only exercised the ad, product and recommendation paths.
