---
name: demo-setup
description: Plan the future Many Alerts, One Incident live demo. Use when asked to set up, rehearse, or run this repo's demo, or to prepare its newcomer walkthrough. First identify the current gates and turn the storyboard into a reviewable preparation plan; the legacy live launcher is retired.
---

# Future demo preparation

Read [the current status](../../../README.md) and [future demo storyboard](../../../docs/demo-runbook.md), then inspect the accepted ADRs and the local evidence closeout linked there. Explain the proposed Fault → Cascade → one Incident → evidence-backed Report milestone and ask which optional recovery, Memory, Change, and audience scenes the engineer wants to prepare.

For each requested scene, list its audience surface, required evidence, owner decision, and the current local/external boundary. Make a preparation checklist with exact stop conditions and a labelled replay fallback. Distinguish source tests, admission-only replay, native/provider evidence, tenant read-back, human adjudication, and a qualified live rehearsal. Preserve pending or unknown states rather than turning them into a pass.

Do not use the historical Compose, `doctor --with-model`, `verify --live`, or reset path as a current setup procedure. The former direct-token entrypoints refuse and their one Alert lifecycle does not implement the accepted Run, Forwarder, accounting, Match, or Report contracts. When asked to execute a live demo, report the missing gates from the storyboard and prepare the operational runbook only after the exact evidence and authorization exist. Do not reroute the provider-blocked ticket #19 path.

Done when the engineer has a reviewable scene order, the required evidence and decision for each live step, and a clear distinction between available local material and externally gated work. This skill does not change credentials, tenant state, resources, or spending.
