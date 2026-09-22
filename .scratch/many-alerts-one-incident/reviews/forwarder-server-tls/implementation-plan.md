# Fixed service TLS listener implementation plan

2026-09-22, baseline 6e3f005. Local application source/tests under standing scope.
No push, actual secret reads, native/provider/tenant calls, deployment or C2 work.
Only temporary synthetic TLS certificate/key fixtures may be loaded in tests.
Preserve the four protected dirty files. Full suite before code commit.

Module: grafana_jsm_sandbox/forwarder_server_tls.py.
API: FixedTLSListener(service: str, *, context: ssl.SSLContext), open() -> None,
accept(*, timeout: float = 1.0) -> ssl.SSLSocket, close() -> str (closed/unknown).
TLSListenerError(ValueError) exposes fixed nonsecret code/message and no raw
exception chaining. Constructor opens no socket, reads no files, starts no worker.

The trusted operator transfers exclusive ownership of a fresh, unused exact
SSLContext instance with PROTOCOL_TLS_SERVER and its server certificate/key
already loaded. The caller must never mutate/use it afterwards or share it with
another service. Reject a non-None keylog_filename; TLS secret logging is not
permitted. Serialize ownership-marker check/set with one module-level lock;
failed adoption after claiming does not release the context. Capture only the
expected service name in the SNI callback. This is an explicit trusted dependency, not untrusted input or
an attestation of certificate/key custody. No mutable context getter. Mark the
context claimed using a private ownership marker; deny duplicate adoption. Set
minimum TLS1.2 and maximum MAXIMUM_SUPPORTED, disable client certificate auth
(CERT_NONE; per-request sentinels authenticate clients), and select HTTP/1.1 as
the sole ALPN protocol. Install a fixed SNI callback that returns
ALERT_DESCRIPTION_UNRECOGNIZED_NAME for absent/wrong SNI. No default service,
context switch, key/certificate or upstream fallback. The strict client/readiness
probe separately verifies server CA, SAN and lifetime; listener open is not
readiness or proof of a certificate being loaded.

Only exact known service names select immutable SERVICE_PROFILES. open binds
one AF_INET/SOCK_STREAM non-inheritable socket to the exact fixed loopback port
and listens with backlog4. No SO_REUSEPORT, SO_REUSEADDR, wildcard, alternate port,
DNS or fallback. A bind/listen/setup failure permanently closes the instance,
cleans owned sockets and raises a fixed error. open is one-shot (never restart
or silently reopen); repeated open rejects. close before open is terminal.

At most one accept caller per instance, enforced without waiting for another
accept. Others get a fixed busy error. A single finite positive timeout <=10s
(exact int/float, not bool/NaN/inf/huge ints) covers accept and explicit TLS
handshake, with nonfinite/regressing monotonic observations denied. All accepted
sockets are non-inheritable. wrap_socket(...server_side=True,
do_handshake_on_connect=False), then handshake with remaining timeout; check
final deadline and terminal state before returning ownership to the caller.
No application reads/writes, request permit, lease check, response or dispatch.
Accept timeout/peer handshake failure cleans that connection and leaves an open
listener available for a later attempt. Idle accept uses <=0.1-second polls clipped
to the original deadline, checking close between polls; this waits for one
admission and does not retry a connection or TLS handshake.

A state lock serializes socket ownership transfer, terminal state and wrapping
(the wrap itself must not handshake while locked); a separate nonblocking gate
serializes accept callers. close may interrupt a pending raw accept or TLS
handshake by shutting down/closing the retained listener and in-flight socket.
No window may lose ownership of a just-accepted socket or raw-to-SSL transfer.
An active accept operation must be tracked until its final cleanup, including
when close wins a race before the accepted socket is recorded. Previously
returned connections belong exclusively to the caller and close must not touch
them. No background worker is created by this class.

close reports closed only after all owned descriptors close successfully and
no accept operation remains active. If accept is still exiting, return unknown;
a later close may observe completion. Descriptor-close exceptions/failure to
observe fileno<0 latch unknown permanently; preserve safe handles for retry and
never close a raw fileno without a verified ownership transfer. Do not hide a
failed descriptor close by returning closed on a later call. Context ownership
cannot be reused/released after close. Python/OS stalls are not hard real-time
bounded by lock acquisition/close. Caller owns thread joins and returned sockets.

Terra implementer owns module only. Terra tester owns
tests/test_forwarder_server_tls.py (input, lifecycle, deadlines, ownership and
failure paths). Root owns tests/test_forwarder_server_tls_integration.py for
real TLS, SNI rejection, strict-client composition, plaintext/stall handling,
close-during-accept/handshake and single-use lifecycle, plus docs/evidence.
Reuse temporary synthetic certificate fixture via explicit pytest fixture import
from test_forwarder_tls_integration where practical, without modifying old tests.
Ephemeral bind adapters must assert the fixed production address and declare
that limitation. Also test actual fixed bind/exclusive occupancy for every
service without killing any occupant; conflicts fail visibly rather than fall
back. An independent reviewer inspects frozen source/tests. Root full suite.

Remaining local work: bounded HTTP receipt/response and route policies with
lease/dispatch coordination, then durable Receiver/recovery/accounting. No legacy
launcher wiring or native/deployment acceptance is supplied by this unit.

## Review corrections

Root source review required cleanup and close to serialize ownership, retained
handles on failed cleanup with denial of later accepts, interrupted-open cleanup,
and unconditional accept-gate release despite timeout-restoration faults. Real
Darwin testing showed close alone did not promptly wake idle accept; the original
1.5-second completion assertion was retained and deadline-clipped polling added.
The operator supplies the exclusively owned configured context; no certificate
loader, native configuration or protected key-mount acceptance is implied.
