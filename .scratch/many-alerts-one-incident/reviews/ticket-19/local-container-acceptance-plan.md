# Ticket 19 — remaining local acceptance plan, 2026-09-19

Current continuation: [September 21 review follow-up](c1-c2-review-followup-2026-09-21.md) records completed Fable/Sol source reviews, corrected C1 evidence checks and the bounded C2 oracle. The full suite passed 476 tests / 36 skipped. Attempt 4 remains closed pending fresh execution approval; C2 configuration, integration and runtime contracts remain preparation gates.

Current status: **C0 validated offline; C1 partially supported and incomplete.** [C1 attempt 3](c1-attempt-3-outcome.md) passed five positive native sessions (35/35 cases), the revised pre-admission network predicate and 12 direct-connect denials. It stopped at a counterexample: the Prometheus path accepted a padded backend body of 10 MiB + 1 byte despite the fixture's expected rejection. Cleanup is independently verified. Remaining negative/direct/final-snapshot checks are NOT RUN. This one retry is consumed; no fourth attempt follows automatically. [C2 preparation](c2-preparation-card.md) is drafted but C2 execution remains NOT RUN and separately gated. Ticket 19 remains claimed; ticket 12 remains blocked.

Subsequent [parallel source preparation](c1-c2-preparation-outcome.md) passed 429 tests / 36 skipped and prepared the corrected cap fixtures, C2 seeds and remaining-check harness. Required Fable review timed out without a result; the prepared harness has a closed execution gate. C2 also requires a complete response oracle before an execution card.

Historical preparation and acceptance targets follow; the measured per-tool exception above supersedes any universal interpretation of the 10 MiB helper constant.

Subsequent C1 preparation is now complete for the [first container measurement card](c1-execution-card.md): [source/pin outcome](c1-preparation-outcome.md), prototype `3a16de9`, 363 passed / 36 skipped. Unix adapters, receipt correlation, native-case mapping, probes and Linux/base-image pins are prepared. The first card covers a bounded subset of the complete C1 matrix below and names its unmeasured rows; no container execution or acceptance is implied.

Original planning authorization: the earlier "proceed" accepted drafting this bounded, local, model-free plan only. The plan itself authorized no implementation, Docker build/pull/start, service-account creation, model call, shared-tenant operation or cloud work. The planning validation at the end records that historical step.

## Decision this work should inform

Determine whether pinned mcp-grafana can deliver auditable telemetry results inside the copied Run-container boundary, through the scoped TLS Forwarder, against disposable local Grafana. Give ticket 12 a per-criterion evidence packet and a list of unresolved conditions. Do not automatically select Eyes, implement all of ticket 36, or require the separate three-Fault model qualification program merely to make this tool decision.

Attempt 4 answered the single-label Change question in one model sample. The remaining high-value work is complete response capture, timing attribution, filesystem/credential isolation and actual local Grafana grants/routing. No fifth paid fixture attempt is proposed.

## Current evidence and source constraints

Grounding: main `9a60396ffe99c1db5e7e2544072d374bb203a7e8`; prototype `3375fdbac41e844266e4c1135748799b019ce924` on `prototype/mcp-grafana-eyes`.

| Finding | Consequence for this plan |
| --- | --- |
| [Stage A](stage-a-verdict.md) exercised 31 native-client assertions on macOS, with exact fixture read-backs. | Reuse its cases and source references, but preserve the frozen source/evidence. Host measurements do not establish Linux-container behavior. |
| [Attempt 4](stage-b-attempt-4-outcome.md) completed and answered Q3; full MCP response transcripts are missing. | Build capture first. A fresh replay cannot reconstruct what the previous model actually saw. |
| `prototype/provenance/manifest.json` pins mcp-grafana v1.5.1 for **Darwin x86_64**. | Independently select and checksum the Linux artifact for the actual Docker engine architecture. Do not copy the Darwin binary or reuse its hash as Linux provenance. |
| Root `Dockerfile:20–24` specifies a Node tag, Claude Code 2.1.272 and jira-as 2.0.0. | Record source plus resolved platform/image digests and the built image ID. Use a throwaway derivative containing the Linux MCP binary and deterministic probe entrypoint. No Claude invocation is needed. |
| Root `docker-compose.yml:24–34` uses `otel-lgtm:latest`, anonymous Admin and host-published ports; the demo service reads `.env`. | Do not launch or extend that Compose project for this experiment. Use an independent definition with no demo provisioning, alerts, traffic, Receiver or `.env` inheritance. |
| `prototype/stage_a/run_stage_a.py:35–138` records matching JSON-RPC responses, but uses unbounded line/queue/stderr storage and discards unmatched messages from the transcript. | Reuse protocol sequencing conceptually, not its unbounded recorder as audit-ready code. Capture must preserve notifications, malformed/partial frames and failure evidence too. |
| Pinned `tools/response_utils.go` limits bodies read through that helper to 10 MiB; attempt 3 shows this is not universal across tools; Loki source defaults to 10 lines, caps at 100, and requests one extra to detect truncation. | Measure byte-limit behavior separately from line truncation and any later Claude presentation/spill behavior. These source constants are test inputs, not fresh container results. |
| Stage B's permissive-read fixture allows discovery and subset matching; frozen Stage A enforces exact allowed scope. | Keep their roles explicit. Do not adopt unrestricted Stage B reads as the ADR 0011 production authorization policy. |

