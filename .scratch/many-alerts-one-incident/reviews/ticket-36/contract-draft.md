# Ticket 36 Forwarder contract draft

Status: source-only preparation. This draft records accepted constraints and open
inputs for the future implementation-ready specification. It neither changes the
current Forwarder nor accepts a listener, client, credential, route, runtime, or
deployment.

## Scope and current boundary

[ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md)
chooses one Forwarder sidecar, separate loopback HTTPS service endpoints, fixed
upstream origins, service-scoped sentinels, and Receiver-only authority. [ADR
0013](../../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md)
supersedes the earlier Anthropic exception: the five-service target is Jira,
Confluence, Grafana, Kubernetes, and Anthropic.

The current Python Forwarder is not a partial implementation of this contract. It
is an in-process HTTP Jira proxy with one active sentinel and no service-specific
request policy. Its existing behavior remains described by [ticket 17 source
facts](../ticket-17/facts.md). Do not use a current pass of its HTTP tests as TLS,
sidecar, multi-service, control-plane, or bypass-resistance acceptance.

## Settled invariants

| Area | Contract invariant | Source |
| --- | --- | --- |
| Topology | One Forwarder sidecar is separate from the Receiver/Run container. Each service has a distinct loopback HTTPS listener; native clients retain native paths, including Confluence /wiki. | [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) |
| Origin and headers | A listener fixes its service and canonical upstream. It rejects caller-selected origins, unsafe paths, and upstream redirects; it strips caller Authorization, Host, and proxy/hop credentials before adding only the configured credential. | [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) |
| TLS | Deployment-local tooling owns the CA and endpoint certificate. The signing key stays outside the pod/image; only the Forwarder mounts the server key. Clients verify CA, hostname/IP, and expiry without an insecure fallback. | [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) |
| Authority | Every Run receives a distinct sentinel per declared service. Managed upstream credentials and the control authority are outside Run mounts and environment. | [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) |
| Control | Receiver-only authenticated registration occurs before launch. Revocation occurs on exit, timeout, and cancellation; restart invalidates every admission. A Run cannot reach the control channel merely because its token was omitted. | [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) |
| Effects | Revocation does not roll back a dispatched operation. Timeout, disconnect, or uncertain delivery never authorizes an automatic mutation retry; the uncertain effect is retained for ticket-21 reconciliation. | [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md), [ADR 0012](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md) |
| Telemetry | Current-rehearsal read scope is an enforced request boundary. Export is bounded best effort and never a new-Run readiness gate or a reason to repeat confirmed OPS work. | [ADR 0010](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md), [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) |

## Accepted Change and Confluence constraints

[ADR 0015](../../../../docs/adr/0015-changes-record-operator-actions-and-observed-stages.md)
keeps coordinator mutation/control/emergency credentials outside Runs. Its dedicated
Loki Change stream has distinguishable producer identity and current-rehearsal read-only
Eyes/Forwarder retrieval. Runs cannot forge authoritative coordinator records or invoke
action control through Kubernetes or export. Optional Grafana annotations are derived
audience views, not Run write authority. Change journal/stream durability and seven-day
retention remain distinct from best-effort Run telemetry.

[ADR 0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md)
keeps curator/manifest authority outside Runs. Permit only approved-reference reads,
registered current-rehearsal draft create/read/expected-version updates and narrowly
necessary scoped metadata. Deny publication, approval, unrestricted CQL/space enumeration,
attachments, comments, labels, move/copy/delete, permissions/restrictions and cross-scope
metadata/pagination leaks. Require draft status and bind each body to the exact composed
version; conflict requires reread/review. Serve references only when returned page/version/
digest match the approved manifest. Unknown creates hold secondary Memory work rather than
retrying or adopting by title. Immediate reference revocation cancels affected Runs under
ADR 0012, preserves confirmed/uncertain effects, and holds subsequent model dispatch for
operator review. Unknown exposure conservatively includes affected manifest admissions.
These restrictions are settled; ticket 43 still supplies concrete enforceable schemas.

## Proposed service contract matrix

These are contract rows, not endpoint schemas. An unresolved policy means the
service must remain unavailable to Runs, rather than forwarding a broad request.

