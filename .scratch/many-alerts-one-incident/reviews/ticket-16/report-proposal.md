# Ticket 16 Report proposal

Status: source-only proposal. This document specifies a compact, cited Report
shape and delivery boundary. It does not execute Jira, Kubernetes, Prometheus,
Loki, Tempo, Change, Memory, a model, a tenant, or a paid attempt. It does not
assign semantic grades or approve a human adjudication.

## Proposed lifecycle and rendering choice

Use one logical `report_id` across immutable revisions. Create the Incident with
an initial, self-contained bounded Report in its Description, including all seven
sections and its initial `partial`/`unknown` status. Later complete or corrected
revisions append self-contained dated comments; never rewrite the Description or
edit/delete an earlier comment. A correction appends a new comment with
`supersedes_revision_id`, preserving the earlier defect and citations. This is a
proposal pending native comment/update capability and operator review.

Every revision contains these sections, even when a section is explicitly
`unknown`, `partial`, or `undetermined`:

1. summary and current lifecycle status;
2. blast radius, affected services, and Alerts;
3. UTC-source timeline with source-clock uncertainty and Receiver elapsed
   durations where available;
4. evidence observations and bounded gaps;
5. Suggested root cause, visibly observed or inferred, with qualitative confidence;
6. suggested remediation with authorization/effect status; and
7. Fingerprints explained with source-group/member references.

`complete`, `partial`, `undetermined`, `blocked`, and `unknown` are report
completeness/status values, not semantic grades. The Report must distinguish a
missing response, an empty returned response, a transport error, and evidence
that was not queried. A citation or tool name alone never supports a claim.

## Stable IDs and revision record

Use opaque lowercase UUIDv4 values unless an owning interface supplies a stable
ID: `series_id`, `lifecycle_id`, `run_id`, `attempt_id`, `report_id`,
`report_revision_id`, `incident_id`, `claim_id`, `citation_id`, and
`exchange_id`. A correction increments `revision_ordinal` and points to the
prior revision; identities are never reused. Store `submitted_at`, model/auth/
venue/Memory condition as recorded values or `unknown`, not inferred claims.

The Run-facing object is proposed as `report-draft-v1`; it maps to Ticket 39's
authoritative private `report-revision-v1` capture record after sanitization and
audit capture. This proposal does not define a competing immutable audit store.

Proposed `report-draft-v1` fields:

```json
{
  "schema_version": 1,
  "record_kind": "report_draft",
  "report_id": "uuid",
  "report_revision_id": "uuid",
  "supersedes_revision_id": null,
  "lifecycle_id": "uuid",
  "run_id": "opaque-or-unknown",
  "attempt_id": "opaque-or-unknown",
  "revision_ordinal": 1,
  "submitted_at": "2026-09-22T12:00:00Z",
  "status": "partial",
  "confidence": "undetermined",
  "sections": {
    "summary": "Observed checkout errors increased during the bounded window.",
    "blast_radius": "Observed services: checkout; other scope is unknown.",
    "timeline": "At 12:00:04Z the returned metric window changed.",
    "evidence": "See citation 00000000-0000-4000-8000-000000000002.",
    "suggested_root_cause": "Undetermined; the error-rate observation does not establish a dependency failure.",
    "suggested_remediation": "Operator review required; no mutation was requested.",
    "fingerprints": "fp-example and its Alert members remain linked."
  },
  "claims": [{"claim_id":"00000000-0000-4000-8000-000000000001","claim_kind":"observation","text":"Checkout errors increased in the returned window.","observed_or_inferred":"observed","status":"asserted","evidence_refs":["00000000-0000-4000-8000-000000000002"],"derived_from":[]}],
  "citations": [{"citation_id":"00000000-0000-4000-8000-000000000002","source_kind":"prometheus","provenance":"local_association","source_interface":"fixture","query_or_reference":{"expression":"synthetic_error_rate","from":"2026-09-22T12:00:00Z","to":"2026-09-22T12:05:00Z","step":"60s","returned_values":[{"value":0.2,"unit":"ratio"}]},"scope":{"service":"checkout"},"exchange_id":"00000000-0000-4000-8000-000000000003","observation_status":"returned","observed_at":"2026-09-22T12:00:04Z","evidence_ref":"00000000-0000-4000-8000-000000000004"}],
  "arithmetic": [],
  "gaps": ["evaluation evidence unavailable"],
  "envelope": {"content_sha256": "sha256-of-canonical-redacted-record", "canonical_utf8_bytes": 0}
}
```

The example is a bounded synthetic fixture, not a complete conformance instance,
and carries no operator Ground truth, credentials,
account identity, private audit body, scoring feedback, or pre-awarded verdict.
Persist canonical UTF-8 JSON with sorted keys, no insignificant whitespace,
unique object keys, schema version, and finite bounded numbers. Reject unknown
fields/enums, malformed UTF-8, invalid timestamps, duplicate IDs/ordinals,
excessive nesting, and bounds violations. The envelope's `content_sha256` and
`canonical_utf8_bytes` are excluded from the hashed draft/ADF bytes; the
authoritative Ticket 39 record carries any predecessor/reference digest. No
self-hash is embedded in the bytes it hashes.

