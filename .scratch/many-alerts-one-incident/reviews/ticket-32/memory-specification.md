# Ticket 32 Memory storage and offline acceptance specification

Status: proposed implementation contract, source-only, 2026-09-22. This file
does not change a Skill, receiver, Jira/Confluence record, tenant, volume,
credential, authentication grant, model, cluster, headless session, or runtime.
“MUST” is a requirement for a future implementation. A passing offline fixture
is not native, tenant, venue, model, or live acceptance.

## Authority and settled boundaries

ADR 0009 and ticket 13 settle the authority split:

| Store | Authority and permitted use |
| --- | --- |
| OPS | Authoritative Incident identity, open status, accepted member set, current per-Fingerprint state, Severity/Urgency, Reports, and Incident-to-draft link. Memory cannot create eligibility, Match, membership, completion, or Severity facts. |
| Confluence MAOIREF | Human-approved reference pages and runbooks. A reference is usable only through ticket 43’s exact manifest page/version/body-digest contract. |
| Confluence MAOIDRAFT | One reviewable draft postmortem after confirmed normal completion. Draft creation/update is a secondary effect and remains ticket 43’s mapping, receipt, and reconciliation authority. |
| Memory directory | Sanitized observations, hypotheses, retrieval hints, source references, and corrections. Entries are untrusted data, never instructions, Ground truth, credentials, raw prompts, raw tool bodies, or a second Incident database. |
| Receiver recovery journal | Durable admission, execution, intent, effect, and recovery state under ticket 37. It is separate from Memory and inaccessible to Runs. |
| Private audit | Ticket 39’s operator-only capture and review material. Memory and shared telemetry receive only bounded references and projections. |

The ordering is fixed: retrieve fresh OPS candidates/member state and approved
references before Match; verify every cited source before relying on it; append
Memory learning only after the relevant OPS write is confirmed and the Report
revision is persisted; create or update a draft only after confirmed normal
completion. A failed secondary Memory or draft write never undoes confirmed OPS
work and is reported as incomplete Memory. Human correction owns moving members,
merging duplicate Incidents, and Severity correction.

Ticket 14 settles additive `cascade-<value>` and `fp-<fingerprint>` membership
labels, exact-repeat/pending reduction, thirty-minute candidate eligibility,
current member state, and human correction. It deliberately leaves the physical
current-member representation unspecified. This specification therefore defines
an adapter projection and validation contract, not a claim about a Jira field,
property, label, or installed API.

## Proposed OPS projection

The OPS adapter returns a bounded `incident_snapshot-v1` for each candidate:

| Field | Requirement |
| --- | --- |
| `incident_id`, `project`, `issue_type`, `status`, `created_at` | Server-returned identity and UTC/Jira-clock values; project/type/status are checked against the intended venue. |
| `labels` | Complete server-returned label set. Accepted membership preserves every `cascade-*` and `fp-*` label additively; Memory never replaces or removes labels. |
| `members` | One entry per accepted Fingerprint: `{fingerprint, current_state, state_observed_at, source_revision, state_digest}`. `current_state` is `Firing`, `Resolved`, or `Unknown`. |
| `severity`, `urgency` | Server-returned ratcheted state. Memory cannot lower or infer either value. |
| `report_ref` | OPS Report identity plus latest immutable revision identity/digest; a missing or conflicting Report is an incomplete candidate. |
| `correction_pending`, `rehearsal_provenance` | Server-returned correction hold and any recorded origin metadata; neither is inferred from Memory. |

`members` is a proposed adapter-level view. Before native enablement, the
adapter must bind it to an explicitly approved OPS representation and prove
read-back. An older/imported Incident without the managed schema marker is
`Unknown`; absence of a done-state label or field never proves `Firing` or
`Resolved`. A proposed done-state label/property mapping may be enabled only
with a versioned marker, migration rule, and exact read-back. It cannot silently
reinterpret existing Incidents. A fresh OPS read is authoritative; a cached
Memory entry is never a substitute.