| Service | Required route condition | Credential/sentinel rule | Readiness | Policy input still needed |
| --- | --- | --- | --- | --- |
| Jira | Fixed Jira origin and native Jira paths only. | Separate Jira credential and Jira-scoped sentinel. | Mandatory before new Runs. | Exact allowed reads/writes, request bodies, response caps, and reconciliation records. |
| Grafana | Fixed Grafana origin; request-aware telemetry and current-rehearsal scope. | Separate Grafana credential and sentinel; no anonymous or direct backend route. | Mandatory before new Runs. | Ticket 12's exact Eyes operations, native request forms, and query constraints. |
| Change retrieval (Grafana subpolicy) | Dedicated current-rehearsal Loki Change queries with distinguishable coordinator provenance. | Read-only Grafana sentinel; no coordinator/control credential or record-forging path. | Verify diagnostic-record retrieval before operator injection; annotations remain optional. | Ticket 12/41 query schema and producer-boundary acceptance. |
| Kubernetes | Fixed mediated read route; no general API proxy. | Narrow service-account credential only in Forwarder; Kubernetes-scoped sentinel. | Mandatory before new Runs. | Ticket 12's exact tools, resources, namespaces, and permitted pod-status requests. |
| Confluence | Fixed Confluence origin preserving /wiki; approved reference/draft scope only. | Separate Confluence credential and sentinel. | Optional; failure is visible missing Memory. | Ticket 43's manifests, native operations, grants, page/version/digest rules, and expected-version body binding. |
| Anthropic | Fixed fifth endpoint with streaming and no direct credential route. | API key outside Run; Anthropic-scoped sentinel only. | Mandatory before model Run admission. | Verified client endpoint/trust configuration, credential replacement, streaming/usage handling, direct-route prevention, and ticket-38 billing interface. |
| Telemetry export | Receiver-owned projection and any separately verified permitted native-export path; neither grants general service access. | No Run control credential follows from export. | Best effort; never mandatory. | Queue/send bounds and verified sanitization/correlation behavior. |

## Service, control, lease, and effect states

State names below are proposed specification vocabulary, not existing runtime
types. Any state without an enforceable policy is fail-closed.

| Object | State | Entry condition | Permitted transition | Required visible result |
| --- | --- | --- | --- | --- |
| Service route | UNAVAILABLE | Missing policy, TLS, credential custody, or acceptance prerequisite. | Only an authenticated, validated readiness result can make it READY. | Missing mandatory routes hold admission; optional Confluence exposes degraded Memory. No direct fallback. |
| Service route | READY | Listener, fixed origin, TLS, control channel, and route policy are available. | Receiver may register a scoped lease. | Mandatory-route readiness is recorded separately from Notification recovery. |
| Lease | REGISTERED | Receiver authenticates to control plane before Run launch with Run ID, service, allowed scope, and bounded expiry. | ACTIVE only while the matching Run is admitted. | Registration receipt contains no sentinel or upstream secret. |
| Lease | ACTIVE | Request has the right listener, sentinel, lease, and policy shape. | REVOKING at exit, cancellation, 270-second work deadline, or explicit operator cancel. | Accepted requests remain attributable to lease and service. |
| Lease | REVOKING | Exit/cancel/deadline closes new dispatch immediately while acknowledgement/cleanup completes. | REVOKED on acknowledged invalidation or expiry; missing acknowledgement keeps admission held. | No new upstream request; previously dispatched effects remain separately tracked. |
| Lease | REVOKED | Revocation is acknowledged, lease expires, or either Receiver/Forwarder restarts. | No reactivation; a retry is a new Run and lease. | Later use is denied without reaching upstream. |
| Control plane | UNAVAILABLE | Authentication, OS identity, mount isolation, or reachability cannot be verified. | READY only after boundary checks pass. | New Run admission is held. |
| Effect | NOT_DISPATCHED | Policy or pre-dispatch denial stops request transmission. | Ticket 21 may permit one bounded alternate Report attempt when proven. | No inferred upstream change. |
| Effect | PENDING_OR_UNKNOWN | Request may have reached upstream but response/closeout is incomplete. | Reconciliation only; never automatic replay. | Run outcome remains held/incomplete as ticket 21 defines. |
| Effect | CONFIRMED | Trusted Forwarder response and required read-back agree. | A new justified operation may follow; the confirmed operation is never replayed. | Preserve effect even if optional Memory/export later fails. |

