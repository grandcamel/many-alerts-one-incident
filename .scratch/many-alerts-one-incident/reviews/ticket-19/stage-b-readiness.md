# Ticket 19 — Stage B readiness and gap assessment, 2026-09-18

Prepared by the Kimi K3 orchestrator under the 2026-09-18 handoff. **Stage B remains NOT RUN and separately unauthorized.** This is reversible local/read-only preparation only: no model, tenant, container, cloud or paid API activity occurred, and none is proposed for execution without explicit approval.

## Verified current state

- Main repo HEAD `23a2e95` on `main`, working tree clean (matches handoff).
- Prototype repo HEAD `5f90bfbb20a5a63edecaa118d9a214c0e08389e4` on `prototype/mcp-grafana-eyes`, clean; `prototype/stage_a/artifacts/stage-a.json` summary reads `supported: 31, refuted: 0`, matching the [Stage A verdict](stage-a-verdict.md).
- Dependency graph unchanged: ticket 19 claimed, ticket 12 blocked, all downstream edges intact ([frontier audit](../planning-frontier-2026-09-18.md)).

## Delegation record

One bounded Flash task (`claude-api` skill search + client help capture) was dispatched via `headless antigravity --model gemini-3.8-flash-medium --role worker --allow read-only`. Terminal classification: **execution failure** — the harness auto-denied the `command` permission in headless mode and produced no final message. A retry would require editing permission settings or a prohibited bypass mode, so per the headless reference the task was completed locally from canonical evidence instead. No panel was dispatched: the remaining gaps are factual/protocol requirements, not ambiguous reasoning that a review could change.

## Fact findings

### F1 — `claude-api` skill: NOT FOUND (current, not historical)

Searched this session: `~/.claude/skills/`, `~/.agents/skills/`, `~/projects/.agents/skills/`, `~/.claude/plugins/` (marketplaces, cache, pearpass-plugin, wiredove-plugin), `~/.config/`, and the project checkouts. No exact or near-miss match. The previous session's observation is confirmed as current. A `find-skills` installer skill exists but installing a new skill is a system change outside this preparation scope.

### F2 — `claude` CLI 2.1.272 self-documentation (captured `claude --help`, `claude mcp --help`, `claude auth --help`)

Documented in current help:

- Print mode: `-p, --print`; machine-readable output `--output-format text|json|stream-json`; `--no-session-persistence`.
- Model and effort: `--model <model>` (aliases `fable`/`opus`/`sonnet` or full name); `--effort low|medium|high|xhigh|max`.
- Client budget guard: `--max-budget-usd <amount>` (print mode only) — per ADR 0013 this is a secondary estimate-based guard, not a hard billing ceiling.
- MCP: `--mcp-config <files...>` / `--strict-mcp-config`; `claude mcp add <name> -- <command> [args]` supports stdio servers with env — sufficient to launch the pinned mcp-grafana v1.5.1 stdio binary.
- Tool/permission scoping: `--allowedTools` / `--disallowedTools` / `--tools`; `--permission-mode`; `--permission-prompts none` for unattended Runs.

**Not documented in help:** any custom API base-URL/endpoint configuration (no `ANTHROPIC_BASE_URL`-style variable appears). `--bare` states Anthropic auth is strictly `ANTHROPIC_API_KEY` or `apiKeyHelper` via `--settings`. There is no `config` subcommand in 2.1.272. Per the handoff rule against inventing flags, the mediated-endpoint mechanism is **unverified from installed self-documentation**.

## Gap assessment against Stage B prerequisites

From [experiment-plan.md](experiment-plan.md) §Stage B and ADRs 0012/0013/0014:

| # | Prerequisite | Status | Gap |
| --- | --- | --- | --- |
| G1 | Required `claude-api` skill before asserting model/CLI flags | **Missing** (F1) | Plan prerequisite 2 is explicit. Either the skill is obtained/installed (user action) or the protocol is amended to accept verified installed self-documentation (F2) as the contract. This is a decision for the user, not the orchestrator. |
| G2 | Mediated Anthropic path: fifth Forwarder endpoint, per-Run sentinel, real key outside the Run | **Compatibility unverified** | ADR 0013: "Actual compatibility is unverified." Client endpoint configuration is not documented in current help (F2). A model-free local routing probe can settle this — see P1 below. |
| G3 | Diagnostic reservation ($3/attempt, weekly envelope, durable Receiver-owned ledger) | **Not built** | ADR 0013 admission rules. A reservation/ledger format can be drafted locally; no spend occurs in preparation. |
| G4 | Private operator-only evidence capture (100 MiB/Run, 2 GiB total, 30-day, ADR 0014) | **Not built** | Capture layout and sanitizer contract can be drafted locally, reusing Stage A's known-secret scan pattern (`prototype/stage_a/run_stage_a.py:329`). |
| G5 | 270/20/10-second budget with monotonic clock, interruption, reaping, revocation | **Design-ready** | Stage A already demonstrated process reaping and mid-session revocation; the Stage B runner design can carry these over. No new measurement needed pre-authorization. |
| G6 | Model qualification (three representative Fault lifecycles) | **Out of scope here** | Ticket-19 Stage B is a usefulness probe and does not count toward qualification (experiment plan; ADR 0013). |

## Proposed concrete next experiments (require explicit authorization; none launched)

- **P1 — Mediated-path routing probe (local, model-free):** extend the throwaway Forwarder subset with a local mock Anthropic listener; configure the client via its documented settings mechanism to target it with a per-Run sentinel and no real key; observe whether the client's request arrives at the listener with the sentinel and whether any direct-route fallback occurs. No paid API contact — the mock terminates the request. Settles G2 factually before any spend. This is a new bounded local experiment beyond the Stage A authorization and needs its own approval.
- **P2 — Stage B experiment card (document only):** single controlled read-only prompt, pinned Stage A fixtures with source-grounded expected results, declared model/effort, 270/20/10 enforcement, reservation record, private capture manifest, and ticket-21 outcome fields — drafted for approval so one decision authorizes a fully specified attempt.

## Missing decisions to request (once preparation is confirmed complete)

1. G1 adjudication: install/obtain the `claude-api` skill, or amend plan prerequisite 2 to accept installed CLI self-documentation (F2) plus official documentation references.
2. Authorization for P1 (local, model-free) if G2 must be settled before the paid experiment card is finalized.
3. Stage B itself: paid, separately gated — not requested by this document.
