# Ticket 36 Forwarder implementation specification

Status: proposed implementation contract, source-only, 2026-09-22. This document
changes no listener, workload, credential, provider, tenant, client, or Run. “MUST”
below is a requirement for a future implementation; it is not a claim about the
current Python Forwarder, a deployed sidecar, or installed native clients.

## Authority and capability boundary

[ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md)
settles one Forwarder sidecar with five distinct loopback TLS listeners, fixed
origins, scoped sentinels, Receiver-only control, and no direct fallback. [ADR
0012](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md) owns Run
classification, containment, and recovery. [ADR 0013](../../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md)
makes the Anthropic listener mandatory before model launch; it does not make a
reservation a billing cap. [ADR 0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md)
settles Confluence reference/draft scope and revocation.
The current Forwarder is one in-process HTTP Jira proxy with one sentinel. It is
not a partial implementation of this specification. The local
[mediated-client fixture](../../../../prototype/mediated_client/README.md) proves
only synthetic loopback TLS/framing behavior. Buffered fixture responses do not
qualify native streaming, deployment isolation, or any tenant/provider route.
The proposed pod has a **main container** containing Receiver and one untrusted
Run process tree, and one **Forwarder sidecar**. The operator/control plane and
CA signing key are outside this pod. A Run is never a control-plane client and
never receives an upstream credential, Forwarder server key, CA private key, or
sidecar configuration volume.

## Fixed listeners, origins, and TLS

The following are proposed deployment constants. A deployment that cannot bind a
mandatory listener exactly remains `NOT_READY` for Run admission; a failed
Confluence listener is only `DEGRADED` Memory. Neither condition may substitute
a prefix route, shared port, HTTP, or caller-selected origin.

| Service | Bind / port | Fixed origin and allowed base | Mandatory for launch | Credential |
| --- | --- | --- | --- | --- |
| Jira | `127.0.0.1:17441` | configured HTTPS site origin, `/rest/api/3/` | yes | Jira-only managed credential |
| Confluence | `127.0.0.1:17442` | configured HTTPS site origin, `/wiki/api/v2/` | no; visible Memory degradation | Confluence-only managed credential |
| Grafana/Eyes | `127.0.0.1:17443` | configured HTTPS Grafana origin | yes | Grafana read-only credential |
| Kubernetes | `127.0.0.1:17444` | configured HTTPS API-server origin | yes | narrow Forwarder-only service-account token |
| Anthropic | `127.0.0.1:17445` | configured HTTPS Anthropic API origin, `/v1/` | yes for model Run | Anthropic API key only in sidecar |

Listeners bind IPv4 loopback only. IPv6, wildcard, host-network, NodePort,
Ingress, Unix-socket, and clear-text alternates are absent unless this contract
is revised. Each has one certificate with SAN `127.0.0.1` and service DNS name
`forwarder-<service>.maoi.local`; the native client configuration MUST use that
DNS name, not disable hostname verification. The one local CA signs all five
leafs. Its private signing key is in operator-controlled rotation tooling,
never the image, pod, Secret mounted into the sidecar, or main container.
Proposed leaf validity is 24 hours; Receiver accepts a leaf only when remaining
lifetime is at least 10 minutes. Rotation follows ADR 0011's controlled
**deployment restart**: hold admission for the affected mandatory route, revoke
its leases, journal/reconcile in-flight effects as unknown where needed, replace
the sidecar leaf/key, start a fresh Forwarder generation with no leases, then
prove fresh strict-TLS readiness before registrations resume. An optional
Confluence cert/origin/credential/listener failure degrades only Confluence; it
cannot make an otherwise ready mandatory route unavailable. The old CA may
overlap a new CA for at most 24 hours during a deliberate CA rotation; both trust
bundles are public-only. The endpoint key is read-only to the sidecar UID and is
not logged, returned, or copied into a Run environment.
Client trust is a public CA file in a read-only Run mount with the system public
roots. The pod's operator-owned `/etc/hosts` mapping pins each
`forwarder-<service>.maoi.local` name to `127.0.0.1`; the Run cannot modify it
and does not need DNS egress. The selected native client must have a documented
endpoint/base-URL and CA configuration that preserves strict TLS. A client whose
documented interface cannot set both without carrying an upstream credential is
unsupported. It does not receive a direct origin as a compatibility fallback.

