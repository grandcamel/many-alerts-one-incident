# Ticket 19 — C1 first container measurement card, 2026-09-19

## Prepared network guard amendment — not yet executed

The user's next "proceed" authorized the bounded interface inspection and resulting source preparation. [The outcome](c1-network-guard-outcome.md) establishes nine inactive, unaddressed, unrouted tunnel links in a fresh pinned network-none base container. The diagnostic container was removed. This amendment prepares one fresh full C1 attempt; its build/start/admission has not been authorized by the diagnostic step or executed.

Updated prototype source: `7741d2060aceb9bb475a42c2f9f3adc5f3c1db7e`; `run_probe.py` SHA-256 `03801ad63e9de783697d0c7a11344e977c7cd4496d0c0d6b546ceee527317c3c`. Full suite: **409 passed, 36 skipped**; 44 new kernel-replay/rejection tests. Verification: `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/network-guard-20260919/verification.json`, SHA-256 `1217126183210ae59ef3a4cccf3c1cb8b25998891ef67135ee8826f0e097e230`. The PEM helper at attempt 2 remains in this source. No frozen base/binary input, Dockerfile, Compose resource, capability, authority, sample count, budget or cleanup rule changes.

For the next full attempt, use a fresh private evidence directory and rebuild the Run derivative from this exact probe; record its new content ID instead of requiring attempt 2's derived Run ID. Preserve old evidence and consumed authorizations. Freeze the new operator harness/hash and input/source manifest before launch; do not execute either archived attempt harness unchanged.

Replace the historical `interfaces == ['lo']` and empty-proc-route assertion with both the probe's boolean and an operator-side call to the committed `network_state_allowed` on its full inventory. Require exact agreement between the legacy interface index/name list and the new link list. A false predicate, missing/incomplete inventory or disagreement stops before admission. Repeat the same inventory validation on the final Run snapshot; the old harness merely saved that final snapshot and must not be reused without this change.

```python
from prototype.local_acceptance.run_probe import network_state_allowed

def require_network_state(snap):
    inventory = snap["network_inventory"]
    assert snap["network_state_allowed"] is True
    assert network_state_allowed(inventory)
    assert sorted(tuple(row) for row in snap["interfaces"]) == sorted(
        (row["index"], row["name"]) for row in inventory["links"]
    )
```

The predicate allows only the measured loopback state and optional exact named inactive tunnel profiles, requires solely the measured loopback addresses and four local-table routes, and rejects unknown/active links and additional paths. It does not replace mandatory network-none/no-capability/identity checks or the exact gateway/backend IP and private-socket connection probes. Run those probes and require all denials before sentinel admission. No automatic retry or widening follows a different observed profile. Native certificate variants and interruption/restart drills remain outside this first measurement, as below. A user instruction to proceed with this prepared full attempt supplies the remaining execution authorization; no additional paid/model authority is requested or implied.

## Attempt 2 amendment — authorized before launch

**Execution result:** [attempt 2](c1-attempt-2-outcome.md) is now complete and its authorization consumed. Provisioning, baseline parity and exercised identity/filesystem checks passed; the declared interface-only-`lo` guard failed before admission. Cleanup is independently verified. No third container run is authorized by this amendment.

The user explicitly requested "try again" and reported closing the MacBook lid. This authorizes one fresh attempt under the same resource inventory, measurement limits and stop/cleanup rules. Attempt 1's recorded provisioning rejection is retained; lid closure is not assumed to explain it. The operator now canonicalizes the generated public certificate with `openssl x509 -outform PEM` before the unchanged strict provisioner receives it. The actual generator/provisioner/TLS-loader path is tested at prototype `79b8ee6fc16be777033f4fc7af6e11a5bf6aa3d1`; full suite **365 passed, 36 skipped**. Service/Run source, image bases and Linux binary pins are unchanged.

