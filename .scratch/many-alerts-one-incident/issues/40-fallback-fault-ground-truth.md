# Fallback Fault Ground truth

Type: task
Status: claimed
Blocked by: 24

## Question

Write and obtain human review of the repository-only Mechanism/Trigger definition for the designated presentation fallback, `adFailure`, before it supplies ADR 0014's third qualification sample. Do not choose a new fallback or reopen the three main Faults. Ticket 10 names the fallback at lines 120–122 but gives explicit Mechanism paragraphs only at lines 130, 167 and 210 for the primary three Faults.

Verify the mechanism against committed pinned source/artifacts; identify Trigger and observable diagnostic evidence without substituting a flag name for a causal explanation. Integrate ticket 29's later venue observations (lines 162–174), which supersede ticket 10's older “never measured” note: adFailure has intended-venue measurements, but those are not current model qualification. Preserve the distinction between measured original thresholds, replay-derived corrected thresholds and new live acceptance. Record uncertainties without provisioning or running a model/demo. The approved definition stays out of Run-readable Memory, OPS and shared telemetry.

Supply the reviewed definition and evidence references to tickets 38/39's qualification matrix. If committed evidence cannot establish it, record the exact missing evidence and retain the qualification gate; do not invent a Mechanism or silently drop fallback coverage.

## Work in progress

Claimed after ticket 34 was committed. Offline committed-source/artifact verification only; the definition remains pending human review. No cluster, model, demo or upstream runtime changes.

## Offline review outcome — Mechanism gate remains open

[Venue evidence](../reviews/ticket-40/venue-evidence.md) confirms the historical Trigger/configuration sequence, observed signals, original-rule failure to fire before undo and the limited offline threshold comparison. [Source review](../reviews/ticket-40/source-facts.md) did not locate pinned service/caller source in the bounded inspected refs/local candidate inventory. Metric and trace counts cannot establish the exact failure branch, RPC code or caller fallback.

The [incomplete definition](../reviews/ticket-40/definition-pending.md) records the confirmed Trigger and exact missing causal evidence. Obtain pinned implementation or an adequate reviewed source artifact before drafting the Mechanism for human approval. This ticket remains unresolved and the fallback qualification gate remains closed; no implementation or live acceptance occurred.
