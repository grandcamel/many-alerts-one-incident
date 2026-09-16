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
- Model: fit-to-slot. Opus 5 at high effort is the hypothesis to test first.
- Structured events, the fourth signal: Kubernetes Events, Changes, and Run events from the Transcript and the harness's own telemetry export.
- Carried from chapter one: one command brings everything up; one presenter action starts the story; a replay script survives a broken Grafana.

### Facts gathered while charting

- Laptop: Intel 13-inch MacBook Pro, 4 physical cores and 8 threads, 16 GB. Docker Desktop 4.0.0 (2021, Engine 20.10.8, HyperKit) at 4 CPUs and 8 GB; it predates the built-in kind provisioner. No Kubernetes context; kind, k3d, minikube and helm are not installed; `kubectl` and `doctl` are.
- Grafana groups by `grafana_folder` and `alertname` with a 10 s group wait and a 1 m repeat, so a Cascade of N rules is N Notifications today.
- Grafana runs with anonymous access at the Admin role.
- The `grafana/otel-lgtm` image runs Grafana, Loki, Tempo and Prometheus (not Mimir), ingests OTLP only, and today answers the demo container on every backend with no credential.
- Docker Desktop's VM exposes 4 CPUs and 7.8 GiB to containers at the current 8 GB setting.
- `jira-as` 2.0.0 and `confluence-as` 1.1.1 are installed side by side in `~/.as-plugins-venv`; the image carries `jira-as` only.
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

## Not yet specified

- Alert rules: how many, over which signals, with what thresholds, so that one Fault yields a Cascade of five to ten Alerts inside the slot. Waits on Faults.
- Kubernetes Events into Loki: the research recommends the Collector's `k8sobjects` receiver watching events and pods, exported as OTLP; whether it rides in the Demo's own collector or a separate one waits on the system.
- Skills: how the one Skill becomes several (Hands, a triage method, per-signal query guides) and what each holds. Waits on Eyes and Memory.
- The presenter's one action for chapter two and its undo. Waits on Faults.
- Replay fixtures for a Cascade. Waits on Faults and many-to-one.
- The Confluence space: which space, what seeds it, what a Run writes there, and restricting the account's write to that space, since `confluence-as` has no space guard. Waits on Memory.
- What the audience sees of Memory growing. Waits on Memory.
- Cost per demo. Waits on the Run timing prototype.
- The Report's Jira ADF shape. Waits on the Report.
- How rehearsal scores a Report against Ground truth, by hand or by a script. Waits on the Report.
- Provisioning the cluster, laptop or cloud, as a task, with the `doctl` rule: never create without `--ha=false`, `--size` and `--count`. Waits on where it runs.
- The Run telemetry dashboard: what the audience sees of the Run observing itself. Waits on Run telemetry.

## Out of scope

- Auto-remediation. The Run never acts on the cluster or the system. Ruled out while charting.
- Chapter one. grafana-jsm-sandbox `main` stays as it is; this effort lives in the seeded repo.
- Problem, the OPS issue type for recurrence. Reserved, as chapter one left it.
- Sev-0 and Major incident. The Run never sets them, as chapter one decided.
- Production hardening beyond the demo boundary: multi-tenancy, high availability, real paging.