Attempt 2's initial preflight record is retained at `/Users/jasonkrueger/maoi-stage-b-evidence/c1/attempt-2-20260919`. It stopped before any resource creation because the driver check matched CLI spacing literally. Read-back confirmed the exact driver/version; the parser was corrected to compare trimmed field values (including a rejection check for a different driver). The same authorized retry continues in the fresh directory `/Users/jasonkrueger/maoi-stage-b-evidence/c1/attempt-2-runtime-20260919`, preserving the first record. Its source verification record is `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/attempt-2-verification.json` (SHA-256 `c135b76b22795821f859211742aaf79e5dd2cccd1783420585a788354c3fc626`). Resource names may be reused only after verified absence of attempt-1 resources, with new exact IDs captured. No automatic third container attempt or relaxation follows a failure. The record below describes attempt 1 and the shared execution procedure.

Current status: **authorized and consumed by C1 attempt 1**. The user's subsequent "proceed" authorized this bounded build/start. [Attempt 1](c1-attempt-1-outcome.md) built the images and started the services, then stopped at Forwarder provisioning before admission; exact-resource cleanup is verified. No retry is authorized by that consumed instruction. The commands below are the historical execution card, not permission to rerun it.

Original preparation status: the earlier "proceed" authorized source adapters/probes and pin preparation after C0. The [accepted plan](local-container-acceptance-plan.md) required separate C1 approval of the exact inputs, topology, limits and resource inventory. No model, paid API, real Grafana, tenant or cloud operation is included. No push or publication is included.

This first C1 measurement covers Linux native compatibility, complete positive response capture, byte-cap/error behavior, scoped Unix transport, direct Run boundary probes and cleanup. It does not automatically complete every C1 acceptance row. Native-client negative certificate variants, in-container mid-query interruption/revocation, and restart-persistence drills remain explicitly unmeasured unless separately added to this card before execution. Host tests for related behavior are preparation evidence only. Ticket 19 stays claimed and ticket 12 blocked.

## Frozen inputs

Source: `/Users/jasonkrueger/projects/maoi-mcp-grafana-prototype/prototype/local_acceptance/`; see [preparation outcome](c1-preparation-outcome.md) for its local commit and source hashes. `containers/inputs.json` is the machine-readable input record.

| Input | Exact value / interpretation |
| --- | --- |
| Engine | Docker 29.8.0; Desktop 4.91.0 (239619); Compose 5.5.1; `desktop-linux`; Unix endpoint `/Users/jasonkrueger/.docker/run/docker.sock` |
| Builder | `desktop-linux`, driver `docker`, BuildKit v0.33.0; no bootstrap or remote builder |
| Target | `linux/amd64` |
| Run base | Local image ID `sha256:5abb2fb0c6bebe246ee31e56e4634edc92fe8b3be75bc5dcd12cf00f0592abe9`; existing `grafana-jsm-sandbox` image. No registry RepoDigest exists. Image history records Claude Code 2.1.272 and jira-as 2.0.0; source-file parity is still a runtime read-back. |
| Fixture base | Local image ID `sha256:51cce855bb6e44a8ff6ed0f46ded8850f246bfc7549801459f83fc34b80c210f`; inspected RepoDigest `python@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285` |
| Native client | mcp-grafana v1.5.1, upstream source `2a33c72f211560e4ffb39d6b99cad3c3dc2a3f6e` |
| Linux archive | `mcp-grafana_Linux_x86_64.tar.gz`, SHA-256 `3ef1c7a66aab3ba149de53681d72ea58244baa41331eb3aed9cdd2f68acc0db7` |
| Linux executable | SHA-256 `208b71a4f1cf707834734671c6d784a8db4ffcf414a182ddc38d21384de8e125`; 57,880,738 bytes; staged mode 600 at `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/mcp-grafana-linux`, not executed |
| Publisher checksums | SHA-256 `058aab9249a0beeecf861c82a0ce927930fcce17d6b527ce28b052c2a0e19ff5`; both release metadata and downloaded checksum file match the archive |