Automatic updates preserve membership and ratchet Severity/Urgency only after an
accepted Match. Human-owned correction is required for reassignment, duplicate
merge, or Severity lowering. A pending correction blocks automatic completion.
Normal completion requires every accepted member to be explicitly `Resolved`;
human-forced completion is separate and names unresolved members.

Each automatic OPS mutation carries the adapter's exact expected snapshot
revision/digest and operation ID. The adapter rejects a missing or stale
precondition before dispatch; a conflict, ambiguous response, or incomplete
read-back holds the Incident and requires a fresh complete snapshot. A successful
read-back verifies Incident identity, revision, complete labels/members, and the
intended additive/ratcheted delta before Memory can record the result. Native
enablement must establish the venue's exact precondition form and read-back
semantics; this is a required capability gate, not a claim that Jira offers a
generic compare-and-set operation.

## Memory records and provenance

The directory stores immutable `memory-entry-v1` records. Required fields are:

| Field | Bound and meaning |
| --- | --- |
| `entry_id`, `rehearsal_id`, `run_id`, `incident_id` | Lowercase UUIDs except opaque owning IDs; immutable scope and provenance. `run_id` may be null only for an operator-approved reference import. |
| `kind` | `observation`, `hypothesis`, `retrieval_hint`, `correction`, `retraction`, or `loss`. |
| `claim` | Redacted UTF-8 text or bounded structured value, explicitly `observed`, `inferred`, `unknown`, or `unverifiable`; never a semantic grade. |
| `fingerprints`, `services`, `dependencies` | Bounded scope selectors; they describe the entry and cannot expand OPS eligibility. |
| `source_refs` | One or more `{source_kind, source_id, source_revision, source_digest, observed_at, source_scope}` records. `source_kind` is `ops_read`, `report_revision`, `forwarder_receipt`, `forwarder_effect`, `query_result`, `reference_manifest`, `change_projection`, or `operator_approved`; `source_scope` is normalized and bounded, never a raw query/body. |
| `report_revision_id`, `ops_snapshot_digest` | Optional links required when the entry describes a Report or current member state. |
| `supersedes_entry_id`, `correction_reason`, `actor` | Required for correction/retraction; original content remains immutable. |
| `created_at`, `schema_version`, `canonical_bytes`, `content_sha256` | Receiver-recorded metadata; hash and byte count are envelope fields excluded from hashed bytes. |

For `forwarder_effect`, the reference additionally records its fixed ticket-37
effect receipt ID, `effect_status`, `readback_status`, target identity, and target
version; all are required for a claimed confirmed effect. For a
`forwarder_receipt`, the reference records its transport outcome only.

An observation requires a returned OPS/query/approved-reference record, approved
system observation, or a `forwarder_effect` with ticket 37 `effect_status` and
`readback_status` both `confirmed`, plus the target identity, target version, and
read-back digest. A `forwarder_receipt` is transport correlation only: it records
its `NOT_DISPATCHED`, `DISPATCHED_UNKNOWN`, or `PARTIAL` state in a `loss` entry
with claim status `unknown` or `unverifiable`; it cannot itself support an
observed claim. Receipt outcome `confirmed` and read-back `confirmed` project
to ticket 37's effect state `CONFIRMED` only after the target checks above.
An inference names its supporting observed entry IDs and remains visibly
inferred. A source digest detects changed bytes; it does not prove provider
identity, causal truth, tenant authority, or billing.
Unknown, stale, revoked, missing, redacted, or unverifiable sources produce a
visible gap/loss entry or hold and cannot become a current fact. No raw prompt,
tool body, credential, account identity, repository adjudication Ground truth,
or unbounded model prose is persisted.

Corrections append a new entry with `supersedes_entry_id` and either
`correction` or `retraction`; they never edit, delete, or hide the predecessor.
The default current view excludes superseded/retracted entries but exposes the
chain and reason. A correction pending for the related Incident blocks automatic
completion and draft promotion. A Memory correction cannot move OPS membership.

