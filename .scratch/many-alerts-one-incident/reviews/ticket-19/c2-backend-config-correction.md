# C2 backend configuration correction — source-only, 2026-09-21

The compiler now renders configuration candidates for the two failures retained in [attempt2](c2-attempt-2-outcome.md). Tempo's live-store shutdown marker, live-store WAL and scheduler work cache all use the existing `/data/tempo` mount. Loki advertises loopback to match its private gRPC listener. No new runtime attempt, mount, quota, listener exposure, account/token operation, ingestion or native/model qualification occurred.

## Corrections and source support

Tempo3.0.3 revision1900ed7bb supports `live_store.shutdown_marker_dir`, `live_store.wal.path` and `backend_scheduler.local_work_path`. They are now `/data/tempo/live-store/shutdown-marker`, `/data/tempo/live-store/traces` and `/data/tempo/backend-scheduler`, respectively. The live-store WAL is distinct from the already configured trace-storage WAL. All share the existing 256 MiB data tmpfs; the compiler's writable-path inventory includes the new subdirectories. Read-only root, `/tmp`32MiB, UID2000 and all other limits are unchanged. [Pinned-source trace](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-backend-config-correction/tempo-source-findings.md) binds YAML fields to defaults and consumers. The bounded target=all source audit excludes BlockBuilder; it does not justify adding that module's storage or enabling metrics-generator.

Loki3.7.7 revision7a40404f propagates `common.instance_addr` into its internal rings and frontend. Rendering `127.0.0.1` aligns that advertisement with its existing `127.0.0.1:9095` listener, while Grafana and the operator retain the frozen cross-container HTTP address on port3100. The pinned vendor single-instance configuration uses the same loopback/in-memory-ring pattern. [Loki source evidence](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-backend-config-correction/loki-source-findings.md) and the compiler contract record the distinction between same-container gRPC self-reference and cross-container HTTP URLs.

The production diff changes only the two rendered YAML documents, Tempo's descriptive writable-path inventory and source provenance. The comparison against source8797b16 proves every other container-spec field unchanged, including mounts, listeners, UID, root-read-only flag, capabilities, environment, resource and log limits. The other three rendered artifacts are byte-identical. [Comparison](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-backend-config-correction/configuration-comparison.json).

## Validation and reviews

Full prototype suite: **595 passed, 36 skipped**. Focused configuration suite: **24 passed**. Focused C2 source/test lint passes. New regression cases verify Loki's internal/external address distinction under two private networks and check all five configured Tempo storage paths lie within the existing mounted data directory with its unchanged quota. The returned compiler candidate remains NOT_RUN.

Final **Sol PASS** independently verifies the unchanged source and the supplementary pinned-source anchors. The original review's source-excerpt gap is closed. [Final review](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-backend-config-correction/sol-final-review.md), SHA256 `728e5887d468bc2aef3cf4b889a87eb320c8a51372a69f6ab45116a6623687a7`.

The fresh one-shot requested Fable review of this new correction received an explicit provider `cyber` safeguard refusal and automatically fell back to Opus. Opus's PASS included the missing Tempo excerpts and Loki default-value question; the final Sol review verifies both using [supplementary raw-file anchors](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-backend-config-correction/supplementary-source-anchors.md). No source, tests, original packet or previous review changed. Original identical-panel packet SHA256 `f4f7ed796692c9ba59b820aba75026ec88ddbe44a5406ac62571323edca42bfa` remains immutable.

**Fable review remains unavailable.** Native session `ec73b008-9d1f-4814-8163-51ea0677503a` confirms the refusal and actual final-review model `claude-opus-4-8`; unlike the earlier inspection-review session, this session records Fable refusal output13021 tokens and Opus output2731. Session API-equivalent cost is $2.2206075, not daily billing. No retry, rewording or parent reroute occurred. The user's previous exception covered only the inspection correction/attempt2; it does not waive Fable for this correction. [Adjudication](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-backend-config-correction/review-adjudication.md).

## Runtime boundary and next step

This is a source-supported candidate, not a verified runtime repair. The Python tests parse YAML but do not execute the pinned Go configuration decoder or binaries. Effective configuration, successful startup, complete four-service readiness, internal Loki query/scheduler behavior, writable-path use and capacity under the shared256MiB limit remain unverified. No new gRPC network exposure or extra writable mount is assumed as a fallback.

The old attempt1/2 roots and receipts remain consumed and immutable. A future attempt must use a fresh run ID/root, newly compiled configuration and ownership digest, newly bound source/rendered hashes, final review disposition and an explicitly approved execution card. Old harness manifests intentionally do not match the changed compiler; do not refresh or reuse them. No attempt3 is authorized by this source work. The [attempt3 card](c2-attempt-3-card.md) now supplies a fresh identity/root and the exact proposed scope for a separate approval; no activated harness exists.

Ticket19 remains claimed, ticket12 blocked, and C1 gaps, qualification and spend-reservation boundaries remain unchanged. Private evidence: `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-backend-config-correction`. All work and commits remain local.

Local prototype commit: `817f466acc47f8df51c389934e000ed6dc6271d2`. Source/test/contract hashes match the full-suite validation and final review.
