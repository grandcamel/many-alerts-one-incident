# Forwarder service, lease and control core

The application modules `forwarder_services` and `forwarder_leases` provide the
first local implementation unit of the reviewed Forwarder contract. They are
not wired into the legacy HTTP/OAuth launcher. No listener, native client or
provider connection is started by importing or using these modules.

`SERVICE_PROFILES` pins five immutable IPv4 loopback listener descriptions.
`classify_readiness` requires explicit Boolean route facts: missing Jira,
Grafana/Eyes, Kubernetes or Anthropic readiness holds the mandatory route set.
Missing Confluence readiness is reported separately as degraded optional Memory.
The result classifies supplied facts; it does not attest them or authorize a Run.

`LeaseRegistry` belongs to a trusted Receiver control adapter. It creates a fresh
Forwarder generation and scoped random sentinels, supports registration followed
by explicit activation, and preserves immutable Run/attempt/service bindings.
An exact live registration replay returns its grant. Changed scope or expiry,
expired/revoked replay, and wrong service or generation cannot restore authority.

The registry uses one monotonic clock and lock. Leases expire at their supplied
deadline, no later than the bounded registration/launch window. Heartbeat loss,
control EOF and Receiver boot replacement invalidate existing authority. A late
heartbeat or repeated handshake cannot revive it. Clock failure or regression
holds the registry; restart recovery belongs to the durable Receiver journal.

The grant intentionally carries its sentinel to the trusted controller, with
the secret excluded from its representation. Receipts and snapshot projections
contain metadata only. Control reason codes are closed values. Count, age and
encoded-byte limits bound retained metadata; these are not measurements of the
Python process's heap. History is diagnostic rather than a durable audit log.
The limits are 256 live leases, 1,024 retained lease records, 128 diagnostic
receipts, and 512 KiB of encoded metadata. Registration reserves space for future
state changes and a full diagnostic ring, so the byte budget can refuse a new
lease before the record-count limit. Recent lease records are never evicted to
admit another lease; diagnostic receipt loss is counted explicitly. Records and
receipts age out after 310 seconds. `metadata_bytes` counts the full snapshot's
canonical JSON encoding, including that count field.

`check` is an instantaneous authorization observation. It does not authorize a
later network write: the future transport must recheck current authority and
coordinate dispatch initiation with revocation. This module cannot prove socket
peer identity, kernel isolation, safe native-client configuration, provider
credential custody, or the disposition of bytes already sent.

## Authenticated control sessions

`ForwarderControl` serves an already accepted Unix stream socket. Both sides
check the actual OS peer UID: the server uses the configured Receiver UID, and
`authenticate_receiver` uses the configured Forwarder UID. Darwin uses
[`getpeereid`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/getpeereid.3.html)
to obtain effective credentials established at connection time. The Linux
`SO_PEERCRED` branch needs validation on Linux. Unsupported identity mechanisms
deny authentication.

Construction supplies a 32-byte control secret. A fresh challenge, generation
and Receiver boot ID bind role-separated HMAC-SHA256 proofs. The Receiver helper
verifies the Forwarder proof before returning handshake metadata. The raw secret
is never transmitted. A successful registration response intentionally delivers
the lease sentinel over that authenticated channel; diagnostics do not retain it.

Commands are limited to registration, activation, revocation and heartbeat.
Exact parameter sets and increasing sequence numbers prevent extra control
fields from overriding session identity. Frames are length-prefixed UTF-8 JSON,
limited to 8 KiB, four object levels and bounded scalar fields. Each frame uses
one absolute deadline, at most ten seconds in this controller. Malformed frames,
duplicate keys and unsupported values fail closed.

One connection owns control. Successful replacement revokes the previous
connection's leases, including when the Receiver boot ID is unchanged. Old
commands and finalizers cannot act on a replacement owner. EOF, timeout, failed
response or rejected commands release authority before any error response is
written. If closeout fails, `LeaseRegistry.hold()` permanently denies authority
without reconstructing a clock; recovery needs a fresh registry generation.

