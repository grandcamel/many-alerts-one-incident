# What the audience sees of Memory

Type: grilling
Status: resolved
Blocked by: 13

## Question

What should the audience see as Memory grows across Runs within the slot? Show enough to distinguish authoritative OPS state, cited directory learning, draft postmortems and human-reviewed Confluence guidance, without presenting a hypothesis as a proven cause or a draft as approved knowledge. Decide how missing context, incomplete secondary writes and fresh-rehearsal reset are visible. Preserve ADR 0008's Ground-truth exclusion and ADR 0009's trust boundaries. Produce the presentation contract; do not build a dashboard or run the demo.

## Accepted scoring input from ticket 24

ADR 0014 adds a sanitized human-review status for the audience: pending until reviewed, with corrections/disputes visible. Keep the operator scoring inputs and private audit bundle outside Run-readable telemetry and Memory; do not present Memory-assisted and cold-start samples as a controlled comparison.

## Accepted Confluence input from ticket 33

ADR 0017 distinguishes Run drafts from separately published human-curated references, with reviewer/source revision/version/digest provenance. Show unavailable/revoked reference context and incomplete/uncertain draft work; an approved label is not approval. Revocation-driven cancellation and review cannot be presented as rolled-back OPS work.

## Work in progress

Claimed after ticket 33 was committed. Presentation-contract planning only; no dashboard implementation, new audience access, publication, model or demo run.

[Accepted constraint evidence](../reviews/ticket-34/facts.md) identifies source authority, draft/approval/revocation states, operator-only audit separation and comparison limits. [Round 1](../reviews/ticket-34/round-1.md) records the accepted surface, cards, presentation sequence, failure states and replay controls. All five recommendations were accepted; the consistency audit found no further policy choice.

## Answer

[ADR 0018](../../../docs/adr/0018-audience-memory-view-preserves-source-and-review-state.md) accepts one operator-only read-only audience view with separate OPS state, directory observations/hypotheses, postmortem drafts and approved references. Cards retain source/revision/time and approval/verification provenance, distinguish available from retrieved context, and never present record counts as quality.

Presenter-controlled before/after snapshots preserve historical context while visibly overlaying corrections/revocations. Human review remains separate from execution and publication approval. Refresh is five-second best effort, with a section stale after 30 seconds without refresh and source timestamps retained. Explicit failures/gaps cannot hide confirmed OPS success or appear as learned content. Live/replay identity and sample time remain visible; mutation controls stay outside this view.

[Ticket 44](44-memory-audience-projection-and-acceptance.md) specifies projection/access/schema and offline acceptance. No UI, account access, publication or runtime implementation occurred.
