# The Forwarder's growth

Type: grilling
Status: open
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
