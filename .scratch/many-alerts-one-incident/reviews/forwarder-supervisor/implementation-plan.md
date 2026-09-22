# Bounded control supervisor implementation plan

2026-09-22. Baseline b592df8, pushed at the user's explicit request before this
local continuation. Consume the reviewed next-supervisor-unit.md in the sibling
forwarder-listener directory. No native, provider, credential, deployment or C2
work. Preserve the four unrelated dirty files. Full tests precede local commit.

Terra owns grafana_jsm_sandbox/forwarder_supervisor.py; a separate Terra worker
owns tests/test_forwarder_supervisor.py. Root owns integration tests, docs and
evidence. Sol reviews the final source and tests independently.

## API

`ControlService(listener: PrivateControlListener, control: ForwarderControl)`
owns a fresh unopened listener and unused controller exclusively. It starts no
work in its constructor. `start()` opens the listener and starts one accept
thread, returning self. It may run only once; fixed `ServiceError.code` rejects
invalid lifecycle or configuration. `endpoint` returns the listener path only
while running. No raw exception/path/secret data enters diagnostics.

`stop(*, timeout=2.0)` initiates permanent shutdown, then observes all owned
threads against one monotonic deadline (finite positive timeout at most ten
seconds, excluding Python/OS scheduling stalls). Return frozen `ServiceCloseout`
with `state` (stopped or unknown), `reason` (fixed code), `listener_state`
(removed, unknown or not_open), and `threads_alive` (includes accept thread).
Stop before start is terminal, holds the controller, and may report stopped with
not_open because no endpoint was ever created. Start failure raises a fixed error
and runs cleanup; later stop still observes the result. A service that published
an endpoint needs removed for clean completion. Unknown endpoint cleanup never
becomes removed merely because threads exit. Later stop may refine thread
completion after a prior timeout, but never reopens or revives authority.

## Ownership and concurrency

One accept loop, at most four handler threads (including started threads whose
wrapper is finishing), no unbounded queue or completed-thread history. Retain
worker thread records until is_alive() is false, then reap. At most one additional
transient accepted descriptor belongs to the accept loop; track it before worker
dispatch and close it synchronously on capacity denial. Thus at most five
user-space accepted descriptors can be owned, with at most four executing
handlers. This makes the reviewed draft's transient handoff bound explicit.

Reserve and publish the handler record before Thread.start, with a synchronized
handoff that prevents worker completion racing start publication. Start failure
closes that descriptor and releases its reservation; any ambiguous started thread
remains tracked. Catch unexpected BaseException in worker wrappers, close the
owned descriptor in finally, and trigger fatal shutdown. Normal ControlOutcome
rejection/EOF is not an orchestration failure. Do not retain unbounded outcomes.

Serialize lifecycle transitions and shutdown initiation. Set stopping before
snapshotting sockets or workers. Hold controller authority via shutdown before
closing the listener. Close any transient accepted descriptor and every worker's
owned socket even if it has not entered the controller yet. Never hold the service
state lock across socket I/O or joins. An accept error while running and an
unexpected worker error initiate the same fatal stop path, preserving fixed
failure reason. Internal threads initiate cleanup but do not perform blocking
joins; external stop observes completion. Never join oneself. Include accept
thread and all handler threads in the shared join deadline; a self-join case
remains unknown while that caller thread lives. One cleanup failure must not
suppress the remaining cleanup or thread observation. Fatal failures can produce
unknown outcome even when resources were subsequently cleaned.

## Validation and remaining work

Use real temporary pathname sockets and synthetic secrets for authentication,
lease shutdown, four occupied workers and excess clients. Use deterministic
events/barriers and narrow injection for thread-start failure, accept failure,
worker BaseException, stop/accept races, concurrent stops, unknown endpoint
preservation and bounded joins with eventual completion. No sleep-based races.
Check that diagnostics omit injected details. Run focused tests, independent
review, full repository suite, then commit only owned files locally.

Fixed service TLS/request policies, durable Receiver/accounting, mounted secret
loading, Linux peer credentials and deployment/native/provider acceptance remain
separate units. This class is not wired into the legacy launcher.

## Full-suite test coordination repair

The first full-suite run found an existing slow-drip TLS test reading and writing
one client SSL object concurrently, producing SSLV3_ALERT_BAD_RECORD_MAC. Root
owns a narrow repair in tests/test_mediated_client.py: send the slow drip from one
thread, require observed peer closure before the existing total deadline bound,
and assert no upstream receipt. Only explicit connection-close/EOF exceptions
count as closure; generic TLS record errors remain test failures. Preserve the
failed-suite log, independently review the test change, and rerun the full suite.
No fixture transport or production behavior changes are included in this repair.
