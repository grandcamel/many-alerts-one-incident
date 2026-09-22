# Local mediated-client TLS fixture

This package is an offline, synthetic transport experiment.  It runs two fixed
TLS loopback listeners: a test client calls the mediator, and the mediator calls
its own fixed synthetic upstream.  It contains no production Forwarder, Receiver,
Run, native Claude client, provider credential, external destination, or control
channel.

`MediatedClientHarness` permits only `POST /v1/messages` with the exact
`FIXTURE_REQUEST` bytes and buffers only the exact SSE-shaped `FIXTURE_RESPONSE`.
A trusted test controller registers an opaque token for
one bounded lease, activates it, and may revoke it.  The HTTP surface has no
registration, reactivation, revocation, upstream destination, credential, or
handler interface.  Expired/revoked/inactive/non-Anthropic leases and malformed,
oversized, noncanonical, or non-fixture requests are denied before upstream
request bytes are sent.

The mediator rebuilds its upstream headers from fixed framing, Content-Type, and
a synthetic API key.  It never forwards caller credentials, host, proxy, hop, or
connection-named headers.  Both hops use TLS 1.2 or later, CA verification, and
hostname checking.  Upstream redirects, incomplete/oversized responses, TLS
errors, disconnects, and timeouts produce a bounded local gateway failure with no
Location, partial response, automatic retry, fallback, or renewal.  The response
is buffered SSE-shaped fixture data; it is not incremental-streaming or native
client compatibility evidence.

Receipts retain only metadata and body digests.  They contain no token, key,
Authorization value, request body, or response body.  A lease check and its one
bounded upstream send share a lock: `revoke()` waits for an in-flight send to
finish and then prevents later dispatch.  It cannot cancel or undo that in-flight
synthetic request.  This is local thread synchronization, not proof of a
Receiver-only OS-protected control plane, sidecar isolation, native admission,
provider billing, tenant authority, or deployment qualification.

Each mediated dispatch also carries a one-time internal correlation nonce. The
synthetic upstream records a request only when the nonce and its sequence match a
pending mediator dispatch, then consumes that pair. The nonce and internal header
values never appear in a receipt. This prevents fixture-local receipt forgery; it
does not establish an OS or authenticated control boundary.

The configured timeout bounds one upstream hop. Each accepted TLS connection has
an absolute `2 * timeout + 0.2` second deadline, beginning at accept and enforced
by closing the socket; its TLS handshake uses the configured timeout. That leaves
bounded time for the mediator to return a local gateway failure after an upstream
timeout while still rejecting slow-drip handshakes, headers, and bodies. Per-socket
timeouts bound individual blocking operations; the absolute connection deadline
also bounds their aggregate duration and the mediated outbound connect/send/read.
