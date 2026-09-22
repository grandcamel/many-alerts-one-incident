# Next local unit: bounded control-service supervision

Draft queue input, 2026-09-22. This continues the separately approved local
application implementation scope; it does not authorize deployment or a native
client. Review API and race contracts before implementation.

Join `PrivateControlListener` and `ForwarderControl` in a local owner that starts
one accept loop and at most four handler workers. Admission must reserve worker
capacity before thread creation, with no unbounded accepted-socket queue. A
capacity rejection closes its socket without exposing input or credentials.
Control authentication remains exclusively in `ForwarderControl`.

Define one terminal start/stop lifecycle. Stop must first invoke controller
shutdown so all lease checks fail, then close the listener and join every owned
worker against one bounded deadline. A timeout or exception produces explicit
unknown completion; it must not claim thread termination, revocation or clean
endpoint removal. A subsequent call can observe completion without reopening
the held controller or reusing a registry generation.

Track accept failures and worker completion with bounded, nonsecret summaries.
A fatal accept/worker orchestration failure holds authority and enters the same
shutdown path. Never join the current thread. Define ownership transfer for an
accepted descriptor at every thread-start failure and shutdown race. Unexpected
thread exceptions must not leave an unobserved active service.

Use temporary filesystem sockets and synthetic secrets for successful
authentication and shutdown, four occupied slots, excess clients, thread-start
failure, accept failure, stop during acceptance and bounded worker join failure.
Use events/barriers for races; do not replace real descriptor and handler evidence
with test doubles alone. Independent review and the full repository suite precede
the local commit.

## Independent review additions

The bounded plan review requires the accept-loop thread in the owned join set,
not just handlers. Publish started only after successful thread start, and make
concurrent start/stop terminal and serialized. Start failure enters shutdown;
there is no second start or reuse of the controller/registry generation.

Specify descriptor ownership across acceptance, reservation, worker publication
and thread start. Workers may begin before `Thread.start()` returns, so the final
implementation must coordinate this handoff explicitly. Release each reservation
exactly once, including unexpected worker exceptions and thread-start failures.
Track pending starts and accepted descriptors as well as running handlers; the
controller's own slot limit is a second gate, not supervisor accounting.

Capture one monotonic join deadline and spend only remaining time across the
accept thread and handlers. An owned thread must never join itself; its stop
receipt stays incomplete until an external observer confirms its exit. Serialize
shutdown initiation and preserve the first endpoint closeout. One exception must
not suppress the remaining cleanup/join observations.

Define clean completion as held controller authority, removed listener, dead
accept loop, dead handlers, and no outstanding descriptor handoffs. A join timeout
can later gain evidence of thread completion; a terminal unknown endpoint
closeout cannot be upgraded to removed or successful revocation by that evidence.
Diagnostic summaries remain fixed, bounded and nonsecret.

This unit would still leave fixed service TLS/request policy, secret loading,
Linux peer validation, durable Receiver admission/accounting, native client
compatibility and deployment acceptance open. The service owner is a local
building block and must not be silently wired into the legacy launcher.
