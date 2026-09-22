# Ticket 43 Confluence scope, approval, and draft-adapter specification

Status: source-only proposed implementation contract, 2026-09-22.

This defines the future Receiver-owned Confluence adapter required by ticket 43. It
does not create spaces or pages, call a tenant, use credentials, change grants,
publish, or run a model. MAOIREF and MAOIDRAFT are proposed keys only. A separately
authorized preflight must resolve them to verified immutable tenant space IDs and prove
availability/collision state. Public API documentation and local CLI help establish
request shapes, not tenant grants, draft behavior, or direct-route resistance.

## Authority and boundary

ADR 0017 settles separate private reference/draft namespaces; reference approval and
immediate revocation; verified page ID/version/body-digest reference reads; draft
create/read/versioned update; and degrade-only optional Memory if enforcement fails.
ADR 0009 keeps OPS authoritative, allows one draft after normal Incident completion,
and treats draft failure as secondary to confirmed OPS work. ADR 0011 requires a fixed
TLS Forwarder, Receiver-only control, scoped sentinels, fixed origins, bounds, and no
automatic retry after uncertain delivery.

Everything below is proposed implementation contract, not an amendment to those ADRs.
The Receiver is the only adapter/manifest/mapping writer. Runs get a scoped sentinel and
opaque adapter request context only. They cannot call tenant URLs, resolve spaces, alter
manifests, create reference approvals, publish, manage grants, search/CQL, or request
unregistered metadata.

| Actor | Scope |
| --- | --- |
| Human curator/operator | Preflight, approval/revocation, publication, archive/delete, grants, and create/conflict reconciliation. |
| Dedicated non-admin automation principal | Future proven read of approved reference pages and create/read/update-draft of registered draft pages only. |
| Receiver/adapter | Durable policy, mapping, receipt, and delivery writer; Forwarder control caller; opaque read-receipt issuer. |
| Run | One registered page operation per adapter request. No direct tenant or curator authority. |

Capability state is DISABLED, PREFLIGHTED, READY, REVOKED, or HELD. Missing verified
ID, manifest, mapping, receipt, storage, grant/readiness result, or enforceable route
holds only the affected Confluence capability and reports degraded optional Memory. It
does not broaden privilege, adopt a title/label/tree fallback, drop Notifications, or
undo confirmed OPS work.

## Effective grants and explicit denials

Group/role names are not evidence. Future tenant acceptance must demonstrate the actual
automation principal and Forwarder route have these effective grants:

| Verified scope | Permitted operation | Denied to Runs |
| --- | --- | --- |
| MAOIREF page IDs in manifest | Read exactly one current approved page/body/version. | Create/update/publish/archive/delete, collection/list/CQL, attachments/comments/labels/properties/permissions. |
| MAOIDRAFT mapped current-rehearsal Incident | Create one draft, then adapter-receipt read/update that page. | Status current, publication, move/title/parent/space change, delete/archive, collection/list/CQL, attachments/comments/labels/properties/permissions, other rehearsal/Incident access. |
| Curator path | Human-only publication, amendment, grant and archive/delete. | No Run sentinel or adapter route grants it. |

The adapter never resolves a scope by page title, label, parent/tree, query result, or
metadata discovery. Curator preflight provides registered numeric space IDs. It may use
only direct page IDs thereafter.

## Records, persistence, and limits

Identifiers are opaque ASCII UUIDs or tenant decimal IDs stored as strings. The sole
exception is a Receiver-generated read-receipt ID: it is unpredictable 256-bit random
material encoded as bounded opaque ASCII, not a UUID. Reject unknown fields, duplicate
JSON keys, non-finite numbers, invalid UTF-8, and values past the stated bound. Body
digest is lowercase SHA-256 over exact UTF-8 storage bytes; it detects changed bytes but
neither authorship nor publication authority.

