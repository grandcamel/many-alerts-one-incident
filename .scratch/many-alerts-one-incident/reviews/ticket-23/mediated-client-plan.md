# Local mediated-client transport plan

2026-09-22. Baseline 36a89c5. New isolated prototype only; no production Forwarder,
Receiver, Run/container, native model, provider/account or deployment mutation.
Ticket 36 remains a specification task. This harness supplies local acceptance
experiments for part of that specification, not its runtime implementation.

1. Root supplies temporary OpenSSL-generated test CA/server certificates, including
   expired and wrong-hostname variants. Keys never enter Git or retained receipts.
2. Terra implements an isolated two-hop TLS harness: test client -> mediator ->
   fixed loopback synthetic upstream. Luna independently tests transport rejection,
   strict TLS, scoped leases, caps and uncertainty/no-retry cases.
3. Independent review, complete suite, retained synthetic receipts and exact packet
   hash chain using the existing ticket-23 packet-manifest.json SHA-256 predecessor
   link and byte/length inventory (not a per-request receipt chain), then local commit. Official client configuration research is recorded
   separately from runtime evidence. No actual Claude client is launched.

## Fixed harness API and scope

Package `prototype/mediated_client/`. Root owns `certificates.py` with frozen
`FixtureCertificates(ca_cert, server_cert, server_key, expired_cert,
wrong_hostname_cert, wrong_ca_cert)` Paths and `create_certificates(directory)`.
Creates only fresh fixture files in an empty temporary directory, with bounded
OpenSSL subprocess calls and mode-restricted keys. It changes no system trust.

Terra owns `harness.py`, `README.md`, `__init__.py`. Class
`MediatedClientHarness(certificates, *, upstream_mode='ok',
server_certificate='valid', upstream_certificate='valid',
max_request_bytes=4096, max_response_bytes=8192, timeout_seconds=0.5)` is a context
manager. It creates two fixed 127.0.0.1 ephemeral TLS listeners and an internal
upstream context requiring this test CA, hostname checking and TLS>=1.2. There is
no arbitrary origin, port, credential, callback or handler parameter. Certificate
variant enums: valid, expired, wrong_hostname. Upstream modes: ok, redirect,
oversize, truncate, disconnect, timeout. All are synthetic controller choices.

Public `url` gives mediator https://127.0.0.1:port. Test clients use strict stdlib
HTTPSConnection and the test CA. Root certificate factory is also used for wrong
CA/hostname/expiry acceptance tests; no ssl._create_unverified_context.

`register(run_id, service='anthropic', ttl_seconds=270)` returns frozen Grant with
lease_id, run_id, service, expires_at and opaque random `token` (repr=False).
IDs nonempty <=64 safe ASCII characters, services from five ADR0011/0013 names,
TTL finite positive <=270, measured by time.monotonic(); validity requires
now < expires_at, with equality denied. Registration establishes expiry; activation
does not extend it. Maximum 32 registrations per harness, no reuse of
lease IDs/tokens. Grant is only a trusted-controller return; HTTP exposes no
registration, revocation, reactivation or upstream secret. `activate(lease_id)`
permits REGISTERED -> ACTIVE only before expiry. `revoke(lease_id)` permanently
invalidates a lease. Expiry and revocation cannot be undone by activate; new
harness instances start empty. No claim of an OS-protected control plane, Receiver
restart behavior or native Run admission follows from these in-process methods.

