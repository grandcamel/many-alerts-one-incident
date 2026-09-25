# Report audit and scoring specification

Type: task
Status: open
Blocked by: 16, 24

## Question

Produce an implementation-ready specification for ADR 0014, not a scorer implementation or paid run. Define versioned per-Report JSON, immutable revision/evidence identity, lifecycle manifests, readable rendering and grades/rollups. Include supported/unsupported/unverifiable evidence, observed/inferred claims, partial early Mechanisms, final correctness, arithmetic defects, disputes and superseding adjudications. Distinguish corrected Report revisions, reviewer mistakes and clean qualification samples.

Specify operator-only capture outside Run access and Git: correlated request/returned-response and Report revision capture; source/query/time scope; event ordering, truncation/redaction and missing-record detection; credential/identity removal before persistence; private storage, access, reset/expiry and crash behavior. Enforce 100 MiB per Run, 2 GiB total and at most 30-day raw retention, with capacity/readiness preflight for qualification, explicit loss and no silent eviction of unreviewed evidence. Required OPS handling must continue if audit capture fails. Retained compact records/digests must expose expired evidence without retaining raw bodies. Keep Ground truth/scoring feedback out of Run mounts, Memory and shared telemetry; the ADR 0010 feed is not a complete audit source.

Specify deterministic checks and fixtures through real capture/parser/report interfaces: mention versus attribution; flag-only matches; supported inference; fabricated controls; attempted/failed query versus returned evidence; wrong temporal/service scope; empty versus missing response; reused legitimate prior evidence with provenance versus merely copied assertions; tampered/missing/truncated/redacted evidence; arithmetic/units/rounding; Report corrections; duplicate revisions; capture exhaustion/failure; expiry; disputed and changed-rubric adjudications. Mechanical tests demonstrate check behavior, not human diagnostic judgment or model quality.

Define the reviewer checklist, source access, disagreement resolution and append-only verdict history. Integrate ticket 38's two primary plus one fallback qualification matrix and cold/Memory conditions with current Ground truths. No sample can qualify before its Fault definition exists and is reviewed. Preserve all failures and do not silently migrate historical flag-name grades. Integrate ticket 34's audience summary without exposing scoring inputs, and ticket 35's gap/correlation interfaces without introducing a shared raw Transcript feed. Separate offline, human-review, model, billing and intended-venue acceptance; none is run under this planning task.

[Ticket 40](40-fallback-fault-ground-truth.md) supplies the fallback definition prerequisite for future samples; drafting this specification need not wait for it.

## Accepted Change input from ticket 25

ADR 0015 Change records support only their recorded action/stage. A served value or rollout cannot by itself establish application evaluation, recovery or Incident causation. Preserve query/retrieval provenance and Change-record gaps in the audit; unresolved stages, untracked interventions or material gaps exclude clean qualification even when emergency undo succeeds.

## Accepted venue input from ticket 30

ADR 0016 requires private audit artifacts and digests to be preserved off-cluster with verified read-back before destroying their only source. Export does not extend ADR 0014 retention or recreate expired evidence. Include actual presentation/recovery overrun and venue-contamination references without conflating diagnostic pass with qualification.

## Accepted Confluence input from ticket 33

ADR 0017 reference provenance includes approved page ID/version/body digest, delivered-reference identity and approval/revocation history. Capture affected-output review and revocation cancellation without treating Confluence approval as independent system evidence or retroactively erasing Report defects. Keep manifest authority outside Run-readable scoring data.

## Accepted audience input from ticket 34

ADR 0018 consumes a sanitized operator-side human-review summary (pending/reviewed/disputed with qualified rationale), not raw audit or Ground truth. Keep diagnostic review distinct from execution and curated-reference approval; no review/scoring projection enters Run-readable telemetry. Ticket 44 specifies presentation.

## Approved fallback definition from ticket 40

The human approved [adFailure's Mechanism/Trigger definition](../reviews/ticket-40/definition.md), pinned to upstream commit `1755859a9de82c2e5e225be68abc401a5ebf2b4f`. The missing-definition prerequisite is satisfied. Keep it operator/repository-only, not reference material for Runs. It describes nominal one-in-ten ad RPC rejection with frontend error propagation, not total outage; an exact observed 10-percent ratio is not required for a correct diagnosis. Source/image correspondence, retrieved claim support and corrected-rule live acceptance remain qualification gates. Historical zero matching logs do not refute the warning emitted by source.

## Specification progress, 2026-09-22

The [proposed implementation contract](../reviews/ticket-39/audit-specification.md)
now records the concrete state, persistence, integration and acceptance requirements.
Accepted ADR policy remains distinct from proposed implementation choices. See the
[cross-ticket review](../reviews/recovery-accounting-audit-integration.md).
This planning artifact is not runtime, model, billing, tenant or venue acceptance;
the ticket remains open for its unresolved inputs and final integration.

## Local content-free loss format, 2026-09-25: unit 39a

The [39a outcome](../reviews/ticket-39/outcome-39a-loss-marker.md)
adds a pure canonical codec for a bounded local capture-loss marker. It
keeps missing, truncated, redacted, transport-error and unknown states
explicit, while reserving a complete empty response for a separate future
exchange record. Independent source reviews, 21 focused tests, Ruff and the
full local suite (**5,665 passed, 39 skipped**) pass. This codec has no
writer, private storage, redaction, manifest, retention, native provenance
or human adjudication. Offline integration and every native, tenant,
provider, venue and human acceptance gate remain open; this ticket stays
open.

## Local claim-link precheck, 2026-09-25: unit 16c

The [16c outcome](../reviews/ticket-16/outcome-16c-claim-link-precheck.md)
checks bounded untrusted claim/citation IDs and states for structural defects.
It always reports `support_unverified`, even with no defects. Independent
source reviews, 27 focused tests, Ruff and the full local suite (**5,722
passed, 39 skipped**) pass. It does not capture an exchange, retain reviewed
response bytes, establish source provenance or perform human grading. The
private audit integration and external acceptance gates remain open.
