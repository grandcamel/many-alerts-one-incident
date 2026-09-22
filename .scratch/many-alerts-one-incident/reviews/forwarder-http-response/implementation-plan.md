# Bounded non-streaming HTTP response boundary

2026-09-22. Baseline 2f44771. Ninth separately authorized local application unit.
No push, C2 changes/retry, actual credentials, provider/native/tenant calls,
paid experiments or deployment. Full suite before commit. Protected dirty files
remain untouched. This is pure complete-buffer parsing/serialization; upstream
transport, response receipt-before-send and semantic route acceptance remain
subsequent integration work.

## Plan and ownership

1. Implementer owns new grafana_jsm_sandbox/forwarder_http_response.py.
2. Tester independently owns tests/test_forwarder_http_response.py.
3. Root adds adversarial/privacy tests, docs and full-suite evidence.
4. Independent review binds final source/test hashes before local commit.
No existing code/test behavior changes. Verify focused suite before full suite.

## Narrow local contract

Public parse_response(data: bytes) -> ParsedResponse and
serialize_response(response: ParsedResponse) -> bytes; fixed HTTPResponseError
(ValueError) code invalid_response and non-diagnostic message/from None.
Frozen ParsedResponse has status:int and body:bytes (repr excluded). No raw
reason, headers or upstream URL retained. Public constructor is not an authority
boundary: serializer independently validates exact type/status/body/caps.

Exact bytes input only, total <= 2048+16384+1048576 before copying/splitting.
Status line including CRLF <=2048. Exact HTTP/1.1, three decimal status digits,
single separating spaces, nonempty printable ASCII reason. Accept 200-299 and
400-599 only; reject all informational/redirect statuses, upgrade and invalid
ranges. Raw reason is ignored and never serialized. No redirects/follow/retry.

Header region including final blank CRLF <=16384, <=64 fields. CRLF only;
reject folding, malformed names, whitespace before colon, controls/non-ASCII.
Permit ordinary optional surrounding SP/HTAB on values, not embedded controls.
Reject all case-insensitive duplicate field names. Unknown well-formed headers
are discarded, including Location, Set-Cookie, credential and hop-by-hop fields.
Reject Transfer-Encoding, Trailer, Content-Encoding and Upgrade outright: this
unit supports neither chunked nor compressed, streaming, upgrade or close-delimited
framing. Reject Connection tokens naming Content-Length or Content-Type so a
hop-by-hop nominated field cannot establish end-to-end framing. Other Connection
values may be discarded; output always Connection: close. Connection options
must be a nonempty comma-separated list of HTTP token names; reject empty,
quoted or malformed options. Trim surrounding SP/HTAB on each token.

For 204: no Content-Length, no Content-Type, no body (reject even CL: 0).
For 205: exactly canonical Content-Length: 0, no Content-Type/body.
Other accepted statuses: exactly one canonical decimal Content-Length <=1MiB,
exactly Content-Type: application/json, and exactly the declared body bytes.
Require nonempty body. Preserve opaque body bytes unchanged; JSON/schema/scope
validation belongs to service policy. Labelled JSON is not semantic acceptance.
Never infer EOF framing; reject truncation and captured extra bytes.

Serialize deterministic status line with fixed reason (use "Response" for all
body statuses, "No Content"/"Reset Content" for 204/205), Content-Type:
application/json and computed Content-Length for body statuses, only
Content-Length: 0 for 205, neither for 204, and Connection: close for all.
No user/upstream headers or reason text can enter output. No sockets/sends,
receipts, effects, success grading or route/lease permissions from this codec.

Limits and the narrower canonical content-type/framing profile are explicit
local choices; native and real upstream compatibility is NOT qualified. SSE
remains separately gated. Late unread bytes are outside a complete-buffer
parser's detection. Future transport must bound collection under original
handler deadline and emit a sanitized receipt before returning any response.

## Required verification

Success/roundtrip status classes and 204/205, opaque binary body, canonical
serialized header set, stripped private headers/reason and safe repr/errors;
reject redirects/informational/upgrades, wrong HTTP/version/status grammar,
bad CRLF/folding/names/controls, duplicates including mixed case, forbidden
framing/codings, missing/invalid/huge lengths, exact body/header/status caps and
overflows, CL mismatch/extra, no-body status abuse, exact type and hostile
constructor bypass at serializer. No default real network activity.
