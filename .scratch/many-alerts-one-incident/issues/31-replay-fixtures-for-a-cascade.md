# Replay fixtures for a Cascade

Type: task
Status: resolved
Blocked by: 14

## Question

Specify the offline replay fixture set and its caller-visible acceptance checks for the many-to-one mechanics accepted in [ticket 14](14-many-to-one-under-a-cascade.md#answer). This is a planning deliverable for the two agent-ready specs: do not implement the Receiver or Skill, provision a cluster, or run the demo.

## Settled inputs

Ticket 14 retains folder/alertname grouping with 10s wait, 10s interval and 10m repeats; exact-repeat equality includes values; one pending input reduces duplicate Fingerprints by latest local arrival while preserving source group. Both Match paths use a 30-minute created-time window. Reports append evidence/corrections. Human-owned correction blocks automatic completion; a forced completion needs explicit human authorization.

The committed captures on `prototype/cascade-timing` are available as byte-identical extracts in [ticket 14 evidence](../reviews/ticket-14/jira/). The historical delivery filter in [the replay report](../reviews/ticket-14/replay/report.md) is not a changed-policy scheduler or a prediction for the planned 0.03/s threshold.

## Deliverable

Write an agent-ready fixture specification naming each source artifact, the exact inputs, expected Receiver/Run/Jira-visible outcome and acceptance boundary. Cover: identical versus changed-value repeats; coalesced resolved→firing and firing→resolved arrivals; missing members that must not be treated as Resolved; mixed source groups; additive membership; Severity/Urgency promotion only after acceptance; stale/exact and multiple-candidate Matches; wrong-Match and duplicate correction holds; append-only correction provenance; normal completion and explicit forced completion.

Choose the fixture schema, replay interface and expected assertions without assuming a fresh live capture is needed. Distinguish captured inputs from synthesized edge cases and explain what each proves. Keep Report rendering with ticket 16, runtime refusal/timeout behavior with ticket 21, and live OPS editability/matched-Run timing as separate acceptance gates. Do not claim that an offline fixture proves stage timing.

## Work in progress

Claimed for the continuation of ticket 14. Scope is the offline fixture specification only; earlier handoff exclusions still leave Memory and the other named planning tickets untouched. No Skill/runtime implementation, new live capture, cluster, or demo execution.

## Accepted fixture refinement

The human selected **latest admitted state** for duplicate detection within each source group. On the successful admission path, A→B→A while a Run is held must admit the final A and leave it pending, rather than compare against the last completed A and incorrectly drop it. Failure/retry behavior remains with ticket 21. This refinement is accepted, not a remaining question.

## Answer

The [offline Cascade fixture specification](../reviews/ticket-31/fixture-spec.md) defines the versioned YAML case schema, a future replay interface, controlled Jira clock and Run gates, explicit member/Incident seeds, recorded Match judgments, and caller-visible assertions. It is a planning artifact; no harness, fixture implementation, CLI flag or production behavior was added.

Fourteen case families cover value-aware repeats and the accepted latest-admitted A→B→A baseline; both coalescing status orders; omission without resolution; mixed source groups; additive membership and Severity/Urgency ratcheting; rejected, stale and multiple candidates; wrong-Match and duplicate correction holds; normal versus explicitly authorized forced completion; visible edit failure; and append/correction provenance. Full captured Fingerprints and exact source lines are named. Synthetic edge cases and source-body transformations are explicit. The age boundary uses inclusive 1800 seconds as a deterministic interpretation of the accepted thirty-minute window.

Receiver acceptance uses the real HTTP/spawner seam; mutation-contract acceptance uses real CLI request construction and stateful offline read-back. Stubbed Match judgments test routing and side effects, not diagnosis or Skill/model conformance. A recorded result without an observed command cannot prove the mutation. The existing legacy replay interface remains unchanged.

The [source checks](../reviews/ticket-31/source-checks.md) verify the available seams and captured body projections. Runtime refusal/retry behavior remains with ticket 21, Report rendering with ticket 16. Physical state-store representation, live OPS editability and matched-Run timing remain separate implementation/acceptance dependencies. No live run, test harness execution, new capture, cluster or demo was performed for this planning ticket.
