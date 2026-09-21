# mcp-grafana behind the sentinel

Type: prototype
Status: claimed
Blocked by: none

## Question

Run `mcp-grafana` as a stdio MCP server inside a copy of the chapter-one image, read-only (`--disable-write --enabled-tools ...`), pointed at the Forwarder with a sentinel as its token, against an `otel-lgtm` with anonymous access off and a Viewer service account, and drive a print-mode Run against it with the allow list naming its tools. Answer what only running it can: do its tool names read well in the log window; do the output cap and the Loki line default fit a five-minute Run; what does the MCP startup wait cost; does the Forwarder's Bearer swap work unchanged; and what does `docker diff` and the denial line show. Compare against a stub of the `eyes` CLI on the same questions if time allows. The throwaway lives on a `prototype/mcp-grafana-eyes` branch.

## Input from ticket 17

[ADR 0011](../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) settles loopback HTTPS with trusted deployment-local CA, a Grafana-specific sentinel, fixed upstream destination and request-aware read/rehearsal scope. The prototype must test client trust and these boundaries rather than assume the old HTTP Basic-auth Forwarder works unchanged. This planning update does not authorize running the prototype.

## Work in progress

Claimed for offline experiment preparation after ticket 17 was resolved. The current session does not execute the model/container prototype. Preserve an explicit NOT RUN result; preparation cannot resolve this measurement ticket or unblock Eyes.

An [experiment protocol](../reviews/ticket-19/experiment-plan.md) now separates real-client transport checks from a later bounded model experiment and defines evidence/decision rules. All execution remains NOT RUN. It requires only an isolated ADR 0011 Grafana subset, not completion of ticket 36, avoiding a dependency cycle through Eyes.

The [offline fact sheet](../reviews/ticket-19/facts.md) resolves historical token-variable naming as a configuration bridge and confirms that the referenced research did not execute mcp-grafana. It therefore provides no measured startup, tool-output or TLS/sentinel compatibility verdict. Ticket 19 stays claimed and unresolved; ticket 12 stays blocked on the actual prototype.

## Protocol refresh after the planning frontier

The accepted decisions through ticket 40 now leave Eyes/Report as the unresolved dependency path for the remaining specifications. The [frontier audit](../reviews/planning-frontier-2026-09-18.md) records the actual edges. The existing experiment protocol has been reconciled with the five-service target, model-free local Stage A subset, mediated Anthropic requirement for Stage B, 300-second Run policy, diagnostic budget and private evidence capture. No stage is executed and no blocker is removed. The next concrete step is explicit authorization to implement/run the bounded local Stage A prototype; model/tenant/cloud gates remain separate.

## Local Stage A authorized — 2026-09-18

The user subsequently authorized implementation and execution of the model-free local subset. Earlier NOT RUN statements above describe preparation history. The isolated prototype starts from `3e17793` on `prototype/mcp-grafana-eyes`; model/container/tenant/cloud gates remain NOT RUN. Local results do not resolve this ticket or unblock Eyes.

## Local Stage A result

[Stage A verdict](../reviews/ticket-19/stage-a-verdict.md): 31 exercised assertions supported, zero refuted, using real pinned mcp-grafana v1.5.1 against synthetic local TLS/Forwarder/backend fixtures. Frozen prototype commit `5f90bfbb20a5a63edecaa118d9a214c0e08389e4`. Full repository suite: 241 passed, 36 skipped. This is transport-scope evidence only. Model usability/budget, container confinement, real tenant and intended-venue gates remain unexecuted; ticket19 stays claimed and ticket12 blocked.

## Stage B readiness assessment — 2026-09-18

[Stage B readiness/gap assessment](../reviews/ticket-19/stage-b-readiness.md): current `claude` CLI 2.1.272 self-documentation captured; the official `claude-api` skill is now installed; and the P1 local routing probe (prototype commit `1973f90`) measured that the client honors a base-URL override with a per-Run sentinel over streaming SSE. Remaining pre-Stage-B work: the TLS fifth-endpoint subset, billing/rates preflight, and the experiment card. Stage B remains NOT RUN and separately unauthorized; no blocker edge changes.

## Stage B attempt 1 — 2026-09-18

