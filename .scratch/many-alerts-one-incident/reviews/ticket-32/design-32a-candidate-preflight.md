# 32a: local fresh-rehearsal candidate preflight

Status: proposed local source design, 2026-09-25. Ticket 32 stays open.
Authority: accepted ADR 0009, ticket 14's Jira-clock inclusive 30-minute
candidate window, and ticket 32's proposed paginated preflight. This is a
pure check over supplied synthetic OPS pages. It has no authenticated OPS
query, trusted Jira clock, current-member source or Run admission authority.

## Closed local input

The caller supplies exactly `current_rehearsal_id`, `jira_now`, and `pages`.
The rehearsal ID is a lowercase UUIDv4. The clock and every `created_at`
are exact UTC microsecond strings in this synthetic grammar. Pages have
exactly `snapshot_marker`, `cursor_in`, `cursor_out`, `exhausted`,
`total_count`, `elapsed_ms`, and `items`. Marker/cursors are bounded opaque
ASCII; the first `cursor_in` is null, each next `cursor_in` matches the prior
`cursor_out`, and only the final page may have `exhausted=true` with a null
out cursor. All pages share the marker and total count; the final item count
must equal it. One to ten pages, at most 100 incidents per page, at most
five seconds per page and 30 seconds total are proposed limits. Reaching a
tenth page is conservatively incomplete even if it claims exhaustion; at
most nine pages can yield a complete local finding. A missing or
conflicting page, cursor, count, marker, cap, or timing result is incomplete.
Repeated continuation cursors, including a nonadjacent cycle, are incomplete.

Each item has only `incident_id`, `status=open`, `created_at`, and
`origin_rehearsal_id` (lowercase UUIDv4 or null). IDs are bounded opaque
ASCII and unique across pages. The synthetic input has no title, labels,
Fingerprint, cascade label, Memory content, Report, candidate acceptance or
raw Jira payload. An unexpected status or future creation time relative to
the supplied Jira clock is incomplete. An eligible item has `created_at`
within `[jira_now - 30 minutes, jira_now]`, inclusive. An eligible item with
unknown origin is incomplete; one with a different origin is a prior
rehearsal candidate and holds the finding. Older items do not establish an
obligation under this window. The checker must never filter by a rehearsal
label, title, Memory provenance or cached directory state.

The result always carries `admission_status=held_unqualified`. Its finding
is `incomplete`, `prior_eligible`, or `no_prior_in_supplied_pages`, with
bounded prior Incident IDs for inspection. A syntactically invalid input
raises a fixed local shape error. Even complete supplied pages with no prior
candidate cannot grant Run/model dispatch: source authentication, query
coverage, Jira-clock origin, current OPS status and operator disposition
are outside this pure function. No automatic close or disposition occurs.

## File-by-file plan

1. Record this source-only contract and explicit no-permit boundary.
2. Add pure `grafana_jsm_sandbox/memory_candidate_preflight.py`; no
   Receiver/Run/Jira caller is installed. Verify focused syntax/lint.
3. Add `tests/test_memory_candidate_preflight.py` for inclusive boundary,
   older item, unknown origin, malformed/future item, page/cursor/marker/
   count/exhaustion gaps, duplicate IDs, timing and cardinality caps, hostile
   types and no-positive-permit output. Run focused tests.
4. Obtain independent Standards and Spec source reviews, run Ruff and
   `git diff --check`, then the full repository suite before a named local
   code commit. Update ticket 32 and the local frontier with exact results.

## Open gates

Ticket 32 still needs the exact native OPS current-member representation,
fresh paginated query with a trusted Jira clock and coverage/read-back,
conditional updates, Receiver-owned Memory append/read persistence and
identity, Confluence binding and intended-venue durability. Human
disposition of an eligible prior Incident remains human. Native, provider,
paid, tenant, venue and human acceptance are **NOT RUN**.
