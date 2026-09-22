# Fixed-service TLS client implementation outcome

2026-09-22. PASS for the separately authorized local source/test unit, based on
74978ac. This unit is local only; no push or ticket closure.

`connect_service_tls` selects only immutable service profiles and returns an
owned verified TLS socket without sending application bytes. It uses explicit
CA-only trust, TLS 1.2 or newer, exact service DNS plus loopback IP SANs, bounded
certificate validity and one TCP/handshake deadline. It rejects invalid inputs
and clock observations with fixed diagnostics and preserves socket ownership
through setup and cleanup. It is not a lease check, request permit or readiness
attestation.

Two Terra workers implemented source and unit tests. A separate Terra worker
provided [independent source review](review.md); root reviewed the boundary and
added real TLS integration tests. The planned Sol review could not be dispatched
because the agent thread limit was reached. Review corrected cleanup to close a
raw descriptor only after successful detach transfers ownership, preventing an
unsafe double-close if both ordinary close and detach fail.

Validation on the frozen source/test hashes in [validation.json](validation.json):

- Focused suite: **52 passed in 2.15s** (34 unit and 18 integration tests).
- Full suite: **1086 passed, 36 skipped in 143.83s**, exit 0.
- Ruff and whitespace checks passed.
- All five service identities completed real local TLS handshakes with no
  application bytes. Negative cases cover CA, SAN, certificate validity,
  plaintext peers and handshake deadlines; unit tests cover clock faults,
  exact lifetime boundaries and cleanup ownership.

Integration fixtures generate temporary synthetic keys and redirect the asserted
fixed destination to an ephemeral loopback server. This proves destination
selection and TLS verification, not actual fixed-port server binding or native
client configuration. Successful fixture shutdown uses TLS close-notify without
concurrent operations on one SSL object.

No provider/tenant calls, native client execution, real credential access,
deployment, paid attempt, C2 retry or human Report adjudication occurred. The
four protected dirty artifacts remain byte-identical and outside the commit.
Ticket 36 retains its planning-only status; implementation uses separate approval.

Next local work is server-side fixed TLS listeners and request-aware policies,
followed by durable Receiver/recovery and accounting integration. Native and
deployed identity/custody, Linux isolation, aggregate paid exposure and human
Report acceptance retain their existing gates. No further local implementation
scope approval is required.
