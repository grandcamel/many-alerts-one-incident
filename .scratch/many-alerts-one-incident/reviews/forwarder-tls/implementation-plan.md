# Fixed service TLS client boundary

2026-09-22. Local source/test follow-up under the existing approval, baseline
74978ac. No push, deployment, native/provider/tenant requests, real credential
access or C2 changes. Preserve protected dirty files. Full tests before commit.

Implement grafana_jsm_sandbox/forwarder_tls.py with
`TLSBoundaryError(ValueError)` carrying fixed `.code` and
`connect_service_tls(service, *, ca_pem, timeout=1.0) -> ssl.SSLSocket`.
The caller exclusively owns the returned socket and must close it. It is a TLS
transport connection, not a request permit, scope decision, lease check or Run
readiness attestation. No HTTP/application bytes are sent by this function.

Select only the immutable SERVICE_PROFILES service name. No host, port, upstream,
DNS, proxy, insecure mode or alternate address argument. Connect an explicit
AF_INET/SOCK_STREAM socket to the profile's 127.0.0.1/fixed port. Send its exact
server_name as SNI and hostname-verification identity. Do not retry/fallback.

Only caller-supplied public certificate PEM trust is accepted: exact str, ASCII,
nonempty, at most 128 KiB and 16 CERTIFICATE blocks; reject extraneous data,
private-key material, malformed PEM and non-CA certificates. A fresh strict
client SSL context trusts only the supplied CA bundle (no default/system roots),
requires certificate validation and hostname verification, disables common-name
fallback and permits TLS1.2 or newer. No caller-supplied mutable context. No
filesystem or environment credential/trust loading and no system trust changes.

After a successful verified handshake, require exact certificate SAN entries:
one DNS name equal to that service's server_name and one IP Address 127.0.0.1;
reject duplicates, wildcards, other identities or malformed decoded fields.
Require finite UTC notBefore/notAfter, positive validity at most 86400 seconds,
notBefore <= current wall time and remaining validity at least 600 seconds.
These implement the proposed ticket-36 certificate policy locally; they do not
establish a deployed rotation or CA custody process. Never accept certificate
dicts supplied by an external caller as a substitute for a verified handshake.

Timeout is an exact int/float, finite positive and <=10 seconds; bool/huge ints
fail with fixed diagnostics. Capture one monotonic deadline before TCP connect;
reset only the remaining timeout for TLS handshake, and check expiry before
return after certificate policy evaluation. Context construction is bounded by
input size but not a hard real-time operation. Reject faulty/nonfinite or
regressing clock observations. Close raw/wrapped sockets on every failure,
including interrupted setup. All descriptors non-inheritable. Return no raw
certificate/SSL/error/input material in failure messages.

Terra owns the module, another Terra worker owns tests/test_forwarder_tls.py
(input/clock/deadline/ownership unit tests). Root owns
tests/test_forwarder_tls_integration.py (real local TLS certificates/handshakes),
docs/evidence and full suite. Independent review was planned for Sol; the agent
thread limit prevented that dispatch. A separate existing Terra worker reviewed
the final source and tests, alongside root review.
No worker runs the full suite independently.

Integration tests generate synthetic CA/leaf keys only under temporary paths.
To avoid fixed-port collisions among test runs, a test socket adapter redirects
the asserted fixed production destination to its ephemeral local fixture port.
It preserves a real TLS handshake and verifies intended address selection;
it does not qualify actual fixed-port listener binding. Test all five service
identities, wrong CA/name/SAN, expired/not-yet-valid/near-expiry/overlong leaves,
plain non-TLS peers and stalled handshake deadline. Do not swallow generic TLS
errors as successful closure or use concurrent send/recv on one SSL object.

Reference: Python's official ssl documentation describes certificate/hostname
verification, explicit trust, protocol versions and common-name fallback:
https://docs.python.org/3.13/library/ssl.html

Next work remains fixed server-side TLS listeners, request-aware service
policies and durable Receiver/accounting integration; no legacy launcher wiring.
