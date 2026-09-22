# Ticket 39 audit, Report review, and qualification specification

**Status:** proposed implementation specification, 2026-09-22. This file defines
the storage and review contract for ADR 0014. It does not implement a scorer,
collector, report writer, retention service, or human adjudication workflow. It
authorizes no model Run, paid review, credential use, tenant operation, upload,
publication, or intended-venue acceptance.

The contract has two kinds of statements. “Settled” repeats an accepted ADR or
ticket decision and may not be weakened by an implementation. “Proposed” fixes
names and serialization choices for implementation coordination; those choices
may be changed before implementation only by recording a new specification
revision and preserving the old one. A proposed name is not evidence that a
runtime interface exists.

## Authority and settled inputs

| Settled source | Requirement consumed here |
| --- | --- |
| [ADR 0014](../../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md) and [ticket 24](../../issues/24-scoring-a-report-against-ground-truth.md) | Score the Mechanism rather than Trigger-name presence. Deterministic checks are prechecks; a named human decides causal attribution, claim support, and the final verdict. Use separate Mechanism, evidence, and arithmetic grades. Preserve revisions, defects, disputes, and rubric history. |
| [ADR 0018](../../../../docs/adr/0018-audience-memory-view-preserves-source-and-review-state.md) | Audience summaries are sanitized operator projections. They never expose raw audit bodies, Ground truth, scoring feedback, credentials, or account identity to Runs or shared telemetry. Pending, reviewed, disputed, stale, unavailable, and expired remain distinct. |
| [ADR 0010](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md) and [ticket 35](../../issues/35-run-telemetry-integration-and-acceptance.md) | The shared 24-hour sanitized feed is diagnostic and best effort, not a complete citation audit. Audit references may cross-link to it, but raw audit bodies and adjudication material never enter it. |
| [ticket 38](../../issues/38-budget-accounting-and-model-qualification.md) | Qualification uses two primary and one designated-fallback lifecycle per candidate, including cold and Memory-assisted conditions. Each lifecycle independently links initial Report, supported match/update, and final resolution; accounting must join reservation R, defensible U, complete provider coverage, reconciled final charge sum, and hold status. Failed or unverifiable samples do not qualify. Audit completeness is a prerequisite that budget/accounting consumes by reference. |
| [ticket 40](../../issues/40-fallback-fault-ground-truth.md) | `adFailure` is the approved fallback definition, pinned to commit `1755859a9de82c2e5e225be68abc401a5ebf2b4f`. It is repository/operator-only and never Run-readable. |
| [ADR 0015](../../../../docs/adr/0015-changes-record-operator-actions-and-observed-stages.md) | Change records support only their recorded stage. Unresolved stages, untracked intervention, or material Change gaps exclude a clean qualification lifecycle. |
| [ADR 0016](../../../../docs/adr/0016-venue-lifetime-is-bounded-with-protected-teardown.md) | Private audit artifacts and digests are read back off-cluster before the only source is destroyed. Venue overrun and contamination remain separate evidence. |
| [ADR 0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md) | Reference page/version/body identity and approval/revocation provenance are captured as references, not treated as independent causal evidence. |

The approved ticket-23 synthetic rubric remains historical fixture input. Its
approval receipt says `APPROVED_FOR_PINNED_SYNTHETIC_FIXTURE`, excludes Report
adjudication and qualification, and pins the original rubric and fixture
digests. A future Report series must cite that approval or a later frozen rubric
identity; it must never silently reuse historical flag-name grades as Mechanism
qualification.

## Identity, immutability, and canonical bytes

The following are proposed opaque identifiers. They are lowercase UUIDv4 strings
unless an owning interface already has a stable identifier. An identifier is a
logical identity, not a digest and not a credential. No identifier is reused for
a different object.

