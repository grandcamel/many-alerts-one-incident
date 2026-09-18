# Ticket 30 facts (offline, 2026-09-18)

Historical measurement reports are cited from planning commit `7fc74b8`; the rule source is cited from `prototype/cascade-timing` commit `557153b`. Report line numbers refer to the later planning copy, not the earlier measurement-branch version. No current-cluster claim follows.

- **LGTM arithmetic refuted.** The recorded values are 726 MiB to 1640 MiB over 92 minutes
  (`7fc74b8:.scratch/many-alerts-one-incident/issues/26-can-one-doks-node-hold-the-chart.md:176-178`).
  That is 914/92 = **9.93 MiB/min**, not ~14. At that linear rate it reaches a 4096-MiB limit about
  247 minutes after the 1640-MiB observation (about 5.7 hours from 726 MiB), not roughly three hours.
  Neither linear growth nor leak versus warm-up was established, so neither extrapolation is a safe
  uptime bound.

- **Headroom was a snapshot, not duration proof.** Under a fault the one node had 5.95 GiB working
  set and 9.68 GiB available, with no OOM/eviction/pressure and 35/35 pods scheduled
  (`7fc74b8:.scratch/many-alerts-one-incident/issues/26-can-one-doks-node-hold-the-chart.md:74-88`).
  It does not reserve future LGTM growth, load-generator growth, fault/restart overhead, or a
  different cold-start shape.

- **The load-generator OOM is observed, but not a cluster-uptime limit.** C4 observed exit 137 after
  116 minutes during `cartFailure`, and raised critical `service=load-generator`; traffic recovered
  in about 60 seconds and C2 did not fire (`7fc74b8:.scratch/many-alerts-one-incident/issues/29-measure-the-cascade-against-real-rules.md:224-242`).
  The evidence does not establish that 116 minutes equals overall cluster age, a repeatable threshold,
  or a 30-minute safety guarantee.

- **Cold-start claims have uneven support.** Capacity measured cold path ~8m40s and warm ~2m32s
  (`7fc74b8:.scratch/many-alerts-one-incident/issues/26-can-one-doks-node-hold-the-chart.md:182-187`).
  Ticket 29’s text says its earlier harness brought a cluster up in ~9 minutes
  (`7fc74b8:.scratch/many-alerts-one-incident/issues/29-measure-the-cascade-against-real-rules.md:39-43`).
  The bounded review did not locate a supporting committed 12-minute alerting-and-sink measurement; keep that claim unverified rather than treating the search as proof no such artifact exists.

- **C4 scope is not fixed by the current rule.** Its expression aggregates only by container name,
  dropping namespace (`557153b:prototype/cascade-timing/alerting/cascade-rules.yaml:315-346`), and
  the observed rule covers 37 series including kube-system containers
  (`7fc74b8:.scratch/many-alerts-one-incident/issues/29-measure-the-cascade-against-real-rules.md:224-239`).
  A namespace matcher would remove kube-system sources, but it must be validated against the
  load-generator’s intended demo-namespace series; the existing aggregate discarded that label.

Therefore 30-minute safety is not established: the available data contains a short no-pressure
snapshot and two long-run observations, no bounded run-duration/cold-start/restart distribution or
validated C4 selector after scoping.
