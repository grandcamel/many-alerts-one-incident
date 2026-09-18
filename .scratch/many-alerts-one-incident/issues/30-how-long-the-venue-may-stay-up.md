# How long the venue may stay up

Type: grilling
Status: open
Blocked by:

## Question

Graduated from the map's fog on 2026-09-17 by
[Measure the Cascade against real rules](29-measure-the-cascade-against-real-rules.md),
which turned one suspected time bomb into two measured ones and made the
question specifiable.

The venue degrades on a clock, and nothing in the map says what to do about it:

- **LGTM climbs ~14 Mi/min against a 4 GiB limit** (ticket 26: 726 Mi rising to
  1640 Mi over 92 minutes), which reaches the cap in roughly **three hours**.
  Whether that is a leak or cache warm-up was never settled.
- **The load generator is OOMKilled at ~116 minutes** (ticket 29, `exitCode 137`,
  observed mid-`cartFailure` at 2 h 03 m of cluster uptime). It restarts itself,
  traffic recovers in ~60 s, and C2 does *not* fire in the gap — but **C4 does**,
  as a *critical* Alert labelled `service=load-generator`, which under
  one-Run-per-Notification starts a Run about a container nobody injected.

So a thirty-minute slot is safe and a rehearsal day is not, and the second bomb
does not merely degrade the venue — it manufactures a Cascade.

Decide:

- **how long the venue is allowed to live**, and whether `make up` is a
  once-per-day or once-per-rehearsal action. Ticket 26 measured the cold path at
  ~9 minutes and ticket 29 at ~12 with alerting and the sink, so a rebuild is
  cheap enough to be the answer.
- **whether either limit is raised instead.** The load generator's limit and
  LGTM's 4 GiB are both ours to set; raising them trades money and node headroom
  for uptime. Ticket 26 left 9.68 GiB available on the node, so there is room.
- **what the runbook says when the presenter's cluster is older than the limit** —
  refuse to start, warn, or rebuild.
- **whether a `load-generator` restart should be alertable at all.** This is the
  concrete instance of C4 being cluster-wide (37 series including `cilium-agent`,
  `coredns`, `csi-do-plugin`). Either C4 gains a namespace matcher and the demo
  loses restart coverage of its own infrastructure, or the Skill must handle a
  `service` label naming something that is not a demo service.
- **whether LGTM's climb is a leak or warm-up**, and whether settling that is
  worth the cluster time it costs, given that a rebuild may make it moot.

This is a decision, not a measurement: both numbers exist. What is missing is
the rule the spec states.

## Accepted Change input from ticket 25

ADR 0015 requires reconciliation or private operator handoff of unresolved Changes before journal expiry, rehearsal reset or cluster destruction. Teardown cannot silently erase uncertain actuation. Emergency recovery must remain available during telemetry/storage failure. Seven-day retention does not authorize keeping a degraded venue running for seven days.
