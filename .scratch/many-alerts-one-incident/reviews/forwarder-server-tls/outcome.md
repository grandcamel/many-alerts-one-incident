# Fixed service TLS listener outcome

2026-09-22. PASS for the separately authorized local application unit, baseline
6e3f005. This unit is local only; no push or planning-ticket closure.

`FixedTLSListener` adopts one exclusively owned operator-configured server TLS
context and binds one fixed IPv4 loopback service port. It rejects missing or
wrong SNI, configures TLS 1.2 or newer and HTTP/1.1 ALPN, and accepts one client
under a shared finite accept/handshake deadline. It reads no application bytes,
loads no certificate/key files and grants no request, lease or dispatch authority.

Two Terra workers implemented source and unit tests. A separate Terra worker
provided [independent source/test review](review.md); root reviewed the ownership
boundary and wrote real local TLS integration tests. Source review corrected
cleanup races, retained failed-close handles, interrupted-open cleanup and accept
gate release on timeout-restoration faults. Unknown cleanup permanently denies
later accepts and cannot become a clean receipt simply because a retry succeeds.
Returned connections remain caller-owned and survive listener close.

Real Darwin testing exposed an idle accept that stayed blocked despite close:
the initial integration run reported 1 failed and 17 passed in 5.85s. The fix
polls idle accept in at most 0.1-second slices against the original deadline,
without retrying a connection or handshake. The original bounded shutdown
assertion was retained and strengthened with an entered-accept event.

Validation on the frozen hashes in [validation.json](validation.json):

- [Focused suite](focused-tests.txt): **49 passed in 1.76s**, exit 0
  (30 deterministic unit tests and 19 real local integration tests).
- [Full suite](full-suite.txt): **1239 passed, 36 skipped in 138.37s**, exit 0.
- Independent source/test review, Ruff, compile and whitespace checks passed.
- Real TLS client/listener/parser composition across all five services, missing
  and wrong SNI rejection, HTTP/1.1 ALPN, plaintext/stalled handshakes, close
  during accept/handshake, and survival of caller-owned returned connections.
- Actual prescribed fixed-port binds and exclusive occupancy for all services,
  with visible failure on conflicts and no alternate port or occupant removal.

Handshake fixtures separately redirect asserted fixed destinations to ephemeral
ports. Fixed-port tests establish local bind/exclusivity only; neither fixture
qualifies deployed routing/namespace isolation. HTTP fixture collection uses a
known byte length; production bounded receipt/response remains unimplemented.
The operator supplies an unused certificate-configured context and must not
retain mutable use after transfer. The ownership marker cannot enforce that
trusted-caller obligation. Opening is not certificate/readiness acceptance;
strict clients must still verify CA, SAN and lifetime.

The four protected dirty artifacts remain byte-identical and outside the commit.
No actual credentials, provider/tenant requests, native client execution, C2 retry,
paid experiment, deployment or human Report adjudication occurred. Ticket 36
remains planning-only; this unit uses the separate application implementation
approval. No new scope permission is needed for the next local unit.

Next: bounded HTTP receipt/response and route policies coordinated with lease
revocation/dispatch, followed by durable Receiver/recovery/accounting integration.
