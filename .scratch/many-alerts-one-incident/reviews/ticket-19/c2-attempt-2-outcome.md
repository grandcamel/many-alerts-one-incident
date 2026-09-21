# C2 attempt2 outcome — 2026-09-21

The single approved attempt **stopped during readiness checks because Tempo exited**. All four containers passed the corrected post-create identity checks and received successful start-command results. Grafana's UID2000 read-access check passed. No complete four-service readiness round succeeded. The runner returned `FAILED_OR_INCOMPLETE` after 45.360 seconds, then independent verification confirmed removal of all four containers and the network, deletion of the disposable bootstrap password and preservation of the pinned image and preexisting inventories. No new runtime attempt followed.

User approval and the scoped Sol-for-Fable review exception are recorded in [activation](c2-attempt-2-activation.md). Run ID `597603121ff14b578f396ea7c826ba41`; consumed root `/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-2-20260921`. This root must never be reused. No seed/ingestion, account/token operation, native MCP or qualification-model session occurred.

## Observed failures and limits

The terminal guard was `CompatibilityError: container exited before health: tempo`. Tempo 3.0.3 logs report live-store startup failure because creating its shutdown-marker directory required `mkdir /var/tempo`, rejected by the read-only root. The backend scheduler also reports inability to flush its work cache under `/var/tempo`. These are concrete logged incompatibilities between defaults and the current bounded writable-path configuration. They do not justify relaxing the read-only root; the next source investigation should first look for supported path overrides into the existing bounded service-data tmpfs and check all affected defaults. The retained evidence does not yet establish which overrides exist.

Loki logs show gRPC listening on `127.0.0.1:9095` while internal components dial `172.30.246.3:9095` and receive connection refused. Loki nevertheless returned HTTP 200 in later readiness checks, so that status alone does not establish internal query/ingestion compatibility. A source-level listener/advertisement correction must retain the intended authority boundary and be reviewed before another runtime card. No corrective configuration was applied during this attempt.

The new inspection evidence retains `Config.Image` equal to the exact supplied pinned reference and Healthcheck `Test=["NONE"]` plus Interval 30000000000, Timeout 5000000000 and Retries 3 for all four containers. All ten named identity predicates passed for each. This verifies the corrected disabled-healthcheck representation for attempt2; it does not reconstruct attempt1's missing fields or prove its exact cause.

| Backend | Requests | Exact HTTP200 with curl success | HTTP503 | Transport failures |
| --- | ---: | ---: | ---: | ---: |
| Grafana | 9 | 4 | 0 | 5 |
| Loki | 9 | 5 | 4 | 0 |
| Prometheus | 9 | 9 | 0 | 0 |
| Tempo | 8 | 0 | 8 | 0 |

There were 35 health requests. Tempo's ninth state inspection reported not running, so its ninth request did not occur. The harness correctly did not treat curl exit 0 plus HTTP 503 as readiness. Later running-container/network posture verification, version commands, /proc diagnostics, Docker top/diff and complete compatibility acceptance were NOT RUN because readiness failed. Retained service startup logs are distinct from unrun version probes. Strict HTTP framing, seed oracles, native/model/venue qualification and the public Prometheus acceptance gate remain unverified or closed.

## Cleanup and evidence

- network: `79159a2f806fbe196c3f68442ca6ff8bab114791b0f1eed079ecc9c2343edd1e` — independently absent.
- grafana: `2e85b7eaac5a2d170f25ca1ff9e9bf34dac90d6e4356493900f0a33f4c41225c` — independently absent.
- loki: `389fe4b91970f984cd824444f12fe1c043fa280764e57385a33de404d9bda567` — independently absent.
- prometheus: `9c45ff4a2cb81d32885792468e8e7e75580bb2bb021f11bba9d0f09eecfb52ee` — independently absent.
- tempo: `2680ae01fb6535b3fab413561908f559ef1b3d807cb7ba2b329d3993f061bde8` — independently absent.

No unresolved create intents or acknowledged-but-unpersisted IDs remain. Baseline/final/fresh inventories are identical: 15 containers, 6 networks, 70 listed image IDs, 14 volume names. Exact pinned-reference inspection independently confirms image configuration ID `sha256:44a7f733cea9b946b061774e5cbc690cb303e4a2de1719279ae212f01c4ff28f` at digest `35da4355c58162b6f27ccbd43c6214d565bc29fc9b18baaf43b59202c354577b`. No unrelated resource deletion or new volume was observed. Secret absence is separate from the bounded in-process raw/escaped secret scan; no secure-erasure claim is made.

The independent verifier checked 218 command-payload hashes. Its only remaining problem is runtime compatibility incomplete; cleanup and preservation checks pass. Original post-run index of 138 files is retained. Final runtime index verifies 140 files totaling 764,203 bytes, including metadata and the original index; SHA256 `30749ed17029c95c43777d52bbca92785f67b9e79b830591d14e64abd893460a`. Retention expires 2026-10-21T19:56:56.236074Z; no automatic deletion is scheduled. Primary records: [outcome](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-2-20260921/evidence/outcome.json), [independent verification](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-2-20260921/post-run-verification.json), [final index](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-2-20260921/runtime-artifact-index.json).

## Source, review and next work

Activated harness `67ad60e1aa95fb1b983e1addef5a45f4c14e39a9f2d2931209cda82c130fbdf6`; manifest `739212cffe23200eaaedd24949d8f84681a7819848b046a728b6e54976c9b2eb`; unchanged verifier `bdea03ad68d0fb7275212437d4d0e2079c23f038c2131cee8918d4838c25e462`. Prototype source 8797b164b73f7d83eb4183e3d58f00399a10282b remains unchanged. Full prototype suite: 592 passed, 36 skipped; private suite: 79 passed; private lint passed. Sol independently passed activation. The user explicitly accepted final Sol instead of unavailable Fable for this correction; Fable was not retried or credited with an opinion. Terra independently diagnosed the retained logs and configuration; its [report](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-attempt-2-approved/runtime-diagnosis.md) confirms both incompatibilities. Any extra tmpfs or wider listener would require newly reviewed bounds; first investigate configuration-only corrections within the existing limits. Final Sol outcome audit **PASS_WITH_FINDINGS** confirms the outcome account and evidence integrity, with no contradiction or packaging defect. Its findings preserve the declared unrun/runtime/authority limits; they do not change the failed runtime status. Report SHA256 `ca166febd5afe87a02e177b09fc85ef6ebfed1d6c49dbed9731601061fc131d9`.

Next source preparation: resolve Tempo's writable default paths and Loki's gRPC listener/advertisement mismatch using pinned source/configuration evidence, retain current containment/resource limits, add meaningful compatibility regression cases and adversarial review, then prepare a fresh card if another attempt is warranted. This consumed approval does not authorize attempt 3. Ticket 19 remains claimed, ticket 12 blocked; C1 gaps, qualification and spend-reservation boundaries are unchanged. No publishing occurred.
