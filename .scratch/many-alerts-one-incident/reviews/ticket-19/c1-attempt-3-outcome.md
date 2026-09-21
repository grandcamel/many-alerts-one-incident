# Ticket 19 — C1 attempt 3 outcome, 2026-09-20

**Partial support; stopped at a refuted byte-limit expectation.** All five native positive sessions passed their seven cases (**35/35**), with complete unredacted payload verification and 75 exact backend/gateway/Forwarder receipt chains. The third negative byte-boundary case accepted a 10 MiB + 1 byte Prometheus backend response where the fixture expected rejection. The harness stopped and cleanup is independently verified. This consumes the one retry authorized in the [execution card](c1-execution-card.md); no fourth attempt ran. C1 acceptance is incomplete, ticket 19 remains claimed and ticket 12 blocked.

## Scope, preparation and dispatch

Prototype source remained clean at `7741d2060aceb9bb475a42c2f9f3adc5f3c1db7e`. Prelaunch full suite: **409 passed, 36 skipped**, 445 collected in 21.06 seconds. Four additional offline operator-harness tests passed, covering network-state agreement/rejection, absolute deadlines, native-child absence probe syntax and refusal without the execution flag. No prototype source changed in this batch.

The approved parallel dispatch produced a usable Gemini Flash C2 draft. Sonnet harness and Opus guard invocations each timed out after the 480-second ceiling with empty stdout; neither is a passing review. Codex prepared and tested the harness locally. A fresh native GPT-5.6 Sol review returned **PASS_WITH_FINDINGS**, with no blocking finding under the mandatory operator checks. Its low-severity typed-netlink-attribute validation gap and point-in-time inventory limitation remain documented; no network profile or privilege was broadened. Reports, command/status records and staged inputs are private at `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260920-c1-batch/`.

The [C2 preparation card](c2-preparation-card.md) incorporates the Flash draft after source verification and correction of its assumptions. Image registry metadata was inspected; no C2 image was pulled, built or started. The bundled LGTM candidate still needs a verified non-root, read-only, offline startup design and separate source/configuration/seed support. Claude session costs are not established by the timeout records. No qualification model run, reservation release, push or publication occurred, and the test API key was not needed for C1.

## Measured support

Provisioning, pinned identities, capability removal, read-only/no-new-privileges settings, resource/mount/config checks, 11 baseline file hashes and the revised five-dump network predicate passed before admission. Twelve exact direct-connect probes were denied: both recorded gateway/backend IPs at ports 8081, 3000, 3100, 9090 and 3200, plus two private Unix sockets. These are exercised pre-admission address/socket checks, not a durable guarantee against privileged host changes or intended-cluster proof.

One fresh admission served initial and four warm native processes. Each negotiated MCP `2024-11-05`, exposed 22 tools with `readOnlyHint: true`, and passed all seven positive fixtures. Annotations are inventory evidence, not a behavioral write-denial test. Each session had independently verified event/frame sizes and hashes, complete unredacted payloads and 15 three-role receipt joins. After each positive session, the Run probe observed no native MCP child or wrapper; the host transport exited zero, was reaped, and left no process group or open pipes, without escalation.

| Session | First stdout from recorder start (ms) | Initialize RPC (ms) | Tool list RPC (ms) | Seven query RPC range (ms) |
| --- | ---: | ---: | ---: | ---: |
| Initial | 358.341 | 349.860 | 15.487 | 18.167–54.173 |
| Warm 1 | 304.201 | 296.672 | 9.618 | 15.748–34.036 |
| Warm 2 | 261.649 | 254.006 | 8.209 | 17.047–29.780 |
| Warm 3 | 257.863 | 247.113 | 8.161 | 18.794–31.140 |
| Warm 4 | 289.229 | 275.092 | 12.082 | 19.029–29.492 |

RPC intervals run from recorded write intent to matching response and include observed Docker transport overhead. First stdout includes recorder/launch overhead; none of these measurements is pure binary startup or model latency. Complete per-query timings remain in `capture-verification.json`.

## Counterexample and unrun checks

The three exercised Prometheus fixtures returned valid JSON padded with trailing whitespace to exactly 10,485,759, 10,485,760 and 10,485,761 bytes. All returned HTTP 200 through the three-service path and the same successful 153-byte native result. The first two matched their fixture expectations; the last refuted the expected overflow error and raised `native_fixture_mismatch`. Matching request/response hashes confirm delivery through each service. The negative capture retains seven exact receipt joins (82 across all sessions); all retained payload hashes verify and the payloads are unredacted. Its manifest truthfully remains `complete: false` due to the semantic failure. The generic verifier message “incomplete or redacted capture” does not mean payload redaction occurred; `negative-boundary-analysis.json` disambiguates this.

