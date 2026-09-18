# Fallback Fault Ground truth

Type: task
Status: resolved
Blocked by: 24

## Question

Write and obtain human review of the repository-only Mechanism/Trigger definition for the designated presentation fallback, `adFailure`, before it supplies ADR 0014's third qualification sample. Do not choose a new fallback or reopen the three main Faults. Ticket 10 names the fallback at lines 120–122 but gives explicit Mechanism paragraphs only at lines 130, 167 and 210 for the primary three Faults.

Verify the mechanism against committed pinned source/artifacts; identify Trigger and observable diagnostic evidence without substituting a flag name for a causal explanation. Integrate ticket 29's later venue observations (lines 162–174), which supersede ticket 10's older “never measured” note: adFailure has intended-venue measurements, but those are not current model qualification. Preserve the distinction between measured original thresholds, replay-derived corrected thresholds and new live acceptance. Record uncertainties without provisioning or running a model/demo. The approved definition stays out of Run-readable Memory, OPS and shared telemetry.

Supply the reviewed definition and evidence references to tickets 38/39's qualification matrix. If committed evidence cannot establish it, record the exact missing evidence and retain the qualification gate; do not invent a Mechanism or silently drop fallback coverage.

## Work history

Claimed after ticket 34 was committed. Offline committed-source/artifact verification only; the definition remains pending human review. No cluster, model, demo or upstream runtime changes.

## Initial offline review — historical evidence gap

[Venue evidence](../reviews/ticket-40/venue-evidence.md) confirms the historical Trigger/configuration sequence, observed signals, original-rule failure to fire before undo and the limited offline threshold comparison. [Source review](../reviews/ticket-40/source-facts.md) did not locate pinned service/caller source in the bounded inspected refs/local candidate inventory. Metric and trace counts cannot establish the exact failure branch, RPC code or caller fallback.

The [incomplete definition](../reviews/ticket-40/definition-pending.md) records the confirmed Trigger and exact missing causal evidence. Obtain pinned implementation or an adequate reviewed source artifact before drafting the Mechanism for human approval. This ticket remains unresolved and the fallback qualification gate remains closed; no implementation or live acceptance occurred.

## Source gap addressed — submitted for human review

After gap commit `35f2b14`, a read-only upstream 3.0.0 fetch supplied immutable commit `1755859a9de82c2e5e225be68abc401a5ebf2b4f`. [Verification and retained receipts](../reviews/ticket-40/source-verification.md) establish a nominal one-in-ten server-side UNAVAILABLE failure branch and frontend ad-data error propagation. Source emits a WARN log, so historical zero matching log results are not proof the implementation is silent. Historical image/source correspondence remains unverified.

The [proposed Mechanism/Trigger definition](../reviews/ticket-40/definition.md) is ready for the required human review. Ticket remains claimed until approval; corrected-rule and model/venue qualification are separate gates. No source was executed and no cluster/model/demo run occurred.

## Answer

The human approved the [repository-only fallback definition](../reviews/ticket-40/definition.md) with “Approved” on 2026-09-18. Trigger: `adFailure` → `on`. Mechanism: intermittent server-side ad-retrieval rejection with gRPC UNAVAILABLE at nominal one-in-ten probability, propagated by the frontend ad-data handler instead of a successful replacement ad response, with server error instrumentation. This is not a total ad outage or proof of checkout failure.

The source is pinned to upstream commit `1755859a9de82c2e5e225be68abc401a5ebf2b4f`; retained text snapshots, original notices/license and hashes support the definition. Source WARN logging corrects any inference that historical zero matching log lines prove code silence. Original-threshold measurements and corrected-threshold sample comparisons remain separate from live corrected-rule acceptance.

Ticket 40's definition/review gate is complete. Tickets 38/39 may use this approved Ground truth in operator-only qualification/scoring, never as Run-readable context. Source/image correspondence, actual diagnostic retrieval, live corrected-rule behavior and the existing model/venue/permission/budget gates remain outstanding. No source, model, cluster or demo was executed.
