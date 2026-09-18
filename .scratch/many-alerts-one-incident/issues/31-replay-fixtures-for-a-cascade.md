# Replay fixtures for a Cascade

Type: task
Status: open
Blocked by: 14

## Question

Specify the offline replay fixture set and its caller-visible acceptance checks for the many-to-one mechanics accepted in [ticket 14](14-many-to-one-under-a-cascade.md#answer). This is a planning deliverable for the two agent-ready specs: do not implement the Receiver or Skill, provision a cluster, or run the demo.

## Settled inputs

Ticket 14 retains folder/alertname grouping with 10s wait, 10s interval and 10m repeats; exact-repeat equality includes values; one pending input reduces duplicate Fingerprints by latest local arrival while preserving source group. Both Match paths use a 30-minute created-time window. Reports append evidence/corrections. Human-owned correction blocks automatic completion; a forced completion needs explicit human authorization.

The committed captures on `prototype/cascade-timing` are available as byte-identical extracts in [ticket 14 evidence](../reviews/ticket-14/jira/). The historical delivery filter in [the replay report](../reviews/ticket-14/replay/report.md) is not a changed-policy scheduler or a prediction for the planned 0.03/s threshold.

## Deliverable

Write an agent-ready fixture specification naming each source artifact, the exact inputs, expected Receiver/Run/Jira-visible outcome and acceptance boundary. Cover: identical versus changed-value repeats; coalesced resolved→firing and firing→resolved arrivals; missing members that must not be treated as Resolved; mixed source groups; additive membership; Severity/Urgency promotion only after acceptance; stale/exact and multiple-candidate Matches; wrong-Match and duplicate correction holds; append-only correction provenance; normal completion and explicit forced completion.

Choose the fixture schema, replay interface and expected assertions without assuming a fresh live capture is needed. Distinguish captured inputs from synthesized edge cases and explain what each proves. Keep Report rendering with ticket 16, runtime refusal/timeout behavior with ticket 21, and live OPS editability/matched-Run timing as separate acceptance gates. Do not claim that an offline fixture proves stage timing.
