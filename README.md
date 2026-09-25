# Many Alerts, One Incident

This project is designing a demo in which one Fault in the OpenTelemetry Demo raises a Cascade of Grafana Alerts. A bounded Run investigates their evidence and helps maintain **one Jira Service Management Incident for the Fault**, with a Report that distinguishes observations from an inferred cause. Later Alerts may extend the Incident; a human owns corrections and final causal review.

## Current status

**This is a future live demo design, not a runnable live Quickstart.** The earlier one Alert Compose walkthrough and direct-token launcher are retired. `python3 -m grafana_jsm_sandbox`, the standalone legacy Forwarder, and the default Compose demo entrypoint refuse before starting a Run. The journaled Receiver supports local admission-only replay; it does not launch a Run. Local tests and pure preflights do not qualify a provider, tenant, venue, or presentation.

Start with the [future demo storyboard](docs/demo-runbook.md). The [opportunities since the original onboarding branch](docs/demo-opportunities.md) explain why its old setup steps were removed. The accepted [ADRs](docs/adr) and [domain vocabulary](CONTEXT.md) are the design authority. Historical onboarding work and its measured one Alert run remain under [.scratch/demo-onboarding](.scratch/demo-onboarding) for review, outside the newcomer flow.

## Intended audience story

| Beat | What a future audience should see | Boundary that must hold |
| --- | --- | --- |
| Fault and Cascade | One controlled system Fault produces several distinct Alerts. | Repository Ground truth stays outside the Run's world. |
| Admission and Match | Notifications enter a durable, bounded queue; the Run considers candidate Incidents and explains its Match. | An ambiguous Match may create a separate Incident; no silent merge or reassignment. |
| Investigation and Report | Retrieved system evidence supports each observation and a clearly marked causal inference. | The Report's citations and arithmetic are checked; a human reviews causal support. |
| Recovery and cost | A failed or uncertain attempt is held for reconciliation, with its spending reservation and effect state visible. | No automatic retry, duplicate mutation, or capacity inferred from unknown billing. |
| Resolution and learning | The Incident tracks all accepted Alert members through resolution; reviewed Memory and Change can add context. | Forced completion and Memory correction remain human owned. |

The first proposed live milestone is the Fault → Cascade → one Incident → evidence-backed Report path. The [storyboard](docs/demo-runbook.md) also specifies optional recovery, Memory, Change, and audience surfaces and their independent gates. No exact Fault, model, spend, venue action, or demo date is qualified by this document.

## Local work available now

- `python3 -m pytest -q -p no:cacheprovider` runs the repository's offline suite. Its result is local source verification only.
- The [journaled Receiver](docs/recovery-journal.md) can exercise sanitized Notification admission and read back local recovery records without dispatch.
- The accounting ledger and reservation views preserve an **unknown** opening population and reject new reservations until authoritative continuity and billing evidence exist.
- Run/effect, dispatch-permit, supervision, Report, Memory, audit, Change, and audience modules have local hold-only, pure, or preflight contracts. They do not establish a launched Run or accepted external effect.

The [local evidence closeout](.scratch/many-alerts-one-incident/reviews/local-goal-closeout-2026-09-25.md) names the exact open external decisions. The provider-blocked ticket #19 path must remain blocked; it is not a demo fallback.

## Future live admission

The design requires an authoritative accounting opening and current billing source; a guarded Run/effect writer with verified native client and Forwarder paths; protected worker containment and restart reconciliation; an accepted intended venue and separate cloud allocation; tenant permissions and read-back; complete private citation audit; and named human Report adjudication. The [storyboard's gate table](docs/demo-runbook.md#evidence-gates) maps these to the planned scene. Until those receipts exist, present only clearly labelled local replay or design material.
