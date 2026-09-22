# Ticket 44 operator Memory audience specification

Status: source-only proposed read projection, 2026-09-22. This specifies an
operator-only, read-only presentation contract for ADR 0018. It builds no
dashboard, grants no account access, calls no tenant, uses no credentials, runs
no model, and creates no approval, publication, retry, reset, or network-route
control. The projection is not a new Incident, Memory authority, scoring feed,
or source of human adjudication.

## Authority and selected context

The presenter opens one operator-side view with four sections: **Incident state
(OPS)**, **Observations and hypotheses (Memory directory)**, **Postmortem
drafts**, and **Approved references**. A linked sanitized Grafana timeline is
complementary activity evidence; it is never the source of a human verdict.

The Receiver supplies a trusted `context_id`, selected current `rehearsal_id`,
optional `run_id`, and selected `incident_id`. `context_id` is only an opaque
alias for that validated tuple plus the operator authorization generation; it is
not a second source or join identity. Selection is bounded to records already
authorized for the operator channel. Caller text cannot widen source, tenant,
rehearsal, Run, Incident, or audit scope. A rehearsal switch clears the current
selection and visible cards before loading the new context; it never imports
prior-rehearsal artifacts automatically.

The view has no Run-readable mount, telemetry export, prompt/tool channel, or
write route. The only presentation mutations are local selection, pin/unpin of
a bounded snapshot, and safe provenance inspection. Network destinations and
URLs are server-generated from an internal allowlist; arbitrary URLs, query
strings, credentials, fragments, and caller-selected routes are rejected.

## Common projection envelope

Every card and count record has a strict bounded envelope:

```json
{
  "schema_version": 1,
  "projection_id": "opaque-id",
  "record_id": "opaque-source-id",
  "source_class": "ops|directory|draft|reference|ticket37_recovery|ticket35_telemetry|review",
  "rehearsal_id": "opaque-id-or-null",
  "run_id": "opaque-id-or-null",
  "incident_id": "opaque-id-or-null",
  "source_revision": "opaque-revision-or-null",
  "source_observed_at": "UTC-or-null",
  "source_verified_at": "UTC-or-null",
  "projection_refreshed_at": "controlled-clock-time-or-null",
  "source_verification": "confirmed|unverified|conflict|not_applicable",
  "availability": "available|unavailable|missing|unknown|expired|redacted",
  "retrieval": "retrieved|not_retrieved|unknown|not_applicable",
  "review_state": "not_applicable|unreviewed|pending|reviewed|disputed|superseded",
  "mutation_state": "none|write_pending|write_failed|correction_required|revoked",
  "memory_condition": "cold|memory_assisted|unknown|not_applicable",
  "summary": "bounded-sanitized-text",
  "provenance_ref": "opaque-safe-ref-or-null",
  "gaps": []
}
```

`source_verification=confirmed` means the source identity, scope, and returned
record were verified; `availability=available` means a source admission/readiness
record says the material was available; `retrieval=retrieved` means a correlated
receipt proves this Run received it. These are independent axes: a source may be
available and retrieved while its verification is `unverified`, or verified but
not retrieved. `missing`, `unknown`, `unavailable`, `expired`, and `redacted` remain
distinct. `write_pending` or `write_failed` describes a secondary Memory
operation and cannot change confirmed OPS state. `revoked` or
`correction_required` is a current overlay, not a deletion of history.
`memory_condition` is copied only from an admission record; it labels cold versus
Memory-assisted context and makes no claim about diagnosis or speed.

Zero is displayed only when the source explicitly confirms zero. Missing,
unavailable, filtered, expired, or failed retrieval displays an unknown/gap
count, never zero or an empty-success card. Counts are diagnostic counts, not
quality, accuracy, speed, or learning scores.

## Four section projections

### Incident state (OPS)

The authoritative card contains opaque Incident ID, lifecycle/status, bounded
severity/urgency, source-group/member counts, selected rehearsal/run links, and
safe OPS provenance. Ticket 37 execution state and effect state are separate
`ticket37_recovery` projections carrying their journal/receipt owner reference;
they are not `ticket35_telemetry` records, and neither is relabelled as an OPS
state or external confirmation.
It may show confirmed OPS success while draft, audit, telemetry, or Confluence
secondary work is unavailable. It does not display raw notifications, account
identity, credentials, raw errors, private audit bodies, Ground truth, or an
inferred diagnosis.

### Observations and hypotheses

