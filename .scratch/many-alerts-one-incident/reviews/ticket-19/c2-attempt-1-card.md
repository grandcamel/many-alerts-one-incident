# C2 attempt 1 — approved backend compatibility card

User authorization: **“C2 approved. Continue”**. This supersedes the earlier source-only/no-C2-runtime boundary. The user need not repeat approval for the bounded work below. The preparation plan and source review remain prerequisites, and no runtime acceptance is assumed.

## Exact first-stage scope

Run identifier `cd54f95f5c48acc6bbba2141c8d90e21`. Fresh, non-reusable private root `/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-1-20260921`. Docker context `desktop-linux`, engine ID `deea9d93-95ed-4dbc-bdd0-4bedf645c9ca`. Exact Linux/amd64 input `docker.io/grafana/otel-lgtm@sha256:35da4355c58162b6f27ccbd43c6214d565bc29fc9b18baaf43b59202c354577b`; pulled once in 149.484 seconds, local image ID `sha256:44a7f733cea9b946b061774e5cbc690cb303e4a2de1719279ae212f01c4ff28f`. Retain this pinned base after cleanup; no image/volume prune, image build or derivative tag.

Create only the ownership-plan internal bridge network `c2-cd54f95f5c48acc6bbba2141c8d90e21-network`, CIDR `172.30.246.0/24`, gateway `172.30.246.1`, and these exact containers:

| Service | Name | Frozen IPv4 | Health request |
| --- | --- | --- | --- |
| grafana | c2-cd54f95f5c48acc6bbba2141c8d90e21-grafana | 172.30.246.2 | GET http://172.30.246.2:3000/api/health |
| loki | c2-cd54f95f5c48acc6bbba2141c8d90e21-loki | 172.30.246.3 | GET http://172.30.246.3:3100/ready |
| prometheus | c2-cd54f95f5c48acc6bbba2141c8d90e21-prometheus | 172.30.246.4 | GET http://172.30.246.4:9090/-/ready |
| tempo | c2-cd54f95f5c48acc6bbba2141c8d90e21-tempo | 172.30.246.5 | GET http://172.30.246.5:3200/ready |

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

## Launch binding

EXECUTED ONCE. Final source review passed and the user's approval was consumed by attempt1. The run stopped before startup at Grafana's post-create inspection; cleanup is independently verified. See [outcome](c2-attempt-1-outcome.md). The runtime root exists and cannot be reused. No automatic retry is authorized.

The exact private card reviewed before launch remains at `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-approved-compatibility/execution-card.md`. Its final approval/source/review bindings are preserved in sibling `launch-readiness.json`. Executed harness SHA256 `2af099b174a37ca7e97e60d4040b21dcf09b0b126e3e3b00f20b066e60098e4f`; source manifest SHA256 `bbfdaf225742196a056f316c345e40158b7499e72bc2d4ffa1f45fa2a33a38a3`. Full prototype checks592passed/36skipped; private checks30passed, Ruffpass.