## Enforceable process and egress boundary

Separate containers in one pod share a network namespace. Pod NetworkPolicy is
therefore **not** a per-container or per-process direct-route control. The
proposed deployment must use these three independent controls:

1. The Receiver launches each Run under fixed non-root UID `10001`, in a
   distinct cgroup-v2 `run/<run_id>`, and attaches an operator-installed,
   pinned eBPF `cgroup/connect4` and `cgroup/connect6` program. The programs
   permit only TCP `connect` to `127.0.0.1` and ports granted in that Run's
   lease; they reject all IPv6 and every other network destination. The
   cgroup-sock-address attachment controls Internet connect, not socket
   creation or Unix-domain addressing.
2. Before exec, the trusted launcher applies a seccomp profile that allows only
   required `AF_INET`/`SOCK_STREAM` socket use and denies raw/packet sockets,
   `AF_UNIX` socket creation/connection, `bpf`, `perf_event_open`, namespace/
   mount/cgroup-changing calls, and `ptrace`. It sets `no_new_privs`; the Run
   lacks every capability. The profile is a layer of the enforcement design,
   not claimed to be a complete sandbox.
3. Receiver uses UID `10000`; the sidecar uses UID `10002`. Run mount and PID
   isolation hide Receiver/sidecar processes and `/proc` access, omit control
   and credential paths, inherit no open file descriptors other than stdin/out/
   err, and give the Run only a private empty writable work directory plus any
   separately admitted bounded Memory path accessed only through ADR 0009's
   narrow structured append/read operation, not unrestricted file Write.
   Ticket 32 owns that mount; it cannot contain control or upstream credentials. The main container
   does mount the Receiver-only control socket; the Run mount
   namespace explicitly excludes it. The Run has no BPF program/map FD and no
   access that can detach, replace, or join a cgroup.
Linux documents cgroup `connect4`/`connect6` program types and seccomp syscall
filtering, but this is an unimplemented proposal that requires a pinned
kernel/runtime compatibility check. A compatible runtime must attest program
and seccomp profile digests, cgroup path, peer UID/mount isolation, and effective
rules before launch. Failure, an unverified attachment, shared Run/Receiver
cgroup, a privileged Run, host networking, or an unconfined debug container is a
mandatory readiness failure. The pod-level egress policy may additionally
restrict the pod to approved origins, but cannot replace this control. Tests must
attempt literal-IP, DNS, metadata, IPv6, raw/packet and Unix sockets,
ptrace/proc/FD theft, cross-listener, and direct-origin connections from the
actual Run cgroup.

## Control, lease, and generation contract

Only Receiver talks to `ForwarderControl` over the sidecar-private Unix socket.
Mutual OS identity is the socket peer UID plus a Receiver-mounted 32-byte random
control secret. The secret has mode `0400`, belongs to Receiver UID, is never in
a Run cgroup/mount/environment, and is compared in constant time. This is a
proposed local control transport, not proof of a deployed identity boundary.

```
Register(run_id, attempt_id, receiver_boot_id, service, scope_digest, expires_at, generation)
  -> {lease_id, sentinel, generation, expires_at, route_id}
Revoke(lease_id, generation, reason) -> {revoked_at, closeout_state}
Heartbeat(receiver_boot_id, generation) -> {observed_at}; Ready(service) -> {generation, route_id, tls_not_after, policy_digest}
```

