# Ticket 43 primary source map

Retrieved 2026-09-22. These establish public API or local CLI surface only. They do
not establish MAOIREF/MAOIDRAFT availability, tenant draft behavior, effective grants,
Forwarder enforcement, direct-route denial, or a live receipt.

| Source | Fact used | Boundary |
| --- | --- | --- |
| [Atlassian Page API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/) | Documents POST pages, GET pages/id, PUT pages/id. Create fields include spaceId, status, title, body. Direct get documents body-format, status, version, and draft-related parameters. Update fields include ID, status, title, body, version. | Required page fields do not prove a selected tenant accepts the proposed draft form or conflict behavior. |
| [Atlassian Version API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-version/) | Documents direct page-version request form and page-view permission requirement. | Does not grant historical body reads or authorize a cached body fallback. |
| [Atlassian REST API v2 overview](https://developer.atlassian.com/cloud/confluence/rest/v2/intro/) | Documents cursor pagination for collection endpoints. | Runs use no collection or pagination endpoint. |
| [Ticket-33 local CLI help](../ticket-33/cli/page-create-help.txt) | Installed confluence-as 1.1.1 exposes create status draft, direct ID get, and update status/body forms. | Help is not tenant/native lifecycle/permission evidence. |
| [Ticket-33 facts](../ticket-33/facts.md) | Inspected local update path gets current page version then puts plus one and has no expected-version CLI flag. | This behavior is rejected for composed stale-body authorization. |


The [Ticket 43 specification](confluence-specification.md) consumes
[ticket 43](../../issues/43-confluence-scope-approval-and-draft-integration.md),
[ADR 0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md),
[ADR 0009](../../../../docs/adr/0009-memory-has-one-incident-authority-and-reviewed-learning.md),
and [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md).
It remains source-only; no tenant state was inspected.