## Sequence and authorization units

| Unit | Bounded deliverable | Execution boundary |
| --- | --- | --- |
| **C0 — source and capture preparation** | A new recorder/replay driver and offline tests under `prototype/local_acceptance/`; proposed container files, fixture manifest and redacted command plan. | Subsequently authorized and completed: [outcome](c0-capture-outcome.md), 334 passed / 36 skipped and seven synthetic replay cases. No Docker calls, artifact downloads, local Grafana account creation or model clients. |
| **C1 — Linux container with synthetic backend** | One isolated container session exercising the pinned Linux client, full capture, timing, authority negatives, file/mount checks and cleanup. | Separately approve exact image/binary pins, resource limits, topology and create/remove manifest. May build/pull only the listed artifacts and create only experiment-owned resources. No real Grafana account yet. |
| **C2 — disposable local Grafana** | The same client/recorder and accepted boundary against a fresh, pinned local Grafana/LGTM instance containing synthetic telemetry only. | Separately approve local instance provisioning, seeding and creation/revocation of local-only administrative and Viewer service-account credentials. No user's existing Grafana, cluster or shared tenant. |
| **Review — ticket 19 to ticket 12** | Compact result matrix, exact artifact pointers, remaining failures and a proposed tool/allowlist decision for human review. | Neither execution success nor this plan resolves 19 or unblocks 12 automatically. Preserve actual blockers until an explicit ticket decision. |

Implement C0 file-by-file: recorder and framing limits; deterministic case driver; capture/lifecycle tests; proposed container definitions; then evidence manifest and runbook. Verify each major step and run the full repository test suite before committing code. A source-ready C0 does not imply C1/C2 acceptance.

## Capture contract — close the actual audit gap

The operator-owned recorder and deterministic JSON-RPC driver sit outside the Run's writable filesystem, with the recorder on the driver's connection to mcp-grafana's stdio. Keep stdin/stdout separate from stderr and do not allocate a TTY. With Docker, record attachment/transport behavior separately from MCP behavior. Preserve every request and response in both directions, asynchronous notifications, stderr, EOF, malformed frames, partial frames, cancellation and process exit. Record sequence, RPC id, direction, monotonic timestamp, original byte count, digest and complete sanitized payload when within limits. Retain original bytes rather than reserializing JSON as the sole wire evidence.

Correlate each tool call with Forwarder and backend receipts using a case/session identity and request sequence; label ambiguous correlation explicitly. Keep expected fixture results and scoring outside Run mounts. Compare returned records and fields against that manifest, including all trace memberships and final suffixes; do not infer them from response-size increments. An injected recorder overflow or interrupted frame must produce a visible incomplete-capture result, not a semantic pass.

Use a bounded streaming reader, bounded queues and bounded stderr. Predeclare a maximum frame size above the intended successful 10 MiB boundary fixture, account for JSON escaping/wrapping, and test that it is enforced before unbounded allocation. Stop new dispatch when the bundle cannot fit the next known fixture. Keep each session bundle within **100 MiB**, total private evidence within **2 GiB**, raw retention within **30 days**. Exercise exhaustion with a deliberately reduced quota, preserving the failure marker and sanitized evidence that fits. Budget request bytes, responses, logs and temporary spool files together; hashes alone do not substitute for missing payloads.

Scan for every generated credential/sentinel and credential-shaped material before persistence. Capture known synthetic payloads only; redact account identifiers and credential fields while recording what was removed. A redaction or truncation that removes necessary support makes that claim unverifiable. Private capture directories are mode 700, files 600, outside Git and Run mounts. Each manifest includes creation/expiry dates, source/image/binary/config/fixture hashes and exact executed tool versions.

**Scope limit:** a deterministic MCP capture proves what that driver received. It does not measure Claude's context presentation, oversized-output spill files or model reading behavior. Any later model audit requires capture on the actual model-client path and preservation of the relevant tool-result/spill artifacts before cleanup; that is a separate authorized sample, not part of this plan.

## Timing contract