All IDs are Receiver/Forwarder generated opaque ASCII, at most 128 bytes. A
sentinel is 32 random bytes base64url without padding, service- and lease-specific,
and never logged. A service's pinned `ClientProfile` names exactly one verified
nonsecret sentinel grammar: for example Jira/Confluence Basic user=`run`,
password=`sentinel`; Grafana/Kubernetes Bearer; Anthropic is specified
separately below. The sidecar strictly parses that one grammar, removes it, and injects its own
upstream credential. Anthropic's current proposed profile is exactly documented
`Authorization: Bearer <sentinel>`; another header form requires a separately
verified profile rather than a silent substitution. A duplicated, unknown-scheme,
non-ASCII, malformed, expired, wrong-listener, or wrong-generation sentinel is
rejected. HTTP does not claim to identify a Run cgroup; sentinel authentication
and the separately attested kernel egress guard provide distinct controls.
Registration is idempotent
only for the same `(run_id, attempt_id, receiver_boot_id, service, scope_digest, generation)` and returns the
same lease; a changed tuple conflicts. The expiry is immutable and cannot be
extended by replay; a new attempt always requires a fresh lease. The receipt excludes sentinel and
upstream credential.
`generation` is random at Forwarder start. Receiver also generates a fresh
`receiver_boot_id` at its own start. `Register` binds both values, and Receiver
sends authenticated `Heartbeat(receiver_boot_id, generation)` every five
seconds. A Forwarder atomically revokes all leases for a prior boot ID when it
accepts a fresh Receiver boot handshake; it revokes on observed control-connection
EOF and otherwise expires the current boot's leases after 15 seconds without a
heartbeat. The latter is a bounded orphan window, not an immediate restart claim.
Forwarder starts
with an empty lease table and denies all requests until fresh Receiver
registration. Receiver starts with model dispatch held until recovery reconciles
its journal/accounting state and fresh route readiness. A lease expires at the
earliest of explicit revoke, reference/venue revocation, `launch + 270s`, or its
signed `expires_at`; it is never renewed in place. Receiver revokes before
interruption. Revocation atomically prevents new dispatch, but may leave an
already transmitted request `DISPATCHED_UNKNOWN`.
The Forwarder keeps at most 256 active leases and 1,024 short-lived revocation
records, each byte-accounted. It rejects registration before capacity pressure
would evict an active/recent record. Lease/revocation records retain only IDs,
service, scope digest, times, generation, and state for at most 310 seconds;
Receiver/ticket 37 retain durable recovery evidence. A Forwarder closeout failure
is `UNKNOWN`, not a successful revoke, and holds new dispatch.

## Common HTTP boundary

Every listener accepts HTTP/1.1 over TLS only. It permits a single request per
connection and closes it after the response. Request headers are at most 64
headers/16 KiB total; request line at most 2 KiB; body at most 256 KiB; response
headers at most 16 KiB; body at most 1 MiB. For Anthropic SSE the response cap is
4 MiB total, 64 KiB/event, and 1,024 events. Incoming bodies are read with
`limit + 1`; overflow is rejected before upstream dispatch. Responses are
streamed only for the qualified Anthropic SSE route; all other bodies are
buffered with `limit + 1` before forwarding.
Use 5 seconds connect, 10 seconds request-write, and 20 seconds upstream
first-byte/read inactivity limits, clipped to the remaining lease deadline.
The full inbound handler has an absolute 40-second deadline, also clipped to the
lease. Any deadline, local disconnect after dispatch, malformed upstream
framing, response overflow, or TLS close after bytes might have been sent yields
a receipt with `DISPATCHED_UNKNOWN` or `PARTIAL`; no automatic request replay is
allowed. A clearly rejected request before opening the upstream connection is
`NOT_DISPATCHED`.
Accept only origin-form request targets. Reject absolute-form, authority-form,
fragments, `..`, empty/duplicate slash normalization, percent-encoded slash or
backslash, encoded dot segments, control characters, and a query key not named
by the route. Reject duplicate singleton `Host`, `Authorization`,
`Content-Length`, `Content-Type`, and `Accept` headers, even when values agree.
Body routes require exactly one canonical nonnegative decimal `Content-Length`
matching the received bytes; bodyless GET permits absent length or exactly zero.
Reject conflicting/comma-joined lengths, signs, nondecimal forms and unexpected
body bytes. A body route's `Content-Type` is exactly `application/json`; `Accept`
is the pinned route value (`application/json`, or the explicitly qualified
Anthropic `text/event-stream`). Missing or unexpected required singleton values
are rejected before dispatch. Require exactly one client `Host` equal to that listener's pinned
`forwarder-<service>.maoi.local:<port>`; validate then strip it. Reject caller
`Proxy-*`, `Connection`, `Keep-Alive`, `TE`, `Trailer`, `Transfer-Encoding`,
`Upgrade`, `Expect`, `X-Forwarded-*`, and `Forwarded`; accept only the
ClientProfile's one sentinel header/form and reject all other Authorization or
credential headers. The Forwarder reconstructs canonical upstream `Host`,
credential, `Content-Length`, `Accept`, and `Content-Type`; it never forwards
caller credential/header values. It rejects all 3xx upstream replies, strips
`Location`, and returns a bounded failure without following or exposing a
redirect.
Every accepted response produces a sanitized `ForwarderReceipt` before it is
returned: `{lease_id, attempt_id, operation_id?, service, route_id,
request_digest, dispatch_state, http_status_class?, response_digest?, bytes,
started_monotonic, completed_monotonic, generation}`. It excludes URLs beyond
route ID, headers, sentinel, credentials, and body. A receipt is dispatch
correlation, not a trusted external-effect confirmation or billing evidence.
Ticket 37 supplies intent-before-dispatch and required read-back.

