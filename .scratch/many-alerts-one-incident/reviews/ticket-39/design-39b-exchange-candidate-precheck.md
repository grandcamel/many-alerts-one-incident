# 39b: content-free exchange candidate precheck

Status: proposed local source design, 2026-09-25. Ticket 39 stays open.
Authority: accepted ADR 0014, ticket 39's proposed request/response states,
and the reviewed 39a content-free loss marker. This unit examines one
caller-supplied candidate pair. It is not an `exchange-v1` capture record:
there is no selected trusted request/response hook, persisted bytes,
redaction, source scope/order or provenance.

## Closed grammar and negative findings

Input has exactly `audit_bundle_id`, `exchange_id`, `request_state`,
`response_state`, `request_loss`, and `response_loss`. IDs are exact
lowercase UUIDv4. States are the seven proposed values `returned`, `empty`,
`missing`, `truncated`, `redacted`, `transport_error`, and `unknown`.
Each loss is either null or canonical 39a `audit_loss` bytes capped at
1,024 bytes. The caller cannot supply evidence IDs, request/response
payloads, byte counts, query scope, native identity, producer labels,
recorder order or a human finding here.

For `missing|truncated|redacted|transport_error|unknown`, a matching 39a
loss marker is required on that side. It must have the same bundle/exchange
IDs, side and state. For `returned` and `empty`, a loss marker is
unexpected. `empty` is explicit caller assertion of a complete observed
zero-payload response, not inferred from null or absent bytes. Malformed,
noncanonical, duplicate-key or oversized loss bytes fail with a fixed local
error; well-shaped but missing, extra or mismatched markers, or request and
response markers reusing one `loss_id`, produce sorted
fixed defect codes. There is no automatic state repair or later re-query.

Every result, including one with no defects, carries
`capture_unverified`. A `returned` state here is self-asserted and cannot
support a citation. This precheck cannot assert a complete audit exchange,
source identity, retained response content, redaction adequacy, human grade,
qualification, Jira permission or Run admission.

## File-by-file plan

1. Record this source-only restricted contract before code changes.
2. Add pure `grafana_jsm_sandbox/audit_exchange_candidate.py`, consuming
   canonical 39a loss bytes. No capture hook, store or Run caller is added.
3. Add `tests/test_audit_exchange_candidate.py` for all seven state forms,
   explicit empty versus missing, absent/extra/wrong-side/wrong-ID/state
   markers, duplicate loss identity, malformed/duplicate-key/noncanonical/oversize bytes, hostile
   Python values and unconditional unverified output. Run focused tests.
4. Obtain independent Standards and Spec reviews, run Ruff and `git diff
   --check`, then the full repository suite before a named local code
   commit. Update ticket 39 and the local frontier with exact outcomes.

## Open gates

The actual `exchange-v1` writer, correlation and source identity,
redaction, response bodies, private storage, quota/retention/handoff and
human review remain open. Native, provider, paid, tenant, venue and human
acceptance are **NOT RUN**.
