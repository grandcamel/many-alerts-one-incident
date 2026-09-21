# Planning frontier after ticket 40 approval

Snapshot after commit `3e17793`, derived from the issues' actual Status and Blocked by fields. No blocker is removed or measurement ticket resolved by this report.

| Ticket | Status | Unresolved declared prerequisites |
| --- | --- | --- |
| 12 | open | 19 |
| 16 | open | 12 |
| 19 | claimed | none |
| 23 | open | none |
| 32 | open | 16 |
| 35 | open | 12 |
| 36 | open | 12 |
| 37 | open | 16, 36 |
| 38 | open | 36, 37 |
| 39 | open | 16 |
| 41 | open | 12 |
| 42 | open | 37, 38, 39, 41 |
| 43 | open | 16 |
| 44 | open | 32, 35, 39, 43 |

Ticket 19 is claimed, prepared and NOT RUN; it requires client/transport and model measurements before Eyes (12) can select tools. Ticket 23 is unblocked in the map but requires separately authorized paid measurements under the updated auth/budget contract. Neither is an unblocked planning decision. All remaining specification tasks have unresolved declared prerequisites, directly or transitively through Eyes/Report; preparing assumptions does not satisfy those prerequisites.

## Concrete next step

Update ticket 19's existing protocol to the later accepted time, credential, billing and evidence contracts, then seek an explicit transition from planning to a bounded local Stage A prototype: pinned real mcp-grafana stdio client, disposable local TLS/Forwarder subset and deterministic synthetic backend fixtures, positive and negative auth/scope/output cases, sanitized receipts. No model, cloud venue, real tenant credential or external service mutation is needed for this subset. It is source/protocol preparation only until authorized. It can expose a decisive incompatibility but cannot alone resolve the ticket's model-usability/latency questions or unblock Eyes.

Full Stage B remains separately gated by model/CLI verification, mediated Anthropic credentials, approved spend and private evidence capture. The draft protocol remains NOT RUN. No automatic task, prototype implementation or execution was started by this frontier audit.

## Subsequent authorized local measurement

The user authorized local Stage A after this preparation snapshot. [The verdict](ticket-19/stage-a-verdict.md) now records 31 supported fixture assertions at prototype commit `5f90bfb`; model/container/tenant/venue gates remain NOT RUN. Ticket19 remains claimed and all blocker edges above are unchanged.

## Subsequent Stage B measurements — 2026-09-18

Three bounded model attempts ran under separately recorded authorizations (see ticket 19): attempt 1 (mechanics supported; usability inconclusive from fixture discovery denials), an interrupted launch (infrastructure containment failure, fixed; spend pending daily feed), and attempt 3 against a permissive-read fixture (mechanics supported; Q1/Q2/Q4 supported; Q3 refuted by a named selector gap under stricter-than-real fixture semantics). Combined diagnostics spend ≈ $1.7–1.9 of $30. These samples inform but do not settle ticket 12's Eyes selection: ticket 19 stays claimed, ticket 12 stays blocked, and every blocker edge above remains intact.

## Subsequent attempt 4 — 2026-09-19

[Attempt 4](ticket-19/stage-b-attempt-4-outcome.md) completed after the selector correction: Q3 now answers the single-label Change query correctly; Q1 retains a named inference limit, and full response-level audit remains incomplete. The user corrected the daily-feed premise: only session telemetry is available. Known recorded estimates for attempts 1/3/4 total approximately $2.6304; attempt 2 and provider actuals remain unknown. Retain $12 of reservations and the further-dispatch hold after the one-attempt exception. Four attempts do not establish qualification or Eyes selection; all blocker edges above remain unchanged.

## Next bounded preparation — 2026-09-19