| Identifier | Meaning and owner |
| --- | --- |
| `audit_bundle_id` | One private operator-owned capture bundle for one Run or bounded capture attempt. The capture service allocates it before the first record; a lifecycle may join several bundles. |
| `series_id` | One frozen rubric/model comparison series. A rubric change starts a new series unless all retained evidence is explicitly re-adjudicated. |
| `candidate_id` | Stable comparison candidate label, paired with recorded model/auth/venue evidence. It is not a provider credential or a claim of availability. |
| `lifecycle_id` | One Fault lifecycle under one candidate and series. It joins Reports, capture, execution/effect/time/spend references, and the lifecycle rollup. |
| `report_id` | Logical Report across its initial and corrected revisions. |
| `report_revision_id` | One immutable Report revision. A correction appends a new revision linked by `supersedes_revision_id`; it never edits the prior object. |
| `exchange_id` | One attempted tool/query request and its returned response or explicitly recorded absence. |
| `evidence_id` | One persisted sanitized evidence item or loss marker. |
| `adjudication_id` | One human or mechanical review record for one target revision/lifecycle. Verdicts are append-only. |
| `artifact_ref` | Path-independent `{artifact_id, content_sha256, bytes, source_class}` reference. It identifies retained bytes while making no claim that a deleted artifact still supports a claim. |

`run_id`, `attempt_id`, `reservation_id`, `operation_id`, and `intent_id` are
external owner fields. They remain stable across their own journal/ledger
interfaces and are copied only where needed for joining. The audit bundle does
not absorb the recovery journal or budget ledger. A missing join is an explicit
gap, not a generated substitute.

Every persisted JSON object uses UTF-8, sorted object keys, no insignificant
whitespace, and a schema version. Money is referenced from ticket 38; any
necessary checked copy uses its signed integer USD microdollars;
timestamps are UTC RFC 3339 with an explicit offset; byte counts and token
counts are nonnegative integers. `content_sha256` and `canonical_bytes` are
envelope fields: both are excluded from the canonical payload being hashed, then
the digest and byte count are written into the envelope. A duplicate identity
with the same digest is idempotent; the
same identity with a different digest is a tamper/conflict hold. Digests do not
make an expired or missing artifact independently auditable.

The private bundle manifest is append-only. Each record contains its predecessor
digest and canonical byte length; the manifest records the final chain digest,
record count, byte accounting, loss count, and retention expiry. A chain gap,
duplicate ordinal, invalid predecessor, or digest mismatch makes the affected
bundle incomplete. This chain detects integrity changes relative to a separately
trusted anchored root; it does not establish provider identity, native stream
provenance, causal truth, or billing. A hash
stored beside an editable local bundle does not authenticate that bundle.

The lifecycle-to-bundle mapping is append-only and records the `run_id` and
capture purpose for every joined `audit_bundle_id`; it never merges unrelated
source records merely because they share a candidate or Fault.

## Report revision record

The persisted `report-revision-v1` object has this shape. Fields marked required
are required even when their value is an explicit `unknown`/`unverifiable`
state; omission is malformed.

```json
{
  "schema_version": 1,
  "record_kind": "report_revision",
  "report_id": "uuid",
  "report_revision_id": "uuid",
  "supersedes_revision_id": null,
  "lifecycle_id": "uuid",
  "audit_bundle_ids": ["uuid"],
  "run_id": "opaque-run-id",
  "attempt_id": "opaque-attempt-id",
  "fault_id": "payment-cache",
  "incident_id": "opaque-incident-id",
  "report_kind": "initial",
  "revision_ordinal": 1,
  "submitted_at": "2026-09-22T12:00:00Z",
  "condition": {
    "candidate_id": "candidate-a",
    "model_id": "recorded-model-label-or-unknown",
    "auth_mode": "metered_api|subscription|replay|unknown",
    "venue_id": "recorded-venue-or-unknown",
    "memory_mode": "cold|assisted|unknown"
  },
  "source": {
    "interface": "captured_report_response|operator_import|replay_fixture",
    "source_artifact": {"artifact_id": "uuid", "content_sha256": "sha256"},
    "redaction_policy_id": "redaction-v1",
    "loss": []
  },
  "content": {
    "mechanism_text": "redacted reviewed Report text",
    "observations": [],
    "causal_claims": [],
    "evidence_bullets": [],
    "arithmetic_assertions": [],
    "uncertainties": []
  },
  "completeness": {
    "status": "complete|partial|missing|redacted|truncated|unknown",
    "missing_fields": [],
    "evidence_refs_complete": true
  },
  "content_sha256": "sha256-of-canonical-redacted-record-without-envelope-fields",
  "canonical_bytes": 0
}
```

