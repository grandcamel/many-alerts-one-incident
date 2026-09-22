# Execution backlog

Updated 2026-09-22. This is the current work queue; the [map](map.md) preserves
historical decisions and measurements. Accepted ADRs take precedence over old
measurements or proposed specifications. Ticket counts are workflow status,
not a percentage of the finished product.

## Standing authority and continuation

The user requested aggressive ticket progress without repeated “continue”
prompts, cheaper-model delegation, and local commits. Automatic continuation
`advance-many-alerts-one-incident` is active every 30 minutes. The user authorized
the reviewed local application source/test proposal by replying `continue` to
the pending scope question; the [approval record](reviews/native-runtime-source-implementation-approval.json)
preserves that scope. No repeated scope approval is needed for these local
implementation follow-ups. Native/provider/tenant/deployment and spending gates
remain separate; unchanged status should not produce repeated notifications.

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
- Latest code validation: **977 passed, 36 skipped**, including 103 service,
  lease and authenticated-control tests plus the existing integration regressions.
  The [control-session outcome](reviews/forwarder-control/outcome.md) and
  [first application outcome](reviews/forwarder-lease-implementation-outcome.md)
  record their distinct local source validation; the existing
  [supervised streaming outcome](reviews/ticket-23/supervised-streaming-outcome.md)
  retains its separate fixture evidence.
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

The user approved the [local runtime source implementation proposal](reviews/native-runtime-source-implementation-proposal.md)
as a separate follow-up to the planning tickets. The
[first application unit](reviews/forwarder-lease-implementation-plan.md) implements
fixed service profiles, mandatory/optional readiness and scoped lease state.
Its [review and full-suite outcome](reviews/forwarder-lease-implementation-outcome.md)
is complete. It does not wire the legacy launcher or claim authenticated control/OS isolation.

The [second application unit](reviews/forwarder-control/outcome.md) adds
authenticated control over accepted Unix stream sockets, bounded framing and
owner replacement/closeout. Local Darwin peer-UID and synthetic-secret tests pass.
Listener provisioning, Linux peer validation, mounted secret custody, kernel
isolation and service request transport remain separate work and evidence gates.

| Order | Tickets | Concrete next deliverable | Completion boundary |
| --- | --- | --- | --- |
| 1 | 37, 38, 39 | Initial specification batch retained; consume it in the next contracts and reconcile later interface deltas | Planning artifacts with explicit unresolved inputs and real-interface acceptance cases; no claim of runtime acceptance |
| 2 | 35, 41, 43 | Reviewed initial specifications retained; reconcile later Eyes/Forwarder and venue interface deltas | Exact contracts derived from accepted ADRs; version-specific or tenant facts retain evidence gates |
| 3 | 12, 16, 36 | Initial proposals retained; integrate client selection, exact native bindings and later acceptance evidence | Progress independent sections despite C2; surface only genuinely missing human decisions; do not silently choose a provider-blocked implementation |
| 4 | 32, 42, 44 | Initial drafts retained; bind native OPS state, storage, provider age/inventory and operator projection to future evidence | Planning only; preserve distinct storage, retention and authority boundaries |
| 5 | Authorized application implementation follow-ups | Service profiles, scoped leases and accepted-socket control sessions complete; next add listener provisioning, fixed TLS/request policies and durable Receiver/accounting integration | Local code/tests authorized by separate scope decision; native/provider/tenant/deployment execution remains closed pending evidence |
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

The local implementation scope is authorized; no further user input is needed
for the next application source/test unit. Existing paid, native, tenant, venue
and human-adjudication gates remain unchanged.