The Forwarder never automatically reissues an upstream request, including after
connect failure, 429, 5xx, provider error, timeout, redirect or malformed reply.
Disable native-client hidden retries in its pinned profile and verify the
observed request count. A separately admitted continuation/read-back is a new
bounded operation. A new write after failure requires the owning Receiver
recovery decision; the sole shorter Report path still requires NOT_DISPATCHED.

### Trusted dispatch permit

Before any Jira/Confluence mutation or billable Anthropic request, the Forwarder
uses a proposed separate Receiver-owned authenticated Unix endpoint for a
bounded `AuthorizeDispatch` exchange. The existing control session is
Receiver-command/Forwarder-reply only and cannot carry an unsolicited reverse
request. The exchange supplies the registered lease/attempt, route,
canonical request digest and sanitized operation target/plan. The Receiver must
resolve this to its admitted logical operation ID, not an ID asserted by the
Run. If the selected native-tool adapter cannot establish that binding, hold the
route; do not invent an identity from a successful-looking response.

The Receiver commits and reads back ticket-37 intent and applicable ticket-38
exposure admission under a defined global store order, then freshly verifies
the new journal head and current ledger reservation/exposure before returning
a one-use permit bound to lease, boot/generation, attempt,
operation, intent, request digest and monotonic expiry. The Forwarder consumes
the permit at L1 admission with its final lease check, then re-verifies the
same consumed permit, grant, route, digest, target and deadline at L2 before
the first possible upstream byte. Duplicate same-operation/digest requests
return recorded status, not another live permit; conflicting reuse is held.
Missing/late approval before L1 is NOT_DISPATCHED only with trusted
no-connect evidence and a finalized receipt. A denial after L1 but before L2
is FAILED only with trusted zero-byte evidence and a finalized receipt;
deadline sweep or receipt failure remains dispatch-unknown and holds. No
post-L1 denial qualifies for the shorter Report path. A crash after intent or permit
consumption holds reconciliation and never revives a permit. This does not
promise an atomic commit with the upstream service. The detailed
[19k seam](../run-recovery/design-19k-dispatch-permit-seam.md) keeps current
permit routes closed until Receiver and accounting authority exist.

Authorization frames are proposed <=8,192 bytes, one outstanding authorization per service,
with a five-second deadline clipped to the work lease; they carry no raw body or
credential. The separate Receiver endpoint needs its own measured connection,
file-descriptor, buffer and pending-request allocation. Exhaustion denies and
holds; it cannot borrow capacity from the existing opposite-direction control
session.
Persist only correlation and digests under ticket 37/38; private audit capture
uses ticket 39. Final client-to-logical-operation binding remains an explicit
acceptance gate.

## Route policies

An undeclared route, method, query parameter, JSON field, ADF field, page/issue
ID, namespace, resource, or response schema is rejected before dispatch.
`scope_digest` binds the allowed IDs, source/rehearsal window, operation class,
and manifest/recipe revision to the lease; caller strings only select within it.
Each route validates JSON types, no duplicate keys, depth <=16, arrays <=256,
strings <=16 KiB, and finite integer ranges. Route configuration itself is
operator-owned, versioned, size-capped at 64 KiB, and digest-recorded.