The user authorized exactly one bounded attempt; it executed against the synthetic fixtures with a real model through the mediated endpoint. [Outcome](../reviews/ticket-19/stage-b-attempt-1-outcome.md): boundary/budget/containment/sentinel/denial contracts **supported** ($0.286 client estimate vs $3 reservation, 82 s of 270 s, post-run sentinels 401); fixture-question usability **inconclusive due to fixture under-specification** — the exact-query allowlist denies the discovery endpoints a real client needs. Options 1–3 for any second attempt are recorded in the outcome; each needs new authorization and respects the P3 reconciliation hold. Ticket 19 stays claimed; ticket 12 stays blocked.

## Stage B attempts 2–3 — 2026-09-18

User directed unrestricted reads (no SI/PII in synthetic fixtures); fixture amended to permissive-read with discovery endpoints. Attempt 2 was interrupted by an infrastructure containment failure (fixed; no evidence; spend unknown pending daily feed). Attempt 3 completed: [outcome](../reviews/ticket-19/stage-b-attempt-2-3-outcome.md) — mechanics supported (198 s of 270 s, $1.1392 estimate matching token accounting exactly), Q1/Q2/Q4 supported with the model demonstrating discovery-driven probing, Q3 refuted by a named selector gap (fixture exact-match stricter than real Loki). Options for any attempt 4 recorded there; ticket 19 stays claimed, ticket 12 stays blocked.

## Stage B attempt 4 — 2026-09-19

The user corrected billing visibility to session telemetry only and authorized one $3 attempt after the fixture selector correction. [Outcome](../reviews/ticket-19/stage-b-attempt-4-outcome.md): completed in 222.531 s; $1.20549925 token-derived estimate matches the client estimate; both post-run sentinels returned 401; key file deleted. Q3's single-label Change query now succeeds and the answer matches fixture ground truth; Q2 and honest deletion non-attempt are supported for exercised scope. Q1's correct count/suffix retains explicitly inferred trace membership for records 5–11. Client-version drift and missing full MCP response transcripts remain evidence limits. Provider actuals remain unknown, all $12 of reservations are retained, and the one-attempt exception is consumed. Ticket 19 stays claimed; ticket 12 stays blocked; no qualification or blocker removal follows.

## Remaining local acceptance plan — 2026-09-19

The user authorized drafting the [bounded model-free plan](../reviews/ticket-19/local-container-acceptance-plan.md): C0 source/capture preparation, C1 synthetic Linux-container checks, C2 disposable local Grafana, then a criterion-level review for Eyes. No implementation or container execution is authorized by that planning instruction. The plan identifies the Darwin-only binary pin, unsuitable existing Compose configuration, incomplete MCP capture and unresolved loopback/control/bypass enforcement as concrete preparation gates. Ticket status and blocker edges remain unchanged.

## C0 source and offline capture completed — 2026-09-19

The subsequent "proceed" authorized C0. [Outcome](../reviews/ticket-19/c0-capture-outcome.md): bounded recorder/driver, fixtures, container proposal and tests committed locally at prototype `69c3999`; full suite **334 passed, 36 skipped**, including 39 C0 tests. Seven synthetic replay cases matched with verified complete, unredacted payload evidence and process cleanup. No Docker, download, credential, model or cloud operation ran. Unix adapters/probes, correlation/native-tool mapping and Linux/image pins remain preparation work before C1. C1/C2 are NOT RUN; attempt 4's model-response audit remains incomplete, $12 reservations remain retained, and ticket/blocker status is unchanged.

## C1 source and pin preparation completed — 2026-09-19

The next "proceed" authorized adapter/probe/pin preparation. [Outcome](../reviews/ticket-19/c1-preparation-outcome.md): prototype `3a16de9`, full suite **363 passed, 36 skipped**, including 29 new tests. The scoped Unix adapters, correlation, native-case driver, Run probes and Linux/base-image pins are prepared; the downloaded Linux binary was not executed. The [first C1 execution card](../reviews/ticket-19/c1-execution-card.md) freezes exact resources, build/start commands, measurements and cleanup for separate execution approval. Docker inspection/rendering and host synthetic tests do not establish container acceptance. Native certificate variants and in-container interruption/restart drills remain unmeasured by this first card; C2 remains unimplemented. Ticket/blocker status, paid-dispatch hold and $12 reservations are unchanged.

## C1 attempt 1 stopped at provisioning — 2026-09-19

