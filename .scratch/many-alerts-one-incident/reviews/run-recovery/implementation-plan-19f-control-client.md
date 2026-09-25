# Unit 19f: Receiver Forwarder-control closeout client plan

Status: local implementation plan, 2026-09-25. Fixed point: `c9f533a`.

## Scope and order

1. Add a Receiver-side session over an already connected Unix stream socket.
   Use the existing peer-UID and mutual-HMAC handshake. Keep the generation
   and boot ID from that handshake; close the socket on any command ambiguity.
   This unit does not connect a pathname, provision credentials or start a
   Forwarder listener.
2. Offer only `heartbeat`, `revoke` and `closeout` commands. Maintain the
   controller's exact one-based sequence. Validate complete reply schema,
   sequence, operation, generation, requested lease identity, fixed receipt
   values and bounded closeout counts/times. Any rejected, missing, stale,
   malformed or mismatched reply makes the session terminal and returns a
   fixed uncertainty code. A closeout observation is data, not dispatch or
   effect authority; `quiescent` does not erase pending or uncertain counts.
3. Test against the real in-memory gated `ForwarderControl` on Unix socketpairs:
   authenticated heartbeat, known/unknown closeout, revocation with an
   installed synthetic lease, prior-session replacement, malformed/lost reply
   and sequence mismatch. Check no raw sentinel or secret in errors or result
   representations and no registration/activation method on the client.
4. Run focused tests, Ruff, independent Standards and Spec reviews, then the
   full suite before a code commit. Record ticket 36/37 progress and exact
   remaining external and integration gates.

No production caller is added. Registration/activation require a later
verified durable reservation and dispatch permit; this unit never accepts a
caller assertion of those gates. A live Forwarder closeout still needs a
durable Receiver observation before relaxing a Run or effect hold.
