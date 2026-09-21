# Ticket 23 offline implementation plan — 2026-09-21

Authorized continuation: implement and test the offline execution core. Preserve the
previous source packet and unrelated C2 work. No paid probe, model-target switch,
credential operation, container or live tenant operation is part of acceptance.

1. Add an isolated `prototype/run_timing` package: strict transcript classification,
   monotonic lifecycle transitions, inert length-case dispatch and conservative budget
   admission/capture. No production Receiver or historical runner edits.
2. Add failure-oriented tests using synthetic observations and a virtual clock. Check
   boundary times, malformed/duplicate terminals, identities, denial/receipt conflicts,
   stale receipts, fixed-case order, unknown spend, allocation limits and capture bounds.
3. Run targeted checks, then the full repository suite. Obtain independent Standards,
   Spec and bounded Fable review, recording actual availability and review limitations.
4. Record coverage and remaining native integration gates; retain CLOSED execution card.

The offline executor must never accept arbitrary shell commands for execution or launch
model clients. A native process/cgroup or container binding, actual client permission
events, Forwarder custody/routing, durable authoritative ledger, and private audit store
are separate integrations. Simulated receipts, revocation and process observations do
not qualify those boundaries. Implementing them does not grant runtime authority.
