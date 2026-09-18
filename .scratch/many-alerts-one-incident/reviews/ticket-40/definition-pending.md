> Historical gap record, superseded by the [source-verified approved definition](definition.md). The human approved it on 2026-09-18.

# Fallback Fault definition — incomplete, not approved

## Confirmed selection and Trigger

The designated fallback remains `adFailure`. Historical capture records `off` → `on`, boolean `true`, via ConfigMap edit followed by flagd rollout and an in-pod variant read-back. It separately observes ad error metrics/traces and later frontend error metrics. See [venue evidence](venue-evidence.md) and [source facts](source-facts.md).

## Mechanism — evidence gate still open

Do not yet assert the service method's exact failure branch, returned RPC code/message, failure frequency, caller fallback/conversion or end-user impact. The inspected committed artifacts contain signal counts and configuration receipts but not the pinned service/caller implementation or detailed response evidence sufficient to establish those causal claims. A service error plus frontend errors is not a complete Mechanism under ADR 0008.

Required evidence: the pinned OpenTelemetry Demo implementation of the ad request failure branch and its caller path, with an immutable source revision corresponding to the intended version; alternatively a reviewed committed source/response artifact establishing those facts. Name any source-versus-deployed-version uncertainty. The bounded offline search did not find it; this does not prove no other local copy exists.

## What remains required before qualification

1. Establish and cite the Mechanism, separately from the Trigger, then obtain the human review required by ticket 40.
2. Verify the corrected C1 threshold in the intended venue. Existing samples cross 0.03/s for frontend/frontend-proxy, but do not establish a live corrected-rule Cascade, its timing or complete alert-state behavior.
3. Retrieve the actual supporting diagnostic evidence for a future model sample. Historical trace counts do not supply a claim-by-claim citation audit.
4. Apply the existing three-sample, scope, time, spend, recovery and venue gates. Do not drop fallback coverage or claim primary-only qualification satisfies them.

Ticket 40 remains claimed/unresolved. No new Fault, runtime change, source fetch, model or cluster operation occurred. This file is a gap record, not approved Ground truth, and stays outside Run-readable stores.