## Narrow interface

The future Receiver-owned service exposes only these bounded operations to an
admitted Run or trusted Receiver caller:

```text
memory.append(rehearsal_id, run_id, idempotency_key, entry) -> append_receipt
memory.read(rehearsal_id, scope, view=current|history, cursor?) -> memory_page
memory.read_entry(rehearsal_id, entry_id) -> entry_or_gap
memory.status(rehearsal_id) -> {generation, state, counts, bytes, hold_reasons}
```

`append` accepts only a Receiver-verified caller identity bound to the active
`{rehearsal_id, run_id, lease_id, generation}`; an operator reference import uses
a separately verified operator identity. The service derives and records caller
kind/identity and rejects caller-supplied attribution, an unbound rehearsal/run,
unknown schema/enum, duplicate JSON keys, malformed UTF-8, invalid number form,
raw-secret fields, missing source verification, an OPS-dependent entry before
confirmed OPS write, or a correction whose parent is absent. The caller cannot
select a filesystem path, write a file, alter the current projection, or supply a
server identity. A duplicate `(rehearsal_id, idempotency_key)` with the same
canonical digest returns the original receipt; a different digest is a conflict
hold. Entry, index, hash predecessor, attribution, and receipt commit atomically
or none is visible.

`read` requires the current rehearsal ID and a bounded scope of at most 32
services, 64 dependencies, 64 Fingerprints, and 16 registered Incident IDs. It
returns source references, status, loss/correction links, and continuation state;
it never returns private audit bodies, prior-rehearsal directory entries, raw
Confluence bodies, or scoring/adjudication material. History is explicit and
bounded, not an implicit bypass of current-state filtering. A query cannot use a
label, title, old rehearsal, or cached entry to create a candidate.

## Persistence, identity, and reset

Proposed storage is a dedicated persistent volume mounted in the main container
at `/var/lib/maoi/memory`, with root and each rehearsal directory owned by
Receiver UID `10000`, mode `0700`, and no sidecar or Run mount. The Run reaches
it only through the structured append/read service; it receives no path, file
descriptor, control socket, database credential, or unrestricted Write. This is
the narrow ADR 0009 exception and is distinct from ticket 37’s Receiver journal.
The exact volume class, fsync/WAL implementation, and container binding remain
unverified deployment choices.

Proposed bounds per rehearsal are: 64 MiB total canonical records/indexes,
4 MiB reserved for recovery/reset handoff, 4,096 entries, 64 KiB per entry,
256 KiB per append batch, 16 entries per batch, 128 source references per entry,
32 correction links per chain, and 8 KiB structured claim text. The whole Memory
volume, including current and archived generations, handoff manifests, and
indexes, is capped at 256 MiB and four generations. At capacity the service holds
new append/admission; it never deletes acknowledged records or an unresolved
obligation to make room. Reads return at most 100 entries or 1 MiB, with one
continuation and a five-second local deadline. A bound is checked before
dispatch/commit. These are proposed Memory limits and do not consume ticket 37’s
128 MiB recovery-journal cap or ticket 39’s private audit budget.
Off-cluster Memory archives and their indexes share this global quota; relocating
an old generation cannot create an unbounded second archive. In-progress copies
count against the quota until verified cleanup, and retain the original expiry.

Input is limited to 256 KiB before parsing, depth 16, 64-byte keys, 256-byte
opaque/source IDs and scopes, 128-byte service/dependency/Fingerprint selectors,
and 64 lowercase hexadecimal bytes for a SHA-256 digest. Record selectors use
the same cardinality limits as reads; other arrays have at most 128 elements.
Numeric values are
base-10 signed 64-bit integers only; decimal, exponent, non-finite, oversized,
and boolean-for-integer forms are rejected. These sublimits apply before index
allocation or canonicalization.

