# Common HTTP request boundary implementation plan

2026-09-22, baseline 4e1b206. Separately authorized local source/test work.
No push, native/provider/tenant requests, actual secrets, C2 changes or deployment.
Preserve the four protected dirty artifacts. Full suite before commit.

Implement a pure complete-buffer parser in grafana_jsm_sandbox/forwarder_http.py:
`parse_request(data: bytes, service: str, *, allowed_query_keys: frozenset[str] =
frozenset(), accept: str = "application/json") -> ParsedRequest`.
This is structural validation, not route authorization, lease checking, HTTP
transport or readiness. Only trusted route configuration may supply the query
allowlist and expected Accept. Never dispatch directly from this result.

ParsedRequest is frozen, with service, method, path, query (tuple of key/value
pairs), accept, body (bytes), sentinel (str). Exclude path/query/body/sentinel
from repr; no raw headers retained. HTTPBoundaryError(ValueError) has fixed code
and fixed message, with no caller values or raw exception chaining.

Input must be exact bytes. Before copying/decoding, cap the complete input at
2048 + 16384 + 262144 bytes. Request line including CRLF <=2048 bytes; header
section after request line INCLUDING final blank CRLF <=16384 bytes, <=64 fields;
body <=262144. Exactly METHOD SP target SP HTTP/1.1 CRLF. Methods only GET, POST,
PUT, PATCH, DELETE. Reject bare CR/LF, obs-fold, whitespace before header colon,
non-ASCII/control/DEL header bytes. Accept header names case-insensitively, with
exactly one space after colon and no leading/trailing value whitespace. Header
name uses RFC token characters. Reject every duplicate header (stricter than
singleton minimum). Narrow profile accepts only Host, Authorization,
Content-Length, Content-Type, Accept and optional User-Agent; never return or
forward User-Agent. All other headers (including proxy/hop/credential headers)
fail closed until a verified client profile explicitly extends the allowlist.

Host and Authorization and Accept required. Host exactly fixed service DNS:port.
Accept exactly trusted expected value; expected value only application/json or,
for Anthropic only, text/event-stream. GET allows no Content-Type, absent length
or canonical 0, and no body. Other supported methods require Content-Type exactly
application/json and canonical Content-Length (0 or nonzero digit followed by
digits, <=262144); exact received body length. JSON semantic validation belongs
to route policy. Any trailing/pipelined bytes beyond length fail. Parser assumes
its caller has captured one complete bounded message; it does not police future
socket bytes or implement a transport deadline. Future server must close after
one request and must not parse a second request.

Basic Jira/Confluence credentials decode strictly and canonically to run:<token>;
other services use exactly Bearer <token>. Token is canonical unpadded base64url
of exactly 32 bytes (43 characters; reject noncanonical pad bits). Decode Basic
with validate=True, re-encode exact comparison, ASCII and exact run: prefix.
This only extracts a sentinel, never proves registration, service lease or scope.

Target is ASCII origin form with leading /, no fragment/backslash/control/DEL,
no //, no . or .. path segments. Path characters limited to RFC3986 pchar plus
slash. Reject malformed escapes, percent-encoded slash/backslash/dot/percent,
controls, DEL or non-ASCII octets; reject escaped unreserved characters as
noncanonical aliases. Other escaped ASCII such as %20 stays encoded in path;
route matching must use this exact path and never silently normalize it.
Query absent or nonempty key=value pairs separated by &, no empty components,
no repeated decoded keys, no semicolon separators. Strict percent-decode and
plus-to-space for values; require decoded ASCII without controls/DEL. Keys use
unreserved ASCII spelling with no percent/plus aliases, must belong to trusted
allowed_query_keys. Reject empty keys; allow empty values. Query allowlist is
exact frozenset of at most32 nonempty unreserved ASCII names <=128 characters;
invalid config rejects even without query. Max32 query pairs. Values are not
semantically authorized by this parser; route must validate their meaning.

Terra implementer owns module only. Terra tester owns tests/test_forwarder_http.py.
Root owns adversarial/integration tests, documentation, review and full suite.
Separate reviewer inspects final files read-only. Do not modify existing TLS code.

Validation must cover each service, Basic/Bearer canonical grammar and secret
redaction; complete/bodyless/body request framing; exact size boundaries and
overflows; conflicting lengths/pipelining/header smuggling; path/query ambiguity;
wrong profile and accept; malformed types/config. Use synthetic sentinels only.
No HTTP server, native client compatibility or deployed request acceptance claim.

## Review refinements

The implementation uses one fixed `invalid_request` error code. Root adversarial
tests caught newline validation incorrectly including body bytes; validation now
stops at the header boundary so pretty-printed JSON and opaque body bytes remain
intact. Duplicate slashes are rejected in the path only; URL-valued query text
remains data for route-specific validation. Content-Length has a six-digit bound
before numeric conversion. Independent final review is bound to frozen hashes.

Protocol references: [HTTP/1.1 message syntax](https://www.rfc-editor.org/rfc/rfc9112.html)
and [URI syntax](https://www.rfc-editor.org/rfc/rfc3986.html). The local profile
uses deliberately stricter acceptance rules and does not assert native-client
compatibility or implement a general-purpose HTTP server.