The `content` text is the exact reviewed **redacted** revision. The unredacted
source is never persisted. If redaction changes a claim or removes the text
needed to review it, `source.loss` and `completeness` say so and the affected
claim is `unverifiable`; a digest of a discarded source is not a substitute for
the missing evidence.

Each observation, causal claim, and evidence bullet has a stable local `claim_id`,
redacted text, `claim_kind`, `observed_or_inferred`, `scope`, and zero or more
`evidence_refs`. `observed` requires a supporting returned response or approved
system observation. `inferred` must identify the observations from which the
inference was made and remain visibly labelled. A flag, component, Change ID,
or retrieved page by itself is not a Mechanism grade.

An arithmetic assertion stores decimal operands, units, operation, displayed
result, reproducible result, stated precision/tolerance, and the precheck result.
Missing operands are `unverifiable`; incorrect displayed arithmetic is a defect
even when it does not change the Mechanism. Rounding is accepted only when the
Report states units and precision and the reviewer accepts the stated tolerance.

The JSON examples in this document are schematic field illustrations, not
complete valid instances. Implementations reject an unknown schema version,
unknown field or enum, duplicate JSON key, duplicate identity/ordinal, missing
required field, non-finite number, invalid UTF-8/timestamp, excessive nesting,
or a value beyond its pinned string/array/object bound.

## Correlated capture and provenance

The capture adapter accepts records only through the real request/response and
Report interfaces selected for the implementation. Direct construction of a
passing object is not an acceptance test. It must preserve source correlation
without claiming native authenticity that the interface does not provide.

Each `exchange-v1` record contains:

```json
{
  "schema_version": 1,
  "record_kind": "exchange",
  "exchange_id": "uuid",
  "audit_bundle_id": "uuid",
  "run_id": "opaque-run-id",
  "source": {
    "interface": "native_capture|forwarder_receipt|query_result|fixture",
    "producer_id": "sanitized-producer-label",
    "source_sequence": 17,
    "observed_at": "2026-09-22T12:00:00Z",
    "ingested_at": "2026-09-22T12:00:00Z",
    "query_scope": {"rehearsal_id": "uuid", "service": "grafana", "time_start": "...", "time_end": "..."}
  },
  "request": {"state": "returned", "evidence_id": "uuid", "bytes_observed": 120, "bytes_persisted": 93},
  "response": {"state": "returned", "evidence_id": "uuid", "bytes_observed": 512, "bytes_persisted": 401},
  "correlation": {"native_id": "opaque-or-null", "capture_link_id": "uuid", "confidence": "explicit|local_association|unknown"},
  "loss": [],
  "content_sha256": "sha256-of-canonical-record-without-envelope-fields"
}
```

`source_sequence` and a recorder `ordinal` establish observed order. Wall-clock
or ingestion time alone never establishes causal order. A native/session ID is
copied only when the source emitted it; the recorder may create a
`capture_link_id` for its own association, but must not present it as native
identity. One response linked to multiple requests, a duplicate response, a
missing sequence, or a conflicting native ID is a visible correlation gap and
cannot support a clean citation audit.

The request and response states are closed values:

| State | Meaning |
| --- | --- |
| `returned` | A complete source record was observed and persisted after redaction. |
| `empty` | A complete source record was observed with zero payload bytes. This is not `missing`. |
| `missing` | No source record was observed for the expected exchange. |
| `truncated` | Capture ended before the source record was complete. |
| `redacted` | Capture completed but required content was removed before persistence. |
| `transport_error` | The interface reported a transport failure; delivery/effect remains distinct. |
| `unknown` | The available evidence cannot distinguish the other states. |

