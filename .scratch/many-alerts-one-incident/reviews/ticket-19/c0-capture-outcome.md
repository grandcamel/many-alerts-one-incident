# Ticket 19 — C0 offline capture outcome, 2026-09-19

Verdict: **supported for synthetic recorder scope**. The user's subsequent "proceed" authorized C0 source/capture preparation and offline tests in the [local acceptance plan](local-container-acceptance-plan.md). C0 is implemented and committed locally at prototype `69c39993d8290ac2c8cc65e11a02c2ad4474a5e3` on `prototype/mcp-grafana-eyes`. C1/C2 remain NOT RUN. Ticket 19 stays claimed; ticket 12 stays blocked.

## Delivered source

The isolated prototype is `/Users/jasonkrueger/projects/maoi-mcp-grafana-prototype`. New source is in `prototype/local_acceptance/`, with tests in `tests/test_local_acceptance.py` and the operator runbook in `prototype/local_acceptance/README.md`. No Stage A, Stage B, root Docker/Compose or production package source changed relative to `3375fdb`.

The recorder preserves bounded stdin/stdout/stderr payloads and metadata, including write intent/completion, notifications, malformed and partial frames, RPC/timing records, EOF and process cleanup. The selector-based transport bounds reads, writes, RPC/session time and cleanup of its owned process group. Capture faults stop new dispatch and prevent a success verdict. Secret sanitation includes registered secrets, credential/account fields and JSON escape variants; redacted evidence is explicitly unverifiable for the unredacted fixture verdict.

Private evidence uses exclusive destinations and a serialized root quota: 64 MiB frames, 1 MiB stderr, 100 MiB bundles including a manifest reserve, 2 GiB per configured evidence root, directory mode 700 and file mode 600. A 30-day expiry is recorded; automatic deletion and crash-lock recovery are not implemented. Disk failure may prevent the final manifest, which remains incomplete evidence. Frame writes do not claim power-loss durability.

The driver launches only the bundled network-free synthetic Python peer in isolated mode with an explicit PATH/LANG environment. Its seven cases compare all expected records/fields: default and complete application logs, Change logs, empty results, instant/range metrics and a fetched trace object. These synthetic tool schemas do not establish native Grafana compatibility.

## Validation and private evidence

Final source validation before committing:

- `env -u DEMO_END_TO_END -u DEMO_CONTAINER python3 -m pytest`: **334 passed, 36 skipped** (370 collected, 16.23 seconds), including all **39 C0 tests**.
- Ruff format/check and `git diff --check`: passed. Proposed YAML was parsed with PyYAML only; no Docker command ran.
- Tests cover large output, split/fragmented reads, notifications/floods, redaction, protocol errors, quota/disk faults, write/RPC deadlines, cancellation, descendant cleanup, explicit environment isolation and failure classification. An earlier large-output check exposed a quadratic email scan; it was corrected. An earlier full-suite failure exposed process-group permission errors masking the original fault; conservative cleanup reporting and a regression test corrected it. The counts above are for the final revision.

The final offline command was `python3 -m prototype.local_acceptance.driver --output /Users/jasonkrueger/maoi-stage-b-evidence/c0/offline-2026-09-19`. All seven cases matched. Private files remain outside Git:

| Read-back | Verified result |
| --- | --- |
| Bundle | `/Users/jasonkrueger/maoi-stage-b-evidence/c0/offline-2026-09-19` |
| Manifest SHA-256 | `9462fcedbf883f668d09c29d6b826737e40ebe1c12f5eafc3be09fa62797e475` |
| Event index SHA-256 | `ae515f2adf6e88e71e357dfb8e59e40cd5dcebcc6bfa95514b089f532de8e1c7` |
| Capture | Complete, unredacted; 58 consecutive events, 19 payload files; every stored payload hash, original byte count and original hash verified |
| Provenance | All five recorded Python/fixture source hashes match the committed source; Python 3.13.7 |
| Lifecycle | Exit 0; direct child reaped, owned process group gone, pipes closed; no escalation; root lock released |
| Storage | 138,567 bundle bytes; 323,734 bytes across the surrounding evidence tree at read-back; C0 root/bundle directories 700, bundle files 600 |
| Retention | Created 2026-09-19T22:24:05.968934Z; expiry 2026-10-19T22:24:05.968934Z |

The library quota covers the private `c0` root. The combined surrounding evidence-tree count above was checked separately; earlier Stage B artifacts and directory permissions were not changed.

## Remaining acceptance boundary

`containers/Dockerfile.proposed`, `compose.yaml.proposed` and `inputs.json` describe an unexecuted topology: network-none Run plus loopback TLS Forwarder, private Unix data/control sockets, and a fixed-target gateway on a separate backend network. They contain no approved Linux artifact or image pins. Unix adapters, socket ownership/readiness, receipt correlation, native tool-case mapping and container identity/filesystem/network probes still need implementation and review. YAML is source preparation, not evidence that the engine enforces that topology.

The next preparation work is to implement those adapters/probes and resolve exact platform/artifact/image inputs into a concrete C1 execution card. C1 build/start and C2 disposable Grafana provisioning remain separately gated. No Docker inspection, pull/build/start, download, credential provisioning, native MCP launch, model call, Grafana instance or cloud action occurred in C0. Nothing was pushed or published.

This replay cannot reconstruct attempt 4's missing model-client MCP responses or establish model spill-file behavior, Linux confinement, real Grafana grants or intended-cluster acceptance. Provider actuals remain unknown; all **$12 reservations remain retained**, and the paid-dispatch exception is consumed. No ticket resolution, blocker removal or further paid attempt follows from C0.
