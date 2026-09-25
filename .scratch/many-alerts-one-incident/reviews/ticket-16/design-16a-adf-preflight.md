# 16a: local ADF byte preflight

Status: proposed local serialization slice, 2026-09-25. Ticket 16 remains
open. Authority: accepted ADRs 0006, 0012 and 0014, plus the ticket-16
Report proposal's synthetic ADF example and proposed 8,192-byte field bound.
No Jira or Report delivery is authorized by this slice.

## Exact local contract

Accept only the example's ADF subset: a `doc` with `version: 1` and a
nonempty `content` array of `heading` or `paragraph` blocks. Each block has
one nonempty `text` node; only a `heading` has `attrs: {"level": 2}`. No
marks, links, lists, code, extra fields or attributes are accepted. This
small grammar keeps native-dependent ADF features disabled. One text node
contains at most 2,048 UTF-8 bytes. The serialized canonical UTF-8 ADF is
at most 8,192 bytes, measured after JSON escaping and markup. At most 128
blocks are inspected, and text byte bounds are checked before serializing
the whole document. Use the
existing strict JSON decoder and canonical encoder: duplicate keys,
non-finite numbers, malformed UTF-8, noncanonical bytes and unknown shapes
fail closed. The result is immutable bytes, a byte count and a SHA-256
digest; neither count nor digest is embedded in the bytes hashed.

The decoder accepts only canonical bytes and returns a fresh preflight
artifact. This supports exact file/stdin byte read-back in synthetic tests;
it is not a staging writer or transport adapter. Fixed non-diagnostic error
codes carry no caller content. Ordinary text escaping, including multibyte
Unicode, is preserved by the canonical encoder. The tiny grammar cannot
reach ADF node depth 8; nested/unsupported structures are rejected rather
than treated as depth-8 conformance evidence.

## File-by-file implementation plan

1. Add pure `grafana_jsm_sandbox/report_adf.py` with `encode_preflight` and
   `decode_preflight`, an immutable artifact and fixed error codes. No I/O,
   credential, provider or dispatch API. Verify syntax and lint.
2. Add `tests/test_report_adf.py` for the proposal's exact example. Parse its
   noncanonical literal with the generic strict JSON parser, encode that value
   canonically, and decode the canonical bytes; reject the original literal
   with `decode_preflight`. Cover Unicode/escaping byte counts, malformed and
   duplicate-key bytes, unsupported nodes/attributes, 2,048-byte text and
   8,192-byte document edges, and a local file byte read-back fixture.
   Run targeted tests.
3. Record source reviews, run Ruff and `git diff --check`, then the full
   repository suite before a named local code commit. Preserve protected
   ticket-19/planning files and the receiver-journal panel.

## Acceptance boundary

This is serialization-only source and synthetic evidence. It does not
validate seven-section Report claims/citations, create immutable revisions,
prepare a whole Jira request, prove installed-client file/stdin behavior,
authorize a Forwarder effect, or make a human grade. Native, provider,
tenant, paid, venue and human acceptance are **NOT RUN**.
