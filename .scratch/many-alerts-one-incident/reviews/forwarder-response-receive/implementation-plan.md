# Bounded non-streaming TLS response collection

2026-09-22. Baseline 1220f4c. Tenth separately authorized local source unit.
Preserve four protected dirty files. No push, provider/native/tenant calls,
actual credentials, C2 retry, paid experiment or deployment. Full suite before
commit. This collector receives only on caller-supplied established TLS; it
opens no connection and sends nothing, so receipt-before-client-send remains
unimplemented. Existing response codec's 83 tests must remain unchanged.

## Execution plan

1. Implementer owns forwarder_http_response.py refactor and new
   grafana_jsm_sandbox/forwarder_response_receive.py. First verify existing
   response tests after pure-head refactor, then implement bounded collection.
2. Tester owns tests/test_forwarder_response_receive.py, including head tests.
3. Root owns real local TLS and independent adversarial tests, docs, evidence
   and full-suite execution.
4. Independent reviewer binds final source and test hashes before local commit.

## Shared pure response head

Export MAX_STATUS_LINE_BYTES=2048, MAX_HEADER_BYTES=16384, MAX_BODY_BYTES=1048576.
Add frozen ParsedResponseHead(status:int, body_length:int), and
parse_response_head(data:bytes) -> ParsedResponseHead. Input is exactly one
complete status/header region ending with its blank line, no body bytes.
Reuse the existing status/header/Connection/coding/204/205/length grammar in both
head and full parser; do not duplicate grammar or allocate a dummy declared body.
Ordinary body statuses require positive canonical length; 204 yields zero with
no CL/type, 205 yields zero with exactly CL0/no type. Full parse enforces exact
actual length and opaque body preservation. Serializer behavior unchanged.

## Collection contract

receive_response(connection:ssl.SSLSocket, *, deadline:float) -> ParsedResponse;
ResponseReceiveError(ValueError) carries fixed code, sanitized message/from None.
Follow prior request collector error precedence: claim socket permanently under
module lock before reading; reject repeats/concurrency including after failure.
Exact SSLSocket only, open fd, server_side is False, TLS1.2/1.3,
PROTOCOL_TLS_CLIENT context, CERT_REQUIRED and check_hostname is True, negotiated
ALPN None or http/1.1. These are current transport/configuration checks only;
trusted owner must establish/retain approved fixed-origin identity/trust and
exclusive socket use. Never treat this as upstream/route/lease attestation.

Use caller's original absolute monotonic handler deadline clipped to its lease:
finite exact int/float, future and at most 40s away at entry, reject bool/NaN/inf/
huge integers. Working finite non-regressing clock checked before/after each
recv, before timeout restoration and after it. Each recv timeout is min(20s,
remaining original deadline), never a fresh overall budget. No reconnect/read
retry on timeout/error; SSL WANT is not retried here (socket is blocking timed).

Collect bounded status line and headers incrementally (<=4096/read, each clipped
to remaining region cap+1). Recognize headerless 204 via immediate CRLF after
status line. Parse entire head before further body reads and retain any coalesced
body prefix. Reject prefix beyond body length. Read <=65536 and <=remaining+1
for body; reject captured excess. Exact completion returns without EOF or extra
byte probe, including204/205. No second response on same socket, no keep-alive
reuse. Body max1MiB. Reject malformed/redirect/unsupported head before waiting
for more body bytes. Final full parser validates collected buffer.

Temporarily alter socket timeout and restore prior value. Restoration failure
cannot return success, even inside a caller's handled exception. Preserve an
existing receive/parser/interruption failure if restoration also fails. Socket
remains caller-owned: no send, close or shutdown by collector. Output contains
only status/opaque body and grants no route success, receipt or send authority.
Captured extra bytes rejected; later/unread TLS records cannot be detected and
must never become another response. Future owner closes socket and records the
correct uncertain/partial effect state based on dispatch context, never inferred
solely from this collector's error. SSE/chunked/compressed stay unsupported.

## Validation

Head/full equivalence, exact head termination,204/205, canonical and huge lengths,
maximum declaration without dummy body, exact cap boundaries. Deterministic fake
TLS tests for fragmented/coalesced/max body, EOF/overflow, head rejection before
further read, 20s inactivity/original deadline, slow drip/clock regression,
invalid TLS states, permanent/concurrent claims, timeout restoration precedence
including ambient except, pre/post-restore clocks. Real local TLS success with
fragmented opaque response,204/205, malformed/redirect/unsupported heads,
captured extra bytes, stalled/truncated input, repeated-call rejection.
No real upstream compatibility, fixed-origin qualification or external effects.

## Root review refinements

Check immediate empty header termination after every received fragment, not
only when the status line is first located. A late-returning read is rejected
when its observed elapsed interval reaches 20s even if the full handler deadline
has not expired; setting a socket timeout alone must not turn a late return into
success. Existing response tests remain unchanged. Real local TLS tests cover
one-byte fragmentation of no-body responses and leave peer EOF unnecessary.