This refutes a universal 10 MiB **backend-body** rejection expectation for the exercised Prometheus query path. It does not show a 10 MiB MCP result, an unbounded allocation, a meaningful-result-size limit bypass, or model presentation/spill behavior. At the pinned upstream commit, [Prometheus backend source](https://github.com/grafana/mcp-grafana/blob/2a33c72f211560e4ffb39d6b99cad3c3dc2a3f6e/tools/prom_backend.go) constructs the Prometheus API client and delegates queries to it, instead of invoking the shared `readResponseBody` helper. This source observation is consistent with the measured tool-specific behavior; the entire client dependency has not been audited. The exact source copy and hash are retained privately.

**NOT RUN after the stop:** error, redirect, timeout and prior-run negative cases; direct valid/missing/wrong credential, write, CA and hostname probes; post-revocation 401 check; final full network/filesystem snapshot. Native certificate variants and in-container interruption/restart drills also remain outside this measurement. The negative host transport exited zero and was fully reaped without escalation; a post-failure process snapshot showed only the Run hold process. That observation does not replace the unrun final network/filesystem checks.

## Cleanup and evidence

The run lasted 77.056 seconds, from `2026-09-20T16:55:10.771523+00:00` to `2026-09-20T16:56:27.827239+00:00`; setup took 14.143 seconds and cleanup 8.954 seconds. Cleanup revocation returned zero. Independent read-back confirmed all four exact container IDs, experiment network/volume/tags and both derived image IDs absent; both original base images remain and the transient operator-secret directory is absent. The capture scan found zero matches for the five known secret values. Build cache was not pruned.

The new Run derivative was `sha256:ec6e05ce7d33491036fd815dc34aece8736fc45a2c6e9f2c8bda609de4027a3f`; service derivative was `sha256:f4c61c6e7d435e591d22e50c2a5151e464d45014d9f4d2a668d2fd0676e00c50`. Both were removed. Engine, base and executable pins remained those frozen in the execution card.

Private runtime evidence: `/Users/jasonkrueger/maoi-stage-b-evidence/c1/attempt-3-20260920/`. The verified index contains 254 files / 59,295,545 bytes, excluding the index itself. Retention expires `2026-10-20T16:55:10.771523+00:00`. Evidence/capture directories are private; readable build-context source and public CA modes are deliberate exceptions beneath the private root. No raw captures or authority values are committed.

| Artifact | SHA-256 |
| --- | --- |
| `ledger.json` | `c63a8823431e7eaf8cc83ab63f74246b02846a66dedc027c88c2451d0a95e6d5` |
| `capture-verification.json` | `cee6882059eda0e39c02cac3eb1a3ec2c494f48e34f86a528708d0588da2cb82` |
| `negative-boundary-analysis.json` | `6b3d85773cad405705326bdae7676d7997f1ad5018dbfef39e7831e796608d53` |
| `independent-cleanup.json` | `cd6edd60e99ec3c525e16595b9f1dcf76b12a1bb43399d42791857a70b79af84` |
| `artifact-index.json` | `9903fb62d8c59422cdabea8481ecba0e5f6e94d174e319490ef53c385e3d7040` |

The prelaunch verification manifest and harness hashes remain frozen in the execution card. The private pinned Prometheus backend source SHA-256 is `7f109edd7460f62800c2d21a34f394af6c6d86672d67bc5478e5f3cb584b3776`.

## Next bounded work

Prepare a per-tool response-limit audit and correct the fixture/acceptance contract against the actual client paths. Preserve this counterexample; do not merely relax the failing expectation or infer a universal cap. Prepare a subsequent bounded card for remaining negative/direct checks after that correction, with any necessary positive regression cases justified explicitly. Independently, C2 startup/configuration and seed preparation can continue in parallel because it does not require another C1 execution. A further container attempt or C2 provisioning needs its own concrete authorization; neither follows automatically from this result.

## Subsequent adversarial scan qualification — 2026-09-20

Review of the inherited operator harness found that its original raw-value scan and post-serialization replacement could miss JSON-escaped multiline PEM keys. The historical “zero matches” result above is retained with that limitation; it is not a complete escaped-value check. A separate read-only inspection of all 255 retained files (including the index) found no raw/JSON-newline private-key header followed by a base64-like key body. That pattern check is also bounded and does not recover the deleted original keys or prove absence under every encoding. Report: `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/attempt-3-secret-scan-followup.json`. The original runtime evidence/index remains unchanged. The prepared attempt-4 harness fixes structured redaction and scans additional canonical forms across all regular file types.