### Jira

The proposed Jira policy uses the installed native operation metadata recorded
in [Eyes, Report and Forwarder source checks](../eyes-report-forwarder-sources.md).
`OPS`, project/type/field IDs, allowed transition IDs, and comment limits are
trusted intended-venue preflight configuration, pinned by digest before
registration; historical IDs are never portable bindings. Report-bearing create
and comment routes enforce ticket 16's narrower limits: <=8 KiB serialized ADF,
<=16 KiB complete serialized Jira request, and <=64 KiB total Report ADF per
attempt. Count bytes after final encoding and reject before dispatch.

| Route ID | Request | Bounded shape | Result and retry rule |
| --- | --- | --- | --- |
| `jira.issue.get` | `GET /rest/api/3/issue/{issueIdOrKey}` | registered/scoped candidate or effect identity; fixed fields <=32; returned project=`OPS` and type=`Incident` verified | 200 JSON <=1 MiB; otherwise incomplete read |
| `jira.search` | `POST /rest/api/3/search/jql` (`searchAndReconsileIssuesUsingJqlPost`) | trusted 30-minute open-candidate template for exact Fingerprint/cascade only; maxResults <=100, fixed fields, one bounded continuation; no caller JQL | 200 JSON <=1 MiB. A negative result is not proof an uncertain create failed because enhanced search can be eventually consistent |
| `jira.issue.create` | `POST /rest/api/3/issue` | only fixed OPS/Incident fields: summary <=512 bytes, bounded ADF description, configured Severity/Urgency/Source and additive fingerprint/cascade labels; no properties, transition or history metadata | 201 key/id; lost response is uncertain create and reconciles by trusted identity/receipt, never title search retry |
| `jira.issue.update` | `PUT /rest/api/3/issue/{issueIdOrKey}` | accepted membership/current-state/Severity/Urgency operations only; labels preserved/additive. The only `update` array allowed is exact `labels`: add admitted Fingerprint/cascade membership; add/remove only corresponding done-state labels from latest admitted status. Removing membership or reassigning Alerts remains human-only; no description rewrite, correction deletion, arbitrary field edit, or history metadata | 204/200 plus required read-back |
| `jira.comment.add` | `POST /rest/api/3/issue/{issueIdOrKey}/comment` | new bounded immutable ADF Report revision only; no author/visibility override, caller ID/time, or edit/delete | 201 plus returned ID/read-back |
| `jira.comments.list` | `GET /rest/api/3/issue/{issueIdOrKey}/comment` | chronological revisions <=100 / 1 MiB / one continuation; must cover required Report history | missing/truncated/conflicting history is `INCOMPLETE`, never silently complete |
| `jira.comment.get` | `GET /rest/api/3/issue/{issueIdOrKey}/comment/{id}` | comment ID from trusted create receipt or scoped history, bound to the registered parent Incident; no expand; return only ID, bounded ADF and server times | 200 plus exact submitted ADF read-back; <=64 KiB response; unknown ID/body mismatch holds confirmation |
| `jira.transition` | `POST /rest/api/3/issue/{issueIdOrKey}/transitions` | one preflight-pinned transition ID and only required resolution field for Resolve | 204 plus required read-back; HTTP success alone is not eligibility |

No bulk endpoint, project/user/field discovery, attachment, comment edit/delete,
issue delete, permission/admin API, webhook, JSM service desk, issue-link route,
arbitrary JQL, caller-derived query, or generic payload transport is exposed.
`jira-as api call --body @file|-` is local input capability only: a future trusted
body producer must write bounded validated bytes without broadening the Run's
Read plus approved command authority or adding a shell pipeline. The Atlassian
v3 issue/search references document endpoint families and JSON formats; site
field/workflow configuration, native mediated invocation, rendering, and tenant
permission behavior remain unverified.

### Grafana/Eyes and Kubernetes

The following adopts ticket 12's proposed logical operations; it does **not**
select a client. Each Grafana operation maps only to its pinned datasource UID
and native path under `/api/datasources/proxy/uid/{pinned_uid}/{native_path}`.
If that proxy mapping, the native form, response schema, or scope predicate is
not verified, the operation stays unavailable; it never falls back to a direct
backend or generic Grafana/dashboard route.

