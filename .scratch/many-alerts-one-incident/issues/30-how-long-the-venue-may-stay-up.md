# How long the venue may stay up

Type: grilling
Status: resolved
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

## Work in progress

Claimed after ticket 25 was committed. Offline evidence review and policy decisions only; no cluster, model, demo or spending. Historical uptime observations do not establish a guaranteed safe duration or current resource behavior.

## Evidence correction before decisions

[Offline facts](../reviews/ticket-30/facts.md) refute the opening growth arithmetic: 726 to 1640 MiB over 92 minutes is 9.93 MiB/min, not 14. Linear growth and the projected three-hour limit are not established. The observed load-generator OOM and node-headroom snapshot do not prove a safe 30-minute window or a repeatable failure age. The quoted 12-minute cold path remains unverified by the bounded review. [Round 1](../reviews/ticket-30/round-1.md) records accepted fresh-session age policy, resource baseline, infrastructure visibility and state-preserving drain. All four recommendations were accepted. [Round 2](../reviews/ticket-30/round-2.md) records the accepted readiness, admission, cloud-budget and teardown contract. All five second-round recommendations were accepted.

## Answer

Both rounds are accepted in [ADR 0016](../../../docs/adr/0016-venue-lifetime-is-bounded-with-protected-teardown.md). Fresh venue per presentation/full rehearsal; start by cluster age 30 minutes after five healthy baseline minutes, launch no model Run at or after age 85, and hold ordinary admissions at 90. Keep tested resource baselines and cluster-wide C4 visibility; these thresholds are policies requiring validation, not measured safe durations. Overruns use labelled replay while bounded recovery continues.

Readiness requires fresh observations, LGTM/load-generator working sets below 80 percent of verified limits, at least 25 percent node memory available and no unexpected pressure/critical conditions, alongside accepted OPS/recovery/Change/budget/capture gates. Cloud has a separate $10 weekly planning envelope and $2 creation-attempt reservations, with late/unknown charges and residual resources accounted outside the cluster.

Teardown requires verified private off-cluster handoff of protected state and explicit unresolved obligations, followed by provider inventory verification. A timer or successful delete command is not cleanup proof. [Ticket 42](42-venue-lifecycle-and-protected-teardown-specification.md) owns the implementation-ready specification and offline/future venue acceptance plan, including one no-Fault 90-minute baseline plus existing qualification samples. No provisioning, cleanup, tuning, purchase or model run occurred.