Every non-`returned` state carries a bounded loss code, source, observed time if
available, and whether the gap was detected before or after persistence. Empty
and missing response cases are separate fixtures. A later query cannot silently
replace the response that the Run saw; it is a new source record with its own
provenance.

## Redaction before persistence

The capture boundary receives bytes transiently, applies a pinned redaction
policy, and persists only the redacted canonical body or a compact loss record.
Credentials, API keys, bearer values, sentinels, cookies, authorization headers,
account identity, personal identity, private paths, raw prompts, raw commands,
and unfiltered tool bodies are prohibited from persisted audit records. The
redactor fails closed if the policy is unavailable or cannot classify a field;
it does not retain a raw fallback for operator convenience.

Each redaction record includes `redaction_policy_id`, policy digest, field/path
classes removed, original and persisted byte counts, and `support_lost` boolean.
It never includes the removed value. If a removed value was needed to establish
a claim, that claim is `unverifiable`. Redaction warnings must go to bounded
operator diagnostics, not to shared telemetry with the removed value.

The shared ADR 0010 feed may receive only its own allowlisted projection and a
sanitized `audit_bundle_id`/`evidence_id` gap reference. It is never used as a
complete response source and never carries adjudication rationale or Ground
truth.

## Storage, limits, crash, access, and expiry

The audit bundle is operator-owned and off-cluster, outside Run mounts, the
Memory directory, shared telemetry storage, and Git. A proposed local layout is
one private root per host with mode `0700`, separate capture-writer and reviewer
principals, and an access log containing actor class, bundle ID, operation,
timestamp, and outcome. The access log contains no credentials or raw bodies.
The implementation must document the actual OS/storage control; a directory
mode in a source fixture is not proof of production isolation.

The settled ADR quota is on **stored redacted audit evidence**, not an
unbounded source-input allowance:

- At most **100 MiB per Run** of retained redacted evidence and framing.
- At most **2 GiB total** of retained redacted evidence across active and
  retained bundles. The writer reserves stored capacity atomically.
- Each retained evidence artifact expires at most **30 days after that
  artifact's capture time**. Bundle close, a later record, or export cannot
  extend the oldest artifact. A shorter explicit expiry is allowed.

The implementation must separately propose an ingress/processed-byte budget to
bound transient offered input before redaction; that proposal does not replace
the settled stored-byte caps. Unredacted input may exist only transiently in
the recorder process while sanitizing. No unredacted body may reach disk, a
crash dump, a log, a retry spool, or a fallback artifact. “Raw” in accounting
means bounded source input and the retained sanitized evidence category, never
an unredacted persistence stage.

Metadata, loss markers, verdict records, and artifact digests have a separate
bounded allocation included in the aggregate 2 GiB limit and, for Run-attributed
records, its 100 MiB limit. Proposed metadata sublimits are 64 MiB globally,
1,024 loss records and 1 MiB of loss metadata per bundle, and 8 MiB per lifecycle;
implementers must pin or revise these values before acceptance. A reserved
terminal `loss_overflow` record replaces individual details after either count
or byte saturation and carries counts, first/last timestamps, and affected
identities. It must be emitted at most once, never evicted, and makes the
affected bundle incomplete. A capacity failure stops accepting affected
evidence, returns a capture-gap result, and never silently evicts unreviewed
evidence, grows without bound, retries indefinitely, or blocks required OPS.
Affected claims/lifecycles become `unverifiable`/excluded.

Before a qualification attempt, preflight checks writable private storage,
redactor readiness, quota reservation, retention clock, append/read-back, and
crash-recovery state. A missing or stale preflight is a hold, not a best effort
pass. Capture failure after OPS work has begun must not prevent safe recovery;
the gap remains part of the lifecycle record.