The archive and checksum file came from the [v1.5.1 release](https://github.com/grafana/mcp-grafana/releases/tag/v1.5.1). Recheck local image IDs, source and binary hashes before any mutation. Do not resolve mutable tags anew, download replacement bases, change architecture, substitute the Darwin client or bootstrap another builder. Derived image IDs are build outputs: record and verify them before starting the experiment, without inventing a registry digest.

## Resource and authority inventory

Use only project `maoi-c1-20260919`. Expected containers are the four Compose services `run`, `forwarder`, `gateway`, `backend`; record their full IDs and labels immediately after creation. Expected network: `maoi-c1-20260919_backend`, internal. Expected volume: `maoi-c1-20260919_data_socket`. Refuse collisions with existing experiment names; do not adopt or delete an older resource.

Allowed temporary image references are `maoi-c1-20260919-run-base:pin`, `maoi-c1-20260919-service-base:pin`, `maoi-c1-20260919-run:prepared` and `maoi-c1-20260919-services:prepared`. Record their IDs; the two base references point to existing images and must not remove those images or their original tags. Build cache may remain; no pruning is authorized.

The Run is UID/GID 1000, read-only, network-none, no capabilities, no-new-privileges, 2 CPUs, 2 GiB memory, 256 PIDs and the three declared tmpfs paths. It holds the namespace while fresh native children run through `docker exec`. The Forwarder is UID/GID 2000, shares only the Run network namespace and listens on loopback 8443. It holds its authenticated control socket and server/upstream authority in private tmpfs. The Run sees only public CA trust and its scoped sentinel.

Gateway and backend use UID/GID 2000 on the separate internal network. Freeze the backend's actual numeric IPv4 address from its exact container/network inspection into the gateway's private config; no caller URL or DNS controls the upstream. The data volume is mounted only in gateway/Forwarder. All three services use read-only filesystems, no capabilities, no-new-privileges, 1 CPU, 256 MiB and 64 PIDs each. The service image creates the volume directory as 2000:2000 mode 700; Unix sockets are mode 600. Verify actual volume/mount ownership before admission. No host PID namespace, Docker socket, host home, demo `.env`, public ports or additional network is allowed.

Public CA trust is the only host bind into the Run. Generate synthetic sentinel/control/upstream values and one short-lived local TLS fixture only after C1 execution is approved. Keep the CA signing key in an operator-only host directory. Use `operator.py provision` over stdin to put server key/certificate and config into Forwarder tmpfs; put only the upstream token into backend tmpfs and the fixed backend address into gateway tmpfs. Never put credentials in build contexts, arguments, images, receipts or displayed configuration. Control runs through operator-authorized Docker exec inside the Forwarder, not a host/VM Unix-socket bind assumption.

The public-CA directory must be mode 755 and its sole `ca.pem` file mode 444 so Run UID 1000 can read the bind mount. Its enclosing operator directory stays mode 700. This exception contains public trust only; capture directories, signing keys and authority files remain private. Verify this exact content/mode split before admission.

## Build and startup procedure

1. Create a new private directory under `/Users/jasonkrueger/maoi-stage-b-evidence/c1/`, mode 700, outside Git, with distinct `run-context`, `service-context`, `public-ca`, `operator-secrets` and capture directories. Keep all private files mode 600. Do not reuse a previous bundle. Record hashes and a create/remove ledger before mutation. Combined retained evidence stays below 2 GiB; each MCP bundle is at most 100 MiB, each service receipt file at most 8 MiB, retention 30 days.
2. Construct the Run build context from only `containers/Dockerfile.proposed` as `Dockerfile`, the verified binary as `mcp-grafana-linux`, and `run_probe.py`. Construct the service context from only `containers/Dockerfile.services` as `Dockerfile` plus `__init__.py`, `wire.py`, `adapters.py`, `c1_cases.py`, `service.py`, `operator.py`. Hash every staged file and compare with committed source. No repository-wide context or credential directory.
3. Create the two experiment-local base tags from the exact inspected IDs and verify them. Build using the commands below, with explicit local Docker context, `--pull=false`, `--network=none` and the inspected `docker` builder. These Dockerfiles perform no network/package installation. If local resolution fails, stop; do not fall back to a registry pull or a different builder.

```sh
docker --context desktop-linux image tag sha256:5abb2fb0c6bebe246ee31e56e4634edc92fe8b3be75bc5dcd12cf00f0592abe9 maoi-c1-20260919-run-base:pin
docker --context desktop-linux image tag sha256:51cce855bb6e44a8ff6ed0f46ded8850f246bfc7549801459f83fc34b80c210f maoi-c1-20260919-service-base:pin
docker --context desktop-linux build --platform linux/amd64 --pull=false --network=none --build-arg RUN_BASE=maoi-c1-20260919-run-base:pin --build-arg MCP_LINUX_SHA256=208b71a4f1cf707834734671c6d784a8db4ffcf414a182ddc38d21384de8e125 --tag maoi-c1-20260919-run:prepared "$C1_RUN_CONTEXT"
docker --context desktop-linux build --platform linux/amd64 --pull=false --network=none --build-arg SERVICE_BASE=maoi-c1-20260919-service-base:pin --tag maoi-c1-20260919-services:prepared "$C1_SERVICE_CONTEXT"
```

`C1_RUN_CONTEXT` and `C1_SERVICE_CONTEXT` must be the two exact ledgered directories from step 1. Record full derived image IDs, then use those IDs as `RUN_IMAGE` and `SERVICE_IMAGE`, not the tags. The BuildKit rootfs changes are only the declared binary/source/directory operations. Keep build/setup timing separate from measurements.

4. Supply an explicit private Compose environment file containing only `C1_PROJECT`, `RUN_IMAGE`, `SERVICE_IMAGE`, `PUBLIC_CA_DIR`, `RUN_SENTINEL`. Invoke the committed standalone Compose file with `--project-directory` set to the private experiment directory and `--env-file` set to that file; use a minimal process environment. Render privately, sanitize before persistence, then inspect declared mounts/limits against this card. The earlier preparation render used base IDs and a noncredential sentinel solely to check syntax; it is not the executable configuration.
5. Start exactly the four services with `docker --context desktop-linux compose --project-name maoi-c1-20260919 --project-directory "$C1_DIRECTORY" --env-file "$C1_ENV_FILE" -f "$C1_COMPOSE_FILE" up -d --no-build --pull never`. The service processes wait at most 60 seconds for provisioning; immediately record exact IDs and backend address, then provision each service via `docker --context desktop-linux exec -i --user 2000:2000 "$SERVICE_ID" python3 -m local_acceptance.operator provision`, supplying the role-specific JSON on stdin. Config is published last; no overwrite/reuse is accepted.
6. Read back public-CA contents (no key), exact image/container/network/volume IDs, non-root modes, capabilities, PID/network membership, mount sources, service `ready` receipts and authenticated Forwarder `status` before admission. Verify actual binary hash and installed versions inside Run without invoking Claude. Compare copied baseline package/Skill hashes with the source snapshot, or report mismatch and stop. Run `snapshot` and `network` probes before admission. A reachable backend/control path, undeclared write, credential read, routing interface or identity drift stops the experiment.

Provisioning JSON is generated from the operator's synthetic credentials: Forwarder `{role, config:{sentinel,control_token,upstream_token}, server_key, server_cert}`; backend `{role,config:{upstream_token}}`; gateway `{role,config:{backend_host,backend_port:8081}}`. `backend_host` is the inspected private numeric IPv4 address. Never inline concrete credential values into this card or logs.

## Measurement procedure

The following values are runtime outputs bound to the ledger, not arbitrary target selectors: full `C1_RUN_ID`, `C1_FORWARDER_ID`, `C1_RUN_IMAGE_ID`, `C1_SERVICE_IMAGE_ID`, and exact backend IP. The driver independently checks the container IDs, images, project and service labels.

Admit once using `docker --context desktop-linux exec --user 2000:2000 "$C1_FORWARDER_ID" python3 -m local_acceptance.operator admit`. Record one initial session and four fresh-client sessions against the same warmed services. Each session uses a distinct private bundle and the following command from the prototype checkout:

```sh
python3 -m prototype.local_acceptance.native_driver --execute-approved-c1 --suite positive --output "$C1_NEW_BUNDLE" --run-id "$C1_RUN_ID" --forwarder-id "$C1_FORWARDER_ID" --run-image "$C1_RUN_IMAGE_ID" --service-image "$C1_SERVICE_IMAGE_ID"
```

Run one additional `--suite negative` session for byte boundaries at 10 MiB minus one, exactly 10 MiB and plus one, upstream failure/redirect/timeout, and prior-Run scope denial. Stop on unexpected results; no automatic retry or looser timeout. Native RPC timeout remains 5 seconds, MCP Grafana timeout 1 second; gateway/Forwarder upstream bounds are 0.65/0.9 seconds. Native children have a 60-second in-container lifetime plus bounded cleanup. Report each observed initialization/query duration, not a percentile or pure-binary startup claim.

Use `docker --context desktop-linux exec --user 1000:1000 "$C1_RUN_ID" python3 -I /opt/c1-probe.py snapshot` for UID/capabilities/no-new-privileges, mount and route inventory, read/write probes and tmpfs entries. Use the same prefix with `network --backend-ip "$C1_BACKEND_IP"` to check the exact backend address at ports 8081/3000/3100/9090/3200 and private Unix socket paths. Add each actual experiment gateway/backend interface IP (maximum eight targets). Require only loopback interfaces/routes in the Run; missing DNS alone is insufficient.

For direct TLS/authority/write-denial checks, call operator `begin --case direct-probes`, then Run probe `direct`, then operator `end`. Expected direct results: valid read 200; absent/wrong sentinel 401; admin write 403; untrusted CA and wrong hostname fail verification. Confirm only the valid read dispatched upstream. These are **direct probes**, not native-client negative TLS qualification.

After measurements, invoke operator `revoke`. A subsequent Run `direct` probe must report 401 for the valid/missing/wrong/write requests, with no new backend requests; TLS-negative cases still fail verification. No second admission is permitted. Record native child absence from the Run's process inventory independently of host Docker-client reaping. Inspect filesystem layers **and** mounts/tmpfs before teardown. An intact MCP capture alone cannot qualify process containment or authority isolation.

Export each exact service's `/run/receipts/events.jsonl` into the private evidence directory before stopping it. Scan all exports for every generated authority value; redact and downgrade any affected claim. Parse `control/case_end` events in the MCP bundles and call `native_driver.join_receipts` with the three exported receipt streams for successful responses. Require unique IDs, matching request hashes and response hashes/statuses; explicitly explain expected timeout/redirect transformations and verify the corresponding backend effects. Report missing/ambiguous joins as inconclusive. Verify every MCP frame/event/manifest hash, source/image provenance and file mode after export.

## Bounds, teardown and result

Preparation/build/readiness budget: ten minutes. Probe/session budget: ten minutes. Cleanup: at most two minutes. Each service self-expires after ten minutes following provisioning; ensure planned samples fit that smaller service lifetime. Stop on the first unsupported boundary, unusable capture, source/config drift, unexpected failure or missed bound. No automatic retry, larger allowance, shared Compose invocation or fallback client.

Teardown only exact ledgered IDs: revoke first, export receipts and mount/layer/process read-backs, stop and remove the four recorded container IDs, then remove the recorded experiment network and volume after checking their labels/memberships. Verify no recorded container/listener/child remains. Remove only experiment-created derived image tags/IDs and temporary base tags after verifying their current identity; preserve the original base images and all unrelated resources. Do not use broad `down`, `prune`, tag globs or removal by an unverified reused name. Delete transient synthetic keys/authority files after retained captures are scanned; retain bounded sanitized evidence and expiry metadata.

Emit a per-criterion matrix distinguishing native Linux MCP, direct Run probes, synthetic backend receipts, source/static checks and NOT RUN rows. Success here cannot recover attempt 4's missing model-client responses, prove model spill behavior, real Grafana grants, intended Kubernetes confinement or Eyes selection. C2 remains unimplemented and separately gated. Provider actuals remain unknown; retain all $12 of reservations; no additional paid attempt is authorized.
