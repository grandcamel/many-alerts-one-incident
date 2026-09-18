# The Forwarder's growth

Type: grilling
Status: resolved
Blocked by: 03

## Question

Chapter one's Forwarder holds one Atlassian credential, forwards plain http from a Run to one site, and swaps a per-Run sentinel for the real token (ADR 0002). Chapter two asks it to front Confluence on the same site, Grafana on another, and possibly a Kubernetes API. Is it one Forwarder with a route per site, or one process per site? And what does it speak on loopback: `confluence-as` as released refuses a plain-http site URL (see "confluence-as as the peer of jira-as"), so either the Forwarder terminates TLS on 127.0.0.1 with a certificate the image trusts, or `confluence-as` gains an http option upstream and is pinned to that release. Which, and does the same answer serve whatever the Eyes research says the Grafana tools need? Produces an ADR beside 0002.

The Eyes research proposes a shape to start from: one Forwarder with two routes, the Atlassian site with a basic-auth swap (Jira and Confluence sharing it) and Grafana with a Bearer swap, and a possible third route for `kubectl proxy` (see "Where a real Kubernetes could run").

## What ticket 09 settled, 2026-09-16

ADR 0007 moves the Receiver and each Run into the cluster, so the Forwarder
becomes a **sidecar** rather than a process on the laptop, and both the Atlassian
token and the Anthropic key become Kubernetes Secrets. Grafana is in-cluster and
unexposed. ADR 0002's shape is unchanged — the Run still holds only a sentinel —
but "one Forwarder or one per site" is now also a question about one sidecar or
several containers in the pod.

## Work history

Claimed after tickets 13 and 15 were committed. Offline planning only: verify current routing, credential and trust boundaries before the human decision round. No live credential use, cluster, demo, client patch or runtime implementation.

The human accepted all five recommendations in the first [decision round](../reviews/ticket-17/round-1.md). It covers topology, loopback TLS, service-scoped credentials/sentinels, mediated Kubernetes reads, and request enforcement. ADR 0007’s sidecar requirement is retained, with its misleading “pod is still one container” wording to be corrected in the resulting ADR.

[Offline facts](../reviews/ticket-17/facts.md) distinguish the existing in-process HTTP Jira Forwarder from the proposed sidecar. Current forwarding fixes the upstream origin and does not follow redirects itself, but returns redirects to the client; client follow behavior is unverified. Confluence requires HTTPS. Service credentials, TLS and control-plane isolation remain planned, not implemented.

The human accepted the second [decision round](../reviews/ticket-17/round-2.md), covering endpoint addressing, trust ownership, admission/revocation, redirect and uncertain-write handling, bypass prevention, and readiness. Both decision rounds are accepted.

## Answer

[ADR 0011](../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) records the eleven accepted decisions. One Forwarder sidecar exposes separate fixed-origin loopback HTTPS endpoints for Jira, Confluence, Grafana and Kubernetes, preserving native paths. Receiver and Run children remain in the main container; ADR 0007's incorrect one-container wording is corrected. Deployment-local CA trust replaces the need to patch Confluence for HTTP, without bypassing certificate verification.

Each Run/service has its own sentinel and independently scoped upstream credential. Receiver-only control authority registers scopes and revokes them on exit/timeout/restart, with bounded orphan leases. Only the Forwarder holds managed service credentials and its TLS private key. Request-aware restrictions enforce read-only telemetry/rehearsal scope and mediated Kubernetes reads, with no general proxy, Secret reads or execution access. Approved Jira/Confluence writes remain available.

Reject redirects, strip caller credentials, and never blindly retry uncertain mutations. Verify backend bypass prevention and OS/control isolation; pod-level policy alone is insufficient. Forwarder/control/TLS plus mandatory Jira/Grafana/Kubernetes routes gate new Runs. Optional Confluence may degrade visibly; telemetry export remains best effort. Ticket 21 owns pending-work recovery and overall Run classification.

[Ticket 36](36-forwarder-integration-and-acceptance.md) carries concrete integration and acceptance specifications. Exact Eyes tools remain ticket 12, prototype behavior ticket 19, and Confluence grants ticket 33. [Evidence](../reviews/ticket-17/facts.md) is source-only; no multi-service/TLS implementation, live permissions, credentials, cluster or demo acceptance was performed.
