# Authenticated Forwarder control session: local implementation plan

2026-09-22. Separate local implementation authorized by the existing runtime
source approval. Baseline `67454b3`; planning ticket 36 remains open.

## File ownership and sequence

1. Terra implements `grafana_jsm_sandbox/forwarder_control_protocol.py`: bounded
   length-prefixed JSON frames over an already accepted Unix stream socket.
   A separate worker owns `tests/test_forwarder_control_protocol.py`.
2. Root implements `grafana_jsm_sandbox/forwarder_control.py` and
   `tests/test_forwarder_control.py`: OS peer UID extraction, challenge/response,
   one active controller session, exact commands and lease dispatch, EOF and
   replacement closeout. Add documentation and evidence after focused validation.
   Root also adds a no-clock `LeaseRegistry.hold()` latch so an exceptional
   control closeout cannot leave check authority usable. It has no wire command
   and no reset operation; recovery requires a fresh registry generation.
3. Independent review of source and negative tests, root integration review,
   then the full suite before a local commit. Preserve the four unrelated dirty
   C2/planning-frontier files. No push or credential/provider/native operations.

## Protocol module API

`MAX_FRAME_BYTES = 8192`; `FRAME_TIMEOUT_SECONDS = 10.0`.
`ControlProtocolError(ValueError)` carries a fixed `.code` with no caller values.
`recv_frame(sock, *, timeout=FRAME_TIMEOUT_SECONDS) -> dict` and
`send_frame(sock, payload, *, timeout=FRAME_TIMEOUT_SECONDS) -> None` use a
four-byte unsigned network-order length followed by UTF-8 JSON. One absolute
monotonic deadline covers the whole read or write; restore the socket timeout.
Clean EOF before a frame is `eof`; partial EOF is `truncated_frame`. Reject zero
or oversize lengths before reading a body, oversize output before sending bytes,
invalid UTF-8/JSON, duplicate keys, nonfinite numbers and non-object roots.
Bound nesting to four object levels, keys to 64 ASCII bytes and string values
to 512 UTF-8 bytes. Arrays are absent from this protocol. Other allowed leaves
are booleans, null, finite floats and signed 64-bit integers. Error messages are
fixed codes; do not log or retain raw frames. Do not read beyond one frame.

## Session contract

The application receives an already accepted AF_UNIX/SOCK_STREAM socket. This
unit does not bind filesystem listeners, load mounted secrets or claim private
mount/namespace enforcement. Operator construction supplies a 32-byte synthetic
or future provisioned control secret and the expected Receiver UID. Actual OS
peer identity is read from the socket, never supplied in a wire field. Unsupported
platforms or failed identity lookup deny authority. Local Darwin peer checks may
be tested; Linux SO_PEERCRED remains source-only unless run on Linux.

The server sends `{op:challenge, generation, challenge}` with a fresh 32-byte
hex challenge. Receiver sends exact `{op:hello, receiver_boot_id, proof}`. Proof is
HMAC-SHA256 over UTF-8 `receiver\0generation\0challenge\0receiver_boot_id` using
the control secret. The response contains a role-separated `forwarder` proof
over the same binding. Compare proofs in constant time. Never send the control
secret. Receiver-side helpers must verify the actual Forwarder UID and server
proof before treating hello as authenticated. The shared secret and peer UID are
distinct checks; these tests do not establish deployed credential secrecy.

After hello, exact messages are `{op, seq, params}`, with monotonically increasing
integer sequence numbers starting at 1, bounded to signed 31-bit positive values.
Operations are register, activate, revoke and heartbeat. Generation and boot ID
come from authenticated session state, not per-command fields. Parameters must
match the operation's exact schema before calling the registry. Replies bind
`op`, `seq`, `ok` and `result` or a fixed error code. Register replies carry the
grant sentinel only on the authenticated control channel; diagnostic outcomes
and errors never include it. No readiness, accounting or dispatch permit is
invented by this session.

At most four accepted connections execute per controller, and at most one is the
authenticated owner. A successfully authenticated replacement invalidates the
previous session and revokes its leases even for the same boot ID. Serialize
owner checks and registry mutations. An old session's finalizer cannot revoke a
new owner's leases. Bad authentication cannot displace an existing owner. EOF,
framing failure, timeout or response-write failure closes the owning session and
revokes its leases. Clock/closeout failure remains held/unknown; never report
successful revocation after an exception. No direct or insecure fallback.

## Validation

Test fragmentation/coalescing without consuming the next frame, deadlines,
EOF/truncation, all parser limits and secret-free fixed errors. Exercise actual
local Unix socketpairs with synthetic secrets: valid handshake/lifecycle,
wrong peer/secret/proof and replay, schema/sequence rejection, EOF after grant,
replacement while an old session is waiting, and old-finalizer isolation.
Verify no registry mutation before authentication. Keep OS UID observation
separate from deployed mount, kernel, native client and provider acceptance.
