# C2 attempt 3 — backend configuration compatibility card

**PREPARATION ONLY — execution is not authorized.** Attempts 1 and 2 are consumed. This card proposes exactly one run with the reviewed backend configuration correction. It does not activate a harness. Final Sol review has passed source preparation; the user must explicitly accept that review in place of the unavailable Fable opinion for this correction and authorize this one attempt before activation. Earlier exceptions do not carry forward.

## Exact first-stage scope

Run identifier `27792cef867e4a1ea76495c4cb9df174`. Fresh, non-reusable private root `/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-3-20260921`. Docker context `desktop-linux`, engine ID `deea9d93-95ed-4dbc-bdd0-4bedf645c9ca`. Exact Linux/amd64 input `docker.io/grafana/otel-lgtm@sha256:35da4355c58162b6f27ccbd43c6214d565bc29fc9b18baaf43b59202c354577b`; previously pulled during attempt-1 preparation in 149.484 seconds, recorded local image ID `sha256:44a7f733cea9b946b061774e5cbc690cb303e4a2de1719279ae212f01c4ff28f`. Retain this pinned base after cleanup; no image/volume prune, image build or derivative tag.

Create only the ownership-plan internal bridge network `c2-27792cef867e4a1ea76495c4cb9df174-network`, CIDR `172.30.246.0/24`, gateway `172.30.246.1`, and these exact containers:

| Service | Name | Frozen IPv4 | Health request |
| --- | --- | --- | --- |
| grafana | c2-27792cef867e4a1ea76495c4cb9df174-grafana | 172.30.246.2 | GET http://172.30.246.2:3000/api/health |
| loki | c2-27792cef867e4a1ea76495c4cb9df174-loki | 172.30.246.3 | GET http://172.30.246.3:3100/ready |
| prometheus | c2-27792cef867e4a1ea76495c4cb9df174-prometheus | 172.30.246.4 | GET http://172.30.246.4:9090/-/ready |
| tempo | c2-27792cef867e4a1ea76495c4cb9df174-tempo | 172.30.246.5 | GET http://172.30.246.5:3200/ready |

No operator probe container, seed/ingestion, service-account/Viewer token operation, gateway/Forwarder/Run, native MCP session or qualification model call occurs in this stage. The automated health predicate is curl exit 0 and an exact HTTP 200 status line. Retained bodies and framing are observations for independent review, not asserted service-specific readiness or strict-adapter framing acceptance. Health and local version/process/listener/mount observations are compatibility evidence only, not the seed oracle or C2 acceptance. The public Prometheus compatibility gate stays closed.

## Containment and authority

Use the compiler's direct entrypoint/command, UID:GID2000:2000, read-only root, capability dropALL, no-new-privileges, no privileged mode/devices/host PID/IPC/network, no published ports, exact fixed IP/network ID, one CPU, memory1GiB with memory+swap1GiB, 128PIDs, 32MiB /tmp and 256MiB service-data tmpfs with prescribed ownership/options, and json-file2m/two-file log rotation. Disable the inherited all-in-one image healthcheck with --no-healthcheck; no wrapper or extra component is started. Match effective inspect fields and exact read-only config mounts against the compiler and rendered hashes before start. Docker's built-in exposed-port metadata is not a published port; inspect actual PortBindings/PublishAllPorts.

The image ENV is frozen by hash in image-inspection.json; it contains PATH and public component versions only, and no GF_* override. Reject drift or unexpected overrides without printing values. Do not capture host env or unrelated-container configuration. Preserve existing container/network/image IDs and volume names. Require no image-declared volumes before any create; no volume creation/removal is authorized. The pulled image also has 32 public OCI/Red Hat metadata labels, frozen in image-inspection.json. Container identity checks require that exact inherited map merged with the C2 ownership labels; reject any preexisting io.maoi.c2.* label collision. Network labels remain exactly the ownership plan. Label matching supplements the durable received ID and never permits adoption.

Generate one disposable Grafana bootstrap password in process. Use a single file mode0444 below an owned0700 host authority directory, mounted read-only at the compiler's password path in Grafana alone. This file-mode exception permits UID2000 to read the dedicated bind while host ancestors remain private. No password value in argv/env/evidence; no user credential read/refresh. Verify readability without printing it. Unlink after Grafana is confirmed absent; report any residue explicitly. No APFS/SSD secure-erasure claim.

## Ordering, evidence and stop conditions

Observe each exact planned name absent before creation; distinguish absence from engine/transport failure. Durably persist create intent before the call and one canonical full64hex engine ID after exit0 before any subsequent create/start. Network first, then canonical four service order. Start only receipt-backed, freshly inspected matching IDs. No retry after ambiguous create/start, no name/label adoption, no automatic cleanup of an acknowledged-but-unpersisted ID. Unknown effects are manual-audit blockers even if discoverable by name.

