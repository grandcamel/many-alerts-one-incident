# Bounded HTTP response codec independent review

## Early contract review

The codec is appropriately a complete-buffer framing and sanitization boundary.
It must not be described as upstream transport, a durable response receipt, a
route success decision, or native/provider compatibility evidence. In
particular, a later transport still owns deadline-bounded collection, handling
late bytes, response receipt-before-send, and the decision whether a parsed
status has any route meaning.

Final implementation should preserve these security properties:

- Cap total input before splitting/copying, then independently bound status
  line, complete header region, field count, and body. Parse only CRLF framing;
  reject bare newline/folding and all captured bytes beyond canonical length.
- Apply duplicate detection case-insensitively before discarding unknown
  headers. Parse `Connection` values as comma-separated case-insensitive tokens
  with OWS trimming, so `content-length` or `content-type` cannot be nominated
  hop-by-hop through spelling/whitespace aliases.
- Treat 204 and 205 as separate framing states: 204 has neither Content-Length
  nor Content-Type/body; 205 has only canonical zero Content-Length and no
  Content-Type/body. Other accepted statuses need a nonempty opaque body,
  canonical decimal length, and exact JSON media type.
- Serialization must independently validate exact `ParsedResponse` type and
  fields, discard any hostile constructor-bypassed state, and emit only the
  deterministic status/header set. Never reflect raw reason/header/body data in
  representations or errors beyond the deliberately returned body bytes.

## Final hash-bound source and test review

Reviewed source SHA-256
`05491343f5ab49610b6c8fdbe921ebbdef109a0d92a8a4e045c81e069b1f5db6`,
unit-test SHA-256
`2fa68b84ff6870c8b7b9313a8015cc1eca971b0cdd72e917f14c2de99e2496a5`,
and root adversarial-test SHA-256
`174d70b6fbccf345632bde0cc8bdda0d311467386170d9cd5a5cddaa66ce6ad3`.

Verdict: **PASS (source and test review)**.

The parser imposes the total cap before splitting, then independently enforces
status-line, header, field, and body bounds. It accepts only exact HTTP/1.1
status-line separators, printable reasons, and the stated 2xx/4xx/5xx ranges.
Header parsing rejects framing/coding/upgrade fields and duplicates before
discarding unknown metadata. Connection options are trimmed and validated as
nonempty token names individually, preventing case or OWS aliases from
nominating Content-Length or Content-Type.

No-body statuses are distinct: headerless 204 is accepted only with no body or
framing fields; 205 needs precisely canonical zero Content-Length. Other
statuses require canonical bounded Content-Length, exact JSON media type, and a
nonempty opaque body of exact declared length. Serialization independently
checks exact value type and complete fields, then emits only deterministic
status/reason/framing headers and the opaque body.

The reviewed tests cover status/header/body limits, framing/status grammar,
mixed-case duplicates, forbidden fields, 204/205, opaque binary data, no secret
projection, Connection token aliases/OWS, constructor bypass/mutation/missing
attributes, and error-chain suppression. The root focused log reports 83 tests
passing; that runtime evidence is root-owned and was not rerun here.

This remains a complete-buffer codec only. It creates no socket, receipt,
response send, route-success decision, lease authority, external effect, or
native/provider acceptance. Late unread bytes, deadline-bound transport
collection, receipt-before-send, and semantic route policy remain separate.
No source/test edit, network/provider/native, credential, C2, full-suite,
commit, or push action was performed by this reviewer.