Every record is canonical UTF-8 JSON with sorted keys, unique keys, a schema
version, bounded integers, and a predecessor digest. On process or pod restart,
the service verifies the root, predecessor chain, indexes, and generation before
serving reads or writes. A corrupt, missing, or conflicting record holds the
directory; it must not silently recover a valid prefix, discard acknowledged
entries, or treat absent state as no learning. Recovery requires an operator
read-back-verified handoff or authoritative reconstruction.

Reset is operator-only and creates a new rehearsal ID/generation. Before reset,
active Runs and unresolved ticket-37 effects are held/reconciled, Memory is
exported to a bounded private handoff manifest, and the handoff digest is read
back. The manifest records each referenced source's owning system, retention
deadline, and unresolved obligation; it is a reference, never a copied ticket-39
audit artifact or an extension of its retention. An archived generation may expire
after 30 days only when its handoff has been read back and every recorded
obligation is reconciled; an unresolved obligation prevents expiry and instead
holds further admission at the aggregate capacity. Reset never closes or edits
OPS Incidents, clears accounting reservations, deletes Confluence history, or
makes an uncertain draft absent. The old directory is retained or archived under
its generation but is inaccessible to a new Run unless explicitly approved
reference material is delivered through the ticket-43 manifest.

## Rehearsal admission and Confluence integration

At fresh-rehearsal preflight, query all OPS Incidents that could satisfy ticket
14’s exact-Fingerprint or cascade candidate rules: open status and Jira-created
time within the inclusive thirty-minute window. The proposed query accepts at most
100 returned Incidents per page, ten pages, five seconds per page, and 30 seconds
total; every page must carry the same query/snapshot marker and the final page
must explicitly exhaust its cursor/count. A timeout, missing page, changing
marker, count disagreement, or page-cap reach is incomplete and holds Run/model
dispatch. Do not filter by rehearsal label, Memory provenance, title, or cached
directory state. If any prior-rehearsal Incident remains eligible, hold new
Run/model dispatch until it ages out or a human explicitly disposes of it. Never
auto-close it, clear uncertainty, or hide it from the candidate set. Bounded
Notification admission/coalescing may continue under ticket 37 while this gate is
held.

Reference delivery uses ticket 43’s frozen manifest, exact page/version/body
digest, revocation serialization, and exposure record. A revoked, changed,
unavailable, or unverified reference is unavailable and visibly degrades Memory;
it is not replaced by the latest page. If bytes may have crossed the Run boundary,
ticket 37 cancellation/reconciliation applies. An approved reference may provide
context, but it cannot make an old OPS Incident eligible, establish a Match, or
promote a prior Incident into the current rehearsal.

Draft identity and expected-version receipts remain ticket 43’s single mapping
authority. Memory stores only the OPS Incident/draft link and receipt references;
it must not create a second mapping store. `draft.create` is eligible only after
confirmed normal OPS completion, persistent Report link, current-rehearsal
mapping/create intent, and no correction/hold. A successful native response needs
trusted read-back. Lost response, mapping failure, stale version, or uncertain
transmission is `CREATE_UNKNOWN`/`UPDATE_UNKNOWN` and holds Memory for human
reconciliation; no title adoption, duplicate create, later-version overwrite, or
automatic retry. Confirmed OPS completion remains confirmed when this secondary
step fails.

## Offline acceptance matrix

Acceptance must exercise the real selected caller/adapter boundaries and a
stateful offline OPS/Confluence backend; directly constructing a passing entry is
not sufficient. Use Ticket 31’s Cascade fixtures and extend/reference them; do
not replace them with stubs presented as model proof.

