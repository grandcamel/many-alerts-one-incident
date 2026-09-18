# What the audience sees of Memory

Type: grilling
Status: open
Blocked by: 13

## Question

What should the audience see as Memory grows across Runs within the slot? Show enough to distinguish authoritative OPS state, cited directory learning, draft postmortems and human-reviewed Confluence guidance, without presenting a hypothesis as a proven cause or a draft as approved knowledge. Decide how missing context, incomplete secondary writes and fresh-rehearsal reset are visible. Preserve ADR 0008's Ground-truth exclusion and ADR 0009's trust boundaries. Produce the presentation contract; do not build a dashboard or run the demo.

## Accepted scoring input from ticket 24

ADR 0014 adds a sanitized human-review status for the audience: pending until reviewed, with corrections/disputes visible. Keep the operator scoring inputs and private audit bundle outside Run-readable telemetry and Memory; do not present Memory-assisted and cold-start samples as a controlled comparison.
