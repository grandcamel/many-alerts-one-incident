# Execution backlog

Updated 2026-09-23. This is the current work queue; the [map](map.md) preserves
historical decisions and measurements. Accepted ADRs take precedence over old
measurements or proposed specifications. Ticket counts are workflow status,
not a percentage of the finished product.

## Standing authority and continuation

The user requested aggressive ticket progress without repeated “continue”
prompts, cheaper-model delegation, and local commits. At the user's request,
automatic continuation `advance-many-alerts-one-incident` was deleted on
2026-09-22 for transfer to a fresh Claude session. Do not recreate this session's
reminder automatically. The user authorized
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
`b592df8`; it does not make later pushes automatic. The provider-blocked C2 implementation is not
retried; its unrelated dirty files and the historical planning-frontier edits
are preserved. No paid probe starts on an assumed balance or an unqualified
transport. A planning-only ticket does not become runtime/deployment authority
merely because its document is finished.

## Verified baseline

- 44 tickets: 30 resolved, 13 open and ticket 19 claimed.
- The supervised streaming integration joins an actual fixed child to the
  bounded two-hop Python loopback TLS fixture.
- Latest code validation: **3500 passed, 36 skipped**, including focused
  service, lease, control, listener, supervisor, TLS, HTTP, receipt, response-send,
  JSON, route-policy, dispatch-gate, exchange, upstream-connector and
  control-framing tests plus existing regressions.
  The [control-framing outcome](reviews/forwarder-control-framing/outcome.md),
  [upstream connector outcome](reviews/forwarder-upstream/outcome.md),
  [dispatch-gate outcome](reviews/forwarder-dispatch/outcome.md),
  [route-policy outcome](reviews/forwarder-routes/outcome.md),
  [receipt and response-send outcome](reviews/forwarder-receipts/outcome.md),
  [TLS response collection outcome](reviews/forwarder-response-receive/outcome.md),
  [HTTP response outcome](reviews/forwarder-http-response/outcome.md),
  [bounded HTTP receipt outcome](reviews/forwarder-http-receive/outcome.md),
  [server TLS outcome](reviews/forwarder-server-tls/outcome.md),
  [HTTP boundary outcome](reviews/forwarder-http/outcome.md),
  [TLS client outcome](reviews/forwarder-tls/outcome.md),
  [supervisor outcome](reviews/forwarder-supervisor/outcome.md),
  [private-listener outcome](reviews/forwarder-listener/outcome.md),
  [control-session outcome](reviews/forwarder-control/outcome.md) and
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
Linux peer validation, mounted secret custody, kernel
isolation and service request transport remain separate work and evidence gates.

The [third application unit](reviews/forwarder-listener/outcome.md) adds private
filesystem socket creation, guarded acceptance, conservative cleanup and permanent
controller shutdown. Independent review and the full local suite pass. The
[supervisor planning input](reviews/forwarder-listener/next-supervisor-unit.md)
defined bounded accept/handler ownership and observable shutdown completion.
Actual deployed parent/ancestor/group/mount isolation remains unqualified.

The [fourth application unit](reviews/forwarder-supervisor/outcome.md) joins the
private listener and authenticated controller under one lifecycle owner. It
bounds handlers and transient accepted sockets, retains startup/shutdown
ownership, and reports unknown completion until outstanding work is observed.
Fixed service TLS/request policies and durable Receiver/accounting integration
remain subsequent local implementation work.

The [fifth application unit](reviews/forwarder-tls/outcome.md) adds fixed-service
TLS client connections using only explicit CA trust, exact SAN identities and
bounded certificate lifetime. All five services pass real local TLS handshakes;
negative trust, identity, lifetime and deadline cases fail closed. Test routing
uses ephemeral fixture ports, so fixed server-port binding remains unqualified.
Server-side TLS listeners/request policies and durable Receiver/accounting
integration remain subsequent local work.

