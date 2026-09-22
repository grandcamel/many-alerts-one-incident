# Bounded TLS HTTP request collection plan

2026-09-22, baseline a71fa1c. Separate authorized local implementation follow-up.
No push, C2 edits/retry, actual credentials, native/provider/tenant calls or paid
experiments. Preserve protected dirty files. Full suite before code commit.

One implementer owns changes to forwarder_http.py and new forwarder_http_receive.py.
First refactor pure header parsing, verify existing HTTP tests, then add transport.
Tester owns tests/test_forwarder_http_receive.py. Root also owns public head
contract/equivalence tests in tests/test_forwarder_http_head.py and real TLS integration
in tests/test_forwarder_http_receive_integration.py, docs and full-suite evidence.
An independent reviewer checks frozen final files. Do not edit old tests.

## Pure parsing reuse

Add parse_request_head(data: bytes, service: str, *, allowed_query_keys=frozenset(),
accept="application/json") -> ParsedRequestHead to forwarder_http.py. It accepts
EXACTLY a complete request line plus header section ending CRLFCRLF and no body.
Return frozen service, method, path/query (repr excluded), accept, sentinel
(repr excluded), and body_length. Reuse existing limits/grammar/config/header,
path, query and sentinel validation. Export MAX_REQUEST_LINE_BYTES=2048,
MAX_HEADER_BYTES=16384, MAX_BODY_BYTES=262144 for collector limits. Preserve
parse_request behavior including opaque body, exact body length and extra-byte
rejection by sharing the same header-validation implementation. No dummy body
allocation from Content-Length, duplicate grammar or relaxation of old rules.

## Transport API

receive_request(connection: ssl.SSLSocket, service: str, *, deadline: float,
allowed_query_keys=frozenset(), accept="application/json") -> ParsedRequest.
HTTPReceiveError(ValueError) provides closed fixed nonsecret code/message;
no raw SSL/socket/parser details or exception chaining. The caller supplies the
original absolute monotonic handler deadline clipped to its lease, not a fresh
per-read or post-handshake budget. Deadline must be exact int/float, finite,
future, and at most 40 seconds after the first observed monotonic time. Reject
bool, huge ints, NaN/inf, expired values and nonfinite/regressing clock samples.
Check the same deadline before/after every recv, before return, and clip each
socket timeout to its remaining time. No retry/fallback on socket or TLS errors.

Require an exact already-handshaken server-side ssl.SSLSocket, TLSv1.2/TLSv1.3,
with PROTOCOL_TLS_SERVER context and an open descriptor. This validates transport
state, not fixed-service identity, lease or route authority: trusted caller binds
the supplied service to its FixedTLSListener. No public raw-socket mode. A
module-level lock claims each socket with a private permanent marker before any
read; repeated/concurrent receive calls fail without receiving bytes. The caller
must not mutate/remove the marker or concurrently operate this connection.
A failed receive is still consumed and cannot be retried on that socket.

Caller retains socket ownership on success/failure, must close after its one
response or any failure, and must never process later bytes as another request.
Receiver performs no sends, shutdown, close, application retry or upstream I/O.
Temporarily changes timeout and restores it before returning; restoration failure
must not yield success. Preserve an existing failure or interruption if restore
also fails, suppress raw restore details, and retain the consumed marker.

## Collection bounds

Collect request line then headers incrementally, in chunks at most4096. Request
line including CRLF <=2048; subsequent header section including final blank CRLF
<=16384. Before more input, determine the applicable remaining cap; never allocate
or request unbounded receive bytes. Read at most cap+1 to detect overflow. A
header recv may include a bounded prefix of body; preserve those bytes. Reject
invalid/oversized header immediately when determinable and validate the complete
head through parse_request_head before further body reads. Existing allowed
query/Accept settings are trusted caller configuration and are validated by the
pure parser; they never come from the request.

Declared body <=262144. After head validation, total required length is known.
Reject already captured bytes beyond that length. Read remaining body in chunks
<=65536 and <=remaining+1; reject a captured extra byte. Do not perform a blocking
extra-byte probe after the exact body is complete; HTTP clients need a response
without half-closing their request. EOF/truncation/clock or I/O failure rejects.
Final parse_request validates the complete bounded buffer without modifying
body data. Result is request structure only, never a dispatch permit.

The collector cannot detect bytes arriving after success or already waiting in
another unread TLS record. The consumed socket marker and required one-response
close prevent interpreting those bytes as another request. Do not claim complete
pipelining detection or production route/response admission. No response writer,
route policy, lease/revocation dispatch or journal/accounting is implemented here.

## Verification

Existing 104 HTTP parser tests stay unchanged and pass after refactor. Add exact
head boundary/equality tests, header/body fragmented/coalesced capture, EOF at
line/header/body, invalid lengths and overflows rejected before further reads,
absolute deadline slow drips and clock regression, byte/request caps, timeout
restoration failures, exact TLS-state requirement and concurrent one-shot claim.
Real TLS tests use existing temporary synthetic material and listener helpers,
strict client and collector composition, fragmented/opaque body, malformed/head
rejection, stalled input and repeated receive refusal. No native/deployed claims.

## Review refinements

Root review corrected successful-return handling when timeout restoration fails.
The collector now tracks primary failure within its own invocation, rather than
using sys.exc_info (which can inherit a caller's handled exception). Existing
receive errors/interruption keep precedence. The final deadline check follows
restoration and compares against the latest pre-restore clock observation.
Exact server-side state and oversized recv returns are rejected; body read
requests remain <=65536, clipped further to remaining body plus one.

The public head tests prove equivalence, exact independent line/header limits,
maximum body declaration without a dummy body, truncation, type and privacy
boundaries. Collector tests include stream fakes respecting requested read sizes
and exact caps; TLS fixtures retain the separate synthetic/local boundary.

## Full-suite corrective follow-up

The first full suite failed the existing Darwin stalled-TLS-handshake shutdown
assertion (1 failed, 1291 passed, 36 skipped). The original log is retained in
full-suite-before-handshake-fix.txt. This expands the current local change to
forwarder_server_tls.py and its deterministic unit tests: resume a nonblocking
handshake on SSLWantRead/SSLWantWrite under the original deadline, poll readiness
at most0.1s, and check terminal state between waits. Nonblocking SSL steps serialize
with close; readiness waits do not hold the state lock. Fatal TLS errors never
restart a handshake/connection. Restore a finite remaining timeout before
returning socket ownership. Keep the existing real shutdown assertion unchanged.
Independent review and full suite must cover the corrected server source too.
