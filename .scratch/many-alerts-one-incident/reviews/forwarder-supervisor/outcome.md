# Bounded control-service supervision outcome

2026-09-22. PASS for separately authorized local application source and synthetic
tests. The user-requested push completed through b592df8 before this continuation.
This new implementation unit remains local; no further push or deployment occurred.

`ControlService` joins an unopened private listener and unused authenticated
controller under one terminal lifecycle. One accept loop owns at most four
handler threads and one transient accepted descriptor. Startup publication and
socket handoff stay tracked through failure or concurrent stop. Shutdown holds
controller authority before endpoint removal, closes owned descriptors and
observes the accept thread and handlers against one shared join deadline.

Closeout preserves unknown endpoint cleanup, pending starts, live threads and
fatal orchestration failures. A handler stopping the service cannot certify its
own exit. Later external observation may confirm thread completion without
reviving the held controller. Ordinary authentication rejection does not poison
the service. Unused/exclusive dependency ownership remains a caller precondition.

Terra workers implemented the supervisor and 20 lifecycle/failure tests. Root
added five integration tests for actual pathname authentication and leases,
rejected-client recovery, hold-before-removal, self-stop and shared join budgets.
Sol's [independent review](review.md) passes at the recorded source/test hashes.

The first full suite found one existing TLS test failure: concurrent send and
receive on the same test-client SSL object produced SSLV3_ALERT_BAD_RECORD_MAC.
The [failed-run log](full-suite-before-tls-test-fix.txt) records 1 failed, 1033
passed and 36 skipped. Root repaired only that test's coordination: a single
thread sends the slow drip, observed peer closure and the original elapsed bound
are required, and no upstream receipt is allowed. Specific closure errors are
accepted; other TLS record errors still fail. Sol reviewed that patch separately.
No fixture transport or production behavior changed for this repair.

Validation on final files:

- Supervisor/listener/control group: **80 passed in 11.99 seconds**.
- Mediated-client regression module after final repair: **50 passed in 5.85 seconds**.
- Full repository rerun: **1034 passed, 36 skipped in 151.45 seconds**, exit 0.
- Ruff and code/document whitespace checks passed. The raw failed-test output
  retains pytest's trailing whitespace verbatim. Protected ticket-19 and historical
  planning-frontier files retain their prior hashes and are excluded from commit.

The [validation record](validation.json) binds source, tests, documentation and
the [full-suite log](full-suite.txt). All sockets and certificates used here are
local fixtures with synthetic secrets. This does not qualify Linux peer identity,
deployed UID/group/ACL/mount isolation, mounted-secret custody, native model
clients, provider/tenant behavior, paid accounting or human Report adjudication.
No C2 retry or modification occurred.

Next local work is fixed service TLS and request policies, then durable
Receiver/accounting integration. The supervisor is not wired into the legacy
launcher. Existing native/provider/deployment gates remain; no further user input
is required for the authorized local source/test continuation.
