# Non-streaming HTTP response boundary outcome

2026-09-22. PASS for the ninth separately authorized local application unit, baseline
`2f44771`. Final validation is recorded in [validation.json](validation.json).
This is local complete-buffer source work; no push or planning-ticket closure.

`parse_response` validates bounded HTTP/1.1 response framing and retains only
status and opaque body bytes. It rejects redirects/informational statuses,
duplicate fields, unsupported encodings, malformed framing, overflows and
captured extra bytes. The status line/header/body have independent limits.
Status 204 and 205 have explicit distinct no-body framing. Unknown well-formed
headers and the raw reason are discarded, including Location and credential
headers. Connection cannot nominate framing headers as hop-by-hop fields.

`serialize_response` revalidates the public value and builds a fixed reason and
canonical headers with `Connection: close`. It rejects malformed, subclassed,
mutated or incomplete constructor-bypassed objects. The body's representation
is hidden; no raw upstream metadata enters diagnostics or serialized headers.

Terra workers implemented source and contract tests, and a separate Terra worker
provided independent review. Root added adversarial/privacy tests and reviewed
headerless 204 handling, status separators, Connection whitespace and fixed
errors for incomplete constructed objects. Review findings were corrected before
final validation. See [review.md](review.md) for frozen source/test hashes.

The profile intentionally accepts only canonical non-streaming length-delimited
JSON-labelled bodies, plus the specified no-body statuses. Body bytes remain
opaque; passing the codec does not validate JSON semantics, scope, route success
or complete external-effect evidence. Chunked/compressed/SSE, native client and
real upstream compatibility remain unqualified. The byte cap bounds supplied
buffers, not any upstream socket read or late unread bytes.

Validation on frozen artifacts:

- [Focused tests](focused-tests.txt): **83 passed in 0.17s**, exit 0
  (44 contract tests and 39 independent adversarial/privacy tests).
- [Full suite](full-suite.txt): **1378 passed, 36 skipped in 261.99s**, exit 0.
- Independent source/test review, Ruff, compilation and whitespace checks pass.

No sockets or response sends are added. Later transport must collect under the
original handler deadline, coordinate receipt-before-send and close after one
response. Creating serialized bytes grants no dispatch or forwarding authority.
No provider/tenant/native calls, actual credentials, C2 retry, paid experiment,
deployment or human Report adjudication occurred. Four protected dirty artifacts
remain unchanged and unstaged. Ticket 36 stays open as a planning ticket.

Next: bounded response transport and request-aware route policy, then atomic
lease/revocation/dispatch coordination and durable Receiver/recovery/accounting.
The existing local source authorization covers that work; no additional user
scope decision is required.