| Record | Required fields and invariant |
| --- | --- |
| space_binding | binding ID, proposed key, verified space ID, preflight receipt digest/time, state. Key alone never authorizes. |
| reference_manifest_entry | entry/manifest revision, page/space IDs, status current, exact version/body digest/bytes, source provenance, approval/revocation identity pseudonyms and times. One page/version/digest per entry. |
| reference_delivery | run/rehearsal, manifest revision, entry/page/version/digest, delivery time/state. Commit before body crosses Run boundary; exact duplicate is idempotent. |
| draft_mapping | tenant pseudonym, OPS Incident ID, nullable page ID, origin rehearsal, last confirmed version/digest, create intent, mutation receipt, state, OPS link. Unique tenant plus Incident forever through tombstone. |
| read_receipt | Receiver-generated unpredictable 256-bit opaque ID, run/rehearsal, page/space IDs, stored title, draft status, version/digest/body bytes, issued/expiry, mapping or manifest revision, consumed state and input digest. Expiry is at most 60 seconds and never later than the Run lease. Server-owned, never a Run-supplied version claim. |
| draft_intent and draft_receipt | intent, mapping, run/attempt/operation IDs, input/response digest, response class, observed/recorded times, state. Intent commits before Forwarder dispatch. |
| revocation_event | manifest revision, entry IDs, reason category, actor pseudonym/time, affected runs or exposure_unknown, ticket-37 cancellation reference. |
| handoff_manifest | storage generation, bounded mapping/manifest/revocation digests, unresolved states, successor location, read-back digest. |

Use one Receiver transaction for mapping, intent, receipt, delivery, and ticket-37
journal references where available. Never assume atomic commit with Forwarder or tenant.
The shared Receiver database has ticket-37's 128 MiB aggregate cap, including journal,
Confluence rows, row payloads, bodies, indexes, and tombstones, with its 16 MiB recovery
reserve. Confluence active allocation is at most 24 MiB of that aggregate: 256 active
mappings; 2,048 retained mapping/manifest/receipt/revocation rows; 256 KiB stored
sanitized body and response body; 64 KiB request body; 128-byte opaque IDs; 512-byte
title; 4 KiB safe diagnostic; 64 manifest entries/revision; and 128 delivery rows/active
Run. Reserve intent plus terminal receipt capacity before dispatch. Capacity failure
retains unresolved records and holds the capability.

Keep mapping, manifest, revocation, and idempotency tombstones 52 weeks. Archive/index
storage is bounded to 64 MiB total, 8 MiB per handoff, and 32,768 duplicate-rejection
keys; it is not a way around the Receiver database cap. Before compaction, an operator
makes a bounded read-back-verified archive/handoff with that index. Missing, unreadable,
conflicting, or over-cap history is history_unavailable: reference serve and draft
create/update remain held, never title-adopted. A fresh rehearsal cannot read or modify
old drafts merely because mappings are retained.

## Documented native forms and fixed request policy

Atlassian documents v2 page create, direct page get, and page update. Create accepts
spaceId, status, title, and body. Direct get documents body-format, status, version, and
draft-related query fields. Update requires ID, status, title, body, and version. The
local confluence-as 1.1.1 help exposes page create/get/update plus draft status; its
inspected source GETs current version then sends plus one and exposes no caller
expected-version parameter. This is a capability fact, not authorization for stale-body
updates.

Only the following forms are permitted through the fixed Confluence Forwarder origin.
Reject all other methods, paths, absolute targets, redirects, duplicate/framing/hop
headers, query keys, pagination cursor, expansions, and body fields. At the loopback
adapter boundary, accept exactly one expected service-scoped sentinel Authorization value
and exactly the fixed loopback Host; validate both against the active lease, then strip
them and rebuild the upstream request with only managed upstream credential and canonical
Host. Reject duplicate Authorization/Host, unexpected authorization schemes, caller
upstream credentials, and every other caller credential. Allow one Accept application/json
header and, for body requests, one Content-Type application/json header. Reject Expect
and transfer encoding.