Each directory item contains opaque entry/revision IDs, kind
`observation|hypothesis`, a short redacted summary, explicit
`observed|inferred|unknown` status, source class, linked Run/Incident/rehearsal,
observation and verification times, separate verification/availability/retrieval
axes, bounded evidence references, and visible gaps. A hypothesis never renders
as a confirmed cause.
Directory counts do not establish Match eligibility or diagnosis; OPS remains
authoritative.

### Postmortem drafts

Each draft card contains opaque draft/Incident IDs, origin rehearsal, operation
kind, and the mapped Ticket 43 state
(`pending|not_dispatched|confirmed|create_unknown|update_unknown_or_conflict|
human_held|status_unknown_or_bypass|revoked`). `pending` is an uncompleted
intent; all other values are deterministic projections of Ticket 43’s typed
receipt/hold states, never invented success. It also contains last confirmed
version/digest prefix, create/update receipt reference, source and verification
times, and review state. A draft remains unapproved until a human publishes a
separate approved reference. Lost or uncertain create/update work stays visible;
the view never title-adopts, recreates, or promotes a page.

### Approved references

Each reference card contains opaque manifest/entry/page references, approved
space/page identity only where the operator is authorized to inspect it, exact
approved version/digest prefix, source Incident/Report revision, reviewer
approval status, provenance, delivery/retrieval state, and current revocation or
correction overlay. Changed, archived, deleted, unverifiable, expired, or
revoked material is unavailable for current use. A pinned historical reference
does not restore approval or make it readable to a Run.

## Human review projection

The view may consume a separate operator-private, sanitized Ticket 39 review
projection. It shows only recorded status `pending|reviewed|disputed|superseded`,
an approved reviewer alias when present, qualified bounded rationale, review
time, report revision, and evidence-completeness state. It never generates a
grade, confidence, causal conclusion, or qualification decision. A disputed or
superseded review remains visible with its predecessor and superseding record;
neither replaces history. The ADR 0018 phrase “corrected” is represented by this
Ticket 39 `superseded` record plus the explicit predecessor/overlay; no second
review enum is invented. Ground truth, scoring feedback, private audit bodies,
credentials, and personal/account identity never enter cards, URLs, Run feeds,
or shared telemetry.

## Provenance inspection and safe links

Inspection opens a bounded operator-side record containing source class, opaque
record/revision IDs, scope, source and verification times, returned/available/
retrieved state, digest prefix, capture/interface class, and explicit loss or
redaction reasons. It may show a short sanitized evidence excerpt only when the
source policy permits it; raw Report, tool, API, log, trace, Confluence, or audit
bodies are never rendered. A missing source receipt, malformed response, clock
failure, or incomplete pagination is shown as a gap.

The complementary Grafana link is generated from a fixed internal route and
selected timeline reference. It carries no raw query, token, account identity,
or caller-supplied URL. Its target remains a sanitized Ticket 35 timeline; a
successful presentation refresh does not make the source evidence fresh.

## Snapshots, corrections, revocation, and replay

A presenter may pin bounded **before** and **after** snapshots. Each snapshot
stores `snapshot_id`, selected context, mode, sample time, source revision/digest
references, card/count projection, and capture time. Before shows material
verified available at admission; after shows later confirmed draft/observation
changes. A snapshot is immutable and later source updates cannot rewrite it.

Every live or replay render applies a current correction/revocation overlay after
the pinned projection. Revocation, withdrawal, correction, expiry, or unavailable
source state always dominates the pin. If the current overlay itself is
unavailable, current approval/revocation is `unknown`; the historical pin remains
historical and cannot be shown as currently approved. A pinned snapshot cannot reapprove,
re-expose, or serve withdrawn Confluence material to a Run. Historical review
survives raw-artifact expiry as `historically_reviewed_not_independently_reauditable`;
the view never claims current support from an expired audit bundle.

Replay mode remains visibly `REPLAY`, retains its recorded rehearsal/Run/sample
time, and uses the same state vocabulary. Replay data cannot masquerade as live
current work. Current revocation/correction overlays still appear, while replay
source data remains at its recorded sample time; no silent live re-query repairs
a missing historical record.

## Refresh, clocks, and failures

When available, projection refresh is attempted every five seconds. Each section
shows independent source observation time, source verification time, and
projection refresh time. A successful cache refresh does not advance source
verification time. Using a controlled monotonic clock, more than 30 seconds
without a successful section refresh marks that section `stale` and displays its
last verified time. A clock discontinuity, invalid source timestamp, or replay
clock mismatch marks freshness `unknown`/`clock_unavailable`, never fresh.

