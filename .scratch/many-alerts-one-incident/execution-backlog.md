# Execution backlog

Updated 2026-09-22. This is the current work queue; the [map](map.md) preserves
historical decisions and measurements. Accepted ADRs take precedence over old
measurements or proposed specifications. Ticket counts are workflow status,
not a percentage of the finished product.

## Standing authority and continuation

The user requested aggressive ticket progress without repeated “continue”
prompts, cheaper-model delegation, and local commits. Automatic continuation is
active in the existing task every 30 minutes, under automation
`advance-many-alerts-one-incident`. It reports meaningful changes or required
action, rather than repeated unchanged status.

The [experiment authorization](reviews/ticket-23/experiment-authorization.json)
covers aggregate experiment cost strictly below $50 across attempts and retries;
it is not a fresh allowance per worker, week, or restart. Current provider actuals
and available balance remain unreconciled. A reservation is not a hard charge
ceiling. The approved pinned synthetic rubric remains approved; human review of
future Reports is a separate requirement.

Local specification, implementation within authorized scope, testing and review
continue without another permission question. Full tests precede commits that
change code. Work stays local. The explicit 2026-09-22 push was completed through
`ee2d838`; it does not make later pushes automatic. The provider-blocked C2 implementation is not
retried; its unrelated dirty files and the historical planning-frontier edits
are preserved. No paid probe starts on an assumed balance or an unqualified
transport. A planning-only ticket does not become runtime/deployment authority
merely because its document is finished.

## Verified baseline

- 44 tickets: 30 resolved, 13 open and ticket 19 claimed.
- The supervised streaming integration joins an actual fixed child to the
  bounded two-hop Python loopback TLS fixture.
- Latest code validation: **874 passed, 36 skipped**, including 39 new supervised
  integration tests and the existing streaming, buffered and process regressions.
  See the [supervised streaming outcome](reviews/ticket-23/supervised-streaming-outcome.md).
- The [native readiness register](reviews/ticket-23/native-adapter-readiness.md)
  separates implemented synthetic fixtures from the unqualified native client,
  provider accounting, isolation and intended venue.

## Priority queue

Retained specification batches: [recovery](reviews/ticket-37/recovery-specification.md),
[accounting](reviews/ticket-38/accounting-specification.md), and
[audit](reviews/ticket-39/audit-specification.md), followed by
[telemetry](reviews/ticket-35/telemetry-specification.md),
[Change](reviews/ticket-41/change-specification.md), and
[Confluence](reviews/ticket-43/confluence-specification.md).
The [first integration review](reviews/recovery-accounting-audit-integration.md)
and [second integration review](reviews/telemetry-change-reference-integration.md)
record their shared boundaries and corrections. Remaining interface and
live-evidence gaps stay explicit; drafting does not resolve those gates.
The [Eyes](reviews/ticket-12/eyes-proposal.md),
[compact Report](reviews/ticket-16/report-proposal.md), and
[Forwarder](reviews/ticket-36/forwarder-specification.md) proposals now extend
those drafts; their [integration review](reviews/eyes-report-forwarder-integration.md)
retains the unresolved client and native-boundary gates.
The [Memory](reviews/ticket-32/memory-specification.md),
[venue lifecycle](reviews/ticket-42/venue-specification.md), and
[audience](reviews/ticket-44/audience-specification.md) drafts now complete the
initial specification sequence. Their
[integration review](reviews/memory-venue-audience-integration.md) preserves
reset, teardown, retention and human-review boundaries. Tickets remain open
where exact implementation choices or acceptance inputs are still missing.

The [incremental synthetic TLS fixture](reviews/ticket-23/incremental-streaming-outcome.md)
now proves first-frame delivery, partial failure and bounded revocation in the
local fixture. The
[supervised streaming join](reviews/ticket-23/supervised-streaming-outcome.md) now
binds an actual fixed child's decoding to those receipts and process evidence.
The [native-launch evidence contract](reviews/ticket-23/native-launch-evidence-outcome.md)
now maps 14 evidence areas to pre-launch, post-attempt and sample-set phases.
The installed client/source pins and all six historical approved fixture inputs
were reverified. Native execution remains closed.

The next substantive step is the
[local runtime source implementation proposal](reviews/native-runtime-source-implementation-proposal.md).
Tickets 36 and 37 explicitly exclude runtime implementation from their current
planning scope. Source implementation therefore needs that scope decision; more
synthetic stream cases cannot supply the missing runtime boundaries.

| Order | Tickets | Concrete next deliverable | Completion boundary |
| --- | --- | --- | --- |
| 1 | 37, 38, 39 | Initial specification batch retained; consume it in the next contracts and reconcile later interface deltas | Planning artifacts with explicit unresolved inputs and real-interface acceptance cases; no claim of runtime acceptance |
| 2 | 35, 41, 43 | Reviewed initial specifications retained; reconcile later Eyes/Forwarder and venue interface deltas | Exact contracts derived from accepted ADRs; version-specific or tenant facts retain evidence gates |
| 3 | 12, 16, 36 | Initial proposals retained; integrate client selection, exact native bindings and later acceptance evidence | Progress independent sections despite C2; surface only genuinely missing human decisions; do not silently choose a provider-blocked implementation |
| 4 | 32, 42, 44 | Initial drafts retained; bind native OPS state, storage, provider age/inventory and operator projection to future evidence | Planning only; preserve distinct storage, retention and authority boundaries |
| 5 | 23 and integration follow-ups | Native-launch evidence contract and source pins complete; local application implementation proposal ready for scope decision | Existing planning-only tickets grant no runtime implementation; proposed code/tests stay local and keep native/provider/tenant/deployment execution closed |
| 6 | Live qualification | Execute a concrete, technically ready experiment under standing cost authority | Known cumulative exposure below $50, required transport/account/evidence/venue gates and human adjudication; no automatic qualification from synthetic success |

Independent specification sections may advance before their linked tickets
close. Missing tenant evidence does not prevent writing a precise acceptance
case. Conversely, a drafted acceptance case is not a passing test or proof of
deployment behavior. Keep ticket status open where its actual completion
criteria remain unmet and link completed deliverables from the issue.

## Remaining external gates

| Gate | What is missing | Work that can proceed meanwhile |
| --- | --- | --- |
| Provider-blocked ticket 19 C2 | Original implementation path remains blocked; no retry authority is inferred | Other tickets, source contracts and independent fixtures |
| Paid experiment admission | Authoritative prior charges, unsettled exposure and a defensible remaining cumulative balance; technical admission still incomplete | Ledger/recovery specification and offline boundary tests |
| Native client and venue | Exact observed client behavior, protected credentials/control, enforced route/lease, account and deployment acceptance | Source preparation and explicitly synthetic fixtures |
| Human Report adjudication | Actual future Report revisions and private evidence for a named human reviewer | Capture/parser contracts, deterministic prechecks and evidence preparation |
| External actions outside scope | Concrete provisioning, new auth/keys, publication or tenant mutation not already authorized for that action | Prepare reviewable plans and continue other local work |

The prepared implementation scope decision is the next required input. Existing
paid, native, tenant, venue and human-adjudication gates are unchanged; approval
of local code/tests would not satisfy those external acceptance gates.