| Route ID | Fixed native request / server-owned arguments | Scope projection |
| --- | --- | --- |
| `pod_list` | `GET /api/v1/namespaces/{ns}/pods?labelSelector={workload}&limit={n}` | fixed namespace/workload; owner UID verified; at most 2 pages |
| `pod_status` | `GET /api/v1/namespaces/{ns}/pods/{name}` | only a `pod_list` handle; status projection only |
| `pod_events` | `GET /api/v1/namespaces/{ns}/events?fieldSelector=involvedObject.uid={uid}&limit={n}` | fixed namespace/registered UID; note/message omitted/categorized |
| `service_endpoints` | `GET /apis/discovery.k8s.io/v1/namespaces/{ns}/endpointslices?labelSelector=kubernetes.io/service-name={service}&limit={n}` | fixed service; at most 2 pages; readiness/port counts only |
| `metrics_instant` / `metrics_range` | `GET /api/v1/query` or `/api/v1/query_range` with server PromQL template, bounded time/step | registered app/resource template; <=1,000 series / <=3,600 samples each |
| `logs_range` | `GET /loki/api/v1/query_range` with server LogQL template, time/limit/direction | fixed stream labels/source/rehearsal; <=10,000 projected rows |
| `traces_search` / `trace_get` | `GET /api/search` server TraceQL template; `GET /api/traces/{admitted_trace_id}` | optional; trace ID only from admitted search; service/time allowlist |
| `eyes.run_telemetry_query` / `eyes.change_query` | ticket-35/41 fixed server templates | own/earlier current-rehearsal Run or `maoi-change` producer-bound stream only |
| `grafana_health` | fixed registered health route | Receiver readiness only; no datasource discovery |

Every request uses trusted lease fields and a Receiver-issued scope digest; caller
namespace, resource, datasource, PromQL/LogQL/TraceQL, selector, or dashboard
filter is never authority. Deny Secrets, ConfigMap write, exec, attach,
port-forward, proxy, log-subresource, every watch, every list other than the
four listed bounded collections, arbitrary discovery, and every write. The global Eyes ceiling is
32 operations/Run, 30 seconds each, 10,000 records, 1 MiB, and two server-issued
pages. Query text <=8 KiB, depth <=8, strings <=2 KiB, arrays <=256; query time
is current rehearsal, <=24 hours old, and not future. The narrower applicable
limits from tickets 35 (five self-observation queries) and 41 (100 Change rows,
1 MiB, five seconds) win. Unknown labels/returned scope, overflow, malformed
shape, or inability to prove Kubernetes Event selector support is unavailable or
incomplete, never silently truncated. Change read cannot send records/create an
annotation/invoke coordinator control; its source identity is collector-derived.
Ticket 41's operator coordinator uses a separate authenticated action path;
its guarded PATCH/DELETE rights never pass through the Run Kubernetes listener.

### Confluence

The Confluence route adopts ticket 43 exactly and preserves `/wiki`. Permitted
route IDs are `reference.read`, `draft.create`, `draft.read`, and
`draft.update`; each has the fixed v2 path/method/body shape, page/space IDs,
manifest generation, route-specific required status, metadata subset, response
caps, and receipt-token binding in [ticket 43’s specification](../ticket-43/confluence-specification.md).
The adapter issues the opaque one-use `read_receipt` after a scoped read
containing tenant page ID, version, title, exact stored body-byte SHA-256, run,
rehearsal, expiry <=60 seconds and lease bound. A new composed draft body has
its own exact byte digest; it is not required or expected to equal the old source
body digest. The adapter atomically consumes the receipt and persists an update
intent binding old page/version/digest to the new-body digest before upstream
update. Same receipt plus same new digest returns recorded status; a differing
new digest conflicts. `409` stale version never auto-retries; possible-send is
`UPDATE_UNKNOWN`/`CREATE_UNKNOWN`, not `NOT_DISPATCHED`. Revocation serializes
with dispatch admission and conservatively cancels exposed active Runs.

