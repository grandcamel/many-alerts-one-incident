# Forwarder integration and acceptance

Type: task
Status: open
Blocked by: 12, 17, 21, 22, 33

## Question

Produce an implementation-ready specification for [ADR 0011](../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md), not runtime changes. Define the one-sidecar/five-listener layout; native path handling; fixed upstream origins; per-service credential and sentinel configuration; operator-owned local CA/server certificates and client trust; certificate/lease/request-size/response-size/timeout bounds; and controlled rotation.

Specify Receiver-only authenticated registration/revocation, enforceable Receiver/Run OS identity and mount separation, orphan lease expiry, restart invalidation, and treatment of in-flight uncertain writes. Demonstrate why Runs with Read and approved tool access cannot obtain control credentials or upstream secrets. Shared pod networking is not a per-container authorization mechanism. Specify bypass prevention and mediated Anthropic path and permitted telemetry-export path without contradicting ADR 0010's best-effort export.

Combine ticket 12's exact Eyes operations and ticket 33's Confluence grants with request-aware policies: allowed path/body/query shapes, current-rehearsal telemetry scope, Kubernetes resource/namespace restrictions, and explicit Jira/Confluence writes. Deny unscopable queries, unknown operations and caller-directed origins. Define redirect rejection and header normalization without leaking authority. Native clients must use scoped sentinels through verified TLS; no insecure/direct fallback.

Offline acceptance must cover real client request construction and local TLS/transport boundaries: valid and wrong-service sentinels; pre-admission/revoked/expired/restart authority; inaccessible control plane/secret mounts; hostname/CA/expiry failures; path/encoded-path and absolute-target handling; redirects; malformed/oversize requests; read queries using POST; prohibited writes and Kubernetes subresources; unknown mutation outcomes without blind retry; mandatory-route readiness versus optional Confluence and export failure. Keep source, offline, model/tool, tenant/RBAC and deployment acceptance distinct.

Readiness must not discard pending Notifications or decide overall Run outcomes; ticket 21 owns recovery/classification. No live credential, cluster, demo or runtime implementation is authorized by this planning ticket.

ADR 0013 adds Anthropic API-key custody outside Runs, a fixed fifth endpoint and per-Run sentinels. Specify and verify streaming, supported client endpoint/trust configuration, credential replacement, safe usage visibility, revocation, direct-route prevention and mandatory Anthropic readiness. Do not assume client compatibility or restore the old direct-key exception. Coordinate billing exposure with ticket 38; revocation cannot stop billing for an already-dispatched request.

## Accepted Change input from ticket 25

ADR 0015 adds dedicated current-rehearsal Loki Change queries to the read-only Eyes policy. The operator coordinator and its mutation/control credentials stay outside Runs and their Kubernetes Forwarder route. Verify source distinction and prevent a Run from forging authoritative coordinator Change records or invoking action control. Optional annotations require no new Run write authority.

## Accepted Confluence input from ticket 33

ADR 0017 requires registered current-rehearsal draft IDs/Incidents and exact approved reference versions/digests, enforced status/operation and expected-version body binding. Deny other Confluence operations and cross-scope metadata leaks. The installed CLI read-then-increment is insufficient stale-body protection; ticket 43 supplies the narrow contract. Keep curator/manifest authority outside Runs and disable affected routes when enforcement is unverified.

## Specification progress, 2026-09-22

The [Forwarder specification](../reviews/ticket-36/forwarder-specification.md) supplies concrete proposed
operation, scope, payload and acceptance contracts. The
[integration review](../reviews/eyes-report-forwarder-integration.md) and
[source checks](../reviews/eyes-report-forwarder-sources.md) preserve the shared
request, retrieval, revision and uncertain-effect boundaries. This is planning
work, not an accepted replacement ADR, changed tool permission, or runtime
acceptance. The ticket remains open for its unresolved inputs and final review.
No provider-blocked C2 retry or live request was performed.

## Separately authorized application follow-up, 2026-09-22

The user's [separate implementation approval](../reviews/native-runtime-source-implementation-approval.json)
authorizes local application source and tests outside this ticket's planning-only
scope. The [first unit](../reviews/forwarder-lease-implementation-outcome.md)
adds fixed service profiles, mandatory/optional readiness and the in-process
scoped lease registry, with independent review and local tests. It does not wire
the existing launcher, authenticate control peers, start listeners or establish
native, tenant, credential-isolation or deployment acceptance. This ticket stays
open; authenticated control, fixed TLS/request policy and the remaining evidence
are subsequent work.

The [second local unit](../reviews/forwarder-control/outcome.md) adds authenticated
control sessions on accepted Unix sockets: OS peer-UID checks, bounded
challenge/response and commands, replacement fencing, and revocation or a held
registry on failed closeout. Its full suite passes 977 tests with 36 skipped.
This does not provision a listener or validate deployed secret/mount/kernel
isolation, Linux peer credentials, service TLS or native request policies.

The [third local unit](../reviews/forwarder-listener/outcome.md) provisions a private
filesystem Unix socket under a verified operator parent, checks permissions and
identities around acceptance, and preserves replaced/unknown paths during cleanup.
Permanent controller shutdown holds authority and interrupts admitted sockets.
Independent review passes; the full suite reports 1009 passed and 36 skipped.
Managed accept/worker supervision remains next, followed by service TLS/request
policy. Deployed identity, ancestor/mount/ACL/group and credential isolation remain
separate acceptance gates. This planning ticket remains open.