## Claim and citation semantics

Each claim has `{claim_id, claim_kind, text, observed_or_inferred, status,
evidence_refs, derived_from}`; proposed non-grade statuses are
`asserted|unreviewed|unknown`. `observed` requires a returned response or
approved system observation. `inferred` names the observed claims from which it
was derived and remains visibly labelled. `unknown`/`unverifiable` preserves the
gap; it is not a wrong finding. Confidence is qualitative only:
`high|medium|low|undetermined`, with a short rationale and no numeric semantic
threshold. Human adjudication remains a separate pending/reviewed/disputed
record; this proposal never fills its grade or approval.

Every citation has:

```json
{
  "citation_id": "uuid",
  "source_kind": "prometheus",
  "provenance": "native_returned|local_association|unknown",
  "source_interface": "native_capture|forwarder_receipt|query_result|fixture|unknown",
  "query_or_reference": {},
  "scope": {"service": "checkout", "from": "2026-09-22T12:00:00Z", "to": "2026-09-22T12:05:00Z"},
  "exchange_id": "uuid-or-null",
  "observation_status": "returned|empty|missing|truncated|redacted|transport_error|unknown",
  "observed_at": "2026-09-22T12:00:04Z",
  "evidence_ref": "evidence-id-or-null"
}
```

`source_interface` is assigned from the trusted capture boundary, not Run prose;
its known values map directly to ticket 39's exchange source interface. Unknown
remains an explicit capture gap. `native_returned` is permitted only when that
boundary observed native provenance; fixtures/replays never gain it from their
payload labels. Correlation provenance and source interface are separate fields.
Truncation or redaction that removes support stays visible and unverifiable.

The `query_or_reference` shape is source-specific and bounded:

| Source | Required query/reference fields |
|---|---|
| Prometheus | `expression`, range `from/to`, `step`, returned series/sample reference, and units. |
| Loki | `logql`, stream selector, range, direction, limit, returned entry IDs/timestamps, and query status. |
| Tempo | `traceql`, range, trace/span/event IDs, service scope, and returned span/event reference. |
| Kubernetes | API group/version, verb, namespace, kind/name, UID, resourceVersion, field selector, and returned observation digest. |
| Change | `change_id`, `stage_id`, stage sequence, requested/accepted/observed outcome, and Change evidence digest. |
| Memory | `memory_entry_id`, revision, retrieval mode, content digest, and review state; Memory is context, not independent confirmation. |

The citation must identify what was returned at the time, not only a reusable
query. A later query gets a new `exchange_id` and cannot repair a missing
original response. Keep action evidence separate from symptoms, diagnosis,
repository Ground truth, and scoring feedback. A Change citation supports only
its recorded stage; a ConfigMap write is not a served value, rollout health is
not recovery, and a Trigger name is not a Mechanism.

## Arithmetic and bounded evidence

Each arithmetic assertion stores decimal operands, units, formula, displayed
result, reproducible result, precision/tolerance, and citation IDs for every
operand. Missing operands are `unknown`; estimates never become provider actuals.
Rounding is allowed only when units and precision are displayed. An incorrect
displayed result remains a revision defect even if the causal suggestion is
otherwise supported.

Proposed Report transport bounds, measured in serialized UTF-8 bytes after ADF
JSON serialization:

| Field | Proposed bound and behavior |
|---|---|
| Initial Description ADF | 8,192 bytes; reject/hold before dispatch if exceeded. |
| One self-contained revision comment ADF | 8,192 bytes; do not split one revision across comments; overflow blocks that revision. |
| One revision content | 7,000 UTF-8 bytes of redacted prose/structured fields before ADF markup. |
| All Report ADF for one attempt | 64 KiB, including framing and citations. |
| Claim/citation arrays | 64 claims and 128 citations per revision; 128-byte IDs; 4 KiB query/reference object. |
| ADF nesting/text | Depth 8; one text node 2 KiB. Proposed node enum: `doc`, `heading`, `paragraph`, `text`, `bulletList`, `listItem`, `codeBlock`; mark enum: `link`, `strong`, `em`, `code`. Pin supported attributes and native support before enabling each. |
| Whole Jira request | 16 KiB serialized UTF-8 bytes including envelope and field names; reject/hold before dispatch. |

These are proposals requiring native acceptance. The historical accepted 9,417
character command and denied 11,313-character command describe one client/policy
configuration and are not universal safe limits. Measure every field and request
as serialized UTF-8 bytes, including ADF markup, and retain the measured byte
count/digest. Overflow is `blocked` with an explicit omission/gap; never truncate
silently or retry indefinitely.

## Synthetic ADF example

This bounded fixture is serialization-only, not a complete Report, Jira call, or
semantic grade:

```json
{"version":1,"type":"doc","content":[{"type":"heading","attrs":{"level":2},"content":[{"type":"text","text":"Summary"}]},{"type":"paragraph","content":[{"type":"text","text":"Observed checkout error evidence is cited; root cause remains an inference."}]},{"type":"paragraph","content":[{"type":"text","text":"Status: partial. Confidence: medium."}]}]}
```