The [sixth application unit](reviews/forwarder-http/outcome.md) implements the
common complete-buffer HTTP boundary independently of the pending server TLS
listener. It validates framing, fixed Host/Accept profiles, canonical sentinels,
path structure and allowed query keys. Independent review and all 104 focused
tests pass. Parser success grants no lease, route or dispatch authority. Next
join bounded server receipt/TLS, request-specific policy and atomic dispatch
checks, then durable Receiver/recovery and accounting integration.

The [seventh application unit](reviews/forwarder-server-tls/outcome.md) adds
fixed service TLS listeners, exact SNI rejection, exclusive context/socket
ownership and deadline-bounded accept/handshake. Real local tests bind all five
actual fixed ports exclusively and separately compose the strict TLS client,
listener and parser using ephemeral handshake fixtures. Darwin idle-accept
shutdown now uses short polls against one deadline. Independent review and
49 focused tests pass. Bounded production HTTP receipt/response and route-specific
dispatch checks remain next; native/deployment readiness is still unqualified.

The [eighth application unit](reviews/forwarder-http-receive/outcome.md) adds
bounded incremental TLS request collection with shared head validation, opaque
body preservation, one-shot socket claims and the caller's absolute deadline.
Its 157 HTTP focused tests and 52 listener regression tests pass. The first full
suite exposed stalled-handshake shutdown on Darwin; nonblocking TLS steps and
short readiness waits correct it without changing the original integration
assertion. That assertion passes five repeated runs; independent review and the
final full suite pass (1295 passed, 36 skipped). Bounded response handling and
request-aware service policy remain next, then atomic dispatch and durable
Receiver/recovery/accounting. No native or deployment qualification is implied.

The [ninth application unit](reviews/forwarder-http-response/outcome.md) adds a
bounded non-streaming complete-buffer response parser and canonical serializer.
It discards upstream headers/reasons, rejects redirects and unsupported framing,
separates 204/205 no-body rules and revalidates constructed response values.
Independent review, 83 focused tests and the full suite (1378 passed, 36 skipped)
pass. Opaque JSON-labelled bytes remain
subject to route policy; serialization performs no send or receipt creation.
Bounded response transport and receipt-before-send coordination remain next,
alongside request-aware policy and durable Receiver/recovery/accounting.

The [tenth application unit](reviews/forwarder-response-receive/outcome.md) joins
shared response-head validation to bounded collection on an established client
TLS socket. It enforces independent byte caps, twenty-second read inactivity and
the original handler deadline, preserves one-shot claims and timeout-restoration
failure precedence, and handles fragmented headerless no-body responses.
Independent review and 137 focused tests pass (83 unchanged codec tests plus 54
new deterministic and real TLS tests); the full suite passes with 1432 passed,
36 skipped. No provider connection, client response
send or receipt creation is added. Forwarding with receipt-before-send and route
policy remain next, followed by durable Receiver/recovery/accounting.

The [eleventh application unit](reviews/forwarder-receipts/outcome.md) adds a
bounded sanitized receipt ledger and receipt-gated client response send. Explicit
reserve/connect/dispatch/finalize transitions separate NOT_DISPATCHED, FAILED,
DISPATCHED_UNKNOWN, PARTIAL and TRANSPORT_CONFIRMED. Capacity is checked before
any upstream connection. A client write requires a ledger claim whose digest
matches the private receipt record. Two orchestrated review workflows, a root
redesign of the delivery seam and a final hash-bound review pass. The full suite
passes with 2063 passed, 36 skipped. No upstream connection, lease check, route
policy, permit or durable journal is added. The reviewed
[route-policy plan](reviews/forwarder-routes/implementation-plan.md) is the next
unit, followed by lease/permit/upstream coupling and durable Receiver/accounting.

The [twelfth application unit](reviews/forwarder-routes/outcome.md) adds strict
bounded JSON and the read-only Jira route policy. Receiver scope manifests hash to
the lease scope digest; caller values only select manifest entries, and the
upstream request is rebuilt from trusted values. Only issue read and first-page
search are matchable (partial); the other 23 routes are unavailable with named
missing inputs. Independent review recomputed every golden vector and passed; the
full suite reports 2627 passed, 36 skipped. The reviewed
[dispatch plan](reviews/forwarder-dispatch/implementation-plan.md) defines unit
13a: the atomic dispatch gate, write fence and one-request exchange with an
injected upstream, followed by the fixed-origin upstream connector (13b).

