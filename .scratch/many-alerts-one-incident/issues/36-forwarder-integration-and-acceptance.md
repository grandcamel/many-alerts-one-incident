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
