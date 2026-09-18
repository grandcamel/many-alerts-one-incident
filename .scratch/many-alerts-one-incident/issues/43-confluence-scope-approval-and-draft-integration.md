# Confluence scope, approval and draft integration

Type: task
Status: open
Blocked by: 16, 33

## Question

Produce an implementation-ready specification for [ADR 0017](../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md), not tenant or runtime changes. Resolve proposed MAOIREF/MAOIDRAFT keys to verified IDs only in separately authorized preflight; no space existence is assumed. Define human curator and dedicated non-admin automation roles, exact effective grants and defense through the accepted Forwarder. Group/role names alone are not enforcement proof.

Specify versioned operator-owned approval manifests and durable tenant/OPS-Incident-to-draft mappings with origin rehearsal, confirmed version, receipt and OPS link. Define capacities, persistence/handoff, source provenance, approval/revocation history and audit identities. Keep old mappings for duplicate prevention without granting fresh Runs access to prior-rehearsal artifacts. Human-only reconciliation resolves uncertain creates; never title-adopt or silently recreate. Preserve ADR 0009 normal-completion eligibility and optional secondary-failure semantics.

Enumerate exact native client/API request forms for approved reference ID/version/digest reads, scoped draft create/read/update and necessary metadata resolution. Bound payloads, pages and pagination; fail closed on unknown identity/status/operation. No unrestricted CQL, space enumeration, attachments, comments, labels, publication, move/copy/delete or permission changes by Runs. Specify response sanitization and scope checks for metadata and direct-ID requests; transport scope must not depend on labels or tree placement. Verify native draft retrieval and lifecycle behavior; inspected CLI help is not a tenant receipt.

Design and verify a narrow adapter or Forwarder expected-version contract binding composed content to the read source version. The installed CLI's GET-then-current-plus-one update does not establish that contract. Cover stale body composition before the CLI GET, concurrent human/Run edits, version conflicts, absent status and publication bypass. Do not auto-overwrite or broaden privileges to make a test pass.

Define rehearsal manifest freeze and immediate revocation, exact delivered-reference tracking, active-Run cancellation via ticket 37, conservative unknown-exposure handling, affected-output review and subsequent explicit retry with fresh context. Version/digest mismatch withholds the page; no assumed historical-version capability or cached-reference fallback. Publication creates a separate curator-owned reference identity with reviewer/provenance; retain human-visible histories and no automatic deletion/re-exposure.

Offline acceptance must exercise actual client/Forwarder request and state boundaries: wrong/missing/forged IDs, cross-space/rehearsal read/update, metadata/pagination leaks, unapproved versions/digests, stale composed bodies, duplicate/uncertain creates, status/publication bypass, revoked material already delivered, cancellation with confirmed/uncertain OPS effects, and inaccessible manifest/credentials. Keep these tests distinct from future tenant proof of effective grants, native draft create/read/versioned update, human publication and direct-route prevention using explicitly authorized disposable artifacts. If gates fail, disable only affected Confluence capabilities and disclose degraded Memory. No tenant call, provisioning, credential change, publication or model Run is authorized by this task.

Coordinate interfaces with tickets 32/36/37/39 without circular specification dependencies. Their work can consume this accepted ADR before the concrete interface specification is complete; final integration requires mutually consistent contracts and evidence.

## Accepted audience input from ticket 34

ADR 0018 renders distinct draft/reference identities with approval/version provenance, incomplete writes and immediate revocation state. Its pinned historical snapshots never restore current approval or serve withdrawn references. Expose only safe read-only projection fields to the operator view; mutation/curator controls remain separate.