| Adapter operation | Fixed upstream request | Required response check |
| --- | --- | --- |
| Reference read | GET /wiki/api/v2/pages/page_id with body-format=storage, status=current, include-version=true | 200; returned ID, MAOIREF space ID, current status, version, and exact storage digest/bytes all match immutable manifest entry. |
| Draft read for composition | GET /wiki/api/v2/pages/page_id with body-format=storage, get-draft=true, include-version=true | 200; mapped MAOIDRAFT ID/space, draft status, body, and version. Adapter commits read receipt before returning sanitized body. |
| Draft create | POST /wiki/api/v2/pages with body containing fixed MAOIDRAFT spaceId, status draft, bounded title, and storage body | 200; returned ID/space/status/version/body digest validate, then trusted read-back attaches mapping. |
| Draft update | PUT /wiki/api/v2/pages/page_id with body ID, status draft, stored title, composed storage body, and version number source-version plus one | 200; exact mapped ID/space/draft status, next version, and resulting digest. Conflict/non-200 never retries. |

The chosen direct-draft query/status semantics are proposed adapter policy and must be
tenant-verified. An absent, current, or other returned status is status_unknown_or_bypass
and holds the operation. Collection/label/CQL/parent placement cannot substitute for a
registered direct ID.

The Run-facing projection contains only operation kind, opaque page ID, status, version,
body digest, bounded storage body when that operation permits it, and safe hold/error
code. It drops author/account IDs, links, labels, properties, operations, likes,
ancestors/children, cursors, space metadata, response headers, and any unregistered
field. A missing required scope field or an oversized/unknown response is held rather
than truncated into apparent success.

## Opaque read receipt and expected-version contract

To update, a Run sends only read_receipt_id and composed storage body. The Receiver
obtains page ID, stored title, draft status, source version/digest, mapping, run,
rehearsal, and expiry from its server-owned receipt. It rejects any Run-supplied page,
version, title, space, status, or expected-version assertion.

In one Receiver transaction, validate the unexpired receipt and its lease/rehearsal,
validate body size/UTF-8, atomically mark the receipt consumed, and append the update
intent with the composed-body digest before any Forwarder dispatch. The receipt ID plus
body digest is the idempotency key: a repeat with the same body returns the recorded
intent/receipt status and cannot send twice; a different body is a receipt conflict hold.
Receiver or Forwarder restart invalidates every unconsumed receipt; no receipt is revived.

The adapter sends exactly source version plus one, not a later GET version plus one.
A validation denial before dispatch records NOT_DISPATCHED and does not become uncertain.
After Forwarder transmission may have started, backend conflict, version/body/status
mismatch, timeout, disconnect, malformed/oversize response, or lost receipt records
UPDATE_UNKNOWN_OR_CONFLICT and holds this secondary Memory step for human
reread/review/reconciliation. It does not GET a later version, merge, overwrite, silently
recreate, or automatically retry.

A confirmed receipt proves only adapter-submitted bytes were bound to its observed
version/digest and the backend returned the prescribed next version. It cannot prove
when or from which mental context text was composed, nor prove tenant compare-and-swap
behavior beyond separately authorized acceptance.

## Normal completion, mappings, and uncertain creates

Ticket 37 records draft_create_intent before the Forwarder call and retains Confluence as
an external secondary effect. Create is eligible only after ticket-14 normal completion:
all accepted members Resolved, no human-forced completion, persistent Report link, OPS
Incident ID, current rehearsal, ready draft capability, and no mapping/hold. The Receiver
persists tenant/Incident mapping plus create intent before dispatch.

A validated 200 plus trusted read-back sets CONFIRMED. A malformed request, missing
mapping, unavailable capability, or policy denial before dispatch records NOT_DISPATCHED;
it never becomes uncertain create. After Forwarder transmission may have started,
timeout, disconnect, malformed/oversize response, mapping write failure, duplicate
conflicting receipt, or uncertain create sets CREATE_UNKNOWN and holds Memory for human
reconciliation. The human uses trusted receipt/read-back; absent certain identity becomes
HUMAN_HELD. Never make another create or adopt any title/label/page because it looks
related. Confirmed OPS completion remains valid when draft create/update fails. Reopening
or pending correction holds draft promotion and preserves its mapping.

