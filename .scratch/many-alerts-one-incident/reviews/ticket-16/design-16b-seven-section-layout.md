# 16b: seven-section local ADF layout

Status: proposed local source design, 2026-09-25. Ticket 16 stays open.
Authority: accepted ADR 0014, ticket 16's source-only Report proposal, and
the reviewed 16a ADF byte preflight. This unit formats caller-supplied
synthetic text; it neither validates the truth or retrieval support of claims
nor creates a complete Report or Jira request.

## Contract

`render_report_layout(sections)` accepts exactly the seven keys from the
ticket-16 proposal: `summary`, `blast_radius`, `timeline`, `evidence`,
`suggested_root_cause`, `suggested_remediation`, and `fingerprints`. Every
value is explicitly supplied, nonblank text. No section is defaulted,
inferred, truncated, rewritten or dropped. The caller may state unknown,
partial, or undetermined status in its own text; the builder does not upgrade
it. Text and citation IDs/URLs remain inert plain text, with no ADF link mark,
source retrieval, verification flag, or confidence/grade decision. This API
does not accept claims, citation objects, or status fields, so a passing
render is only shape and byte evidence.

The output uses exactly seven fixed level-2 headings and one paragraph per
heading, in proposal order. Headings are `Summary`, `Blast radius`,
`Timeline`, `Evidence`, `Suggested root cause`, `Suggested remediation`,
and `Fingerprints explained`. The existing `report_adf.encode_preflight`
validates each text node at 2,048 UTF-8 bytes and the canonical ADF document
at 8,192 UTF-8 bytes, then returns exact bytes, byte count and SHA-256.
Unknown keys, missing keys, non-string, empty, or whitespace-only text fail
closed before construction. Existing ADF errors remain fixed codes. No
caller-controlled heading or attribute enters ADF.

The layout may only receive already-sanitized text from a future trusted
boundary. It has no privacy filter, source capture, append-only revision
store, Jira adapter, permission, effect receipt or human grading. In
particular, a nonempty Evidence or Suggested root cause paragraph does not
prove claim-to-returned-response support under ADR 0014.

## File-by-file plan

1. Add this proposed design before code changes. Preserve the 16a codec.
2. Add pure `grafana_jsm_sandbox/report_layout.py` with the closed section
   registry and deterministic ADF builder. Verify Ruff and focused tests.
3. Add `tests/test_report_layout.py` for exact order and bytes, all-seven
   rejection, unknown/partial text preservation, Unicode/escaping and
   document/text overflow, hostile Python types, and inert citation text.
4. Obtain independent Standards and Spec source reviews; run Ruff,
   `git diff --check` and the full repository suite before a named local
   code commit. Update ticket 16 and the local frontier with exact outcomes.

## Open gates

Ticket 16 still needs claim/citation linkage to actual returned evidence,
source-specific reference validation, immutable revision custody, bounded
trusted Jira transport and response/effect read-back. Ticket 39's private
audit and human review remain separate. Native, provider, paid, tenant,
venue and human acceptance are **NOT RUN**.