Section failure is isolated: OPS state, draft state, references, review summary,
and timeline each retain their own failure/gap. Failed optional Memory or
telemetry work cannot hide confirmed OPS success, block Incident handling, or
appear as newly learned content. A source timeout, access denial, redaction
failure, malformed record, or expired evidence remains visible as a safe status.

## Bounds, retention, and access

The audience response is capped at 512 cards total, four section arrays of at
most 128 cards each, 64 provenance references per card, 2 KiB summary/excerpt
text, 128-byte opaque IDs, and 1 MiB serialized response. Drilldowns are capped
at 16 KiB sanitized projection data, one bounded page, and 30 seconds. Generic
arrays are capped at 256 and parser depth at 8; the four section arrays use the
narrower 128-card limit. If a source exceeds a cap, the projection retains
bounded counts and an explicit `truncated` gap with scope/reason; it never
silently drops cards.
Duplicate keys, unknown fields, non-finite values, invalid UTF-8/timestamps, and
oversized records fail closed.

The presentation cache stores only sanitized projection cards, counts, gaps,
snapshot metadata, and digests; it never stores raw audit/source bodies. Its
proposed cap is 16 MiB and four snapshots total across all contexts. Each cache
item and snapshot expires 30 days after capture or at rehearsal handoff,
whichever comes first; expiry is shown as `expired` before removal. A rehearsal
switch clears active cache selection, and a handoff retains only a bounded
digest/status manifest after read-back. That manifest remains under the same
16 MiB, four-item, and 30-day bounds; it is not an archival escape. The global
cap, four-snapshot limit, and expiry apply across contexts, so contexts cannot
create unbounded retained snapshots. It cannot extend source retention or audit
access:

* Ticket 35 Run telemetry remains a 24-hour shared diagnostic feed; after expiry
  its timeline is unavailable/expired, not copied into the audience cache.
* Ticket 39 private redacted audit evidence remains subject to 100 MiB per Run,
  2 GiB total, and 30-day maximum retention; verdict history may remain labelled
  historically reviewed after raw expiry.
* Ticket 43 manifest/mapping/tombstone retention and reference revocation remain
  authoritative; the audience stores only safe status/reference joins and never
  re-exposes a withdrawn page.

Projection access is operator-authenticated and read-only, separate from Run
identity, shared telemetry, private audit storage, Confluence/Jira mutation
routes, and reviewer controls. A source permission failure yields unavailable or
held state; it never falls back to a broader credential or direct route.

## Accessibility and acceptance

Every color, icon, stale marker, review state, gap, and live/replay label has
keyboard-reachable text. A screen reader receives the section name, selected
context, source/verification times, state, count qualifier, and failure reason;
color alone never carries authority or failure. Selection, pin/unpin, and safe
inspection are the only presentation actions. Approve, publish, retry, reset,
reconcile, delete, grant, model, and network-route controls are absent.

Offline acceptance must drive the actual projection, strict parser, source joins,
snapshot store, controlled clock, refresh state machine, safe-link builder, and
keyboard-readable status projection with synthetic records. Cover mixed OPS/
Memory/draft/reference authorities; available versus retrieved; confirmed zero
versus missing; stale threshold edges; clock failure; replay; rehearsal reset;
  before/after pinning; current revocation/correction over pins; expired audit;
  pending/disputed/superseded reviews; failed draft with confirmed OPS; redaction,
private-field/URL leakage, duplicate/oversized/malformed records, and absent
receipts. Fixture success does not prove source authorization, tenant access,
Grafana freshness, human review, or presenter/venue acceptance.

## Sources and unresolved gates

* [Issue 44](../../issues/44-memory-audience-projection-and-acceptance.md),
  [ADR 0018](../../../../docs/adr/0018-audience-memory-view-preserves-source-and-review-state.md),
  and [Ticket 34 accepted constraints](../ticket-34/round-1.md).
* [Ticket 35](../ticket-35/telemetry-specification.md),
  [Ticket 32](../ticket-32/memory-specification.md),
  [Ticket 39](../ticket-39/audit-specification.md),
  [Ticket 43](../ticket-43/confluence-specification.md), and
  [Ticket 16](../ticket-16/report-proposal.md).

The concurrent Ticket 32 Memory-directory source contract, exact operator
authentication, persistence technology, source-join implementation, and native
presenter acceptance remain gates. No dashboard, UI code, screenshots, tenant
calls, model/paid/headless work, credential access, or commit is implied.