The lease may admit work only during the 270-second startup/work window. The
following 20 seconds for interruption/local flush and 10 for kill/reap confer no
new dispatch authority. Revocation begins
at cancellation or the work deadline; it does not prove an in-flight request did
not complete. [ADR 0012](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md)
owns execution classification and recovery.

## Unresolved inputs and required decisions

| Input | Why it blocks an enforceable route | Owner/source | Safe interim rule |
| --- | --- | --- | --- |
| Eyes and Kubernetes operation set | Method-only allowlists cannot enforce telemetry scope, POST reads, pod-status restrictions, or rejected subresources. | [Ticket 12](../../issues/12-eyes.md) | Grafana and Kubernetes routes are unavailable to Runs. |
| Confluence operation and version contract | Current CLI behavior does not bind a composed body to the reviewed version; role names are not enforcement. | [Ticket 43](../../issues/43-confluence-scope-approval-and-draft-integration.md) | Confluence route is unavailable; disclose degraded Memory. |
| Jira request policy | Existing platform-operation intent does not yet define every path, body, response bound, or trusted read-back needed for the new Forwarder. | [Ticket 36](../../issues/36-forwarder-integration-and-acceptance.md) with [ADR 0004](../../../../docs/adr/0004-fingerprint-label-and-platform-ops-only.md) | Do not generalize the chapter-one proxy. |
| Concrete transport/control parameters | Port allocation, certificate lifetime/renewal, request/response caps, timeouts, lease representation, identities, mount paths, and authenticated control transport have no accepted values here. | [Ticket 36](../../issues/36-forwarder-integration-and-acceptance.md) | No listener/configuration is implied. |
| Anthropic mediated client contract | Routing evidence does not establish the intended TLS/client configuration, safe usage visibility, provider billing, or direct-route resistance. | [ADR 0013](../../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md), [Ticket 38](../../issues/38-budget-accounting-and-model-qualification.md) | Keep model admission closed; never restore direct credentials. |

## Acceptance evidence plan

Each row is a required evidence class. A later passing lower row cannot promote an
earlier source-only or synthetic result into tenant, provider, or venue acceptance.

| Evidence class | Required checks | Non-claim boundary |
| --- | --- | --- |
| Source/static | Configuration rejects undeclared service/origin/policy; control and secret mounts have no Run-readable path; state transitions preserve hold/unknown results. | Does not prove OS isolation, client TLS behavior, or upstream policy. |
| Offline transport | Real client request construction through local TLS: correct/wrong-service sentinels; pre-admission, revoked, expired, and restart denial; CA/hostname/expiry failure; encoded/absolute target, redirect, malformed/oversize, POST-read, prohibited-write/subresource, and truncation cases. | Uses synthetic credentials/backends only; does not prove tenant roles or native venue reachability. |
| Offline scoped authority | Forged Change producer/control requests; cross-scope Confluence metadata/pagination; publication/status bypass; stale body/version; unapproved digest; uncertain create; delivered-reference revocation and affected-Run cancellation. | Local fixtures do not establish tenant grants, source authenticity or live revocation. |
| Offline lifecycle | Control loss, lease expiry, cancellation, uncertain mutation, reaping, readiness hold, optional-Confluence degradation, and export failure keep Notifications/effects separate and visible. | Does not classify a real model run or reconcile a live mutation. |
| Native client/model | Selected Grafana/Kubernetes/Confluence/Anthropic clients use the intended endpoint, verified trust, scoped sentinel, and required streaming where applicable. | Requires independently authorized model/client runs; client compatibility is not assumed. |
| Tenant/RBAC and deployment | Effective service roles, direct-route refusal from the Run identity, sidecar identity/mount/network separation, real TLS material lifecycle, and required upstream read/write read-backs. | Requires authorized disposable artifacts or intended-venue work; never infer from role/config text. |

## Draft completion boundary

This draft can support review of the shared state model and acceptance matrix now.
It cannot make ticket 36 implementation-ready until the policy-owner inputs above
are resolved and the selected parameters are reviewed. It authorizes no runtime
change, client invocation, credential use, account operation, cluster work, or
model run.