Appends use a crash-safe temporary record plus fsync/atomic rename or an
equivalent verified mechanism. The manifest chain and expected source sequence
are read back after each bounded closeout. A torn record, missing sequence,
duplicate ordinal, or manifest mismatch marks the bundle incomplete. Restart
does not re-query to fill the gap, claim zero loss, or create a new bundle with
the old identity. It preserves the loss and holds qualification until an
operator explicitly disposes of the affected sample.

Before venue destruction or cluster reset, export/copy the private bundle and
compact manifest off-cluster, read it back, and compare byte counts and digests.
Destroying the only source before a verified read-back is a capture failure and
must be recorded. Export does not extend retention, publish the bundle, or make
expired evidence recoverable.

At artifact expiry, delete retained redacted bodies and mark compact records
`raw_expired_at`. Retain verdict history, identities, grades, rationale, loss
state, and artifact digests only as allowed by the compact-record policy. A
verdict whose supporting raw bundle expired is labelled
`historically_reviewed_not_independently_reauditable`; an already approved
historical review/qualification is not retroactively invalidated, but a new
qualification or independent re-adjudication is held until supporting evidence
is available. Never retain a credential merely because it was in a body
scheduled for expiry.

## Human adjudication records

Mechanical checks produce `precheck-v1` records only. A precheck may identify
schema, identity, link, arithmetic, scope, provenance, redaction, duplicate,
tamper, or completeness defects. It may not assign a semantic Mechanism pass,
award an evidence-supported grade, or qualify a candidate.

An `adjudication-v1` record contains:

```json
{
  "schema_version": 1,
  "record_kind": "adjudication",
  "adjudication_id": "uuid",
  "target_kind": "report_revision|lifecycle|qualification_set",
  "target_id": "uuid",
  "series_id": "uuid",
  "rubric_id": "artifact-ref",
  "reviewer": {"reviewer_id": "private-human-id", "display_alias": "operator-alias"},
  "reviewed_at": "2026-09-22T12:00:00Z",
  "mechanism_grade": "correct|partial|wrong|undetermined|null",
  "evidence_grade": "supported|unsupported|unverifiable|null",
  "arithmetic_grade": "correct|defective|unverifiable|null",
  "claim_findings": [{"claim_id": "uuid", "grade": "supported|unsupported|unverifiable", "rationale": "..."}],
  "defects": [],
  "status": "pending|reviewed|disputed|superseded",
  "supersedes_adjudication_id": null,
  "rationale": "redacted reviewer rationale",
  "content_sha256": "sha256-of-canonical-record-without-envelope-fields",
  "canonical_bytes": 0
}
```

The private reviewer registry may retain a reviewer identifier for
accountability; that registry is an access-controlled review record distinct
from account or personal identity captured in evidence. Audience summaries use
only the approved alias and status. One named human may review an ordinary sample. A
causal or evidence dispute requires a second named human; both rationales and
the unresolved `disputed` status remain until a dated superseding adjudication
reconciles them. A reviewer-error correction is a new adjudication and does not
edit the Report revision or pretend that an earlier reviewer verdict never
existed.

The checklist must examine every Report revision: observation support,
mention-versus-attribution, flag-only claims, retrieved evidence and scope,
observed versus inferred labels, fabricated controls, arithmetic, Change gaps,
reference identity/version, capture completeness, and earlier defects. It must
also record whether the approved Fault Mechanism/Trigger definition was present
before qualification. Ground truth and scoring feedback remain operator-only.

## Lifecycle and qualification rollups

The `lifecycle-manifest-v1` joins immutable revisions and adjudications without
embedding raw bodies:

```json
{
  "schema_version": 1,
  "record_kind": "lifecycle_manifest",
  "lifecycle_id": "uuid",
  "series_id": "uuid",
  "candidate_id": "candidate-a",
  "fault_id": "payment-cache",
  "role": "primary|fallback",
  "ground_truth": {"artifact_id": "uuid", "content_sha256": "sha256", "review_status": "approved"},
  "run_ids": ["opaque-run-id"],
  "report_revision_ids": ["uuid"],
  "adjudication_ids": ["uuid"],
  "audit_bundle_ids": ["uuid"],
  "stage_refs": {
    "initial_report": {"report_revision_ids": ["uuid"], "status": "complete"},
    "supported_match_update": {"report_revision_ids": ["uuid"], "status": "complete"},
    "final_resolution": {"report_revision_ids": ["uuid"], "status": "complete"}
  },
  "accounting_summary_ref": {
    "summary_id": "ticket-38-summary-id",
    "reservation_ref": "ticket-38-R",
    "defensible_upper_bound_ref": "ticket-38-U",
    "provider_coverage_ref": "ticket-38-coverage",
    "final_charge_sum_ref": "ticket-38-final-sum",
    "hold_status": "clear|hold|unknown"
  },
  "condition": {"memory_mode": "cold|assisted|unknown", "model_id": "...", "auth_mode": "...", "venue_id": "..."},
  "execution_effect_time_spend_refs": [],
  "change_refs": [],
  "reference_refs": [],
  "capture_status": "complete|gap|expired|missing|unknown",
  "rollup_status": "pending|passed|failed|incomplete|disputed|excluded",
  "rollup_reasons": [],
  "content_sha256": "sha256-of-canonical-record-without-envelope-fields"
}
```

The lifecycle may span multiple Runs and capture bundles; the arrays and stage
map are joins, not permission to merge unrelated source records. Each
bundle-to-Run mapping is retained in the manifest. The three stage keys are
required exactly once, with bounded arrays retaining every associated revision
and its Run/bundle join, not just a favorable selected update. Missing, duplicate,
unsupported, or unlinked initial,
match/update, or resolution evidence excludes qualification. Money remains
owned by ticket 38 and is referenced by ledger identity; if a copy is
unavoidable it uses ticket 38's integer-micros representation and is checked
against that ledger. A clean accounting summary requires reservation `R`, a
defensible upper bound `U`, complete provider coverage, a reconciled sum of
every charge line, and `hold_status=clear`; generic provider actual/estimate
fields are insufficient.

A clean diagnostic lifecycle pass requires all of the following:

1. The Fault's repository-only Mechanism/Trigger definition existed and was
   human reviewed before the lifecycle was qualified. `adFailure` uses the
   approved ticket-40 definition; the definition is not supplied to the Run.
2. Every asserted observation and causal claim in every revision is supported
   by correlated retrieved evidence or is a clearly labelled supported
   inference. A fabricated control, unsupported causal claim, or confidently
   wrong causal assertion fails the lifecycle even if the final Mechanism is
   correct. Missing, expired, redacted, truncated, or contradictory support is
   `unverifiable`, never proof that the claim was fabricated.
3. A human has reviewed every revision. The final revision has Mechanism
   `correct`, evidence `supported`, and arithmetic `correct`. Early partial or
   undetermined Mechanisms are allowed while investigation proceeds, but their
   assertions remain subject to the support rule.
4. There is no unresolved capture gap, Change stage/intervention gap, source or
   reference identity conflict, venue contamination, incomplete recovery state,
   or disputed adjudication that affects the lifecycle.
5. Execution, external effects, timing, spend, billing, and mediated-client
   readiness each have their own references and accepted status. A diagnostic
   grade never substitutes for those gates.
6. The stage map contains exactly one supported initial Report, match/update,
   and final resolution link, and ticket-38 accounting resolves R/U, complete
   provider coverage, every charge line, and hold status. Missing or duplicate
   stage/accounting evidence excludes the lifecycle.

A corrected final revision can be reviewed and receive its own revision verdict,
but it cannot erase an earlier fabricated observation, unsupported/confidently
wrong causal assertion, or arithmetic defect from the lifecycle history. Such a
lifecycle cannot be a clean qualification sample even when the correction is
good. The original and corrected records remain visible.

