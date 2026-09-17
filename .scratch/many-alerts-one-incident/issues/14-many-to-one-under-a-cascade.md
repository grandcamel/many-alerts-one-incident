# Many-to-one under a Cascade

Type: grilling
Status: open
Blocked by: 10, 11

## Question

With one Run per Notification kept: how is Grafana's grouping set so a Cascade tends to arrive together? Does one-at-a-time survive N Notifications when a Run takes minutes, or does the Receiver coalesce, queue with a cap, or drop repeats? What rule does a Run judge a Match by, what does it read to judge, and what happens when it judges wrong: an Alert filed under the wrong Incident, or a second Incident for a Fault that already has one? What may a later Run change in an existing Report? Extends ADR 0006 with the mechanics it left open.

## What ticket 10 settled, 2026-09-17

Both blockers are resolved, so this is on the frontier.

- **The Cascade's shape is now concrete.** The live Fault raises **two alertable
  conditions** — checkout's error ratio and payment's traffic going to *exactly* zero —
  which instantiate `by (service_name)` into **six to nine Alerts**, each with its own
  Fingerprint. So the many-to-one this ticket designs for is one condition fanning across
  services, not N unrelated rules.
- **The many-to-one shape is already present with no grouping change.** Ticket 26 measured
  `STATUS_CODE_ERROR` across five services at once for a single Fault.
- **Timing to judge against**: first failing trace at ~90 s, first metric-backed Alert at
  3–5 min, absence Alerts landing by 9–12 min. A Run takes minutes
  ([Does a high-effort Run fit the slot](11-does-a-high-effort-run-fit-the-slot.md)), so
  Alerts of one Cascade will arrive *while an earlier Run is still working*. That is this
  ticket's central case, not an edge one.
- **Absence Alerts are the hard part.** They are written on series that do not exist at
  steady state, so they arrive as **NoData**, not Firing, unless each rule wraps in
  `or vector(0)`. Whether a NoData Alert should start a Run at all is a decision this
  ticket shares with [Alert rules for a Cascade](28-alert-rules-for-a-cascade.md).
- **Recovery looks like injection.** Each Fault's undo restarts a service and the flagd
  rollout emits Events identical to the injection's, so a Run investigating after recovery
  sees two indistinguishable rollouts.
