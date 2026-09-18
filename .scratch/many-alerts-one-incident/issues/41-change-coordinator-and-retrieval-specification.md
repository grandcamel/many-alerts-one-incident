# Change coordinator and retrieval specification

Type: task
Status: open
Blocked by: 12, 25

## Question

Produce an implementation-ready specification for [ADR 0015](../../../docs/adr/0015-changes-record-operator-actions-and-observed-stages.md), not an implementation or live probe. Define one operator-controlled in-cluster coordinator, globally serialized actions, immutable request identities, stage sequencing, intent-before-dispatch, fresh version/value preconditions, explicit undo links and crash/restart reconciliation. Map each accepted Fault's existing actuation/undo recipe without generic shell/exec or widening Run permissions.

Specify exact Kubernetes resources, allowed fields and operations, control authentication, operator alias/private-principal handling, mounts/identity separation and prevention of Run control/mutation access. Verify the supported native read-back surface for served values/evaluations without assuming an exec or OFREP route works for every flag; preserve distinct requested/written/rolled-out/served/evaluated outcomes and unknown observations. Cover flagd-ui restriction and detected emergency/out-of-band drift without promising comprehensive Kubernetes audit coverage.

Define the 100 MiB durable operator journal with 10 MiB reserved for recovery, seven-day journal and dedicated Loki Change retention, byte accounting, capacity preflight, persistence across coordinator/pod restart and explicit private unresolved-state handoff before expiry/reset/destruction. Specify schema/body bounds, sanitization and limited actor identity retention. Ordinary injection cannot consume emergency reserve. Disk-full or unavailable storage must not prevent direct operator emergency undo; expose gaps and disqualify the sample rather than pretending the Change is complete.

Specify the collector/Loki source namespace and verified Eyes/Forwarder retrieval, current-rehearsal readiness diagnostic, query and reference shapes, stable Change/stage IDs, deduplicated display and optional derived Grafana annotation. Distinguish action evidence from application symptoms and diagnosis. Keep Ground truth and scoring feedback out of shared records. The stream's seven-day retention is separate from ADR 0010's 24-hour Run feed; its journal is not that feed's persistent spool.

Define monotonic 180-second actuation and 30-second stage-queryability thresholds, bounded export backoff and three-send attempts, operator inspect/reconcile/resume controls and held admission. Timeout cannot imply upstream cancellation. No automatic mutation replay. Verify undo ordering, prior-value restoration under drift checks and required service restart without implying Alert/Incident recovery.

Offline fixtures must exercise real coordinator/journal/transport/query interfaces: duplicate/conflicting IDs; simultaneous injection/undo; accepted write then lost response; rollout still running at timeout; stored versus served mismatch; unavailable evaluation; restart between intent/effect/confirmation; drift and partial action; duplicates/late delivery; no Loki visibility despite export success; collector outage; failed annotations; reserve/capacity/expiry/handoff; inaccessible mutation authority; emergency undo without recording; and redacted identity/forbidden Ground truth. Fixture success is not tenant grants, deployment isolation or live Fault qualification. List separately authorized intended-venue gates for actual actuation, retrieval, authority and failure recovery; run none here.

## Accepted venue input from ticket 30

ADR 0016 gates injection on venue age/readiness and requires verified off-cluster handoff of unresolved Change state before teardown. Preserve emergency undo and explicit uncertain stages when ordinary admission is held. Age 90 is not deletion authority; completed export does not mean the system recovered.