[The local acceptance plan](ticket-19/local-container-acceptance-plan.md) was drafted planning-only, then the user authorized C0. [C0 is implemented](ticket-19/c0-capture-outcome.md): seven synthetic replay cases supported; full suite 334 passed / 36 skipped; bounded capture and proposed container source committed locally. Unix adapters/probes, receipt correlation/native-tool mapping and Linux/image pins remain preparation work before a concrete C1 card. C1 container execution and C2 disposable local Grafana remain NOT RUN and each require separate authorization. Local tests cannot establish intended-cluster isolation or retroactively complete the model audit. Ticket 19 remains claimed, ticket 12 blocked, all downstream edges unchanged.

## C1 preparation result — 2026-09-19

The user subsequently authorized the remaining preparation. [Source/pin outcome](ticket-19/c1-preparation-outcome.md): Unix adapters/probes, correlation/native mapping and Linux/base-image inputs are now prepared at prototype `3a16de9`; 363 passed / 36 skipped. The [first C1 execution card](ticket-19/c1-execution-card.md) is ready for review, with exact resource/build/start/cleanup scope and explicit unmeasured acceptance rows. No containers or native Linux client have run. C1/C2 execution gates, ticket 19/12 status, downstream edges and the paid-dispatch hold remain unchanged.

## C1 attempt 1 — 2026-09-19

The user then authorized C1 execution. [Attempt 1](ticket-19/c1-attempt-1-outcome.md) built both local derivatives and started four services, then stopped at Forwarder provisioning before admission or native MCP measurements. A certificate text/PEM-prefix mismatch is the probable source-level cause; runtime detail was redacted. Exact resources and transient secrets were removed and independently checked. The next bounded work is a PEM-only integration correction and its tests, followed by an explicitly authorized new attempt. No automatic retry, ticket resolution, blocker removal, C2/model run or reservation change follows.

## C1 attempt 2 — 2026-09-19

The user explicitly authorized a retry. [Attempt 2](ticket-19/c1-attempt-2-outcome.md) applied/tested the PEM correction (prototype `79b8ee6`, 365 passed / 36 skipped), passed live provisioning/baseline/identity/filesystem checks, then stopped at the interface inventory guard before admission. Nine additional tunnel-interface names were present with no IPv4 route rows; reachability was not measured and no bypass is established. Cleanup is independently verified. Next preparation is interface-state evidence and a reviewed network-admission predicate; another container attempt is not automatic. All ticket/blocker and paid-dispatch boundaries remain unchanged.

## C1 network guard prepared — 2026-09-19

[One bounded interface inspection](ticket-19/c1-network-guard-outcome.md) confirmed inactive tunnel links with no non-loopback addresses/routes; cleanup was verified. The state-based guard is prepared at prototype `7741d20` (409 passed / 36 skipped, 44 new tests), with operator integration specified in the next-run card. Full C1 measurement remains pending; direct-connect/native/correlation/containment claims and downstream blocker edges remain unchanged. No new model spend or reservation release followed.

## C1 attempt 3 and parallel preparation — 2026-09-20

[Attempt 3](ticket-19/c1-attempt-3-outcome.md) passed five native positive sessions (35/35 cases, 75 verified three-role receipt chains), the revised network guard and 12 pre-admission direct-connect denials. A 10 MiB + 1 byte Prometheus backend body returned success, refuting the fixture overflow expectation and stopping the negative suite. All retained payload hashes verify; cleanup is independently verified. Remaining negative/direct/final-snapshot checks are NOT RUN, and no fourth attempt is authorized. Sonnet/Opus headless preparations timed out without results; Codex prepared/tested the harness and Sol supplied independent review. Flash contributed the [C2 draft](ticket-19/c2-preparation-card.md), which remains unexecuted. Next preparation is a per-tool cap audit/correction and, independently, C2 startup/seed/configuration work. Ticket 19 remains claimed, ticket 12 blocked; qualification/spend-reservation boundaries remain unchanged.

## Parallel C1/C2 source preparation — 2026-09-20

