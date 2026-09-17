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

## What ticket 28 hands this ticket, 2026-09-17

**The premise needs correcting first.** "A Cascade of N rules is N Notifications"
is true of *rules*, not *Alerts*. With `group_by: [grafana_folder, alertname]`
Grafana already collapses instances of one rule, so Fault 1's **7 Alerts arrive
as two Notifications** — one carrying 3 error Alerts, one carrying 4 absence
Alerts — and start **2 Runs, not 7**. The Receiver hands one whole Notification
to one Run (`grafana_jsm_sandbox/notification.py`) and the Skill handles every
Alert inside it. This ticket inherits 2 Runs.

**The handle.** Every rule carries a constant `cascade: otel-demo` label and sits
in folder `demo`, so this ticket can choose `[grafana_folder, cascade]` for one
Notification per Cascade, or keep today's behaviour, **without any rule
changing** — which matters because changing a rule's labels re-Fingerprints it
and orphans every open Incident carrying the old `fp-` label.

**Two hard constraints.**

- `group_by` must **never** contain `service` or `service_name`, or the collapse
  cannot happen: those are the labels that vary across a Cascade.
- Only the **global notification policy** can drop `alertname`. Per-rule
  `notification_settings` is available in Grafana 12.0.1's file provisioning and
  carries `group_by`, but `NormalizedGroupBy()` always prepends `grafana_folder`
  and `alertname` to any non-empty value — the only escape is the special `...`,
  which groups by *all* labels. So per-rule settings make grouping **finer,
  never coarser**.

**A question this ticket now owns.** Severity is graded, not uniform: C1 and C4
are `critical`, the other four `warning`. **If a Cascade collapses to one
Notification carrying mixed severities, what Severity does the single Incident
take?** The Skill has no rule for it, because today it creates one Incident per
Alert and reads the severity off that Alert.