The user authorized the first C1 execution card. [Outcome](../reviews/ticket-19/c1-attempt-1-outcome.md): both pinned local derivative builds and four-service creation succeeded; backend/gateway became ready; Forwarder provisioning failed before admission. Source inspection and an offline shape reproduction point to OpenSSL certificate text preceding the PEM block, rejected by the provisioner's PEM-first check; the redacted runtime error does not directly confirm that root cause. The attempt stopped without retry. All experiment resources and transient secrets were removed, with independent read-back; original base images remain. No native MCP session or runtime boundary probe ran. Ticket 19 remains claimed, ticket 12 blocked, and all paid-dispatch reservations/holds are unchanged.

## C1 attempt 2 stopped at interface inventory — 2026-09-19

The user explicitly requested another attempt after reporting lid closure. [Outcome](../reviews/ticket-19/c1-attempt-2-outcome.md): the PEM handoff correction at `79b8ee6` passed 365 tests / 36 skipped; all services then became ready, 11 baseline file hashes matched, and exercised identity/private-file/write-path checks passed. The Run listed nine tunnel interfaces in addition to `lo`, violating the card's literal interface guard despite an empty IPv4 route table. The run stopped before direct-connect probes, admission or native MCP; interface state/reachability remain unmeasured. All exact resources and transient secrets were removed and independently checked. No third container attempt, ticket/blocker change, C2/model run or spend-reservation change followed.

## C1 interface inspection and guard preparation — 2026-09-19

[Inspection and correction](../reviews/ticket-19/c1-network-guard-outcome.md): one bounded network-none base container confirmed the nine extra tunnel links were down, unaddressed and unrouted; only loopback addresses and four local-table routes existed. Exact cleanup is verified. Prototype `7741d20` adds bounded rtnetlink capture and a strict state predicate with 44 rejection/replay tests; full suite 409 passed / 36 skipped. The execution card now contains the prepared replacement checks. No full C1 retry, sentinel admission or MCP ran. Ticket 19 stays claimed, ticket 12 blocked; remaining native/model/venue and reservation boundaries are unchanged.

## C1 attempt 3 and parallel preparation — 2026-09-20

[Attempt 3](../reviews/ticket-19/c1-attempt-3-outcome.md) passed five native positive sessions (35/35 cases, 75 verified three-role receipt chains), the revised network guard and 12 pre-admission direct-connect denials. A 10 MiB + 1 byte Prometheus backend body returned success, refuting the fixture overflow expectation and stopping the negative suite. All retained payload hashes verify; cleanup is independently verified. Remaining negative/direct/final-snapshot checks are NOT RUN, and no fourth attempt is authorized. Sonnet/Opus headless preparations timed out without results; Codex prepared/tested the harness and Sol supplied independent review. Flash contributed the [C2 draft](../reviews/ticket-19/c2-preparation-card.md), which remains unexecuted. Next preparation is a per-tool cap audit/correction and, independently, C2 startup/seed/configuration work. Ticket 19 remains claimed, ticket 12 blocked; qualification/spend-reservation boundaries remain unchanged.

## Parallel C1/C2 source preparation — 2026-09-20

[Preparation outcome](../reviews/ticket-19/c1-c2-preparation-outcome.md): local prototype `f08f388` saves the per-tool cap correction, deterministic C2 seeds and explicit incomplete-oracle contract; full suite 429 passed / 36 skipped. The private remaining-check harness passes ten offline tests and has stronger exact probe/resource/secret checks. Sol adversarial review passed preparation with the C2 oracle execution gap; requested Fable review timed out after 480 seconds with no output and remains incomplete. The attempt-4 execution gate is closed. No new container experiment, C2 ingestion, qualification model run, ticket/blocker change or reservation release occurred. Next: diagnose the review path and obtain Fable; independently complete the C2 oracle/configuration/driver preparation.

## C1/C2 adversarial review completion — 2026-09-21 UTC

[Review follow-up](../reviews/ticket-19/c1-c2-review-followup-2026-09-21.md): transcript diagnosis recovered the Fable review path; Fable and Sol completed source-preparation reviews. C1 cap/correlation/capture and operator evidence/cleanup checks are hardened, and C2 has a bounded direct-backend oracle with public Prometheus acceptance still blocked. Full prototype suite: **476 passed, 36 skipped**. No new container experiment or C2 ingestion occurred. The [attempt-4 card](../reviews/ticket-19/c1-attempt-4-card.md) records final source/hash bindings and remains closed pending fresh execution approval. Ticket 19 stays claimed, ticket 12 blocked, and qualification/reservation boundaries remain unchanged.
