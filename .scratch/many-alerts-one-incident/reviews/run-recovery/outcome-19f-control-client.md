# Unit 19f Receiver Forwarder-control closeout client

Status: **PASS_LOCAL_CONTROL_CLIENT**, 2026-09-25. Fixed point: `c9f533a`.

The Receiver client authenticates an already connected private Unix stream
socket using the existing UID/HMAC handshake, serializes one-based commands
and offers heartbeat, revoke and closeout only. It checks exact reply shapes,
generation, sequence, requested lease, typed timestamps and coherent
closeout counts. A rejected, lost, stale or malformed reply closes the session
with a fixed uncertainty code. In particular, a success reply cannot smuggle
an overdue flight, a known lease with unknown closeout or a boolean timestamp.
It returns frozen sanitized observations, not a dispatch permit or completed
Run/effect claim.

The [plan](implementation-plan-19f-control-client.md) and independent Standards
and Spec reviews pass after the two reply-validation corrections. Eleven
focused real socketpair tests and changed-file Ruff pass. The full local suite
passes **5434**, skips **39**, in 377.96 seconds. Tests cover heartbeat,
unknown and known closeout, synthetic installed-lease revocation, bad input,
rejected command, wrong sequence, false success frames including nested
Revoke closeout, boolean revocation time, owner replacement, lost reply and
bad authentication. No sentinel or secret is retained in observations.

No endpoint connector, credential provisioning, registration, activation,
heartbeat scheduler, durable observation writer, reservation, permit,
guarded launcher or Run caller was added. Synthetic socketpair behavior does
not qualify native clients, intended-venue isolation or tenant state. The
current v1 Receiver accounting ledger still cannot reserve production spend.
Native, provider, tenant, paid, venue, deployment, power-loss and human
adjudication are **NOT RUN**. Tickets 36 and 37 stay open. No push,
publication, provider experiment or credential change occurred.
