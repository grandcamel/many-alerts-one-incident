# Ticket 19 — C2 preparation card, 2026-09-20

**Draft; no C2 execution authorized or performed.** The user approved parallel preparation alongside the C1 harness and guard review. Gemini Flash supplied a bounded draft; Codex adjudicated it against the existing plan and primary source. The proposed local Grafana experiment remains dependent on C1 results, completed source/config preparation and a final exact-resource execution card.

[C1 attempt 3](c1-attempt-3-outcome.md) now supplies five passing positive sessions, but its Prometheus byte-limit counterexample leaves C1 incomplete. Carry that per-tool limit audit into C2 preparation; do not inherit a universal 10 MiB cap assumption or treat the unrun negative/direct checks as passed.

## Candidate inputs verified without pulling or running images

The [v0.33.1 release](https://github.com/grafana/docker-otel-lgtm/releases/tag/v0.33.1), published 2026-09-18, is the candidate bundled LGTM input. Registry metadata returned:

| Input | Pin |
| --- | --- |
| `docker.io/grafana/otel-lgtm:0.33.1` index | `sha256:d6c52678ab5b7144f27ae569fd778608121c0f4a10eb411983750a0d67c1fbe3` |
| Linux/amd64 manifest | `sha256:35da4355c58162b6f27ccbd43c6214d565bc29fc9b18baaf43b59202c354577b` |
| Existing Run base | `sha256:5abb2fb0c6bebe246ee31e56e4634edc92fe8b3be75bc5dcd12cf00f0592abe9` |
| Existing adapter Python base | `sha256:51cce855bb6e44a8ff6ed0f46ded8850f246bfc7549801459f83fc34b80c210f` |
| Native mcp-grafana Linux/amd64 | v1.5.1, binary SHA-256 `208b71a4f1cf707834734671c6d784a8db4ffcf414a182ddc38d21384de8e125` |

The [tagged Dockerfile](https://github.com/grafana/docker-otel-lgtm/blob/v0.33.1/docker/Dockerfile) declares Grafana v13.2.1, Prometheus v3.14.0, Tempo v3.0.3, Loki v3.7.7 and collector v0.160.0. These are source declarations; executable versions still require instance read-back. No C2 image was pulled, built or started.


The C2 candidate image config was also read directly from the pinned amd64 manifest: no `User` override is set; `Cmd` is `/otel-lgtm/run-all.sh`; version environment entries match the tagged source above. This is registry configuration evidence, not proof of successful container startup.

**Candidate compatibility is unresolved.** The tagged Dockerfile has no final non-root USER, and its Grafana startup script sets paths under `/data` and forces a plugin preinstall entry. The unmodified image is not assumed to meet read-only-root/non-root/offline-start requirements. Inventory every startup write and plugin/network dependency, then prepare an exact derivative or separate pinned backend images. Do not silently relax privileges or enable runtime internet to make this candidate work. Derived image IDs and configuration/source hashes are not yet available.

## Proposed topology and ownership

Preserve the C1 Run network-none namespace, with the Forwarder sharing that namespace and serving loopback TLS. Run stays UID/GID 1000, read-only, capability-free, no-new-privileges, 2 CPUs/2 GiB/256 PIDs with the existing three tmpfs mounts. It receives public CA trust and its scoped sentinel only. Apply the measured network-state predicate plus exact-address denial probes; inactive tunnel interfaces are not described as absent.

Forwarder and gateway remain UID/GID 2000, each 1 CPU/256 MiB/64 PIDs, with private control/config/receipt tmpfs and a mode-700/600 data Unix socket boundary. Only the gateway and local Grafana/backend side attach to the dedicated internal network. There are no published ports, host PID namespaces, Docker sockets, host homes, repository `.env` files, existing tenants or cloud resources in any Run mount.

A separate C2 project/name inventory must be frozen before execution. The backend's exact non-root UID, resource limits, writable mounts and component list remain unresolved until candidate startup is inspected. Reuse the pinned Python base for a bounded operator seeder if its installed standard library suffices; otherwise declare and verify the additional dependency rather than inventing a seeder image digest.

C1 source cannot be used unchanged: `service.py` fixes gateway port 8081, `c1_cases.py` fixes synthetic requests/results, and the native driver fixes the C1 project identity. C2 needs separate explicit configuration/case/identity support and tests; preserve frozen C1 source and evidence. Grafana's Viewer role supplements the Forwarder scope policy and does not replace it.

## Deterministic seed contract

At setup, choose one recent UTC `T0` safely before ingestion, then freeze its exact value, IDs, labels, query windows, payload hashes and expected result sets. Every query in a sample uses that frozen manifest. Do not reuse the C1 fixture's January timestamp against live storage or weaken ingestion limits to accommodate stale seeds: Loki's documented [old-sample limits](https://grafana.com/docs/loki/latest/configure/) must be checked for the pinned configuration.

Prepare these synthetic records before execution:

- Twelve application log entries, including multiline payloads and an explicit expected trace-membership list. Distinguish default ten-line truncation from an explicit limit returning all twelve; preserve final suffixes exactly.
- Current Change and Run streams with multiple labels, plus prior-rehearsal streams. Compare single-label/full-label selectors, label ordering/spacing, negative match, line filters, time windows and direction. Prior-scope queries must be denied by the Forwarder rather than merely returning empty data.
- A known metric series over a fixed interval, with separately declared instant evaluation time, range steps/values and an empty-series query. Confirm whether the pinned backend uses Prometheus or another compatible engine and verify its ingestion path.
- One retrievable trace with a declared root/child-span structure and exact IDs linked to the log ground truth. Verify the actual Tempo/OTLP ingestion contract; do not assume one span count or response shape from C1's synthetic JSON.

Use a bounded operator-only seed path. Readiness polls verify the complete manifest through exact local endpoints within a predeclared setup allowance; a timeout stops the experiment. No silent re-seeding, changed time windows or retry of an acceptance case follows failed readiness.

## Authority and evidence checks

The operator creates one disposable administrative setup credential, one local Viewer service account and one token. Record exact account/token IDs privately for revocation, never token values in arguments or evidence. Verify the pinned Grafana API contract first; the current [service-account API documentation](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/serviceaccount/) documents distinct account/token management operations.

Inject the Viewer token only into Forwarder private configuration via stdin. Run uses its sentinel at the Forwarder, never the Viewer token. Independently exercise:

1. Anonymous refusal at a protected Grafana API (not a public health endpoint).
2. Operator-origin direct Viewer read permission and a write denial against a uniquely named disposable resource with before/after read-back.
3. Run-origin sentinel-mediated allowed reads and scope/write/target denial.
4. Run-origin denial of every actual gateway/backend address at the relevant Grafana/Loki/Prometheus/Tempo ports and private control/data socket paths.
5. Native-client CA, hostname, expiry and sentinel-negative behavior, with no insecure fallback. Retain precise error observations; an MCP tool error is not necessarily process termination.

A real Grafana container does not automatically emit the C1 synthetic backend's `/run/receipts/events.jsonl`. Design the real-backend evidence path explicitly. Forwarder/gateway response hashes, complete native frames, seed read-backs and available Grafana access/audit logs have different evidentiary roles. Do not claim the existing three-role synthetic receipt join without a real backend observation mechanism.

## Lifecycle, limits and teardown

Before C2 runtime, reconcile C1 results for complete native response capture, exact-target isolation, TLS/authority negatives, child containment and interruption/restart behavior. The current first C1 run excludes some native certificate and lifecycle drills; draft their separate bounded card before executing them. A process restart and container recreation are different persistence tests.

Retain the proposed ten-minute setup, ten-minute probe and two-minute cleanup ceilings; freeze backend-specific readiness and per-request limits before approval. Each session bundle is at most 100 MiB, combined private evidence 2 GiB, retention 30 days, directories 700/files 600. Record every changed timeout before execution and stop on unsupported input, usable bypass, unauthorized write, credential leak, incomplete capture or missed deadline.

Teardown has two distinct revocations: revoke the Forwarder's admission, then delete/revoke the exact Grafana token/account through operator authority and verify it. `operator revoke` alone does not revoke Grafana credentials. Export bounded receipts and process/mount state, then remove only ledgered container IDs, experiment-owned volumes/networks and derived image references. Verify their absence and preserve original bases. Delete transient authority files; do not claim secure erasure on APFS/SSD. Container loopback listeners belong to the Docker VM namespace, so a host-port check alone cannot establish their absence.

## Worker adjudication and remaining preparation

Accepted the worker's topology sketch, seed categories, grant probes and stop/cleanup outline. Corrected its fixed January seed time, conflation of Viewer-token and sentinel probes, assumption that Forwarder revocation deletes Grafana credentials, invented Grafana receipt path, host-listener cleanup test and unverified UID/read-only assumptions. Live C1 provisioning/identity checks already passed in attempt 2; they are repeated for new C1/C2 resources, not erased from history.

Remaining work: candidate startup/writable-path inspection; finalized non-root backend packaging/resource bounds; exact source/config/seed hashes; C2 policy/driver/seeder implementation and tests; backend evidence design; full C1 result reconciliation; and a final create/remove inventory. This card is preparation, not a request to execute an incomplete C2 design. Ticket 19 and Eyes remain unresolved.

Private worker output, registry inspection and tagged upstream source captures: `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260920-c1-batch/`.