Only POST /v1/messages with exact `FIXTURE_REQUEST` bytes (module constant:
b'{"fixture":"mediated-client-v1"}') and Content-Type application/json is supported.
This is intentionally a closed synthetic body, not a real Anthropic Messages request
schema. Reject unknown paths/methods/query/encoded/absolute targets before dispatch.
A single Authorization: Bearer <active unexpired anthropic token> is required.
Other-service, unknown, not-active, expired and revoked tokens deny locally.
Require exactly one each of Authorization, Host, Content-Type and Content-Length;
equal duplicates also reject. Parsed Content-Length is the exact decimal str(n),
with no leading zeros or trailing whitespace. Parsed Content-Type must equal
application/json exactly (no parameters); Authorization must equal Bearer plus one
space plus token. The HTTP parser may normalize leading header whitespace; this
is a parsed-header contract, not raw-byte canonicalization. Any Transfer-Encoding
or Expect header rejects. Path is byte-for-byte /v1/messages, with no percent,
query, fragment, absolute-form or trailing-slash variant;
cap declared body before reading, bound read/socket time and reject short bodies.
Set socket timeout before the accepted TCP socket begins its TLS handshake. An
absolute deadline of 2*timeout_seconds+0.2 seconds (at most 4.2s) closes each
accepted connection even during slow-drip reads. Each upstream operation uses
the smaller of the configured timeout and the remaining incoming deadline; the
outbound socket is also closed at that deadline. A late request body cannot start
a fresh upstream time allowance. Normal timeout cases retain time for a gateway
response; deadline exhaustion may disconnect the client and remains held.
Bound aggregate header size at policy validation (8192 bytes), retaining the
stdlib parser's own separate bounded preparse limits. Limits are exact positive
ints <=1MiB; timeout finite positive <=2s, configurable only by trusted test code.

Rebuild upstream headers from fixed values rather than forwarding caller headers:
Content-Type application/json, synthetic x-api-key, required framing and an
internal sequence plus opaque per-dispatch nonce. Stub receipt capture requires
the exact pending sequence/nonce once; neither nonce nor credential values enter
receipts. This is trusted-harness correlation, not an OS access boundary.
Authorization, Host, Proxy-Authorization, X-Api-Key, connection-named and other
caller fields cannot change upstream authority. Upstream destination is always the
harness-owned TLS listener, using IP/CA/expiry verification and no redirect following.
A lease check/dispatch critical section serializes revocation with the one bounded
upstream send; recheck expiry after TLS connect before request bytes. Revocation
acknowledgement must prevent later dispatch, but cannot undo an in-flight request.
Document any waiting for this bounded critical section; it is not instantaneous
native cancellation or a proven 270-second production deadline.

The synthetic response constant FIXTURE_RESPONSE is
b'data: {"type":"fixture_reply"}\n\n'. A successful response requires HTTP 200,
Content-Type text/event-stream, exactly one canonical Content-Length equal to this
constant length, no Transfer-Encoding, complete body bytes equal to that constant,
and no redirect. Buffer at most response_limit+1 bytes. A clean shorter EOF, wrong
body with accurate length, missing/duplicate/ambiguous framing or partial body
cannot pass. Redirect, malformed/truncated/oversize, timeout, disconnect or TLS errors
return a gateway failure with no upstream Location, partial body or blind retry.
This batch tests buffered SSE-shaped response bytes; true incremental streaming and
native client compatibility remain NOT RUN. There is at most one upstream request
per admitted incoming request. Upstream failures revoke the affected lease to hold
further requests; uncertain effects are not converted to not-dispatched.

Metadata-only frozen receipts: `receipts` tuple of RequestReceipt(sequence,lease_id,
disposition,reason,upstream_attempted,request_bytes,response_bytes), dispositions
`denied`, `response_complete`, `upstream_unknown`. Every dispatched failure is
conservatively upstream_unknown even if TLS failed before HTTP delivery. No external
effect confirmation follows from response_complete. `upstream_receipts` tuple of
UpstreamReceipt(sequence,request_bytes,body_sha256,credential_replaced,host_matches,
header_names). Never retain sentinels, keys, authorization values or message bodies.
Bound receipt/request processing to 128 requests total; excess traffic denied with
saturating dropped count, no upstream. Sequential servers and bounded socket waits
must initiate both server shutdowns concurrently and join cleanly within 5 seconds total. Failed cleanup must raise
visibly; no background fixture server is accepted as a successful closeout. No automatic retry, fallback or renewal occurs.

## Evidence boundary

This proves local Python TLS and fixed-fixture transport only. It does not establish
five-service native schemas/listeners, OS/sidecar/control isolation, direct-route
denial from an actual Run, client credential precedence, native streaming, accounting,
provider billing, human Report grading, tenant roles or deployment qualification.
Standing aggregate cost approval remains valid; no paid experiment in this batch.
