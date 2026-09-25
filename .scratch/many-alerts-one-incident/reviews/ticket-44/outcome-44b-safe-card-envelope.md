# 44b outcome: untrusted structural audience card candidates

Status: local source candidate, 2026-09-25. Ticket 44 remains open.

`audience_card.py` accepts one at-most-4-KiB JSON candidate for each of the
four primary audience sections and returns canonical untrusted candidate bytes, a
digest, immutable typed fields and `authority=unqualified`. The exact field
allowlist retains separate source verification, availability and retrieval
**claims** and distinct observation, verification and refresh times. A fixed
display code replaces arbitrary source summary text in this local subset.
Incident and draft cards require an OPS Incident link. Unknown keys,
URL/path-shaped IDs, free-text fields, raw error or Ground-truth fields,
counts, duplicate keys, unsupported statuses and malformed times fail closed.
Syntactically valid opaque IDs may still encode identity or credentials; the
parser cannot certify their content or make its canonical bytes safe to render.
This subset requires a rehearsal ID, narrower than the general nullable
envelope, because it models selected-context primary cards only.

The parser does not know whether a caller is an operator, a source was
authenticated, a record was available or retrieved, a count is complete, a
reference remains approved, or any card is safe to show. It cannot emit an
audience view or Run-readable record. Recovery, telemetry and human-review
projections, approved source summaries, safe inspection, context selection,
current overlays, source-specific ID/content sanitization, source joins,
snapshot storage, accessible UI and presenter
acceptance remain separate work.

Independent Standards and Spec source reviews passed after the Incident-link,
untrusted-ID and redacted-representation fixes. Focused audience/status/parser
invariant tests: **103 passed**. Ruff and `git diff --check` passed. The full
repository suite passed: **5,805 passed, 39 skipped in 436.28 seconds**; see
[`full-suite-44b-safe-card-envelope.txt`](full-suite-44b-safe-card-envelope.txt).
The first full-suite attempt exposed the repository's single-caller
`max_string_bytes` invariant and was stopped; the override was removed and the
full suite rerun cleanly on the final code. Native, provider, paid, tenant,
venue and human
acceptance are **NOT RUN**. No source, provider, tenant, dashboard or model
operation occurred.
