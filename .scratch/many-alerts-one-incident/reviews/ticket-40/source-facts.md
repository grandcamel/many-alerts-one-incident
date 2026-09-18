# Ticket 40: `adFailure` source facts (offline)

**Result: a source-level Mechanism is not established.** The pinned historical
prototype ref is `prototype/cascade-timing` at `557153bf`. Its bounded tree
inventory contains no path matching `src`, `adservice`, `advertising`, or an
OpenTelemetry Demo source-tree name (`source-inventory.txt:1-3`),
and no candidate local OpenTelemetry clone exists at the three conventional
project roots inspected (`source-inventory.txt:3`). This is bounded absence,
not proof that an arbitrarily named source copy cannot exist elsewhere. Ticket
40 requires an exact missing-evidence record rather than an invented Mechanism
(`.scratch/many-alerts-one-incident/issues/40-fallback-fault-ground-truth.md:11-13`).

**Verified Trigger/artifact facts, not Mechanism.** The captured on-transition
records `adFailure` off→on, boolean `True`, ConfigMap resource-version change,
and `flagd` in-pod variant `on` after rollout
(`557153b:prototype/signal-surface/capture/timing-adFailure-on.json:1-9`).
The companion capture says the ConfigMap write alone is inert and records a
`deploy/flagd` restart; it also warns that flagd holding the variant does not
verify the caller/provider (`...:capture/cascade-adFailure-on.log:65-89`). The
captured variants are `off: false`, `on: true` (`...:capture/cascade-adFailure-on.log:76-82`). These establish the historical injection sequence, not what
the service's `getAds` code does, an injected RPC status/code, or a caller
fallback/error conversion.

**Observed diagnostic evidence is separate.** That capture observed ad error
span-metric and errored-ad-trace at t+6, then a frontend error span-metric at
t+132; its ad error-log check never fired in the watch window
(`...:capture/cascade-adFailure-on.log:91-110,195-201`). The symptom harness
queries only generic error trace/metric/log predicates and labels frontend as
“does it reach the caller?” (`557153b:prototype/signal-surface/lib/symptom.py:163-188`). Counts/error status do not establish the causal
mechanism, RPC code, or fallback path.

**Pin boundary.** The historical values file declares chart 0.41.2/appVersion
3.0.0 (`557153b:prototype/signal-surface/values-demo.yaml:1`);
the issue describes that as a chart/app-version and image-default claim
(`.../issues/09-which-system-and-where-it-runs.md:43-48`). Neither is a stored
vendor source file for `adFailure`.

Candidate reviewed definition may safely name the Trigger and observed error
signals, but must leave Mechanism/caller consequence unestablished until a
locally available pinned vendor source (or another reviewed source artifact)
is cited. No source or measurement was executed.
