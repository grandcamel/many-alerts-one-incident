# Ticket 14 D1 replay reconciliation

## Verdict

The reproducible **captured-delivery filter** selects **paymentUnreachable 26→8** and
**emailMemoryLeak 63→12** at 600 s; at 300 s it selects **26→10** and **63→16**.
The earlier payment 10-at-600 result is recoverable, but it comes from a different
equality-on-full-status-set filter that sends on a shrink.  It is not the selected
predicate.  This does not establish what a Grafana policy change would actually emit:
all inputs are POSTs emitted under the committed 60-s policy.

Inputs are byte-identical extracts of
`prototype/cascade-timing` commit `557153bf531222dec1751f4bb5ac31adefcfa323`:
`prototype/cascade-timing/capture/notifications-paymentUnreachable.jsonl`
SHA-256 `f236752a300b784747210b973120cafdb89b8bcfc33b2539359cc6b1724ff2a5`, and
`prototype/cascade-timing/capture/notifications-emailMemoryLeak.jsonl`
SHA-256 `c7243079d22b092ceeaa544f2b2aa613dc4f213114cdee062d86e030eb2d543a`.
Their source line numbers equal the local copies'.  The original policy is
`group_by: [grafana_folder, alertname]`, `group_interval: 10s`, `repeat_interval: 1m`
(`git show rules/cascade:rules/cascade/alerting/notification-policy.yaml:16-21`,
branch `rules/cascade` commit `c78bca6ee131d4075a9958fa0d3495de32bbdd4d`).

## Selected predicate and results

`filter.py` is the minimal reproducer; its result file lists every retained source line.
For each captured POST, its key is the complete `groupLabels` tuple (equivalent to the
committed two-label grouping for these captures).  Its payload state is two sets: firing
fingerprints and resolved fingerprints.  Per group, it retains only the last **sent**
state and POST clock.  It sends: first payload only if it has firing members; a payload
with any firing fingerprint not in the last sent firing set; an all-resolved payload when
the last sent state had firing members; a payload with any resolved fingerprint not in
the last sent resolved set; otherwise only when `last_sent_t < now - repeat` (strictly
elapsed `>` repeat).  It updates state only when it sends.  This is the recovered
`replay.py` predicate (`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/originals/replay.py:17-46`).

| Capture | 60 s | 300 s | 600 s |
| --- | --- | --- | --- |
| payment | 26 | 10 | 8 |
| email | 63 | 16 | 12 |

Exact retained lines/reasons are in [results.txt](/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/results.txt:1).
For payment, 300 s retains `1,3,4,13,14,16,20,21,23,26`; 600 s retains
`1,3,4,16,20,21,23,26`.  The two removed lines are the pure repeats: source line 13,
error group at +460.131 s, and line 14, absence group at +522.681 s
(`git show prototype/cascade-timing:prototype/cascade-timing/capture/notifications-paymentUnreachable.jsonl:13-14`).
At 600 s all remaining payment sends are first/new-firing/new-resolved/all-resolved;
none is a repeat ([results.txt](/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/results.txt:4)).

## Recovered 10-at-600 alternative

The recovered alternative is `sim2.py` (`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/originals/sim2.py:9-41`): it sends when
the full `(fingerprint,status)` set differs (`s != last_set`) after a 10-s group interval,
or when elapsed time is at least repeat.  At 600 s it yields payment 10 and email 12.
For payment it keeps `1,3,4,16,18,20,21,23,24,26`; compared with the selected eight,
lines 18 and 24 are added.  Both are shrinkage: line 18 contains only frontend firing
after line 16 carried frontend firing plus checkout/frontend-proxy resolved; line 24 again
contains only frontend firing after line 23's mixed state
(`git show prototype/cascade-timing:prototype/cascade-timing/capture/notifications-paymentUnreachable.jsonl:16-18,23-24`).  Thus it explains the two-count difference, but changes the
inequality from growth/new-resolution subset checks to any set difference.

## Boundary

This is filtering of an already-delivered 60-s trace, preserving its source POST clock and
payload snapshots.  It is useful for reconciling the historical claims, but is not a
faithful counterfactual scheduler: skipped 60-s POSTs could change later group state and
flush timing.  The separate `sim03.py` is not a substitute: it synthesizes C1 windows
(`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/originals/sim03.py:4-10`) and dispatch ticks (`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/originals/sim03.py:14-34`).  No upstream
Alertmanager implementation was recovered in the supplied artifacts, so “actual Grafana
at 10m” remains unproved.  Ticket 14 correctly requires a pinned predicate before a
number is placed in the specification
(`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:137-145,164-166`).
