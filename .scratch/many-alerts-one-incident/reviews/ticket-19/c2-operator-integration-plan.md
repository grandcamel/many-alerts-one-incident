# Ticket 19 — C2 operator integration preparation, 2026-09-21

**Source preparation only.** The user directed this batch after the [C1 attempt-4 outcome](c1-attempt-4-outcome.md). No C2 image pull, startup, ingestion, account operation or native session is authorized by this plan. C1's completed bounded card does not satisfy its remaining native certificate/lifecycle checks or qualify C2.

The implementation is split between a deterministic four-service configuration compiler and a bounded ingestion/read-back driver tested through a fake transport. The compiler produces explicit direct-binary commands, config bytes, hashes, fixed numeric-address bindings and resource inventories. The driver consumes the frozen seed and complete compiled configuration, submits each seed at most once per driver lifetime, and runs bounded read-only comparisons. A matching Loki or direct Tempo response cannot override the public Prometheus compatibility gate or become overall C2 acceptance.

The integration test must connect the actual compiler output to the driver; testing two unrelated endpoint dictionaries is insufficient. Mutation of caller-owned manifests/maps after construction must not redirect requests or alter the expected data. Worst-case retained raw responses are capped by a 64 MiB preflight bound; request/response bytes and hashes are operator evidence and never belong in Run ground-truth mounts. Production transport, private persistence, crash recovery, Grafana account lifecycle and native Forwarder integration remain explicit separate components until implemented and tested; a fake callback does not prove network containment or enforce a hard timeout on arbitrary code.

## Account lifecycle contract for the future operator

The current [Grafana service-account API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/serviceaccount/) documents the following legacy routes. Grafana 13 deprecates these routes while retaining their availability. This is documentation evidence; exact pinned-instance behavior still needs a read-back.

| Operation | Route | Proposed evidence |
| --- | --- | --- |
| Create Viewer account | `POST /api/serviceaccounts` | Exact unique experiment name, Viewer role, enabled state and returned account ID. |
| Read account | `GET /api/serviceaccounts/<id>` | ID/name/role/organization agreement before granting access and before deletion. |
| Create bounded token | `POST /api/serviceaccounts/<id>/tokens` | Exact token ID/name and positive finite TTL; secret key delivered only through protected operator memory/stdin. |
| Read tokens | `GET /api/serviceaccounts/<id>/tokens` | Exact ID inventory and expiration read-back. |
| Revoke token | `DELETE /api/serviceaccounts/<id>/tokens/<tokenId>` | Exact token absent afterward and independent rejection of the old token at a protected read endpoint. |
| Delete account | `DELETE /api/serviceaccounts/<id>` | Exact created account absent afterward. |

These calls must target only the newly ledgered disposable Grafana instance at its frozen numeric address. Bootstrap credentials belong in a UID-readable private file, not argv, environment dumps or report bodies. The Viewer token enters only Forwarder private configuration; it never becomes a Run credential. Evidence records IDs, statuses and non-secret provenance, excluding token/key values and authenticated request headers.

A timed-out create/token POST is an indeterminate side effect, not permission to repeat it. Record intent before sending, then reconcile through bounded read-only inventory of the uniquely named owned account. Do not adopt a pre-existing match, broaden a query or create another identity to escape uncertainty. If ownership cannot be recovered, stop acceptance and remove the exact disposable experiment resources within the cleanup budget. No existing tenant or shared Grafana instance is in scope.

Forwarder admission revocation and Grafana token revocation are separate steps. The future operator must deny further Run access first, attempt exact token/account cleanup through operator authority, export bounded non-secret evidence, then remove the ledgered containers and temporary resources. Any failed revocation or cleanup remains a reported failure even if destroying the disposable data volume makes the credential unusable.

## Remaining compatibility and integration evidence

Before a C2 runtime acceptance card, establish all of the following with exact source or separately approved instance evidence:

- Direct binary/config compatibility at the pinned amd64 image, UID 2000 readability and all writable paths within the proposed tmpfs mounts. Keep limits unchanged on startup failure.
- Effective Loki label discovery and old-sample configuration; effective Prometheus OTLP receiver and exact stored labels; supported Tempo response schema. The present oracle cannot be promoted by caller-supplied observations.
- A real transport with exact numeric endpoints, no proxy/environment inheritance or redirects, bounded raw HTTP/JSON handling and operator-side absolute-deadline containment. In-memory callback tests cannot supply these runtime guarantees.
- Durable ingestion intent and uncertain-outcome recovery across process loss. In-memory at-most-once behavior is insufficient for crash/restart claims.
- C2 Forwarder/gateway policy and native-case mapping. Carry the C1 denial-receipt finding forward: include active case, method, target/body hashes and a denial correlation identity before returning a denial. Retain no authorization header or secret body.
- Account/grant checks: protected anonymous refusal, Viewer read and behavioral write refusal with before/after resource inventory, independent token revocation, and native certificate/sentinel variants.
- Complete runtime ownership and deletion inventory, exact resource budgets and readiness limits, final guard snapshots and reconciled C1 lifecycle gaps.

No synthetic backend receipt is invented for Grafana. Native frames, Forwarder/gateway receipts, direct backend read-backs and application logs remain distinct evidence. Source compilation, offline simulation, instance startup, ingestion, native behavior and qualification must retain their own statuses.
