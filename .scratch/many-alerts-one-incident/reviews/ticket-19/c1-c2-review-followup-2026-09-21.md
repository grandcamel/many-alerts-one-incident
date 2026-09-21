# Ticket 19 — C1/C2 review follow-up, 2026-09-21 UTC

**This source-preparation batch and adversarial review are complete; container execution remains closed. No new container experiment has run.** This continues the approved [parallel preparation](c1-c2-preparation-outcome.md). Ticket 19 remains claimed and ticket 12 blocked. Runtime, real-backend ingestion, native MCP acceptance for this revision, and qualification remain NOT RUN.

## Claude review diagnosis

The user supplied a successful Fable session transcript. Its read-back confirmed an actual `claude-fable-5-1` response and session usage. The three previously timed-out review transcripts contained their prompts but no assistant response or completed-call usage. Their zero cost-state entries do not independently establish zero billing.

Fresh isolated inline and prompt-file probes both succeeded in about seven seconds. Splitting the 165,993-byte review into separate 47,358/49,556-byte packets and setting medium effort produced two substantive Fable reviews in 215.145 and 402.281 seconds. The C2 oracle review also completed in 306.147 seconds. The working path is demonstrated; the original cause remains unproven because scope, effort and time all changed. All calls used fresh, read-only `headless` sessions with deadlines. No API-key refresh or credential-value inspection was needed.

Session-level API-equivalent costs for those three completed reviews were $1.61215025, $2.22644025 and $2.17658025. The corrected final harness and cap reviews reported $2.54446025 and $2.07515025 respectively. Probe costs are retained separately in the diagnostic artifacts. The canceled review has no usable opinion or asserted zero cost. These are session telemetry, not a daily Claude usage report. Private diagnostic and review artifacts are under `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-claude-diagnosis` and `20260921-scoped-review`.

## Supported corrections

- C1 assessor: strict result/error and text-part shape, boolean `isError` and truncation metadata, and the full pinned overflow-message marker while allowing a tool prefix.
- C1 cap evidence: bind the intended query response's body size to its correlation record, preserving valid datasource metadata lookups. Offline Bundle tests retain and read back exact MCP frame bytes and hashes at 10 MiB − 1, 10 MiB and 10 MiB + 1. All three Tempo cases reserve capture capacity, including an unexpected uncapped overflow response; this does not test the full transport reader or native timing.
- C1 harness: refuse before project imports; use a hash-verified read-only source snapshot for imports, builds, compose and the isolated host driver; compare capture provenance with the frozen manifest.
- C1 evidence and cleanup: required export failures fail the result; reserve separate export/removal/sweep deadlines; force-remove only exact label-verified container IDs; report residual resources and verify base-image preservation; refuse temporary base-tag removal without another retained reference.
- C1 containment and inventory: invalidate and redact or quarantine known-secret matches, record them in the ledger, record interruptions, and validate additional namespace/device/runtime settings against actual attempt-3 inspections.
- C2 oracle: freeze full log rows, labels and multiline content and complete direct Tempo span structure. Public Prometheus acceptance remains blocked in this version because there is no validated label-contract promotion API. Backend discovery/translation and native Tempo response compatibility remain explicit execution gates.

## Review adjudication

Sol found malformed cap-error acceptance, ignored exports, source drift after preflight, and imports preceding the closed gate. Fable independently found export starvation of cleanup, missing residual sweeps, base-image reference risk, and retained-secret handling gaps. These are preparation defects rather than evidence of an observed runtime breach.

Two Fable recommendations needed correction against canonical evidence: all three Prometheus body sizes were observed successfully in attempt 3, and cap cases include datasource lookups as well as their data query. The certificate helper import was already after the old gate; only the top-level project imports preceded it. A follow-up inventory report conflated absent `Sysctls`/`Init` keys with null; offline replay caught that error and the predicates now use the actual absent-key shape.

A final harness review invocation was canceled after that replay failure exposed the incorrect field assumption; it produced no usable opinion. The corrected full harness packet received Fable PASS for source preparation in 436.019 seconds; the final cap packet received PASS with findings in 307.981 seconds. Sol passed the corrected harness and C2 oracle, and reviewed the final cap changes. The small subsequent capture delta implements Fable's recommendations and received a separate Sol PASS with no findings. Old packets and results remain immutable. The execution gate is now named `EXECUTION_GATE_OPEN = False`, expressing both review and fresh-approval requirements without implying that all Fable work is still missing.

## Validation and next boundary

The final prototype full suite passed **476 tests, 36 skipped**, in 23.49 seconds. Private harness tests passed **24 tests** before final binding; the bound harness also passed **24 tests** after the source and manifest constants were replaced. The final binding audit and read-back are recorded below. The prepared [attempt-4 card](c1-attempt-4-card.md) does not inherit consumed runtime approval. C2 still needs exact configuration, endpoint/authority policy, operator seeder/driver integration and separately approved execution. No push, publication, ticket resolution or reservation release follows from this preparation.

## Explicit residual findings

The final Fable cap review has no source-preparation blocker. Its exact-frame storage and overflow-counterexample reservation suggestions were implemented. Remaining advisory findings are recorded without expanding this preparation: the out-of-window Forwarder 409 path has no denied receipt; non-cap numeric error markers remain substring checks; initialize correlation is recorded but independently checked later; malformed receipt rows may raise `KeyError` rather than return a false join verdict. Both outcomes fail acceptance. Response-identity binding is sufficient only for the pinned unique fixture routes.

The C2 direct-backend Loki and Tempo oracle is implemented and source-tested. Prometheus public comparison deliberately raises `ExecutionGateError` in this version; caller-controlled candidate metadata cannot promote a label contract. The proposed `job`/`instance` labels, effective Loki label discovery settings, pinned-image compatibility, exact configuration and seeder/driver integration require later validation. Native Tempo `application/vnd.grafana.llm` comparison remains unsupported. No source review or synthetic test establishes C2 ingestion or native backend acceptance.

SIGKILL/host loss, host orphan-process sweeping, default seccomp/CapBnd measurement, native certificate variants and interruption/restart drills remain unmeasured. The final cap review's runtime error-envelope and timing assumptions remain NOT RUN for this revision. Ticket and spend-reservation boundaries are unchanged.

## Frozen local bindings

Prototype commits: `4179e346a9170b03abe8f0621d00f24773a69f07` contains the reviewed C1/C2 hardening; final `5cbf616328ec7763a9987a9541c60a0fd6254c10` adds the capture counterexample reservation and exact three-size frame read-back. The prototype checkout is clean. No push or publication occurred.

- Source verification: `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/attempt-4-verification.json`, 40 files, SHA-256 `7acc563d7d46cd5db1a280fb3ffc4143833adb47b23ee6e0c7e59e23d975cfd3`.
- Closed harness: `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/attempt-4-execution.py`, SHA-256 `7a1f4a5b3bd8fa22689fd2b6383f7f9db66b47c7195a07f218c1f7c02032652d`.
- Full-suite log: `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-scoped-review/full-suite-final.log`, SHA-256 `a1823e40039da1679534f05a957687de88bd69a7f2f7fc8b1bdae99ee989be3d`.
- Final review/read-back index: `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-scoped-review/final-artifacts.json`; separate `final-binding-sol-review.md` verifies the binding-only change.

`EXECUTION_GATE_OPEN = False` and `execution_authorized: false` remain set. The prospective attempt-4 evidence directory is absent. A later approved gate change must record a new executable hash and independently verify actual runtime receipts, resources and cleanup. Source preparation does not establish those claims.
