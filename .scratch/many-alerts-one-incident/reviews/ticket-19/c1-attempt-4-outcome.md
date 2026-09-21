# Ticket 19 — C1 attempt 4 outcome, 2026-09-21 UTC

**The bounded attempt-4 measurements passed; Fable and Sol returned PASS_WITH_FINDINGS.** One native positive session passed all seven cases, and one negative session passed all 13 cases. The previously unrun direct authority/revocation checks and final resource/network/filesystem snapshots completed. Retained payload and receipt verification passed, and independent Docker read-back confirms cleanup. This supports the [attempt-4 card](c1-attempt-4-card.md)'s exercised scope, not the complete C1 acceptance matrix. Ticket 19 remains claimed and ticket 12 blocked.

## Authorization and frozen inputs

The user's explicit “Approved” followed the status identifying C1 attempt 4 as the next execution requiring approval. Exactly one attempt ran. No retry, C2 runtime, qualification-model experiment, API-key refresh, push or publication followed. This authorization is consumed.

Prototype `5cbf616328ec7763a9987a9541c60a0fd6254c10` remained clean. Its 40 source hashes matched the reviewed manifest, SHA-256 `7acc563d7d46cd5db1a280fb3ffc4143833adb47b23ee6e0c7e59e23d975cfd3`. The approved executable SHA-256 is `e8e9add786fbae80dff837964c8877b3c809dee77dd6fa431575e9fbb44bc855`; it differs from the closed reviewed harness only in opening the gate and recording this approval. The closed original and preparation review artifacts remain unchanged. The approved copy and authorization record are private under `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/` and copied into runtime evidence.

The preceding source-preparation validation remains **476 passed / 36 skipped**, with **24 offline harness tests** and Fable/Sol reviews. No source code changed for execution; these tests were not rerun merely to relabel them as runtime validation. The experiment rebuilt derivatives locally with no network/pulls using the frozen original bases and Linux executable pin.

## Measured results

Both native sessions negotiated MCP `2024-11-05`, listed 22 tools with read-only annotations, completed unredacted captures, and exited/reaped without host transport escalation or open pipes. Native-child absence was separately checked after each session and at the final snapshot. Tool annotations are inventory evidence, not general behavioral write-denial proof.

| Exercised condition | Observed result |
| --- | --- |
| Seven positive fixtures | 7/7 exact fixture matches; 15 three-role receipt chains including initialization and datasource lookups. |
| Prometheus body sizes 10 MiB − 1, 10 MiB, 10 MiB + 1 | All three succeeded with 153-byte MCP frames, preserving attempt 3's counterexample to a universal backend-body cap. |
| Loki body sizes 10 MiB − 1 and 10 MiB | Both succeeded; the padded backend bodies decoded into 429-byte MCP frames. |
| Loki body size 10 MiB + 1 | Native tool error contained the exact pinned response-body overflow helper message. |
| Tempo body sizes 10 MiB − 1 and 10 MiB | Both succeeded. Decoded text was exactly 10,485,759 and 10,485,760 bytes, with hashes equal to the corresponding backend bodies. Full MCP frames of 10,485,884 and 10,485,886 bytes were retained and independently rehashed. |
| Tempo body size 10 MiB + 1 | Native tool error contained the exact pinned response-body overflow helper message. |
| Backend error, redirect, timeout | Native errors reported 500, 502 and 504 respectively; receipt transformations are explained below. |
| Prior-run query | Native Loki call returned 403. Its datasource lookup was forwarded, while two scope-denial records occurred within its serialized case window. |
| Direct Run authority probes before revocation | Valid 200; missing/wrong sentinel 401; write 403; untrusted CA and wrong hostname failed TLS verification. |
| Same direct probes after revocation | All four HTTP attempts returned 401; both TLS-negative variants still failed verification. |

The large Tempo frames now exercise the actual native transport and recorder, beyond the earlier Bundle-only test. Their large size is mostly padding: this does not establish meaningful large-result fidelity, model context limits, spill behavior, or whole-process memory bounds. The overflow case itself returned a small error, so retaining a hypothetical uncapped overflow response remains offline-tested only.

Twelve exact pre-admission gateway/backend-IP/port/private-socket connection probes were denied. Read-back verified eight before/final resource inventories, two full network snapshots, 11 baseline source files, 40 frozen host snapshot files and three native-child absence snapshots. Identity, capability, no-new-privileges, mount/tmpfs, memory/CPU/PID, forbidden-read and permitted-write checks passed at their observed times. These are sampled local Docker checks.

## Payloads, receipt joins and limits

All **178 events and 76 retained payload files** passed sequence, size and original/payload SHA-256 verification, with no redaction. Recorded RPC arguments matched the fixtures; fixture results were replayed using the pinned assessor. This assessor replay is distinct from the independent byte/hash and cross-service receipt checks.

There were **42 dispatched requests**: 15 in the positive capture, 26 in the negative capture, and one direct valid probe. Every request had exactly one dispatch/receive and response per service, matching request target/body hashes. **40** had identical response status/hash across all three services, including the backend 500 error. Two intentionally differed:

- Redirect: the backend returned 307 with an empty body; the gateway returned 502 with `redirect rejected`, and the Forwarder preserved that response.
- Timeout: the gateway returned 504 with `backend unavailable` before the backend's delayed 200 receipt. The Forwarder preserved the 504; the late backend response was not delivered as a successful native result.

The 12 Forwarder denials comprise six scope and six authority denials. Three scope denials fall inside otherwise successful Prometheus case windows (`metric`, `range`, first byte-boundary case); two fall in `prior_run_denied`, and one in direct probes. Denied receipts omit target/method/request ID, so exact denied-request identity cannot be reconstructed from these receipts. Serialized case-window attribution is supported; a specific auxiliary-probe explanation is not claimed. No denial was counted as a successful three-role chain.

## Timing and cleanup

| Session | First stdout from recorder start (ms) | Initialize RPC (ms) | Tool-list RPC (ms) | Query RPC range (ms) |
| --- | ---: | ---: | ---: | ---: |
| Initial | 293.201 | 286.232 | 12.247 | 15.442–25.680 |
| Negative | 230.601 | 221.989 | 12.416 | 13.616–758.778 |

RPC times run from recorded write intent to matched response, including Docker transport overhead. The two large Tempo responses took 752.984 and 758.778 ms; all RPCs stayed below the unchanged five-second bound. No pure binary startup or model latency claim follows.

The final ledger reports 58.472 seconds elapsed, including 14.885 seconds setup, 27.651 seconds measurement and 15.253 seconds cleanup. Its `finished_at` precedes the final secret scan/ledger update, so the wall-clock creation-to-finished interval is slightly shorter. Cleanup finished within its 120-second allocation.

Independent Docker inspection confirmed all four exact containers, the network, volume, four temporary tags and both derived image IDs absent; both original base images remain. Project-filtered residual lists were empty, and the operator-secret directory was removed. The harness-time final scan recorded zero matches for five registered synthetic secret values across the bounded raw/stripped/canonical-JSON forms. Post-run verification summaries, authorization copy and artifact index were added afterward and were outside that scan population. The deleted secrets were not recovered for another scan; no universal or post-verification secret-absence claim follows. Build cache was not pruned.

## Review and remaining work

Fable returned **PASS_WITH_FINDINGS** for the bounded runtime outcome in 114.931 seconds; Sol independently audited the raw retained evidence and also returned **PASS_WITH_FINDINGS**. These are separate from the passing source-preparation reviews. Private reviewer artifacts are under `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c1-attempt4-outcome/`.

Fable confirmed the count/transform reconciliation and identified the denied-request identity gap described above. A blocked auxiliary request or client retry is plausible but unproven. Its verifier-independence caveat is retained: fixture replay and expected body hashes come from the pinned fixture; cross-service hash agreement demonstrates consistency, not independent server provenance. Runtime guards check exact datasource-lookup identities; this post-run verifier does not reconstruct native query URLs to recompute their expected target hashes. Exact captured RPC arguments and fixture-policy checks provide the remaining request-context evidence.

The review packet summarized baseline and approved-harness binding; those were separately verified by the parent against retained files. Direct Run TLS failures are client trust checks, and no native MCP call ran after revocation. Cleanup covers recorded IDs, experiment labels and the scoped image prefix; it does not prove the absence of hypothetical unrelated or unlabeled resources.

The Fable review reported $1.37442025 in native session API-equivalent telemetry. This is reviewer usage, not C1 experiment model usage or daily billing. The C1 run did not invoke a model or use the test Claude API key.

Full C1 acceptance remains incomplete: native-client certificate variants, interruption/restart persistence, hard-termination/host-loss behavior, host orphan-process sweeping and default seccomp/CapBnd measurement are not established. The intended Kubernetes venue, live Grafana grants, real backend ingestion and model-facing behavior remain unqualified. C2 still needs exact configuration, authority/endpoint policy and seeder/driver integration; public Prometheus comparison remains gated and native Tempo LLM formatting unsupported. Ticket/blocker and retained spend-reservation boundaries are unchanged. No fifth C1 attempt is authorized.

## Evidence custody

Private runtime root: `/Users/jasonkrueger/maoi-stage-b-evidence/c1/attempt-4-20260920/`. The historical destination name was retained from the frozen card; timestamps identify the actual September 21 execution. `artifact-index.json` records **212 files / 79,991,201 bytes**, excluding the index itself, with exact hashes and sizes, with retention expiry `2026-10-21T05:00:50.185950+00:00`. Original captures, manifests and receipt files were not rewritten by post-run verification. Only summaries and evidence pointers are committed.

| Runtime artifact | SHA-256 |
| --- | --- |
| `ledger.json` | `eca2b338e5697042bd9e92eabda2921486d77743078967ddc05e7b2a7ef800c9` |
| `capture-verification.json` | `1acb998ae168de1ce18d7f4c3527a932e07e1a9db88ebea5f74415f4ef81a6a7` |
| `runtime-readback.json` | `60b2f876f3353a3d4bf5fd4550074fd6a5ee50e506a836c00d5e3c0c3b91c1a5` |
| `independent-cleanup.json` | `399c7d0cc3418bb19fba4e7f27c3c031e795a32a86af63bb7ac456b86485f0e9` |
| `artifact-index.json` | `718167fb6efb6767d96985c609a7497b5535279902ec311b87b851781fff5ef4` |
