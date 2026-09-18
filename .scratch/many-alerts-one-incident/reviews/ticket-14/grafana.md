# Ticket 14 — Grafana-lens verification

Scope: only the six objections under `## Lens: grafana` in
`/tmp/handoff-ticket-14-panel-objections.md`.  D1–D6 are agreed planning inputs,
not implemented behavior.  Branch citations use `git show <branch>:<path>:line`.
No replay, simulation, Grafana, Jira, receiver execution, or repository mutation was
performed.  In particular, D1 numerical claims remain unestablished: ticket 14 records
two incompatible payment replays and requires the predicate be pinned before a number is
specified (`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:137-145,164-166`).

1. **D1 “26 → 10 is the five-minute number” — UNVERIFIED.**
   **Supports:** the objection accurately identifies a planning-risk: D1 itself says its
   stated counts are wrong and must be re-derived (ticket 14:101-102).  Current committed
   policy is still one minute, not either proposed value
   (`git show rules/cascade:rules/cascade/alerting/notification-policy.yaml:16-21`), and
   the current policy explicitly relies on repeats for trend comments (same file:4-10).
   **Refutes/limits:** the ticket records an unresolved 8-versus-10 result at 10m
   (ticket 14:137-145); this bounded review did not select a DedupStage predicate or
   replay it.  D3 is also only proposed (ticket 14:105-108), so no present system can
   establish the asserted future zero-comment result.  **Smallest correction:** remove
   all interval/count and “only trend comments” wording from D1 until one named predicate
   reproduces the captures; then state the chosen interval and its measured counts.
   **Excluded:** no D1 arithmetic or live timing was tested.

2. **D3(b) deletes every D1 repeat — PARTLY HOLDS.**
   **Supports:** D3(b) is specified as “drop exact repeats” (ticket 14:105-108), while
   the C3 rule deliberately preserves live `values.A` for trend comments
   (`git show rules/cascade:rules/cascade/alerting/cascade-rules.yaml:234-240`).
   Therefore `(fingerprint,status)` alone would omit a field the existing Skill uses as
   the current trend value (`skill/incident-sync/SKILL.md:114-120`).
   **Refutes/limits:** neither “exact” nor a `values` comparison is defined in D3, and
   the claimed 12→6/5→4 figures depend on the explicitly unresolved D1 predicate.
   Further, a matched Run can comment on a newly accepted member, so “every Incident has
   only create and complete” does not follow from repeat suppression alone.
   **Smallest correction:** define D3(b)’s equality key and whether a changed `values.A`
   defeats it; specify the queue-idle/liveness behavior separately.  **Excluded:** no
   delivery or comment count was derived.

3. **D2 “6 → 39 is unreproducible and inverted” — UNVERIFIED.**
   **Supports:** the current policy does retain `alertname` in `group_by`
   (`git show rules/cascade:rules/cascade/alerting/notification-policy.yaml:16-20`), and
   ticket 14 says the global policy is the only place it can be removed
   (ticket 14:53-60).  Comparing groupings is therefore relevant design work.
   **Refutes/limits:** the abbreviated D2 decision states only the design rationale—leave
   reduction to the Run (`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:103-104`);
   it neither reproduces nor disproves an earlier 6→39 rationale.  The objection’s 12/7,
   59/23, and “every interval” comparisons also have no committed reproducible artifact
   cited here.  **Smallest correction:** record the numerical comparison as a defined
   measurement request (dispatcher/version, interval reconstruction, group settings), but
   do not reopen D2 solely from an unverified number.  **Excluded:** no regrouping simulation.