At most four accepted connections execute per controller. Unauthenticated peers
can occupy these slots until their bounded frame deadlines. The caller must
provision the listener and restrict access; this module does not create a socket
path, verify its directory ownership or mount permissions, or load a mode-0400
secret. The caller must also give this adapter exclusive control of its registry.
Local socket tests do not establish deployed UID/mount/kernel or secret isolation.

## Private listener and shutdown

`PrivateControlListener` creates one filesystem Unix socket beneath an
operator-provisioned absolute parent with exact owner UID, control GID and mode
0710. A fresh exclusive child stays private during preparation, then publishes
as mode 02710 with a mode-0660 socket. The complete endpoint is limited to 100
encoded bytes. Directory descriptors anchor identity checks and cleanup; parent
and endpoint permissions are checked before and after accepting a connection.
Accept has a finite deadline of at most one second. Accepted sockets still need
`ForwarderControl` authentication before they can control leases.
Use one accept caller at a time. A lifecycle lock protects open/close and
filesystem guards, while close can interrupt the blocking accept. The returned
endpoint and accepted socket are observations at their checks; later shutdown
still requires the controller's admission gate and caller-owned worker tracking.

The operator must establish stable protected ancestors, trusted group membership,
ACL and mount policy, and distinct deployed identities. Local pathname checks
cannot establish these conditions. Cleanup preserves replaced or unexpectedly
populated paths and reports `unknown`; it never recursively removes a directory
or sweeps stale endpoints. Portable identity-check/unlink operations do not form
an atomic guarantee against trusted same-UID/operator filesystem mutation.

`ForwarderControl.shutdown()` permanently holds lease authority under the same
lock used for admission, then interrupts all admitted sockets outside that lock.
Later connections receive `control_closed`, including when old handlers still
occupy every slot. Call it before removing the private listener. Socket closure
does not prove handler completion: the caller must observe or join its workers.
A held registry requires a fresh controller and registry generation for recovery;
failed revocation remains `unknown` rather than a successful closeout receipt.

## Managed local control service

`ControlService` owns an unopened `PrivateControlListener` and an unused
`ForwarderControl`. Its constructor starts no work; `start()` opens the endpoint
and starts one accept loop. The service admits at most four handler threads,
retaining their records until thread termination is observed. One additional
transient accepted socket can belong to the accept loop during dispatch or
capacity rejection; there is no user-space queue of waiting clients.

Use `stop(timeout=2.0)` to hold controller authority, close owned descriptors and
the listener, and observe the accept loop and handlers against a shared join
deadline. The finite timeout must be positive and at most ten seconds. A
`ServiceCloseout` reports `state`, `reason`, `listener_state` and `threads_alive`.
The reason records the shutdown request or failure; `state` determines whether
cleanup completed. Thus a requested stop can have reason `stopped` and state
`unknown` while threads or startup work are still pending.
`stopped` requires completed cleanup and no live owned threads; `unknown` keeps
incomplete joins, fatal failures and uncertain endpoint cleanup visible. A later
stop may observe that threads exited, but cannot convert uncertain endpoint
cleanup into a successful removal receipt. Python scheduling and OS stalls are
not hard real-time bounded by this join timeout.

Start and stop are terminal: a stopped service never restarts its held registry
generation. Authentication failures from ordinary clients do not themselves
poison the service. Unexpected accept/worker orchestration failures initiate
shutdown with fixed diagnostics. The owner must keep this service's listener and
controller exclusive; importing or constructing it does not wire the legacy
launcher, load a secret or establish deployment isolation.

## Fixed service TLS client boundary

`connect_service_tls(service, ca_pem=..., timeout=1.0)` returns an exclusively
caller-owned SSL socket connected to the service profile's fixed IPv4 loopback
address and port. It sends no application bytes, accepts no alternate destination,
and performs no DNS lookup, proxy selection or retry. A successful connection is
a transport observation; it supplies no lease or request authority.