The fixture must be parsed, serialized as UTF-8, byte-counted, hashed, and
round-tripped before any native binding is considered. It contains no raw
operator truth or private audit material.

## Transport and attempt rules

The preferred future transport is a trusted bounded adapter that submits ADF
from an exact UTF-8 file or stdin and verifies request/response bytes and a
correlated native response ID. The reviewed local CLI source advertises
`--body @file|-` and reads UTF-8 file/stdin JSON, but this is source evidence,
not proof of Run permissions, installed behavior, or an approved Jira route.
The staged producer must write only to an operator-owned 0700 handoff path,
fsync, byte-count/hash/read back, atomically rename, and clean up on success or
failure; it must not assume Run `Write`, arbitrary file creation, or shell pipes.
Do not place ADF in argv or widen permissions. Native binding remains an explicit
gate until the adapter, permissions, response schema, and effect receipt are accepted.

The local source check identifies the narrow future operations as `createIssue`,
`addComment`, `editIssue`, `getComments`, `getIssue`, and bounded candidate
search. The adapter must allowlist fixed OPS/Incident fields and immutable
revision comments, prohibit Description rewrites, author impersonation, and
supplied timestamps, and validate returned project/type/identity. Enhanced
search may be eventually consistent; a negative search is not proof that an
uncertain create did not happen, so reconciliation cannot auto-create a duplicate.

A shorter Report attempt is allowed only before `launch+270s` when trusted
evidence proves the prior create/update was `NOT_DISPATCHED`; the 20-second
flush and 10-second kill/reap period is not a clean retry window. The one shorter
attempt must fit the original budget and state explicit omissions.
It uses a fresh exchange/intent as required by the owning recovery contract and
never creates a second Incident or tests permissions. An uncertain mutation is
held for reconciliation; it cannot receive a shorter duplicate create. A missing
capability discovered before dispatch is `blocked`/`NOT_DISPATCHED`; `unknown`
is reserved for an attempted or potentially dispatched operation whose effect
cannot be established.

## Initial Description and revision comments

The initial create contains the compact first Report in all seven sections. Each
revision comment is self-contained and includes `report_revision_id`,
`supersedes_revision_id`, UTC date, revision ordinal, section content, citation
IDs and gaps. Current payload byte counts and hashes stay in the external
envelope; embedded citations may carry source or prior-revision hashes, never
a self-hash. A later Run appends a dated correction. It does
not rewrite the Description, mutate a prior comment, delete a defect, or replace
an earlier citation. If native comment/update support or correlation is missing,
the revision is `blocked`; an undispatched operation is `NOT_DISPATCHED`, while
an operation that may have been sent remains unknown pending reconciliation.
No direct-credential fallback is allowed.

## Offline acceptance and live gates

Offline fixtures must drive the real Report builder, ADF serializer, revision
store, citation validator, and bounded transport adapter with synthetic returned
responses. Cover duplicate/conflicting revision IDs, missing predecessor,
malformed UTF-8/JSON/ADF, duplicate keys, non-finite numbers, nesting and byte
overflow, empty versus missing/error responses, each source citation shape,
observed versus inferred claims, arithmetic defects, partial/undetermined
Reports, append-only corrections, stale citations, no-op/NOT_DISPATCHED shorter
attempt, uncertain mutation hold, and no raw Ground truth in output. The fixture
must verify byte counts and hashes after file/stdin round-trip.

Future native gates remain separate: approved operator Jira identity and fields,
ADF create/comment/update capability, UTF-8 file/stdin transport, response and
effect receipts, current Run/Incident/Change/Memory bindings, 300-second
containment, budget/accounting, venue, audit capture, and human adjudication.
No Jira, tenant, model, paid call, runtime, or live acceptance is claimed here.

## Sources and open proposals

Primary sources read: issue 16; ADRs 0004, 0006, 0009, 0012, and 0014; Ticket
37 recovery specification; Ticket 39 audit specification; Ticket 23 timing-draft
README, [operator rubric](../ticket-23/timing-draft/operator/rubric.md), preflight,
Run system/task prompts, and the [incident-report SKILL source draft](../ticket-23/timing-draft/run/incident-report/SKILL.md)
plus its rubric approval record. Ticket 23 drafts
and rubric are evidence for boundaries, not an instruction to execute a Skill;
see the [Eyes/Report/Forwarder source checks](../eyes-report-forwarder-sources.md)
for local CLI and ADF documentation evidence, including the
[official ADF structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/).

The chosen Description-plus-append-only-comments shape, ADF node allowlist,
serialized-byte bounds, citation field limits, confidence vocabulary, and
file/stdin adapter are proposals. The native Jira field/comment limits, current
installed CLI permissions, Run transport allowlist, response/effect schemas,
and operator approval workflow remain unresolved gates. ADR 0014's human
semantic review and any scoring grade remain outside this proposal.
