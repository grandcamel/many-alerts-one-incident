# Bounded TLS request collection outcome

2026-09-22. PASS for separately authorized local application implementation, baseline
`a71fa1c`. Validation totals and final verdict are recorded in validation.json.
No push or planning-ticket closure.

The eighth local unit adds incremental one-request TLS collection. Shared pure
head parsing validates framing before body collection without allocating a dummy
body. The collector preserves opaque bytes, independently bounds line/header/body
reads, and enforces the caller's absolute deadline across fragments. A permanent
socket claim prevents concurrent or repeated collection. Timeout restoration
cannot falsely return success or mask the original failure.

Two Terra workers handled bounded source and test implementation; another Terra
worker independently reviewed frozen source/test hashes. Root added head-contract
and real local TLS integration tests and corrected restoration/error precedence
and final clock checks. See [review.md](review.md) for the final review verdicts.

The first full suite exposed an existing Darwin shutdown failure: a stalled TLS
handshake remained blocked after close. Its [original failure log](full-suite-before-handshake-fix.txt)
is retained (1 failed, 1291 passed, 36 skipped). The corrected listener advances
nonblocking handshake steps and waits for read/write readiness outside its state
lock in at most 0.1-second slices under the original deadline. Fatal SSL errors
are not retried. The original real-TLS shutdown assertion remains byte-identical
and passed five separate repeated test runs after correction. The corrective
source and deterministic tests received independent review.

Evidence:

- [HTTP focused tests](focused-tests.txt): 157 passed (104 existing parser tests,
  12 head-contract, 29 collector unit and 12 real local TLS tests).
- [TLS regression tests](tls-regression-tests.txt): 52 passed (33 unit, 19 real
  local integration tests), including the corrected shutdown behavior.
- [Shutdown repetitions](shutdown-regression-repeat.txt): five separate passes
  of the original stalled-handshake integration assertion.
- [Full-suite result](full-suite.txt): **1295 passed, 36 skipped in 154.09s**,
  exit 0. Ruff, compilation and code/document whitespace checks pass.
- Exact artifact hashes are recorded in [validation.json](validation.json).

The caller owns each returned TLS socket and must close after one response or
any error. Exact body completion does not wait for EOF or probe for a later byte;
already captured excess is rejected, but another unread TLS record or later
bytes cannot be detected by this collector. Those bytes cannot be collected as
a second request. Parser/collector success grants no route, lease or dispatch
authority. The supplied service and lease-clipped deadline remain caller duties.

The four protected dirty artifacts remain untouched. Synthetic certificates and
real local TLS fixtures do not qualify native clients, deployed credentials or
namespace isolation. No actual credentials, upstream/provider/tenant/native
execution, C2 retry, paid experiment, deployment or human Report adjudication
occurred. Ticket 36 remains planning-only; this follow-up uses the separate
application implementation approval.

Next: bounded response handling and request-aware service policy, followed by
atomic lease/revocation/dispatch coordination and durable Receiver/recovery and
accounting. Existing local source authority covers that work; no user action is
needed to start the next local unit.