[Preparation outcome](ticket-19/c1-c2-preparation-outcome.md): local prototype `f08f388` saves the per-tool cap correction, deterministic C2 seeds and explicit incomplete-oracle contract; full suite 429 passed / 36 skipped. The private remaining-check harness passes ten offline tests and has stronger exact probe/resource/secret checks. Sol adversarial review passed preparation with the C2 oracle execution gap; requested Fable review timed out after 480 seconds with no output and remains incomplete. The attempt-4 execution gate is closed. No new container experiment, C2 ingestion, qualification model run, ticket/blocker change or reservation release occurred. Next: diagnose the review path and obtain Fable; independently complete the C2 oracle/configuration/driver preparation.

## C1/C2 adversarial review completion — 2026-09-21 UTC

[Review follow-up](ticket-19/c1-c2-review-followup-2026-09-21.md): transcript diagnosis recovered the Fable review path; Fable and Sol completed source-preparation reviews. C1 cap/correlation/capture and operator evidence/cleanup checks are hardened, and C2 has a bounded direct-backend oracle with public Prometheus acceptance still blocked. Full prototype suite: **476 passed, 36 skipped**. No new container experiment or C2 ingestion occurred. The [attempt-4 card](ticket-19/c1-attempt-4-card.md) records final source/hash bindings and remains closed pending fresh execution approval. Ticket 19 stays claimed, ticket 12 blocked, and qualification/reservation boundaries remain unchanged.

## C1 attempt 4 — 2026-09-21 UTC

[Outcome](ticket-19/c1-attempt-4-outcome.md): the explicitly approved bounded run completed 7/7 positive and 13/13 negative cases, direct authority/revocation checks and final snapshots. Retained native MCP payloads and all 42 dispatched request chains were verified (40 exact responses, 2 expected transformations); independent Docker read-back confirms cleanup and base-image preservation. Large Tempo text was retained exactly; denied-request identity remains a named receipt gap. Full C1 matrix, real-backend/model/venue qualification and C2 remain incomplete. The single execution approval is consumed, with no fifth attempt authorized. Ticket 19 remains claimed, ticket 12 blocked, reservations unchanged.

## C2 operator source integration — 2026-09-21 UTC

[Preparation outcome](ticket-19/c2-operator-integration-outcome.md): the resolved four-service configuration compiler and injected seed/read-back driver are connected through actual compiler output and offline failure tests. Runtime configuration compatibility, real bounded transport, durable ingestion intent, account lifecycle and native policy remain unimplemented or unverified. The requested Fable invocation was rejected by the provider safeguard without a review; that requirement remains incomplete. No C2 runtime ran or was authorized. Ticket 19 remains claimed, ticket 12 blocked, with qualification and reservation boundaries unchanged.

## C2 transport and journal preparation — 2026-09-21 UTC

[Source outcome](ticket-19/c2-transport-journal-outcome.md): direct numeric HTTP transport and a one-shot durable ingestion journal are integrated through the real compiler and driver, using in-memory wire peers and private temporary files. The full suite passes 560 tests with 36 skipped; Ruff passes. Sol passed the bounded source review; the corrected `moonshotai/kimi-k3` review is recorded in the outcome. Fixed-length HTTP framing is the supported subset; actual backend compatibility, operator materialization/ownership, account lifecycle and native policy remain unverified or unimplemented. No C2 runtime, ticket resolution, blocker removal or spend-reservation release follows.

## C2 file materialization and ownership preparation — 2026-09-21 UTC

[Source outcome](ticket-19/c2-materialization-ownership-outcome.md): one-shot private configuration staging and exact receipt-bound cleanup selection are committed locally at prototype `6261ac8`. Full suite **583 passed, 36 skipped**; Ruff and Sol adversarial review pass. The fresh correct-provider Kimi review timed out without an opinion. Missing attachment inspection and FIFO substitution failures were corrected before validation. No engine creation/deletion, backend request or C2 runtime occurred. Durable engine receipts/executor, account lifecycle, native policy and compatibility execution card remain preparation work; runtime gates, ticket status and reservations remain unchanged.