`reference.read` requires manifest-approved reference status `current`, version,
and digest. `draft.create` requires an eligible current-rehearsal Incident and
reserved mapping/create intent; no page ID exists yet. `draft.read` and
`draft.update` require the registered mapped page ID. All draft operations
require status `draft`. There is no CQL/search, page list,
attachment, comment, label, permission, move/copy/delete, publication, approval,
or generic metadata route. The shared receipt excludes raw body and private audit
retains ticket-39’s sanitized exact body record. Confluence is optional only
after manifest/revocation/mapping and expected-version adapter gates pass;
otherwise it is unavailable and Memory is visibly incomplete.

### Anthropic and billing seam

Only `POST /v1/messages` is proposed. Require `Content-Type: application/json`,
canonical `Accept: application/json` or `text/event-stream`, `stream` exact
boolean, one configured model ID, bounded messages/tool definitions/schema under
an accounting-approved request envelope, exactly the documented Anthropic
Bearer-sentinel Authorization form, and no caller base URL or other credential
header. The sidecar strips that sentinel and replaces it with its managed API
key. It may never
invoke a provider discovery, billing, files, batches, admin, MCP, or arbitrary
endpoint.

The operator-pinned ClientProfile must supply the required `anthropic-version`
and any other qualified protocol headers before this route is enabled. Validate
at most one caller version header against that exact profile, then discard it
and inject the operator value; a conflicting, duplicate or unknown protocol
override is rejected. Reject `anthropic-beta` by default. A beta header requires
a separately qualified, operator-pinned value and request envelope; it cannot
pass through from arbitrary client input. Missing version/profile evidence holds
the route. This extends the common upstream header rebuild list, not the
service's endpoint or credential authority.

A non-streaming response is bounded JSON <=1 MiB. Streaming forwards validated
SSE frame bytes only after the selected native client and SSE semantics qualify;
it recognizes terminal completion/error, retains a bounded event count/bytes and
records only event categories/counts/digests plus any exact numeric usage fields.
Missing, malformed, partial, or disconnected usage is `unknown`, never zero.
A terminal model result, API 2xx, or local usage estimate does not settle cost.

Before dispatch, ticket 38 must have committed the matching `attempt_id`,
`reservation_id`, defensible liability `U`, and lease receipt. `U` covers the
whole attempt, including every admitted request and possible charge, not a new
allowance per HTTP call. For each AuthorizeDispatch decision, resolve the
registered envelope digest to committed request-count and input/output/tool
bounds and remaining exposure capacity. Atomically reserve/consume that call's
bounded share before the permit is issued. Never reset the counters on retry,
connection, stream error or model turn; an exhausted or unprovable envelope
means NOT_DISPATCHED for the new call and a held accounting gate. An uncertain
previous call keeps its liability until authoritative reconciliation. No finite
or enforceable aggregate envelope means no provider dispatch. The Forwarder
receives IDs and a request envelope digest, never accounting authority or a
reservation/sentinel from a Run. It reports `failed_before_dispatch`,
`dispatched_unknown`, `partial`, or transport receipt to ticket 37/38. Revocation
may stop new frames but cannot prove cancellation, prevent an already sent
request from finishing, or erase a provider charge. Provider charge lines and
coverage-complete reconciliation are ticket 38’s only settlement authority.

## Readiness, effects, and retention

Each service route's own readiness requires its certificate/listener, canonical
origin, credential readability only by Forwarder UID, control-peer validation,
egress-guard attachment/read-back, and route-policy digest load. New Runs require
Jira, Grafana/Eyes, Kubernetes, and Anthropic route readiness; Confluence failure
produces a recorded optional-Memory degradation and cannot gate the mandatory
routes. An optional route lacking its listener or credential may remain
UNAVAILABLE without participating in mandatory readiness. Telemetry export is best effort under ticket 35 and never a readiness
gate. No readiness failure removes admitted Notifications, settled journal
records, accounting reservations, or recovery obligations. Ticket 35 native
export stays disabled for Run processes: their egress guard permits only the
five service ports. A separately configured Receiver-owned best-effort collector
path has its own identity and is not a sixth Run listener or a source of Run
control authority.