Capture, on the driver's monotonic clock: invocation start, first stdout byte, initialize request/response, initialized notification, tools-list completion, first permitted tool dispatch, first matching useful response, each query completion, interruption, EOF and reaping. Report initialization and tool-call intervals separately. Host-observed Docker attach/exec latency includes transport overhead; do not relabel it pure binary startup. Any in-container clock records use their own durations; never subtract monotonic timestamps across macOS and the Docker VM.

Predeclare one first session after container readiness and four fresh-client sessions against the same warmed services. List all five samples individually; this is not a percentile or dependable presentation-time claim. Measure container creation/readiness separately. Preserve the existing 1-second Grafana timeout for the initial comparative fixture cases and the driver's 5-second RPC bound; any change for real Grafana is a dated configuration amendment before that sample, never an invisible retry.

Proposed local execution bounds, to freeze on C1/C2 approval: ten minutes for artifact/build/readiness preparation, ten minutes for deterministic probes, followed by at most two minutes of cleanup. A missed bound stops new work and records what ran. These are local experiment bounds, not the ADR 0012 model Run budget. No automatic retry, larger allocation or replacement venue follows.

## Container and authority contract

Use a dedicated experiment identity and exact create/remove inventory. The Run image starts MCP or an explicitly selected filesystem/network probe, not the Receiver entrypoint, and inherits no host credential environment. The driver and expected-result manifest remain outside the Run. Retain the chapter-one Run constraints: non-root UID, read-only root filesystem, dropped capabilities, no-new-privileges, bounded CPU/memory/PIDs, declared tmpfs only, no Docker socket, host PID namespace, host home directory, cloud config or repository credential mounts. Record enforced runtime settings, not just the YAML proposal.

The intended client route remains a loopback TLS Forwarder endpoint per ADR 0011. The Run receives public CA trust and its scoped sentinel only. Server key, upstream token, CA signing key, administrative credentials and control authority stay outside Run mounts; the CA signing key remains outside the containers. The authenticated admission/revocation channel must be inaccessible to the Run by an enforced OS/mount/identity boundary. Merely omitting its token from environment is insufficient.

**Topology gate before C1:** a source proposal must name and justify the concrete network namespaces, identities, mounts and enforcement mechanism that allow the loopback route while preventing direct backend access. Sharing a network namespace can also make backend routes reachable; an internal Docker network or pod-style namespace alone is not proof of separation. The current fixture's HTTP control port is not accepted as isolated just because its token is absent. Do not resolve this gate by broadening the Run's privileges, giving it the upstream token, or substituting an unmeasured non-loopback topology. If the available local engine cannot enforce the intended isolation, narrow the recorded result to a container/client compatibility test and leave bypass/control isolation unestablished for human review.

This isolates the Grafana subset without implementing the complete five-service Forwarder. Kubernetes credential/OS/network acceptance in the intended cluster, and the mediated Anthropic path for a future model Run, remain separate.

## Deterministic case matrix

| Case | Required observation | Origin |
| --- | --- | --- |
| Handshake and tool inventory | Exact negotiated protocol/tools and separate startup/query timings; no unexpected write tools. | Linux native MCP, C1/C2 |
| Long/multiline logs and trace membership | Exact decoded records, newline preservation, all 12 matching trace ids and final suffix; default 10 has explicit truncation, raised limit returns all expected records. | Native MCP plus fixture truth |
| Line count versus byte cap | Samples below/at/above the configured line count and each verified per-tool backend-body boundary. The proposed universal 10 MiB rejection expectation was refuted for Prometheus in attempt 3; audit client paths and correct the contract before another execution. Use small per-case bundles that fit the capture quota. | Controlled synthetic backend, C1 |
| Metrics and traces | Exact instant/range values and timestamp scopes; a trace fetched by id, not merely a trace string found in logs; empty and failed results distinguishable. | Native MCP, C1/C2 |
| Real selector semantics | Single/full-label Change selectors agree; changed label order/spacing, negative match, line filter, exact count and direction/time-window cases match seeded local data. | Actual Loki through Grafana, C2 |
| Scope versus discovery | Required discovery works; prior-rehearsal Run/Change data and invalid scope expansions are denied. Metadata lookups are distinguished from actual denied telemetry dispatch. | Native MCP plus boundary/backend receipts |
| TLS/authority | Untrusted CA, hostname mismatch, expiry, wrong/absent/expired/revoked sentinel fail without insecure retry or unauthorized upstream execution. | Native MCP |
| Boundary write/target denial | Direct synthetic mutation, unsafe paths, unknown operations and redirect targets are denied independently of disabled MCP writes; redirect sink remains empty. | Explicitly labeled direct probe, not native-tool proof |
| Filesystem and credentials | Read/write probes under the Run UID cannot access upstream/control/key material or undeclared writable paths. Capture pre/post mounts, ownership/modes and allowed tmpfs contents as well as `docker diff`. | Deterministic in-container probes |
| Bypass | From the Run identity, direct Grafana access without upstream credential is refused, direct Loki/Prometheus/Tempo and control access fail, and only the intended mediated route succeeds. Check actual addresses/interfaces, not just DNS names. | Run-side network probes plus upstream receipts |
| Interrupt/restart | Timeout/disconnect/mid-query revocation are visible; child processes reaped; post-run sentinel rejected; Forwarder restart does not restore admissions. Partial requests/results remain marked uncertain. | Local lifecycle drill |
| Recorder failure | Malformed, asynchronous, oversized and partial frames; backpressure; quota exhaustion; abrupt child exit all preserve bounded, truthful failure evidence. | Offline C0 tests and selected C1 drills |