The [fourth local unit](../reviews/forwarder-supervisor/outcome.md) adds bounded
control-service supervision: one accept loop, at most four handlers and one
transient accepted socket, tracked startup ownership, and shared shutdown/join
observation. Unknown endpoint or thread completion cannot become a clean receipt
without the required observations. Independent review passes; the full suite
reports 1034 passed and 36 skipped. An existing TLS deadline test was repaired
to avoid concurrent operations on one client SSL object while retaining its
deadline and no-upstream assertions. Fixed service TLS/request policies and
durable Receiver/accounting remain subsequent local work; this ticket stays open.

The [fifth local unit](../reviews/forwarder-tls/outcome.md) adds a fixed-service
TLS client boundary with explicit CA-only trust, exact service SANs, certificate
lifetime bounds and one TCP/handshake deadline. Independent source review passes;
52 focused tests and the full suite (1086 passed, 36 skipped) pass. Real local
TLS fixtures use an asserted destination adapter to ephemeral ports; they do
not qualify deployed fixed-port listeners, native clients or credential custody.
Server TLS/request policies and durable Receiver/accounting remain next. This
planning ticket stays open and no native/provider/deployment admission changes.

The [sixth local unit](../reviews/forwarder-http/outcome.md) adds the common HTTP
complete-buffer parser: strict framing and sizes, fixed Host/Accept, canonical
Basic/Bearer sentinels, path ambiguity rejection and query-key allowlists.
Independent source/test review passes. Focused tests report 104 passed; the full
suite reports 1190 passed and 36 skipped. Local composition tests preserve the
separate registered/active/revoked/service/scope/generation lease checks. No
server transport, route authorization, native client compatibility or deployed
request acceptance is implied. Server TLS/receipt, route policies and durable
Receiver/accounting remain subsequent work; this planning ticket stays open.

The [seventh local unit](../reviews/forwarder-server-tls/outcome.md) adds fixed
TLS listeners with exclusive configured-context ownership, exact SNI, a shared
accept/handshake deadline and explicit closeout state. Real local fixed-port
exclusivity and client/listener/parser composition pass; deadline-clipped idle
accept polling corrects observed Darwin shutdown behavior. Independent review
passes; focused tests report 49 passed and the full suite 1239 passed, 36 skipped.
The operator still owns context/key custody; production HTTP collection, route
policy and dispatch coordination remain separate work. This planning ticket
stays open, with native and deployment acceptance gates unchanged.

The [eighth local unit](../reviews/forwarder-http-receive/outcome.md) adds bounded
incremental request collection over TLS with shared head validation and one
absolute deadline. A permanent socket claim prevents repeated collection. The
full suite exposed a stalled-handshake shutdown failure; nonblocking handshake
steps and deadline-clipped readiness waits correct it while preserving the
original real-TLS assertion. Independent review passes; 157 HTTP focused tests,
52 TLS regression tests and five shutdown repetitions pass. Final full suite:
1295 passed, 36 skipped. Response handling, route policy, atomic dispatch and
durable Receiver/accounting remain subsequent local work. This planning ticket
stays open; native/deployment and human acceptance gates remain separate.

The [ninth local unit](../reviews/forwarder-http-response/outcome.md) adds a
complete-buffer non-streaming response codec. It enforces status/header/body
bounds and canonical framing, discards upstream metadata and validates again
before canonical serialization. Independent source/test review and 83 focused
tests pass; the full suite reports 1378 passed, 36 skipped. No socket collection,
response send, receipt, route success or native/upstream compatibility is implied.
Response transport, receipt-before-send and service policy remain subsequent
local implementation. This planning ticket stays open.

The [tenth local unit](../reviews/forwarder-response-receive/outcome.md) adds
bounded response collection from an established client TLS socket. It shares
head/framing validation, enforces the original deadline and twenty-second read
inactivity, and preserves caller socket ownership and one-shot collection.
Independent review and 137 focused tests pass; the full suite reports
1432 passed, 36 skipped. Local synthetic TLS observations do not qualify real
upstreams or native clients. Receipt-before-send forwarding, route policies and
durable Receiver/accounting remain subsequent work. This planning ticket stays
open under the separate local implementation authority.

The [eleventh local unit](../reviews/forwarder-receipts/outcome.md) adds the
sanitized receipt ledger and receipt-gated client response send. Explicit
dispatch transitions distinguish the specification's five receipt states.
Capacity failure occurs before any upstream connection. Delivery requires a
locked ledger claim whose digest matches the private receipt record. Independent
review workflows, a root delivery-seam redesign and a final hash-bound review
pass; the full suite reports 2063 passed, 36 skipped. Upstream connection, lease
and permit coupling, route policy and durable Receiver/accounting remain
subsequent work. This planning ticket stays open.

The [twelfth local unit](../reviews/forwarder-routes/outcome.md) adds strict JSON
and request-aware Jira route policy for the two read shapes whose inputs are
resolved: registered issue read and first-page open-candidate search. Scope
manifests bind to the lease digest, selections stay within them, upstream
requests are rebuilt from trusted values, and response validation checks
returned scope. Mutations, projections, continuations and every non-Jira route
remain unavailable with named missing inputs. Independent review passes; the full
suite reports 2627 passed, 36 skipped. Lease/permit/upstream coupling and durable
Receiver/accounting remain subsequent work. This planning ticket stays open.

The [thirteenth local unit (13a)](../reviews/forwarder-dispatch/outcome.md) adds
the atomic dispatch gate and one-request exchange. Admission and a pre-write
fence each pair the final lease check with its ledger transition under one lock,
so revocation, expiry, heartbeat loss, hold or shutdown atomically prevents new
dispatch while already written requests may complete. In-flight and overdue
dispatches remain observable for closeout. Independent review passes; the full
suite reports 2919 passed, 36 skipped. The real upstream connector (13b), control
framing, permits and durable Receiver/accounting remain subsequent work. This
planning ticket stays open.
