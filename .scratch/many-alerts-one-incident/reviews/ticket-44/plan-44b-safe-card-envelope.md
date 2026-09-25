# 44b: structural audience card candidate envelope

Status: local source plan, 2026-09-25. Ticket 44 remains open.
Authority: ADR 0018 and ticket 44's proposed audience contract.

The current 44a policy receives already validated safe claims. This unit
adds a strict parsing boundary for **candidate** cards from the four primary
sections. It does not authenticate a source, select an operator context,
redact arbitrary source text, render a UI, or make any card authoritative.

## File-by-file plan

1. Add `grafana_jsm_sandbox/audience_card.py`. Parse bounded JSON bytes
   using the existing strict JSON parser. Accept an exact structural
   envelope: syntactically bounded but untrusted IDs, section/source pair,
   required rehearsal and OPS Incident link for Incident/draft cards,
   nullable source revision
   and UTC microsecond times, independent verification/availability/retrieval/
   review/mutation/Memory axes, fixed display code, bounded provenance
   reference and a small closed gap-code list. Reject unknown fields,
   duplicate keys, free-text fields, URL/path-shaped IDs, booleans in integer
   slots and invalid time/ID/status values. Return an immutable typed card and
   canonical **untrusted candidate** bytes. An alphanumeric ID can still
   contain identity or credential material; source-specific sanitization is
   required before any output is shown or exported. No supplied summary or
   source body is copied into the output.
2. Add `tests/test_audience_card.py` with valid four-section cards and
   adversarial bytes. Verify no count or zero is invented,
   availability stays separate from retrieval, provenance and times are not
   advanced by projection refresh. Rejected canary free-text fields cannot
   survive in exception text; accepted opaque IDs remain untrusted and may
   appear in candidate bytes. Run focused tests and Ruff after this file.
3. Update ticket 44 and an outcome to state exactly which boundary is local
   and which source, authorization, correction overlay, UI and presenter
   gates remain. Obtain independent Standards/Spec reviews, fix defects,
   run the full repository suite before a named local code commit. Verify
   protected dirty files/panel and stage named paths only.

## Narrow contract

The parser accepts one card at a time, at most 4 KiB, with no user-authored
summary. It requires a rehearsal ID because this subset covers selected
context cards, narrower than the proposed general nullable envelope. Its
`display_code` is a closed structural category, not a diagnosis or human
verdict. A later source-specific adapter and operator-only projection must
prove scope and sanitize IDs and any approved human text before a UI can
render them. Native, provider, paid, tenant, venue and human acceptance are
NOT RUN.