| Case | Required assertion |
| --- | --- |
| Schema and bounds | malformed UTF-8/JSON, duplicate keys, unknown fields/enums, non-finite numbers, depth, entry/batch/store/query caps, and invalid source scope hold before commit. |
| Source verification | current OPS snapshot + Report revision appends; wrong digest, stale version, missing read-back, revoked reference, and cached-only source become unknown/unverifiable. |
| Forwarder provenance | `NOT_DISPATCHED`, `DISPATCHED_UNKNOWN`, and `PARTIAL` transport receipts create only loss/unknown entries; only a confirmed effect receipt with matching target identity/version and confirmed read-back supports an observation. |
| Atomic/idempotent append | exact duplicate returns one receipt; conflicting idempotency key holds; injected index/WAL failure leaves no partial entry or receipt; restart preserves committed entries. |
| Caller and lifecycle bounds | forged run/lease/generation or caller attribution is rejected; input numeric/ID limits precede allocation; aggregate capacity holds rather than erasing records; expired archive needs reconciled obligations and a digest-read-back handoff. |
| Correction history | supersede/retract appends immutable predecessor-linked records; current view hides superseded content while history shows both; missing parent and duplicate ordinal hold. |
| OPS semantics | additive cascade/Fingerprint updates preserve unrelated labels; stale expected revision, conflict, or incomplete read-back holds before Memory append; later Firing replaces earlier Resolved in the authoritative snapshot; omitted members remain unknown/current, never silently Resolved; unsupported done-state mapping holds. |
| Ticket 31 extension | F01 duplicate, F03 A→B→A, F05 state change, F06 omission, F08 additive ratchet, F11 correction hold, and F14 append provenance retain expected orchestration/read-back. |
| Secondary failure | confirmed OPS write plus failed Memory append or failed draft write preserves OPS confirmation and exposes incomplete Memory without repeating the OPS mutation. |
| Confluence | draft create/update receipt loss, stale version, duplicate body, revocation-after-delivery, restart, and unknown create hold under ticket 43; no independent mapping or title adoption. |
| Rehearsal isolation | old directory entries are unreadable after reset; explicitly approved reference delivery is scoped; prior eligible OPS Incident blocks fresh admission until age-out/human disposition. |
| Candidate completeness | missing, changing, over-cap, timed-out, or count-inconsistent candidate page holds dispatch; only an exhausted bounded snapshot can clear the prior-Incident gate. |
| Security and exclusions | Run cannot access path/control/credentials, append raw prompt/tool body/Ground truth, forge source provenance, invoke Confluence publication, or use Memory to create Match/eligibility. |

The evidence layers remain separate: repository/source/CLI checks establish
documented shapes only; offline tests establish adapter and state-machine
behavior; model/Skill conformance is a separate review; volume durability,
permissions, TLS/Forwarder, tenant grants, native OPS/Confluence behavior,
cluster restart/reset, and live venue acceptance remain `NOT RUN`.

## Sources and remaining gates

Read: [issue 32](../../issues/32-memory-storage-and-offline-acceptance.md),
[ticket 13 Answer](../../issues/13-memory.md#answer), [ADR 0009](../../../../docs/adr/0009-memory-has-one-incident-authority-and-reviewed-learning.md),
[ADR 0006](../../../../docs/adr/0006-one-incident-per-fault-and-match-is-a-judgment.md),
[ADR 0012](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md),
[ADR 0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md),
[ticket 14 Answer](../../issues/14-many-to-one-under-a-cascade.md#answer),
[Ticket 16 proposal](../ticket-16/report-proposal.md),
[Ticket 31 fixtures](../ticket-31/fixture-spec.md),
[Ticket 36 Forwarder](../ticket-36/forwarder-specification.md),
[Ticket 37 recovery](../ticket-37/recovery-specification.md),
[Ticket 39 audit](../ticket-39/audit-specification.md), and
[Ticket 43 Confluence](../ticket-43/confluence-specification.md).

The following remain implementation/acceptance gates: exact native OPS current
member representation and managed-schema migration; native field/read-back and
permission behavior; dedicated volume class, fsync/WAL, UID/mode enforcement and
restart durability; structured adapter process identity; ticket-43 manifest and
tenant draft lifecycle; source-query availability and revocation timing; and
audience projection bounds. No runtime, model, tenant, paid, cluster, or live
acceptance is claimed.