Qualification is a set-level rollup, never an average. For one candidate and one
frozen `series_id`, the set contains exactly two primary-Fault lifecycles and
one approved `adFailure` fallback lifecycle, with the recorded set containing at
least one cold and one Memory-assisted condition. All three must be clean,
complete, human-reviewed passes and satisfy the separate execution/effect/time/
spend/venue/client gates. Any failed, unverifiable, incomplete, disputed, or
excluded lifecycle prevents the set from qualifying. A replacement consumes an
existing allocation or a later approved week; it does not delete or replace the
failed record. The result says only what the demonstrated candidate/auth/venue/
Fault scope supports and never claims a success rate or globally cheapest model.

## Deterministic offline acceptance matrix

Tests must drive the actual capture, parser, Report persistence, and rollup
interfaces with bounded synthetic inputs. They must assert records and statuses,
not semantic human grades. Human review, model quality, provider billing,
tenant/RBAC, and intended-venue acceptance remain `NOT RUN` in this planning
task.

| Case family | Required cases and expected contract |
| --- | --- |
| Identity and append-only state | Valid first revision; duplicate same identity/digest is idempotent; conflicting duplicate is held; correction appends and links; missing predecessor, cycle, reordered ordinal, digest mismatch, and malformed identity fail closed. |
| Correlation | One request/response; explicit native ID; recorder-only link; response before request; duplicate response; missing request; missing response; empty response; wrong Run/Fault/service/time scope; delayed response; attempted query with transport failure; returned error; later re-query with distinct provenance. Gaps remain visible. |
| Redaction | Authorization/API key/cookie/sentinel/account identity/private path/raw prompt/raw tool body in every supported location; redaction policy missing; redactor failure; required support removed. Persist no raw fallback and mark affected claims unverifiable. |
| Provenance and claims | Mention versus attribution; flag-only match; approved supported inference; fabricated control; copied assertion without retrieval; reused legitimate prior evidence with provenance; source revision/body digest mismatch; unapproved Ground truth/reference. Prechecks flag; only human records grades. |
| Scope and completeness | Wrong temporal/service/rehearsal scope; missing query result; empty versus missing; truncated response; malformed JSON; interleaved or tampered capture; non-JSON error; unknown source identity; native stream versus sanitized feed confusion. A later query cannot repair the original exchange. |
| Arithmetic | Correct duration/count/rate; wrong units; 52 versus 54 minute defect; accepted stated rounding; missing operand; overflow/negative/nonfinite value. Defects remain attached to the revision and lifecycle. |
| Capture limits | Exactly per-Run 100 MiB boundary; one byte over; aggregate 2 GiB boundary; concurrent reservations; metadata cannot bypass raw accounting; capture exhaustion/failure; no silent eviction; OPS continuation with visible gap. |
| Crash/access/retention | Torn append; crash before/after manifest update; restart sequence gap; verified off-cluster read-back; inaccessible private root; Run/Memory/shared-feed access denied; expiry deletion; verdict retained but raw re-audit unavailable; reset does not erase an unresolved bundle. |
| Review history | Pending until human review; ordinary review; dispute requiring second reviewer; both rationales retained; superseding adjudication; reviewer-error correction; changed rubric starts a new series or explicit re-adjudication. |
| Qualification rollup | Primary/fallback role, approved ticket-40 ground truth, cold/Memory coverage, failed/unverifiable sample, corrected Report, unresolved Change/venue/effect/billing gate, and replacement allocation. No averaging or historical flag-grade migration. |

Fixtures must include expected record digests and loss codes but must not include
credentials, account identity, adjudication Ground truth in Run-readable input,
or a pre-awarded semantic verdict. A fixture that says “pass” tests serialization
only; it cannot be presented as a human grade.

## Interface seams and ownership

The audit adapter is a separate operator boundary. It joins to, but does not
own, the following interfaces:

- **Ticket 37/recovery:** the recovery journal durably records admission before
  acknowledgement and mutation intent before Forwarder dispatch; restart holds
  dispatch and invalidates sentinels. It may reference `audit_bundle_id`,
  `evidence_id`, `attempt_id`, `operation_id`, or `intent_id`, but it does not
  embed Report bodies, raw audit responses, Ground truth, or adjudication
  rationale. Unknown effects remain recovery state, not a diagnostic grade.
- **Ticket 38/budget:** the budget ledger joins by candidate/lifecycle,
  `attempt_id`, `reservation_id`, provider actual/estimate/reservation evidence,
  and audit completeness status. The qualification summary must expose `R`,
  defensible `U`, complete provider-coverage identity, reconciled final-charge
  sum, and hold status; generic actual/estimate fields do not settle it. It
  retains reservations and unknown exposure, does not copy raw audit bodies or
  infer remaining money from a missing bundle, and owns integer-micros money
  values. A missing/expired audit bundle blocks qualification, not necessarily
  safe OPS or ledger reconciliation.
- **Ticket 35/telemetry:** the shared feed receives only sanitized event IDs,
  source class, gap status, and safe evidence references. It is not a raw
  Transcript, capture bundle, or adjudication channel. Delivery loss remains
  visible and cannot be filled by re-querying.
- **Ticket 41/Change and ticket 43/Confluence:** store stable Change IDs/stage
  refs and approved page/version/body-digest refs with their gaps. Neither a
  Change stage nor a curated reference supplies Mechanism truth automatically.
- **Ticket 42/venue:** store venue identity, readiness, overrun, contamination,
  teardown, and off-cluster handoff refs. A private audit export must be read
  back before destroying its only source.
- **Ticket 44/audience:** render only compact sanitized status, provenance,
  gaps, reviewer status, and a qualified rationale summary. Do not render raw
  evidence, Ground truth, reviewer feedback, account identity, or credentials.

No interface may acknowledge a clean qualification result merely because an
`audit_bundle_id` exists. The bundle's capture, redaction, completeness,
review, and retention state must be read back by identity and digest.

## Acceptance boundaries and remaining gaps

This specification is source/planning evidence only. Offline schema and fixture
tests, private human review, model execution, provider billing, tenant/RBAC,
native client compatibility, intended venue, protected teardown, and publication
are separate evidence categories. None can be promoted into another category.

The settled policy leaves these implementation choices proposed: the exact
private storage engine, redaction engine and rule language, UUID versus another
opaque ID generator, filesystem ACL/encryption mechanism, manifest-chain format,
operator access workflow, and machine-readable loss-code registry. Implementers
must choose and pin each before acceptance; they may not weaken the settled
privacy, append-only, quota, expiry, human-review, or qualification predicates.

No scorer or model judge is specified here. A later implementation must first
pass the offline matrix and independent source review, then obtain separately
authorized human/interface and intended-venue evidence. Until then, lifecycle
and candidate statuses remain `NOT_ASSESSED`.

## Sources and coordination

- [Ticket 39](../../issues/39-report-audit-and-scoring-specification.md)
- [Ticket 24 accepted rounds](../../reviews/ticket-24/round-1.md) and [round 2](../../reviews/ticket-24/round-2.md)
- [Ticket 40 approved definition](../../reviews/ticket-40/definition.md)
- [ADR 0014](../../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md)
- [ADR 0018](../../../../docs/adr/0018-audience-memory-view-preserves-source-and-review-state.md)
- [ADR 0010](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md)
- [ADR 0015](../../../../docs/adr/0015-changes-record-operator-actions-and-observed-stages.md)
- [ADR 0016](../../../../docs/adr/0016-venue-lifetime-is-bounded-with-protected-teardown.md)
- [ADR 0017](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md)
- [Ticket 23 approved synthetic rubric](../../reviews/ticket-23/timing-draft/operator/rubric-approval.json)

The recovery and accounting contracts consume only the explicit IDs, statuses,
loss codes and references above. Root integrated the separately authored drafts
and independent internal review; see the [integration record](../recovery-accounting-audit-integration.md).
No implementation assumptions are represented as accepted runtime evidence.