The function accepts only bounded public CA certificate PEM supplied in memory,
with no private-key blocks or non-CA certificates. It creates a fresh client
context with certificate and hostname verification, TLS 1.2 or newer, and no
common-name fallback. It loads only that CA bundle, without loading system roots,
environment settings or files. Python documents these verification controls in
the [ssl reference](https://docs.python.org/3.13/library/ssl.html).

After the verified handshake, the certificate must name exactly the fixed service
DNS identity and 127.0.0.1 in its SAN. Wildcards, additional identities and missing
IP SANs are rejected. Leaf validity must be positive and at most 24 hours, with
at least ten minutes remaining. These are the local ticket-36 certificate-policy
bounds, not evidence of deployed CA custody or certificate rotation.

One monotonic deadline covers TCP connect, TLS handshake and certificate policy
evaluation. Clock faults or regression deny the connection. Setup failures close
owned sockets; interrupted setup still attempts cleanup. If close and detach both
fail, the code preserves the original failure rather than closing a descriptor
still owned by another socket object. Exceptions do not report raw SSL details.
The caller owns request deadlines and socket closure after a successful return.

Tests use real local TLS handshakes and synthetic certificates. A test adapter
asserts the selected fixed destination before connecting to an ephemeral fixture
port; this does not qualify actual fixed-port listener binding or native clients.

## Common HTTP request structure

`parse_request(data, service, allowed_query_keys=frozenset(),
accept="application/json")` validates one complete byte buffer. It accepts
HTTP/1.1 origin-form requests using the deliberately narrow local profile in
`forwarder_http`. The parser rejects ambiguous framing and path aliases, drawing
on the message syntax in [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html)
and URI grammar in [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986.html). This
profile is stricter than general HTTP syntax; native client compatibility still
requires separate evidence.

The request line including CRLF is at most 2 KiB; headers after that line,
including the final blank CRLF, are at most 16 KiB and 64 fields; the body is at
most 256 KiB. GET permits no body, absent length or canonical zero. POST, PUT,
PATCH and DELETE require an exact canonical Content-Length and application/json
Content-Type. The body is preserved as bytes; route-specific JSON validation is
still required. Any captured bytes beyond the declared body are rejected.

Host must match the selected service DNS and fixed port. Authorization and Accept
are required. The narrow header allowlist also permits Content-Length,
Content-Type and an optional User-Agent, which is discarded. Every duplicate or
unrecognized header fails closed. The expected Accept and query-key allowlist
are trusted route configuration, never caller-requested authority. Queries are
denied by default. Values require separate operation-specific validation; decoded
query delimiters remain values and must be safely encoded if reconstructed.

Jira and Confluence use canonical Basic credentials with user `run` and the lease
sentinel as password. The other services use canonical Bearer sentinels. Each
sentinel must encode exactly 32 bytes as unpadded base64url, including canonical
pad bits. The immutable result excludes path, query, body and sentinel from its
representation and retains no raw headers. Parsing only extracts the token;
the current generation, lease, service and scope must still be checked.

This module opens no sockets and grants no dispatch or readiness authority. A
future server must bound receipt while collecting the buffer, enforce TLS and
absolute deadlines, close after one request, select an authorized route, and
coordinate lease checks with dispatch and revocation. A complete-buffer parser
cannot detect bytes that arrive later or establish deployed transport behavior.
The existing launcher is not wired to it.

The next integration units are fixed server-side TLS listeners and
request-aware service policies, followed by durable admission and the guarded
launcher. Real provider/tenant operations, native execution and deployment remain
gated by their own acceptance evidence. Local module tests cannot replace that
evidence or human Report adjudication.

Run the focused local tests from the repository root:

```sh
pytest -q tests/test_forwarder_services.py tests/test_forwarder_leases.py tests/test_forwarder_control.py tests/test_forwarder_control_protocol.py tests/test_forwarder_listener.py tests/test_forwarder_listener_control.py tests/test_forwarder_supervisor.py tests/test_forwarder_supervisor_integration.py tests/test_forwarder_tls.py tests/test_forwarder_tls_integration.py tests/test_forwarder_http.py tests/test_forwarder_http_adversarial.py
```
