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
change code. Work stays local. The provider-blocked C2 implementation is not
retried; its unrelated dirty files and the historical planning-frontier edits
are preserved. No paid probe starts on an assumed balance or an unqualified
transport. A planning-only ticket does not become runtime/deployment authority
merely because its document is finished.

## Verified baseline

- 44 tickets: 30 resolved, 13 open and ticket 19 claimed.
- Local commit `17037db` adds the bounded Python loopback TLS fixture.
- Latest code validation: 794 passed, 36 skipped. The fixture has 50 focused
  tests and 16 retained examples; see the [outcome](reviews/ticket-23/mediated-client-outcome.md).
- The [native readiness register](reviews/ticket-23/native-adapter-readiness.md)
  separates implemented synthetic fixtures from the unqualified native client,
  provider accounting, isolation and intended venue.

## Priority queue

Current specification batch: [recovery](reviews/ticket-37/recovery-specification.md),
[accounting](reviews/ticket-38/accounting-specification.md), and
[audit](reviews/ticket-39/audit-specification.md). The
[integration review](reviews/recovery-accounting-audit-integration.md) records
their shared boundaries and review corrections. Their remaining interface and
live-evidence gaps stay explicit; drafting them does not resolve those gates.
The next independent drafting batch is tickets **35, 41 and 43**.

| Order | Tickets | Concrete next deliverable | Completion boundary |
| --- | --- | --- | --- |
| 1 | 37, 38, 39 | Initial specification batch retained; consume it in the next contracts and reconcile later interface deltas | Planning artifacts with explicit unresolved inputs and real-interface acceptance cases; no claim of runtime acceptance |
| 2 | 35, 41, 43 | Sanitized telemetry, Change coordinator and scoped reference/draft specifications | Exact contracts derived from accepted ADRs; version-specific or tenant facts retain evidence gates |
| 3 | 12, 16, 36 | Consolidate Eyes and compact Report proposals with the Forwarder request/receipt contract | Progress independent sections despite C2; surface only genuinely missing human decisions; do not silently choose a provider-blocked implementation |
| 4 | 32, 42, 44 | Memory acceptance, venue lifecycle/protected teardown and operator audience projection | Consume prior contracts; preserve distinct storage, retention and authority boundaries |
| 5 | 23 and integration follow-ups | Close exact-client, process, transport, accounting and private-evidence gaps in bounded increments | Implementation only where authorized; fixtures retain their limited claims; full tests and independent review before local commits |
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

No new user input is needed for the current local specification queue.
