# Independent bounded-supervisor review

2026-09-22. Verdict: **PASS for this local source unit**. I found no remaining blocking source or test issue in the frozen candidate.

Reviewed SHA-256:

- `grafana_jsm_sandbox/forwarder_supervisor.py`: `6b8ad99cd7865a283b50736632a24876c17c42d074d9a69f6c55ba5ad9acfab1`
- `tests/test_forwarder_supervisor.py`: `5f0a86b8b9797df892bf6b53e577712c86859939a1e66dc2ebd57b224b43ff9b`
- `tests/test_forwarder_supervisor_integration.py`: `aa430d35ff4e6845ca7b3c7ac4d87480afd65030aebc9c95ee71a9bf7865c54d`

The service changes phase to stopping before cleanup, elects one cleanup owner, holds controller authority before listener removal, and keeps concurrent observers from claiming completion while cleanup is in progress. The accept thread is gated until start publication and included in the join set. Accepted sockets remain owned through the transient handoff, capacity rejection, worker reservation, start failure, and shutdown. At most four worker records are admitted, with one transient accepted socket; records are reaped after thread completion. Unexpected `BaseException` in accept and worker paths initiates fatal cleanup. Unconfirmed descriptor closure and unknown listener removal keep the closeout unknown. The stop deadline is captured once, applied to cleanup observation and all joins, and self-join is excluded. No service state lock spans socket operations or joins.

The local tests cover real pathname sockets with synthetic credentials, authentication and held leases, four occupied workers and excess rejection, accept and worker start failures, start/stop races, concurrent stops, unknown endpoint preservation, handler self-stop, and a shared decreasing join budget. The coordinator reported **80 focused tests passed** across the supervisor, listener, and control tests for this candidate. I did not independently run the full repository suite; full-suite validation and the local commit remain coordinator-owned. This review does not establish native, provider, tenant, deployment, C2, or credential acceptance.

## Full-suite test repair review

The first full-suite run reported **1 failed, 1033 passed, 36 skipped**. The failure was the pre-existing `test_slow_drip_tls_request_has_a_total_connection_deadline`: its dripper thread called `SSLSocket.send` while the main test thread called `SSLSocket.recv` on the same object, and the client observed `SSLV3_ALERT_BAD_RECORD_MAC`. The failure log is retained separately by the coordinator.

I reviewed the narrow test-only revision at `tests/test_mediated_client.py` SHA-256 `830e293ae25bc6abbdd1b49f9f75ab800b2fd8968cc6d9d2970aa23f20dcdbaa`. The drip is now driven on one client thread. The test still requires observed peer closure before its two-second guard, elapsed time below the connection budget plus 0.5 seconds, and no upstream receipts. It accepts only specific socket/TLS closure errors; unrelated TLS record errors propagate as test failures. This preserves the deadline assertion without concurrent operations on one SSL object. The coordinator reported the targeted test passed on this final hash. The module and full-suite reruns are coordinator-owned and were pending when this addendum was written.
