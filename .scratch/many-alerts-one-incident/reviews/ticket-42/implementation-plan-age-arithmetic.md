# Ticket 42a local venue age arithmetic plan

Status: source plan, 2026-09-25. Baseline: `25dd475`.
Authority: ADR 0016 and ticket 42's proposed age formula. This unit checks
arithmetic over caller-supplied claims only; it does not authenticate a
provider receipt or grant session, Fault, Run, creation or teardown authority.

1. Add `venue_age.py` with bounded immutable prior anchor and fresh
   observation shapes. Require exact integer nanoseconds, exact boot and
   resource-digest shapes, nonnegative RTT, provider-now >= creation,
   epsilon between 0 and 5 seconds, and no signed-64-bit overflow. Reject
   malformed or changed resource identity with fixed closed codes.
2. Compute raw fresh bounds before any `max`. On the same boot, advance the
   prior lower/upper by monotonic elapsed time; on a new boot, carry the
   persisted bounds without cross-boot subtraction. Reject a lost same-boot
   anchor or fresh upper below prior upper. Return only descriptive lower,
   upper and new anchor fields. No source-verification or readiness flag.
3. Test exact 30/85/90-minute arithmetic edges, RTT and epsilon, same-boot
   elapsed, restart coverage, stale/rollback receipt, changed identity,
   malformed scalar/boot/time/order, overflow and immutability. Update
   ticket 42 and a local venue-age document with the provenance boundary.
4. Run focused tests, Ruff, independent Standards and Spec source reviews,
   protected dirty-artifact read-back and the full suite before a local code
   commit. Stage only named 42a files.

Provider receipt authenticity, timestamp generation within the measured
request, venue identity, provider inventory, health and cost admission,
protected handoff, deletion and intended-venue acceptance remain separate
gates. A future owner must bind the arithmetic to authenticated current
evidence before making any admission decision.
