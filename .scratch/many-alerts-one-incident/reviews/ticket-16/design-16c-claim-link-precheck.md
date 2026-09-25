# 16c: content-free Report claim-link precheck

Status: proposed local source design, 2026-09-25. Tickets 16 and 39 stay
open. Authority: accepted ADR 0014, ticket 16's proposed claim/citation
fields, and ticket 39's proposed exchange states. This is a deterministic
precheck over caller-supplied, untrusted stubs. It cannot decide whether a
retrieved response supported a claim or grade a Report.

## Closed input and output

The precheck accepts a dict with exactly `claims` and `citations`, both
lists/tuples. At most 64 claim stubs and 128 citation stubs are accepted. A
claim stub has only `claim_id`, `observed_or_inferred`, `status`,
`evidence_refs`, and `derived_from`. A citation stub has only `citation_id`,
`exchange_id`, `provenance`, `source_interface`, and
`observation_status`. IDs are exact lowercase UUIDv4, except an
`exchange_id` may be null to preserve missing correlation. Each claim has at
most 128 citation references and 64 derivation references; IDs are bounded
by their UUID grammar. No claim prose, query, response, credential, account,
prompt, tool body, source scope or private audit body enters this checker.

Closed claim enums are `observed|inferred` and
`asserted|unreviewed|unknown`. Citation enum claims are
`native_returned|local_association|unknown` provenance;
`native_capture|forwarder_receipt|query_result|fixture|unknown`
source interface; and `returned|empty|missing|truncated|redacted|
transport_error|unknown` observation status. These are untrusted labels,
not a source-attested receipt. Invalid shape/type/enum/ID/cap produces a
fixed error before any result.

For well-shaped stubs, the checker returns an immutable, sorted set of
fixed structural defect codes and **always** `support_unverified`. The
defects cover duplicate claim/citation IDs, duplicate references,
dangling citation/derivation references, observed claims with derivations,
asserted observed claims lacking a citation, inferred claims without an
observed source claim or citing a nonobserved source claim, native provenance
claimed through a nonnative interface, and `returned` without an exchange
ID. Multiple claims may cite one citation, and multiple citations may refer
to one exchange; this stub checker has no exchange records with which to
decide correlation ambiguity. An inferred claim must name an observed claim in the
same bounded input; array ordering is not wall-clock or causal proof.
No missing reference is silently repaired by later queries.

Even zero defects is only local structural consistency. It is never
`supported`, `complete`, an ADR 0014 grade, a clean lifecycle, a Jira
permit, or a qualification signal. Native provenance, actual return state,
source scope, observation content, redaction completeness, and semantic
support require ticket 39's trusted capture writer, retained exact reviewed
response, and human adjudication.

## File-by-file plan

1. Record this restricted source-only contract before implementation.
2. Add pure `grafana_jsm_sandbox/report_links.py` with fixed input grammar,
   bounded iteration, defect codes, and unconditional unverified result.
3. Add `tests/test_report_links.py` for empty/consistent inputs,
   duplicate/dangling links and shared exchanges, observed/inferred constraints,
   fixture/native mismatch, returned-without-exchange, hostile values,
   limits, and content-field rejection. Run focused tests and Ruff.
4. Obtain independent Standards and Spec source reviews; run `git diff
   --check` and the full repository suite before a named local code commit.
   Record exact outcome in ticket 16, ticket 39 and local frontier.

## Open gates

Ticket 39's actual exchange capture schema, redaction, retained bytes,
private store, provenance/response identity and human review are missing.
This unit must not be wired to Run/Jira admission. Native, provider, paid,
tenant, venue and human acceptance are **NOT RUN**.