## Manifest freeze, revocation, and human retention

Curator approval creates a manifest revision only after operator read-back confirms
MAOIREF page/space IDs, current status, exact version/digest, reviewer, and source
provenance. A draft cannot become a reference by changing a label or status. Publication
creates a separate curator-owned reference identity linked to source draft/Incident
revision. Manifest excludes planned-Fault postmortems, Ground truth, and scoring hints.

At rehearsal start Receiver freezes a manifest revision. Delivery admission and
revocation share one Receiver serialization key per manifest entry. Before bytes cross
the Run boundary, atomically verify not revoked and append reference_delivery as
EXPOSED; revocation atomically blocks later admission, records all exposed or potentially
exposed deliveries, and invalidates outstanding receipts. A delivery interrupted while
bytes may have crossed is potentially exposed, never silently absent. Cancel each exposed
or potentially exposed Run through ticket 37 and hold later model dispatch for review.
If delivery rows are missing/corrupt, mark every active Run admitted to that manifest
exposure_unknown and cancel/hold conservatively. Cancellation does not erase seen text,
settle confirmed/uncertain OPS effects, or authorize repeat work. Mark affected output
for ticket-39 review; retry only through ticket-37 operator recovery with fresh context
and new budget admission.

Humans retain original drafts/references/provenance and approval/revocation history.
Curator-only archive/delete updates manifest state but retains receipt/tombstone history
and never re-exposes it to new Runs. Reset/handoff preserves unresolved state and
read-backs a private handoff before destruction.

## Interfaces, acceptance, and evidence boundary

| Consumer | Adapter obligation |
| --- | --- |
| Ticket 36 | Fixed Confluence listener/origin, scoped sentinel, path/query/header/body/response checks, TLS/control identity, and direct-route denial. |
| Ticket 37 | Use run, attempt, operation, intent, and cancellation references. Intent before dispatch; confirmed/unknown effects stay separate from execution; no confirmed replay. |
| Ticket 39 | Private operator audit may retain the exact reviewed sanitized reference/draft body under ticket-39 bounds and access rules. Shared audit/Run telemetry receives only receipt, version/digest, revocation, and affected-output IDs; no body, curator identity, or Ground truth. |
| Ticket 32/34 | Return approved reference plus compact provenance; expose draft/reference/held/revoked status with no curator control. |

Offline acceptance uses the actual selected adapter, Forwarder request builder, and
client/HTTP seam with synthetic credential/backend. Exercise forged/missing IDs/receipts;
wrong space/rehearsal/status/version/digest; header/query/body/response/pagination leak;
stale composition and concurrent edit conflict; duplicate create, lost create/update
receipt, restart/handoff/capacity; status-current/publication bypass; revocation after
delivery; cancellation with confirmed/unknown OPS effect; inaccessible storage/control/
manifest; and direct-route attempt. Fixture success does not prove tenant grants, native
draft lifecycle, human publication, client compatibility, TLS custody, or venue.

Separately authorized disposable-tenant acceptance must verify space IDs/effective
automation grants, native draft create/read/update/status/version behavior, approved
reference reads, Forwarder TLS/sentinel/control/direct-route denial, expected-version
conflict behavior, curator publication/revocation, persistence/handoff, and audit/output
review. Until then each affected capability remains disabled or held, and no source or
fixture is promoted to tenant/model/venue acceptance.

## Sources

- [Ticket 43](../../issues/43-confluence-scope-approval-and-draft-integration.md);
  [ADR 0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md),
  [ADR 0009](../../../../docs/adr/0009-memory-has-one-incident-authority-and-reviewed-learning.md),
  and [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md).
- [Ticket-33 facts](../ticket-33/facts.md) and [accepted round two](../ticket-33/round-2.md).
- [Ticket-37 recovery](../ticket-37/recovery-specification.md) and
  [Ticket-39 audit](../ticket-39/audit-specification.md).
- [Primary API source map](source-map.md).