For filesystem evidence, inventory the read-only layer **and** all declared mounts/tmpfs; a clean `docker diff` does not inspect every mount. Probe persistence across an ordinary process restart separately from destruction/recreation of the container/tmpfs. Do not describe tmpfs as surviving container stop/removal. Docker documents filesystem mounts separately from the writable layer and describes tmpfs lifecycle in [container storage](https://docs.docker.com/engine/containers/run/#filesystem-mounts) and [tmpfs mounts](https://docs.docker.com/engine/storage/tmpfs/).

## Disposable real Grafana preparation, C2

Pin Grafana/LGTM and every required backend image by verified platform digest; record versions from the actual instance. Disable anonymous access and public exposure. Seed a minimal, timestamped synthetic dataset via an operator-only path: application logs with known trace membership, current/prior Run and Change streams, a known metric range and an actual retrievable trace. Freeze ids, labels, time windows, expected counts and readiness queries before probing; bounded ingestion readiness polling is setup, not permission to re-seed or retry failed acceptance cases silently.

Create a temporary local service account with the minimum read role confirmed against the pinned version, initially Viewer. Grafana documents service-account roles as controlling their access; a role alone does not establish rehearsal/query isolation ([service accounts](https://grafana.com/docs/grafana/latest/administration/service-accounts/)). Keep setup/admin authority with the operator and the Viewer token only in the Forwarder. Validate anonymous refusal, the required permitted reads, and a narrowly scoped write-denial probe against an experiment-owned disposable resource with before/after read-back. No shared resource can be the target. The Forwarder must still enforce operations and query scope independently of the role.

No tokens are minted in this planning step. Remove/revoke the experiment's local credentials during teardown; preserve redacted grant/read-back receipts. If the role, API, topology or image pin differs from the proposal, update the card before execution.

## Result packet, stop rules and cleanup

Emit one criterion row with verdict `supported for exercised scope`, `refuted by named failure`, or `inconclusive`, execution origin, artifact hash/path, configuration, evidence completeness and explicit limits. Keep reported client errors, boundary causes and actual backend effects distinct. Native tool omissions of diagnostic bodies are a finding, not permission to substitute a boundary log as what the tool returned.

Stop admission on an unexpected writable credential path, reachable control/backend bypass, silent truncation, unusable capture, failed cleanup, source/hash mismatch or incorrect target identity. Preserve bounded sanitized evidence, revoke sentinels, terminate/reap owned processes, and report the failed criterion. No fallback eyes CLI or model attempt follows automatically; the existing protocol permits comparing a fallback only when a demonstrated requirement failure justifies it.

Before removing containers, collect the declared filesystem/mount read-backs and evidence. Teardown addresses only exact recorded container, volume, network and local-account identities from this experiment; no broad prune, shared Compose teardown or cleanup of unrelated resources. Verify removal, revoked authority, closed experiment listeners and absence of owned children. Keep private audit artifacts until their bounded retention deadline; cleanup must not remove the evidence directory.

The final review should distinguish local source readiness, synthetic Linux-container proof, actual local Grafana proof, model/audience usability and intended Kubernetes venue proof. It may propose bounded conditions for ticket 12, but cannot erase missing venue, control isolation or response evidence. The four Stage B reservations remain **$12 retained**, provider actuals remain unknown, and the paid-dispatch exception remains consumed.

## Planning validation

This plan was checked against the current Dockerfile/Compose source, ADRs 0011–0014, Stage A protocol/recorder/source captures, and attempt-4 results. No Docker daemon inspection, artifact fetch, image build, container, service-account operation, code change, model call or cloud action was performed. Test execution is **NOT RUN** for this documentation-only step; the earlier **295 passed, 36 skipped** belongs to prototype `3375fdb`, not this plan. Final validation is local link resolution, whitespace checks and read-back of ticket/frontier pointers. All changes remain local; no publication is authorized.
