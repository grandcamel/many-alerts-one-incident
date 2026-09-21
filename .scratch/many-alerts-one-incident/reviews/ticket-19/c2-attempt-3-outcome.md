# C2 attempt 3 — compatibility observed and cleanup verified

The user explicitly accepted final Sol in place of unavailable Fable for the backend configuration correction and authorized exactly one attempt3 with “Approved. Continue”. That run completed **COMPATIBILITY_OBSERVED**, exit0 in **48.087 seconds**. Independent post-run verification also exited0 with no problems. The approval is consumed; the run/root must never be reused and no attempt4 is authorized.

## What the run establishes

The pinned Linux/amd64 image started all four directly invoked backends with the reviewed configuration at prototype `817f466acc47f8df51c389934e000ed6dc6271d2`. All40 named post-create and all40 named running identity predicates passed, as did Grafana's UID2000 bootstrap-file readability check and the running network/member checks. All four services returned exact HTTP200 in readiness round5 (the sixth round). The curl exit/status predicate is bounded compatibility evidence; response framing and bodies are retained observations, not strict HTTP adapter or seed-oracle acceptance.

| Backend | Readiness requests | Exact HTTP200 with successful command | Earlier observations | Version |
| --- | ---: | ---: | --- | --- |
| Grafana | 6 | 2 | 4 transport failures | 13.2.1 |
| Loki | 6 | 1 | 5 HTTP503 | 3.7.7, revision7a40404f |
| Prometheus | 6 | 6 | None | 3.14.0, revisiond7598b7141418fa35be2b5ec5d0fefb634199610 |
| Tempo | 6 | 6 | None | 3.0.3, revision1900ed7bb |

Version, process status, TCP/TCP6/UDP/UDP6 tables, mountinfo, Docker top/diff and bounded logs were captured for every component. The corrected Tempo paths and Loki advertisement therefore passed startup/readiness in this bounded run; shared tmpfs capacity under ingestion load and internal query behavior remain untested. No mount, quota, listener exposure or privilege was expanded.

[Independent observation audit](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-attempt-3-approved/runtime-observations.md) records PID1 UID/GID2000, zero effective/permitted/bounding capabilities, NoNewPrivs1 and Seccomp2, the bounded data/tmp mounts and selected listener tables. These observations do not prove every process or external reachability. Prior Tempo /var/tempo write-error and Loki self-dial/refusal phrases do not recur in the captured log tails. Other warnings/errors remain: missing Grafana dashboard/plugin/alerting provisioning directories, transient SQLite retries, Loki startup empty-ring error, and Tempo scheduler no-jobs errors and replay/module warnings. Readiness passed despite these messages; this is not a clean-log or successful-query claim.

## Cleanup and integrity

All five durable-receipt IDs were independently absent: network `ba3077a35f36a721d97f091c976277a479300df8ff7660c1e48550c6a60871ad`; Grafana `ad428785014f8ffb2fe52b79a6f11132a6c17707f430ba66c025bf0d926f4d3b`; Loki `b9d4ba3bdf419053b741002cd6e8e7d2aa4c79ecdeea0ddfe39200deb41efd91`; Prometheus `44b38de6d8674bad52675dc6ff6ea7fa0d46e48444dfe9a5cb591b5351722aff`; Tempo `1738c6bc2460d04b92f635877d608ee4523410eca52ec5a5d6286ad163bffb3c`. No unresolved or acknowledged-but-unpersisted creation effects remain. The temporary Grafana password is absent. No user API key was accessed or refreshed.

Baseline, final and independent fresh inventories agree:15containers,6networks,70listedimages,14volumes; no additions or removals. Exact pinned-reference inspection independently confirms image configuration ID `sha256:44a7f733cea9b946b061774e5cbc690cb303e4a2de1719279ae212f01c4ff28f` and repository digest `sha256:35da4355c58162b6f27ccbd43c6214d565bc29fc9b18baaf43b59202c354577b` preserved. Listed image IDs alone are not the base-identity oracle.

All244 retained command stdout/stderr payload hashes verified. The original post-run index has157files/770836bytes; the final runtime index includes that original index and has158files/795010bytes, SHA256 `4fe479977e3c1ad4bda6b9512353622c36a8c0539a69dc94ea82bf53cf0ae104`, all read back. After unlinking the temporary password, the harness scanned the evidence JSON and decoded command bytes then present for the retained in-memory raw/JSON-escaped generated value. The subsequently written final inventories, outcome, parent/verifier/reviewer reports and indexes are outside that scan; arbitrary encodings are outside its claim.

Runtime root: `/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-3-20260921`, runID `27792cef867e4a1ea76495c4cb9df174`. Retention expires `2026-10-21T20:51:04.095245+00:00`; no automatic deletion is scheduled. Prior attempts and preparation packets remain preserved.

## Review and validation

Activation Sol PASS SHA256 `9c39d0089b5c2d88470c80b5ea6b9941f0a96d74b6e8a76c67ace6386e583798` binds the final executor, unchanged verifier, corrected approved-card text, launcher and tests. Reviewer findings were corrected before launch: stale preparation wording, optimization-sensitive launcher assertions, omitted test-source bindings and one inconsistent lint receipt. Full private suite **81 passed**; full prototype **595 passed,36 skipped**; scoped Ruff passed. All19 activation-reviewed file hashes matched immediately before launch; launch-readiness freezes21 artifact hashes including all five test files.

No new external model review was invoked. The prior Fable safeguard refusal and automatic Opus fallback remain accurately classified; this run uses only the user's scoped Sol exception. Terra completed the detailed [runtime observation audit](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-attempt-3-approved/runtime-observations.md), SHA256 `51cdda47c6e82206129176598323e4b81390cd45c2233cc7263d8195443880ea`. Final [Sol outcome review](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-attempt-3-approved/outcome-sol-review.md) **PASS**, SHA256 `0a843565e10099238eb299de47f5a6ad75dcc1661975758d0878edb7c3a11b9c`, independently verifies the bounded claims, cleanup, hashes and remaining acceptance limits. No outcome blocker remains.

## Remaining boundaries and next work

This completes the first-stage backend compatibility experiment in the [approved scope](c2-attempt-3-card.md), not full C2 or Eyes qualification. No ingestion/seed, account or Viewer-token operation, strict-adapter real-backend transaction, gateway/Forwarder/Run session, native MCP or qualification model call occurred. Public Prometheus acceptance remains closed. The next preparation is bounded real HTTP/seed-oracle integration and its separately reviewed execution card; account/native-policy work remains later scope. Ticket19 stays claimed, ticket12 blocked, C1 gaps and spend-reservation boundaries unchanged. All commits remain local.

Primary evidence: [parent read-back](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-attempt-3-approved/runtime-readback.json), [independent verification](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-3-20260921/post-run-verification.json), [runtime index](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-3-20260921/runtime-artifact-index.json), and [activation review](/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-attempt-3-approved/activation-sol-review.md).