Setup<=600seconds; diagnostics<=600seconds; independent cleanup reserve<=120seconds. Each child command has a clipped deadline and streamed stdout+stderr cap; terminate/reap client process group on timeout/overflow. Health exec uses a direct numeric own-container URL, no proxy/redirect, HTTP-only curl with connect1second/max2seconds and body<=64KiB; at most30 readiness rounds. These are bounded operator-origin diagnostics, not Run isolation or authority proofs. Capture per-component version and bounded /proc/1/status, network tables, mount state, Docker top/diff. Do not claim exact effective listener/network behavior beyond observed predicates.

Supporting evidence ceiling2GiB, log export<=4MiB per backend, other command capture<=2MiB, directories0700/files0600 except compiled nonsensitive config trees and the private bootstrap bind described above. Retention30days. Redact raw/escaped generated-secret matches before command evidence is written; retain exact resulting bytes as base64 and hashes. Run the independent post-run verifier and hash/read-back the complete retained artifact set before reporting completion. Scan for the raw/escaped generated secret. Config incompatibility, failed read-back, exited component, deadline, capture failure, unexpected authority or resource mismatch stops progression. Do not relax privileges, rewrite rendered configuration, repeat a seed, expand limits or silently retry a failed acceptance path.

Finally collect logs under the diagnostic budget with a20second total/five-second-per-backend cap, then begin the independent120second cleanup reserve and remove only exact durable-receipt container IDs after current ID/name/labels match. Reinspect the network by received ID and require no attachments before removal. Verify each known ID absent with explicit successful inventory semantics; report errors and unresolved IDs separately. Preserve base images and unrelated resources. Secret invalidation/absence and exported evidence integrity are separate from engine cleanup. A failed compatibility run is not approval for an unrecorded second run.

## Inspection correction

Retain the selected inspection and all ten named identity predicates before evaluating the created/running guard. Require exact image configuration ID and exact operator-supplied Config.Image. Require Config.Healthcheck.Test exactly ["NONE"]; retain omitted, zero or inherited timing fields as observations without equality-gating them. Save environment names/hash only, never environment values. Evidence-write failure stops progression. Any mismatch identifies its field explicitly. These rules do not establish the missing fields or cause of attempt 1.

Independently inspect the exact pinned image reference, bounded to Id and RepoDigests, and require both its configuration ID and repository digest. The image-list inventory still checks preservation of listed images; it is not the base-image identity oracle. Inspection/transport errors remain unverified.

## Backend correction and candidate binding

Prototype commit `817f466acc47f8df51c389934e000ed6dc6271d2` contains the reviewed compiler, contract and regression tests. Tempo explicitly places its live-store shutdown marker, live-store WAL and scheduler work cache under the existing `/data/tempo` tmpfs. Loki advertises `127.0.0.1`, matching its existing loopback gRPC listener. All mounts, quotas, privileges, listeners and cross-container HTTP endpoints remain identical to attempt 2. The other three rendered files remain byte-identical. No relaxation or alternate configuration is authorized if startup fails.

Compiler SHA256 `b57c85dc05f0f6878b2d26f094e0bd14c7c7778f13fc97653db283579a7784f2`. Corrected Loki YAML SHA256 `74b82fee7889e7d27413d4f9b2141e0fff86d887fdec2eee7a51a97563ddb004`; Tempo YAML SHA256 `494c6e7c4656e1713a4a2a9947d0ab271b7c94ec6eb6d05245161a75ef9afadf`. These hashes apply to this card's frozen endpoints.

Full prototype suite: 595 passed, 36 skipped; focused configuration suite24 passed. Final Sol source review SHA256 `728e5887d468bc2aef3cf4b889a87eb320c8a51372a69f6ab45116a6623687a7`. Fable was requested once for this new packet, refused under the provider cyber safeguard, and automatically fell back to Opus. Opus supplied an opinion, but no usable Fable review exists. Neither the refused packet nor earlier packets will be retried, reworded or rerouted.

After explicit approval, prepare a separate attempt3 activation directory from the inspected attempt2 executor/verifier source. Change only the fresh run identity/root, approval validation/gate and source/input bindings necessary for this correction. Preserve all previous runtime and preparation roots. Regenerate configuration and ownership plans from the committed compiler; verify exact rendered hashes above and fresh root/name absence. Freeze the final executor, verifier, source manifest, approval record, card, tests and reviews in launch-readiness evidence before execution. Validate the complete private executor/verifier suite and obtain independent activation review before launch; any further functional change or containment expansion requires separate review. Current runtime engine/image state has not been refreshed by this source-only preparation.

This card's preparation metadata has execution_authorized=false. No activated attempt3 harness exists. The approved run, if later launched, consumes its identity/root even on failure; no automatic second run follows. Source support does not establish pinned-binary startup, shared tmpfs capacity, complete readiness, internal query behavior or qualification. See [correction outcome](c2-backend-config-correction.md).
