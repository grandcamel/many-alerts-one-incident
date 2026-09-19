# Ticket 19 — C1 attempt 1 outcome, 2026-09-19

Verdict: **stopped at Forwarder provisioning; native/container acceptance remains inconclusive**. The user's "proceed" after the [C1 execution card](c1-execution-card.md) authorized its bounded first run. Prototype source stayed frozen at `3a16de9d4195edd480a914d5211a08f2c3f9cab3`; no implementation changes or automatic retry followed the failure. Ticket 19 remains claimed and ticket 12 blocked.

## What ran

Frozen source, Linux archive/binary and local base-image hashes matched. The inspected Docker context/platform/builder matched the card and no experiment resource names collided. Minimal source contexts preserved committed readable source modes inside private mode-700 directories; the Linux binary and private audit/authority files remained mode 600. The public-CA mount was the declared public-trust exception.

Both local derivative builds succeeded using the pinned bases, `--pull=false` and `--network=none`, with no package installation or model invocation:

| Built image | Local image ID |
| --- | --- |
| Run | `sha256:263522d80aefa419778c13eb08c479d27da21a9398e817c935f0b936ec28899f` |
| Fixture services | `sha256:f4c61c6e7d435e591d22e50c2a5151e464d45014d9f4d2a668d2fd0676e00c50` |

The standalone Compose invocation created and started the four experiment containers, internal network and data volume. Backend and gateway provisioning succeeded and each emitted a `ready` receipt. Forwarder provisioning exited 1 with the fixed safe error `C1 operator action failed; no input values logged`. Its receipt file remained empty. The harness stopped immediately, before the runtime-preflight phase, sentinel admission or any native MCP session. No MCP capture bundles exist.

The entire attempt, including cleanup, took **28.353 seconds**. Cleanup took **12.408 seconds**, within the card's two-minute limit.

## Probable cause and diagnostic limits

The frozen certificate helper calls `openssl ca` without `-notext`. Installed OpenSSL help identifies `-notext` as suppressing the generated certificate text. The operator provisioner requires `server_cert` to begin with `-----BEGIN `; a text-prefixed certificate does not satisfy that format check. This is a likely integration mismatch between the certificate helper and provisioning boundary.

A separate offline shape reproduction used the retained public CA and a dummy, non-cryptographic key string. It confirmed that a text-prefixed certificate raises `ValueError("PEM input")` after creating the key file but before publishing config, while PEM-only input passes the shape check. It did not provision a service, create new authority, execute a native client or retry C1. Passing that shape check is not cryptographic validation.

The runtime stderr deliberately omits the underlying exception, and transient server-certificate/key files were removed during cleanup. Therefore the certificate-prefix explanation is **source-supported and reproduced as a format failure, but not directly confirmed from the deleted runtime payload**. Do not upgrade it to a fully observed runtime root cause. The next bounded correction should produce canonical PEM before provisioning and test the actual certificate-helper-to-provisioner path, preserving safe diagnostics and config-last publication. A corrected source revision and a new explicit attempt are required before another container run.

## Evidence and cleanup

Private evidence root: `/Users/jasonkrueger/maoi-stage-b-evidence/c1/attempt-1-20260919`. It contains the execution script, source staging hashes, build logs, sanitized Compose/container read-backs, provisioning results, exported service receipts, failure ledger, offline format diagnosis and an artifact index. Source and binary contexts contain no credentials. Signing keys, service authority and the private Compose environment file were removed. Retained JSON/frame evidence was scanned against all five known secret values (three authority tokens and two private-key texts): **zero matches**.

| Artifact | SHA-256 |
| --- | --- |
| `ledger.json` | `b230ebaa6c16767227006ecc5ddb969c63cc6fb5c44673e206765987028092a9` |
| `forwarder-provision.json` | `8282ebed05cb963e87ca450cfad1d4533c4e28cb833cb4a237c7558fa26ef261` |
| `staged-inputs.json` | `23e0b4f737ec2f0443aae43fec4acecb6733d80d9ce5bc3b84d55837d9a51c3c` |
| `secret-scan.json` | `1288edea570036f82137b0a83d41d2cc38e5cfdd5459ed4c3d0041b760937243` |
| `independent-cleanup.json` | `9d69f8bfdcb2b020795283e2ba4d100c3900d768dec538d202c1da6999fccc0a` |
| `certificate-format-diagnosis.json` | `b339de689e656d32efec52d1572842bea59cee844d64ffd4caf94e8c17df2a1e` |
| `artifact-index.json` | `ce05381ebbbb5c78da999417abbd0b738ac47d87c43c6a32bb4682ae7e86218e` |

The index verifies 47 files totaling 58,026,867 indexed bytes, excluding the index itself. Creation time is 2026-09-19T23:08:34.469813Z; the recorded retention expiry is 2026-10-19T23:08:34.469813Z. No automatic evidence deletion is scheduled.

All four exact container IDs, the recorded network and volume, both derivative image IDs and all four experiment image references were removed and independently verified absent. The original Run and Python base images were independently verified present at their original IDs. No broad cleanup or image/cache prune ran. Build cache may remain as allowed by the card. No sentinel was admitted; no control revocation or post-revocation query was exercised. Authority containment here is destruction of the never-admitted experiment and its transient secret storage, not a successful 401 revocation probe.

## Criterion-level disposition

| Criterion | Result and origin |
| --- | --- |
| Input pins and derivative builds | Supported for inspected local inputs and completed Linux image builds |
| Four-service creation | Supported by Compose and exact-container read-backs; declarative settings alone do not prove enforcement |
| Backend/gateway startup | Supported by provisioning results and each service's `ready` receipt |
| Forwarder provisioning/readiness | Refuted by provisioning exit 1; probable certificate-prefix mismatch |
| Native handshake, seven-case positive samples, byte-cap/error/scope sample | **NOT RUN**; stopped before admission |
| Runtime baseline parity, UID filesystem/route/bypass probes, direct TLS/authority probes | **NOT RUN**; cleanup inspection of settings is not a substitute |
| MCP response audit/correlation and native-child containment | **NOT RUN**; no native process or MCP bundle |
| Exact-resource teardown and transient secret removal | Supported by ledger plus independent post-cleanup read-back |
| Native certificate variants, interruption/restart drills, C2/Grafana, models and intended venue | **NOT RUN**, unchanged exclusions |

No product code changed in this execution turn, so the full source suite was not rerun. The **363 passed / 36 skipped** result remains preparation evidence for the frozen source, not a successful C1 runtime result. The execution harness compiled before launch; documentation links/whitespace and private evidence hashes were checked afterward. No model, paid API, real Grafana, tenant or cloud operation ran. All $12 reservations remain retained, provider actuals remain unknown, and nothing was pushed or published.
