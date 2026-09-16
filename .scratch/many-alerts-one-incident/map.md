# Map: many-alerts-one-incident

Label: wayfinder:map
Charted: 2026-09-15
Lives on: branch `main` in [many-alerts-one-incident](https://github.com/grandcamel/many-alerts-one-incident), seeded from grafana-jsm-sandbox on 2026-09-15 by the ticket "Seed the new repo".

## Destination

Two agent-ready specs, the telemetry simulation and the reasoning Run, plus the ADRs they need, with the second spec blocked on the first, in a new public repo seeded from this one's history. The map is done when `/to-spec` can write both without an open question.

## Notes

### Domain

- Glossary: `CONTEXT.md` on this branch. Chapter two redefines Incident and Match and adds the simulation-side terms. ADR 0006 records the redefinition; ADRs 0001 to 0005 still hold except where a ticket says otherwise.
- Chapter one is the grafana-jsm-sandbox `main` branch. This effort does not touch it.

### Skills every session consults

- `/grilling` and `/domain-modeling` for every grilling ticket.
- `/research` for research tickets. Findings go to `docs/research/<slug>-2026-09.md` on a `research/<slug>` branch, cited to primary sources.
- `/prototype` for prototype tickets.
- The `claude-api` skill before any claim about a Claude model, its price, or a Claude Code flag. Never from memory.

### Standing preferences, decided while charting on 2026-09-15

- Date: soft target 2026-10-31. Slot: assume thirty minutes and one lifecycle, so that one Run may think for five minutes on screen.
- Live demo and public repo both. Public from the first push.
- Plan, don't do. The two specs are the handoff.
- Report-only. The Run never remediates; remediation is a suggestion in the Report.
- One Incident per Fault; the Match is a judgment (ADR 0006).
- Ground truth rule: every Fault has a documented Ground truth, and a Report is judged by whether its Suggested root cause names it. A ticket that adds a Fault writes its Ground truth.
- Citation rule: every claim in a Report's root-cause section cites evidence the Run retrieved.
- Eyes and Hands both go through a sentinel. Anonymous Grafana access goes away.
- One Kubernetes-native Fault is in the story, so Kubernetes is real, gated by the capacity prototype. The fallback is compose with Kubernetes resource attributes and synthesized Kubernetes Events, decided on the map rather than in rehearsal.
- Cloud is allowed: if the laptop cannot hold the simulation, or the demo wants sharing and accessibility, deploy to cloud. DigitalOcean is the one cloud with tooling on this machine.
- Recognizable system preferred: the OpenTelemetry Demo if it fits; a hand-rolled topology copying its shape if not.
- Many-to-one: one Run per Notification stays; Grafana grouping widens so a Cascade tends to arrive together; the Run judges the Match against open Incidents, so the Report grows across Runs.
- Memory is three stores: Incidents in OPS, pages in a Confluence space reached through `confluence-as` as the peer of `jira-as`, and the Memory directory. What lives where is a ticket.
- Model: fit-to-slot. Opus 5 at high effort was the hypothesis; it was tested and does not fit five minutes, see [Does a high-effort Run fit the slot](issues/11-does-a-high-effort-run-fit-the-slot.md).
- Structured events, the fourth signal: Kubernetes Events, Changes, and Run events from the Transcript and the harness's own telemetry export.
- Carried from chapter one: one command brings everything up; one presenter action starts the story; a replay script survives a broken Grafana.

### Facts gathered while charting

- Laptop: Intel 13-inch MacBook Pro, 4 physical cores and 8 threads, 16 GB. Docker Desktop was upgraded on 2026-09-16 to 4.91.0 on Engine 29.8.0, off HyperKit onto the Apple Virtualization Framework, with the kind provisioner built in and selected; `kind`, `k3d` and `minikube` are still not installed standalone and no longer need to be; `helm` is not installed either, and since ADR 0007 it *is* needed. See [Upgrade Docker Desktop](issues/18-upgrade-docker-desktop.md).
- Grafana groups by `grafana_folder` and `alertname` with a 10 s group wait and a 1 m repeat, so a Cascade of N rules is N Notifications today.
- Grafana runs with anonymous access at the Admin role.
- The `grafana/otel-lgtm` image runs Grafana, Loki, Tempo and Prometheus (not Mimir), ingests OTLP only, and today answers the demo container on every backend with no credential.
- Docker Desktop's VM now exposes 8 CPUs and 11.68 GiB to containers at a 12 GiB setting; the slider's ceiling is the host's whole 16 GiB, reserving nothing for macOS.
- `jira-as` 2.0.0 and `confluence-as` 1.1.1 are installed side by side in `~/.as-plugins-venv`; the image carries `jira-as` only.
- Cloud tooling: `doctl` 1.162.0 is installed and authenticated to the PRSM SPACE team; `kubectl` is installed; **`helm` is not**. DOKS offers 1.36.3-do.5, matching the laptop's built-in kind 1.36.1. One `s-8vcpu-16gb` node costs $0.142860 an hour, to the cent what two `s-4vcpu-8gb` nodes cost, with 320 GB of disk.
- Chapter one's recorded Transcript shows `model=claude-fable-5-1`.
- The LGTM image's Prometheus is 3.9.1 and drops delta-temporality counters; the demo stack's Loki now holds a handful of Claude Code records from the research probes of 2026-09-15, carrying the account's email.

## Decisions so far

<!-- one line per resolved ticket: the gist, then the ticket for the detail -->

- [Which model, at what effort, on a headless Run](issues/04-which-model-at-what-effort.md) — `--model` by full id and `--effort` (or `CLAUDE_CODE_EFFORT_LEVEL`) both work on `claude -p`; `high` is the default; Opus 5 is $5/$25 and Fable 5.1 $10/$50 per million tokens; the slot guards are `--max-turns`, `--max-budget-usd` and SIGINT, with no wall-clock cap.
- [confluence-as as the peer of jira-as](issues/06-confluence-as-as-the-peer-of-jira-as.md) — same auth shape and site as `jira-as`, five one-line operations writing storage XHTML, shares the venv; but it refuses a plain-http site URL, so the Forwarder must speak TLS on loopback or `confluence-as` must gain an http option.
- [Where a real Kubernetes could run](issues/05-where-a-real-kubernetes-could-run.md) — the laptop is a rehearsal venue at best (12 GiB floor, Docker Desktop 4.0.0 must be upgraded first); the live venue is two `s-4vcpu-8gb` DOKS nodes at about $3.43 a day with `--ha=false`; Kubernetes Events and pod status reach Loki through the Collector's `k8sobjects` receiver; read-only `kubectl` goes through `kubectl proxy` behind the Forwarder with the sentinel as bearer token.
- [The OpenTelemetry Demo as the system under simulation](issues/01-otel-demo-as-the-system.md) — it is the system: fifteen runtime fault flags whose evaluations are already in the telemetry; the default deployment (7.9 GB of limits) does not fit the laptop but the core layer (about 2.4 GB trimmed) does; chain its collector into LGTM through the documented extras; a flag flip needs a small watcher to become a Change; pin 3.0.0 or a commit.
- [How a Run could see telemetry](issues/03-how-a-run-could-see-telemetry.md) — the LGTM image runs Prometheus, not Mimir; anonymous off works and Viewer answers every read a Run needs; Loki, Tempo and Prometheus must bind to loopback so Grafana is the only door; two candidates survive, `mcp-grafana` read-only in stdio or a standard-library `eyes` CLI, with a prototype to choose.
- [What the harness tells us about a Run](issues/02-what-the-harness-tells-us-about-a-run.md) — Claude Code exports eight metrics, twenty-six log events and beta traces over OTLP, verified in print mode under `dontAsk`; `session_id` joins export and Transcript; the stack's Prometheus drops the default delta counters unless temporality is cumulative; identity attributes ride on every record and need a collector processor or a demo account; the Transcript itself still has to be shipped.
- [Seed the new repo](issues/07-seed-the-new-repo.md) — the effort lives at `github.com/grandcamel/many-alerts-one-incident`, public since 2026-09-15, `main` seeded from this branch with the six `research/*` branches alongside and chapter one untouched at 705732d; a pre-publish audit found no secret or identifier in anything published, corrected six factual errors including both bugs the handoff named, and left the third-party quotations to their own ticket.
- [Does a high-effort Run fit the slot](issues/11-does-a-high-effort-run-fit-the-slot.md) — Opus 5 on high takes 370 s against a seven-Alert Cascade, so five minutes is not realistic. `xhigh` and `medium` both blew the 64,000-token output cap while serializing the Report, which is what stalled them rather than the effort dial; `xhigh` died having filed nothing. Haiku 4.5 finished in 74 s for $0.15 but **fabricated a control**, claiming two services healthy it never queried, so speed came at the citation rule. Fable 5.1 is unmeasured: it alone is refused for want of usage credits, while Opus 5 and Haiku run. Separately: the allow list denies a `jira-as` command on length alone between 9,417 and 11,313 characters. **Report size is the lever** on the clock, the output cap and the command ceiling alike, which makes this the tightest constraint on [The Report](issues/16-the-report.md). A Run that never ran reports `subtype: success` and exits 0; `is_error` is the honest field.
- [Upgrade Docker Desktop](issues/18-upgrade-docker-desktop.md) — 4.0.0 to **4.91.0** on Engine 29.8.0, Compose v5.5.1 and bundled Kubernetes v1.36.1; the VM moved off HyperKit to the Apple Virtualization Framework with VirtioFS. Allocation is now **8 CPUs and 12 GiB** (11.68 GiB to containers) against a slider ceiling of the full 16 GiB, so the 12 GiB floor is met with headroom to spare. **The kind provisioner ships built in and is the selected mode**, disabled by default, with `kubeadm` offered alongside it — and `docker desktop kubernetes status`/`images` answer all of that from the CLI. But **enabling Kubernetes is not CLI-driveable** (corrected by [Can the laptop hold it](issues/08-can-the-laptop-hold-it.md)): the plugin offers only `status`, `images` and `reset-cluster`, so a human at the Dashboard, or a write to `settings-store.json`, is required.
- [Can the laptop hold it](issues/08-can-the-laptop-hold-it.md) — **yes, and not narrowly.** Everything up under load with the fault firing leaves **8.39 GiB of 11.68 GiB free**; the whole stack costs about 2.6 GiB. An idle kind cluster is **~735 MiB**, the figure ticket 05 could not source. Grafana answers a Run-shaped range query in **75 ms** mid-fault. `adFailure` gave 12 errors in 140 requests and flipping it back restored 92 of 92. But memory was never the binding constraint: **VM disk was the first ceiling** (7.1 G free against ~14 G of images, uncosted by tickets 05 and 18, raised to 102 G by hand) and the **host** hit load average 8.84 on 8 threads while the VM idled at 215.8% of 800%. The finding that outlives the fit question: **a Fault's cause is invisible in the telemetry** — 240 metric names in Prometheus, none `feature_flag*`, and flagd's stdout never reaches Loki — so the Change watcher is load-bearing for the Citation rule, not optional. Also corrects the image pin, the compose totals, the backends, the trim and the flag count.
- [Which system, and where it runs](issues/09-which-system-and-where-it-runs.md) — **one `s-8vcpu-16gb` DOKS node at 1.36.3-do.5, Helm chart 0.41.2, everything in-cluster, nothing public** (ADR 0007). The gate passed on memory — ticket 08 left 8.39 GiB of 11.68 spare — so the Kubernetes Fault is real, not synthesized; what decided the venue was the *host*, with no CPU headroom left for the act of presenting. One node beats two at identical cost. The layer is the chart's defaults minus `agent`, `chatbot`, `mcp` and the four backends: **Kafka and the load generator stay on**, which gives all **13 fault flags** and retires `traffic.sh`. The `DEMO_VERSION=latest` trap is **Compose-only** — chart 0.41.2's appVersion pins the images. The Receiver and each Run move into the cluster so every network path points outward and no tunnel is needed; both credentials become Kubernetes Secrets and the Forwarder becomes a sidecar. `make up` stays one command with provisioning behind `CREATE_CLUSTER=1`. Nothing is exposed: the Jira URL, the public repo and a recorded Transcript are the whole sharing story. The shape is **unmeasured end to end** — [Can one DOKS node hold the chart](issues/26-can-one-doks-node-hold-the-chart.md) carries that.

## Not yet specified

- Alert rules: how many, over which signals, with what thresholds, so that one Fault yields a Cascade of five to ten Alerts inside the slot. Waits on Faults.
- Skills: how the one Skill becomes several (Hands, a triage method, per-signal query guides) and what each holds. Waits on Eyes and Memory.
- The presenter's one action for chapter two and its undo. Waits on Faults.
- Replay fixtures for a Cascade. Waits on Faults and many-to-one.
- The Confluence space: which space, what seeds it, what a Run writes there, and restricting the account's write to that space, since `confluence-as` has no space guard. Waits on Memory.
- What the audience sees of Memory growing. Waits on Memory.
- The Run telemetry dashboard: what the audience sees of the Run observing itself. Waits on Run telemetry.

## Out of scope

- Auto-remediation. The Run never acts on the cluster or the system. Ruled out while charting.
- Chapter one. grafana-jsm-sandbox `main` stays as it is; this effort lives in the seeded repo.
- Problem, the OPS issue type for recurrence. Reserved, as chapter one left it.
- Sev-0 and Major incident. The Run never sets them, as chapter one decided.
- Production hardening beyond the demo boundary: multi-tenancy, high availability, real paging.
