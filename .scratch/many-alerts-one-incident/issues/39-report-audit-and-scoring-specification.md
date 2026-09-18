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
