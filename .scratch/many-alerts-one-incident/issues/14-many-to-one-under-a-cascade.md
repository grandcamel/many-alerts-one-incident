# Many-to-one under a Cascade

Type: grilling
Status: claimed
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

## Work in progress, 2026-09-17 — NOT an Answer

This ticket is **claimed and unresolved**. A grilling session ran one round, the human
agreed all six recommendations, and a refutation panel was then cut short by the account's
weekly usage limit. Everything below is durable; the ticket is not resolved.

### Measured first: the Notification volume nobody had counted

Ticket 29 reported "4 firing Notifications -> 4 Runs" for the live Fault. That counted only
deliveries carrying a *new* Alert. The webhook sink recorded every POST, on branch
`prototype/cascade-timing` under `prototype/cascade-timing/capture/notifications-*.jsonl`:

| Fault | actual POSTs | Runs at one-per-Notification | serialized at Opus 5's 370 s | at $1.86/Run |
| --- | ---: | ---: | ---: | ---: |
| `paymentUnreachable` | **26** | 26 | 2 h 40 m | $48 |
| `emailMemoryLeak` | **63** | 63 | 6 h 29 m | $117 |
| `cartFailure` | 23 | 23 | 2 h 22 m | $43 |
| `adFailure` | 3 | 3 | 18 m | $6 |

`repeat_interval: 1m` re-notifies every group every 60 s for the life of the Fault. Chapter
one needed that: one Alert was one Incident, and a repeat was the only way an Incident got a
second comment. Under ADR 0006 that job is gone.

**Turning repeats off is not enough.** Replaying the real per-group timeline with repeats
disabled floors the live Fault at 10 Notifications; with C1 also at `0.03/s` so its
mid-Fault flapping stops, at **8** — still ~49 minutes of serialized Opus 5 Runs against a
thirty-minute slot. No grouping or repeat setting alone makes the arithmetic work.

Also measured: the mixed-state payload ticket 29 found is **three** deliveries, not one —
deliveries 16, 23 and 25, each `status: firing` carrying two resolved Alerts and one firing.

### The six decisions the human agreed, pending refutation

- **D1** `repeat_interval` 1m -> 10m. **Its stated counts are wrong — see the surviving
  objection below. The direction holds; the numbers must be re-derived.**
- **D2** `group_by` stays `[grafana_folder, alertname]`. The reduction is the Run's Match,
  not the router's grouping.
- **D3** The Receiver gains: (b) drop exact repeats, (c) coalesce Notifications arriving
  while a Run is in flight into one pending Notification, (d) the Skill makes a matched Run
  cheap — it appends evidence rather than re-investigating. This retires "one Run per
  Notification" as a literal rule.
- **D4** The Match is three parts in order: exact Fingerprint on an **open** Incident; else
  the `cascade` label plus time, exactly one open => candidate; else judge by reading the
  candidate's Report, stating a confidence. Assumption stated out loud: one Fault at a time.
- **D5** Severity is the highest any of the Incident's Alerts has ever carried, ratcheting
  **up only**.
- **D6** An Incident Completes only when **every** Fingerprint it carries has resolved.
  Firing Alerts are handled before resolved ones within one Notification. Escape hatch: a
  Resolved Notification whose group is entirely resolved lets the Run Complete and name any
  still-open Fingerprints in the closing comment.

### The refutation panel, incomplete

Five lenses (Grafana mechanics, Receiver code, Skill/`jira-as`, ADR/glossary, stage
arithmetic) raised **31 objections**. Verification survived for two lenses only; the weekly
limit killed 40 of 68 agents including the completeness critic.

Full objections, verdicts and reasoning are in the workflow journal — one `{"type":"result"}`
line per agent:
`~/.claude/projects/-Users-jasonkrueger-projects-many-alerts-one-incident/091819f5-bb4c-41c7-a2e6-c2c6e2590647/subagents/workflows/wf_5475d682-1f0/journal.jsonl`

| lens | objections | verified | outcome |
| --- | ---: | --- | --- |
| `domain` | 6 | 6 x 2 votes | 1 survived, 5 killed |
| `receiver` | 7 | 6 tech, 5 scope | 0 survived, 6 killed, 1 unverified |
| `grafana` | 6 | none | **unverified** |
| `jira` | 6 | none | **unverified** |
| `stage` | 6 | none | **unverified** |

**The one objection that survived two adversarial skeptics** (`domain`, against D1,
severity serious): *the stated Notification counts do not replay.* The refuter's replay
gives `paymentUnreachable` 26 -> 8 and `emailMemoryLeak` 63 -> 12 at `10m`, and 26 -> 10 /
63 -> 16 at `5m` — so the pair quoted to the human (10 and 12) comes from two different
intervals. The two payment deliveries that exist at 5m and vanish at 10m are t+460 (C1
group) and t+522 (C2 group), **both pure mid-Fault repeats** — the exact class D1 is
justified by preserving. This session's own replay gave payment 10 at 10m, agreeing exactly
on email and differing by 2 on payment, so **the dedup predicate itself must be pinned
before any number goes in a spec.**

**18 objections are UNVERIFIED and are not conclusions.** Four of them, raised independently
by more than one lens, would hit several decisions at once if they hold — recorded here so
they are not lost, each still to be checked:

- No Incident ever carries a `cascade-otel-demo` label, so D4 step 2 always returns
  `Found 0`. `SKILL.md:76` says the Incident carries `fp-<fingerprint>` "and no other label".
- D4, D5 and D6 all require writing to an *existing* Incident — adding a label, raising
  Severity — and the Skill has no operation that does it.
- D6's escape hatch fires before the Cascade ends in 3 of 3 measured Faults, making it the
  normal path rather than the exception, which inverts D6's rule. (Raised by four lenses;
  **killed** where it was tested, by both the `domain` and `receiver` verifiers.)
- The full lifecycle is ~29.0 minutes flip-to-Complete against a thirty-minute slot, and
  `RUN_TIMEOUT` is a 300 s SIGKILL against a measured 370 s Run. (The RUN_TIMEOUT half was
  **killed** by the `receiver` verifier as belonging to ticket 21.)

### What the next session must do

1. **Pin the replay predicate and re-derive D1's counts.** Two independent replays of the
   same artifact disagree by 2 on `paymentUnreachable`. One agreed predicate, stated in the
   answer, citing the capture files.
2. **Verify the 18 unverified objections**, starting with the `jira` lens — it is the one
   that claims three decisions are unimplementable.
3. **Run the completeness critic**, which never ran: check D1-D6 against every clause of
   this ticket's Question, especially "what does it READ to judge", "what happens when it
   judges WRONG", and "what may a LATER Run change in an existing Report".
4. **Then round 2 of the grilling**, which was never put to the human: the cost of a wrong
   judgment and whether it is correctable; append-versus-rewrite (shared with ticket 16);
   and the exact `group_wait`/`group_interval` values.
