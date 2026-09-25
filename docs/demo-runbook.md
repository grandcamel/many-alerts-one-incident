# Future live demo storyboard

Status: **design only**, 2026-09-25. This is the intended audience sequence under the accepted ADRs. It is not a command runbook or authorization to provision a venue, start a paid Run, change a tenant, or adjudicate a Report. The legacy Compose launcher is retired. Timing, model choice, billed cost, fault menu, and venue readiness are unqualified.

## Audience question

Can one investigated Fault produce many Alerts while responders receive one evidence-backed Incident, with uncertainty, recovery and cost visible instead of hidden?

The presenter should make one approved Fault action in the intended venue. Its mechanism is recorded in repository Ground truth for later human adjudication; the Run cannot read that record. The corresponding Change may expose the triggering operator action, but it cannot tell the Run the Mechanism. The first live milestone ends with a Report and an Incident containing the accepted Alert members. Memory and Change are additional scenes only after their own authority gates pass.

## Proposed screen and sequence

| Scene | Audience surface | What to demonstrate | Honest stop or fallback |
| --- | --- | --- | --- |
| 1. Fault and Cascade | System telemetry and Grafana Alert list | One Fault raises distinct, correlated symptoms. Show the Notification arrival count without treating every Alert as a new Incident. | If the selected Fault or collector evidence is not qualified in the intended venue, use labelled recorded material. |
| 2. Admission | Receiver view of sanitized records and queue/hold state | Durable acknowledgment, latest-admitted status per Fingerprint, bounded coalescing, and a stable work identity across restart. | A journal failure refuses admission; a dispatch hold stays visible. |
| 3. Match | Candidate Incident Reports and OPS Incident | A Run weighs time-bounded candidates, cites evidence for a Match, and leaves ambiguity explicit. One Incident may accumulate several Fingerprint labels. | A suspected wrong Match or duplicate goes to human correction; the Run does not silently merge. |
| 4. Investigation | System telemetry, sanitized Run timeline, Report revision | Every observation cites retrieved system evidence; the suggested root cause is marked as inference and judged against the hidden Mechanism by a named human. Show missing evidence as missing. | Incomplete audit or unsupported claims prevent a clean diagnostic pass. |
| 5. Recovery and budget | Operator-only Run/effect and accounting status | Contrast a clean attempt with a held or uncertain one: confirmed OPS effects survive; retries require reconciliation and a new reservation. Show provider actuals separately from estimates and cloud spend. | Unknown opening balance, outstanding exposure, uncontained child, or uncertain mutation holds dispatch. |
| 6. Resolve | Incident member state and final Report | Resolve only after every accepted member is Resolved and no correction remains pending. Show the final reviewed Mechanism and reproducible arithmetic. | Forced completion needs explicit human authorization and names unresolved members. |
| 7. Learning, if qualified | Reviewed Memory audience card and Change stage | Show source/review status, a prior Incident as context, and operator action versus observed Change stage. | Pending review, stale source, missing tenant grants, or uncertain Change stage stays pending/unknown. |

The Report is not a magic answer: an early revision can be partial, and later Alert evidence can change it through explicit corrections. Run telemetry explains execution and gaps, not the system's cause. Memory is context, not independent confirmation. The Incident remains authoritative in OPS; local journals and cards are not replacement Incident databases.

## Evidence gates

| Before this scene can be live | Required evidence or decision | Current state |
| --- | --- | --- |
| Fault/venue | Qualified Fault menu, intended DOKS topology, current cloud allocation, protected teardown and off-cluster handoff. | Venue work is not accepted for this presentation. |
| Paid Run | Authoritative weekly opening and billing line/adjustment identity, defensible exposure bound, durable reservation writer, current rates/limits, three representative Fault lifecycle qualification samples. | Ledger opens with unknown population and rejects reservation creation; no model is qualified. |
| Run and effects | Authenticated service grants; one-use dispatch permit at the real Forwarder exchange; native client request/stream evidence; durable intent and receipt writer; containment/reap/read-back; restart reconciliation. | Pure and hold-only local claims exist; no guarded launch/effect path is accepted. |
| OPS Incident | Dedicated project authority, actual field and transition read-back, candidate Match and uncertain-write reconciliation. | No tenant acceptance or mutation is claimed by this branch. |
| Report | Trusted Eyes retrieval, private audit capture/redaction and citation links, deterministic prechecks, named human review for each revision. | Local ADF layout and prechecks are not support or causal adjudication. Ticket #19's provider-blocked path stays blocked. |
| Memory/Confluence/Change/audience | Source identity and conditional update, effective tenant grants, reviewed curation, trusted operator identity and stage observations, audience access and revocation. | Contracts and local candidates exist; no live card, Change authority, or tenant grant is accepted. |

These gates follow [ADRs 0006–0018](adr) and the [local evidence closeout](../.scratch/many-alerts-one-incident/reviews/local-goal-closeout-2026-09-25.md). The planned $150 model envelope and $3 reservation in ADR 0013 are policy inputs, not proof that a request has a hard billing cap or that any current spend is authorized. Cloud spend has a separate approval boundary.

## Presenter preparation after gates pass

Once the exact evidence above is accepted, write a new operational runbook against the qualified model, venue, tenant and launcher. It should pin the Fault and its hidden Mechanism, the audience surfaces and access, the clean baseline, timed observations and expected gaps, the stop/reconcile/teardown actions, and an authorized replay fallback. A complete rehearsal must use the intended API auth and venue and retain its billing, effect, audit and human-review receipts. Until then, this document is the reviewable design for that runbook.