The [thirteenth application unit (13a)](reviews/forwarder-dispatch/outcome.md)
adds the atomic dispatch gate and one-request exchange. Lease checks and ledger
transitions share one gate lock at admission and at a write fence before the
first upstream write, so no admission or write begins after an ordered
retirement or shutdown. Scope entries install only after registry-record
verification; overdue flights keep their slot and fire one abort; closeout
reports in-process drain state. Only receipt-backed bytes reach the client, and
no upstream connector ships in source. Two existing modules gained additive
seams. Independent review passes; the full suite reports 2919 passed, 36 skipped.
The reviewed [upstream plan](reviews/forwarder-upstream/implementation-plan.md)
defines 13b, the synthetic fixed-origin connector and v2 request digest.

The [second half of the thirteenth unit (13b)](reviews/forwarder-upstream/outcome.md)
adds the synthetic fixed-origin Jira upstream connector, request digest v2 and
the canonical upstream wire. It has no production caller, and its endpoint
policy accepts only `.invalid` hosts on documentation addresses. Each connect
uses a fresh, read-back TLS context with explicit trust only, writes no
application bytes, and refuses wrong digests before any socket exists; the
channel sends once after the write fence and cannot fall back to plaintext after
an abort. Tests connect only to loopback. Independent review passes; the full
suite reports 3358 passed, 36 skipped. The reviewed
[control-framing plan](reviews/forwarder-control-framing/implementation-plan.md)
defines unit 14: scoped registration with a manifest attachment, closeout
replies and refusal of unscoped services.

The [fourteenth application unit](reviews/forwarder-control-framing/outcome.md)
delivers Receiver scope manifests and lease closeout over the existing
authenticated control connection. Every controller refuses registration for
services without a scope type. A gated controller accepts only scoped
registration, whose manifest attachment is validated before the registry changes
and installed with the control lock released; a post-install owner fence runs
before the sentinel reply. Revoke and a new closeout command report drain state;
`ok:true` means `draining` or `quiescent`, and every uncertain observation holds
the registry before its error frame. Independent review passes; the full suite
reports 3500 passed, 36 skipped. AuthorizeDispatch permits remain deferred until
the ticket-37 durable intent journal exists.

| Order | Tickets | Concrete next deliverable | Completion boundary |
| --- | --- | --- | --- |
| 1 | 37, 38, 39 | Initial specification batch retained; consume it in the next contracts and reconcile later interface deltas | Planning artifacts with explicit unresolved inputs and real-interface acceptance cases; no claim of runtime acceptance |
| 2 | 35, 41, 43 | Reviewed initial specifications retained; reconcile later Eyes/Forwarder and venue interface deltas | Exact contracts derived from accepted ADRs; version-specific or tenant facts retain evidence gates |
| 3 | 12, 16, 36 | Initial proposals retained; integrate client selection, exact native bindings and later acceptance evidence | Progress independent sections despite C2; surface only genuinely missing human decisions; do not silently choose a provider-blocked implementation |
| 4 | 32, 42, 44 | Initial drafts retained; bind native OPS state, storage, provider age/inventory and operator projection to future evidence | Planning only; preserve distinct storage, retention and authority boundaries |
| 5 | Authorized application implementation follow-ups | Service profiles, scoped leases, authenticated control, private listener, managed supervision, TLS client/server, common HTTP parser, bounded request/response collection, non-streaming response codec, sanitized receipts, receipt-gated response send, strict JSON, read-only Jira route policy, atomic dispatch gate, one-request exchange, synthetic fixed-origin upstream connector and control framing (scoped registration, closeout replies) complete; next the ticket-37 durable Receiver journal and recovery, ticket-38 accounting, then AuthorizeDispatch permits, a worker supervisor with readiness and the guarded launcher | Local code/tests authorized by separate scope decision; native/provider/tenant/deployment execution remains closed pending evidence |
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