A service has `UNAVAILABLE`, `READY`, `DEGRADED`, or `REVOKED`; a lease has
`REGISTERED`, `ACTIVE`, `REVOKING`, `REVOKED`, or `EXPIRED`. An effect receipt
is `NOT_DISPATCHED`, `DISPATCHED_UNKNOWN`, `PARTIAL`, `FAILED`, or
`TRANSPORT_CONFIRMED`; only ticket 37 plus required read-back may mark an effect
`CONFIRMED`. A Forwarder restart returns every service to unavailable until a
new generation passes readiness and invalidates all old leases.

Forwarder retains no request/response bodies. It retains receipts and errors for
at most 310 seconds, capped at 2 MiB/2,048 records total, 8 KiB/record; capacity
failure rejects new dispatch before bytes are sent. Receiver/tickets 37, 38, 39,
41 own their distinct durable journal, accounting, audit, and Change retention.
Any retained diagnostic log uses fixed service/route/status/error-category/byte
count and correlation IDs only; it contains no header, token, body, URL query,
or personal/account identity.

## Acceptance and unresolved decisions

| Gate | Required evidence | Does not establish |
| --- | --- | --- |
| Static/offline protocol | real sidecar listener and client request construction; TLS CA/hostname/expiry; duplicate headers; encoded/absolute paths; redirect; cap/deadline; service/wrong/revoked/expired/restarted sentinel; no upstream on pre-dispatch denial | client compatibility, OS/cgroup enforcement, tenant/provider effect |
| Egress/mount/control | actual Run cgroup attacks against all direct IP/DNS/IPv6/metadata/raw/control paths; program/map/read-back; mount/UID/capability inspection; control secret inaccessible | Kubernetes admission security or live upstream authorization |
| Scoped service policy | every allowed and forbidden Jira/Confluence/Eyes/Kubernetes/Anthropic shape; cross-rehearsal/manifest/namespace rejection; Confluence stale/unknown create; intent/receipt recovery | tenant grants, native SDK/CLI behavior, current provider API compatibility |
| Accounting/model | reservation/lease/launch transaction; unknown stream/usage/charge; cancellation after dispatch; multi-line provider coverage and no replay | paid charge amount, billing lag, model quality or qualification |
| Intended venue | exact deployed ports, cert rotation, cgroup guard, effective roles/RBAC, direct-route denial, native endpoint/CA use, scoped upstream read-back | reliability beyond observed venue or future billing |

The following remain choices requiring review before implementation: exact
operator control authentication/secret rotation and native-operation-to-permit
binding; service origins and field/
workflow IDs; cgroup-BPF runtime support and alternative topology if absent;
TLS issuer/renewal delivery; ticket-12 Eyes/Kubernetes route schemas; native
client endpoint and CA knobs; Anthropic request envelope, streaming protocol,
provider cost coverage/lag; and all tenant grants. A missing choice disables
only its route, except the mandatory routes which hold new model Run launch.

## Sources and non-claims

Read: [issue 36](../../issues/36-forwarder-integration-and-acceptance.md), ADRs
[0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md),
[0012](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md),
[0013](../../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md),
and [0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md);
[ticket 23 native readiness](../ticket-23/native-adapter-readiness.md),
[mediated-client fixture](../../../../prototype/mediated_client/README.md),
[tickets 35](../ticket-35/telemetry-specification.md),
[37](../ticket-37/recovery-specification.md),
[38](../ticket-38/accounting-specification.md),
[41](../ticket-41/change-specification.md), and
[43](../ticket-43/confluence-specification.md); the shared
[Eyes/Report/Forwarder source checks](../eyes-report-forwarder-sources.md); plus
Linux kernel [cgroup BPF program types](https://docs.kernel.org/6.15/bpf/libbpf/program_types.html)
and [seccomp filtering](https://docs.kernel.org/userspace-api/seccomp_filter.html),
retrieved 2026-09-22; and official Atlassian [Jira issue API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)
and [JQL search API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/),
retrieved 2026-09-22.

No real TLS certificate, authenticated control identity, sidecar, eBPF guard,
Jira/Confluence/Grafana/Kubernetes/Anthropic request, model run, provider charge,
tenant role, cluster, native-client configuration, or C2 acceptance was run.