4. **D5 ratchet makes all Faults critical; cart is contaminated — PARTLY HOLDS.**
   **Supports:** D5 is an up-only historical maximum (ticket 14:112-113).  C4 is generic
   and critical (`git show rules/cascade:rules/cascade/alerting/cascade-rules.yaml:315-345,371-376`),
   and the committed cart capture includes a critical `load-generator` C4 Alert
   (`git show prototype/cascade-timing:prototype/cascade-timing/capture/notifications-cartFailure.jsonl:6`).
   A wrong acceptance would therefore ratchet the Incident upward permanently.
   **Refutes/limits:** D4 calls the cascade result a *candidate* and requires a judgment
   afterwards (ticket 14:109-111); the capture does not prove that C4 must join cart’s
   Incident.  “All four” and “zero information” are untested aggregate assertions.
   **Smallest correction:** state that only accepted members participate in D5; make
   load-generator admission an explicit judgment/correction case.  **Excluded:** no
   severity inventory or policy change.

5. **D3(c)+D6 stale resolution after coalescing — PARTLY HOLDS.**
   **Supports:** D3 requires coalescing while a Run is in flight, while D6 only orders
   Firing before Resolved *within one Notification* (ticket 14:105-117).  Neither clause
   defines duplicate-fingerprint conflict resolution across merged Notifications or the
   meaning of “its group” after cross-group coalescing.  Current timeout is 300 seconds
   (`grafana_jsm_sandbox/run_spawner.py:36-38`), so a queue contract is material.
   **Refutes/limits:** “older resolved is applied last” assumes a set-union implementation
   that D3 does not prescribe; stale state, completion, lost resolution, and timeout loss
   have not been executed.  The historical 370.3-second result used canned telemetry and
   stubbed Hands (`.scratch/many-alerts-one-incident/issues/11-does-a-high-effort-run-fit-the-slot.md:20-29`), not this path.
   **Smallest correction:** require arrival-ordered, per-fingerprint last-status-wins
   coalescing and retain each source groupKey for D6’s exception.  **Excluded:** no
   coalescer or timeout test.

6. **D1 makes fallback adFailure a two-notification, one-alert demo — PARTLY HOLDS.**
   **Supports:** adFailure is explicitly the designated fallback
   (`.scratch/many-alerts-one-incident/issues/10-faults-and-their-cascades.md:120-122`); its committed capture has three
   records (`git show prototype/cascade-timing:prototype/cascade-timing/capture/notifications-adFailure.jsonl:1-3`),
   all for one C1 fingerprint (same source:1-3).  That makes the objection’s qualitative
   concern appropriate: it is not a many-alert fallback under the measured current policy.
   **Refutes/limits:** direct committed timestamps establish the post-undo part precisely:
   `t0=1789686838` and `undo=1789687445` (`git show prototype/cascade-timing:prototype/cascade-timing/capture/t0-adFailure.txt:1`,
   `.../tundo-adFailure.txt:1`); the Alert starts at +742 and resolves at +862, while its
   firing POSTs arrive at +757 and +817 and the resolved POST at +877 (capture:1-3).
   Thus the Alert starts 135 s after undo (the first POST is 150 s after), and there is
   exactly one 60-s repeat.  Under the objection’s stated elapsed-repeat predicate, 5m
   cannot preserve that repeat: the next repeat after the first +757 POST is +1057, after
   the +862 resolution (and +877 resolution POST).  The 10m count remains D1-unverified,
   but its proposed 5m remedy is false.  **Smallest correction:** add a fallback acceptance
   criterion (minimum members and lifecycle evidence); do not use this capture to select
   5m.  **Excluded:** no replay or live fallback validation.

Overall: verdict tally is **two unverified and four partly hold**.  No objection proves D1–D6 impossible.  Three planning contracts need precision
before implementation—D3 equality, coalesced state ordering/group scope, and D5 accepted
membership.  D1 numerical and D2 comparative claims remain measurement work.

## Subsequent replay reconciliation

The historical D1 filtering discrepancy has now been reconciled in [replay/report.md](replay/report.md): payment 8 and email 12 at 600 seconds under the explicit subset predicate; payment 10 under a recovered full-set inequality predicate that sends on shrinkage. This upgrades the historical filter-count evidence only. Counterfactual Grafana behavior and the alternate-group scheduler comparisons remain unverified. See [stage.md](stage.md) for subsequent boss-reviewed stage conclusions.
