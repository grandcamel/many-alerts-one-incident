# Ticket 19 — Stage B readiness and gap assessment, 2026-09-18

Prepared by the Kimi K3 orchestrator under the 2026-09-18 handoff. **Stage B remains NOT RUN and separately unauthorized.** This is reversible local/read-only preparation only: no model, tenant, container, cloud or paid API activity occurred, and none is proposed for execution without explicit approval.

## Verified current state

- Main repo HEAD `23a2e95` on `main`, working tree clean (matches handoff).
- Prototype repo HEAD `5f90bfbb20a5a63edecaa118d9a214c0e08389e4` on `prototype/mcp-grafana-eyes`, clean; `prototype/stage_a/artifacts/stage-a.json` summary reads `supported: 31, refuted: 0`, matching the [Stage A verdict](stage-a-verdict.md).
- Dependency graph unchanged: ticket 19 claimed, ticket 12 blocked, all downstream edges intact ([frontier audit](../planning-frontier-2026-09-18.md)).

## Delegation record

One bounded Flash task (`claude-api` skill search + client help capture) was dispatched via `headless antigravity --model gemini-3.8-flash-medium --role worker --allow read-only` from an isolated temp work dir. First attempt: **execution failure** — the harness auto-denied the `command` permission in headless mode (`permissions.allow` covered only `command(cp)`). After the user approved adding `command(*)` to `~/.gemini/antigravity-cli/settings.json`, one fresh retry (same prompt, same boundaries, new process) returned **usable**: a structured verdict with searched locations and quoted help extracts. Orchestrator independently gathered the same facts locally before the retry; worker and local evidence agree with no contradictions. No panel was dispatched: the remaining gaps are factual/protocol requirements, not ambiguous reasoning that a review could change.

## Fact findings

### F1 — `claude-api` skill: FOUND and installed 2026-09-18

Earlier this session the skill was confirmed absent from all local skill/plugin locations (orchestrator search plus an independent Flash worker). A `skills.sh` registry search then found the exact official package `anthropics/skills@claude-api` (65.5K installs), now installed at `~/.agents/skills/claude-api`. It documents current model ids (default `claude-opus-5`), the Messages request/response/SSE shapes used by the P1 mock, and `ANTHROPIC_BASE_URL` / `base_url` endpoint override for the SDKs and `ant` CLI (`shared/anthropic-cli.md:31`, `SKILL.md:465`). Plan prerequisite 2's skill requirement is now satisfied; model/effort/output limits remain unfrozen until the Stage B experiment card is approved.

### F2 — `claude` CLI 2.1.272 self-documentation (captured `claude --help`, `claude mcp --help`, `claude auth --help`)

Documented in current help:

- Print mode: `-p, --print`; machine-readable output `--output-format text|json|stream-json`; `--no-session-persistence`.
- Model and effort: `--model <model>` (aliases `fable`/`opus`/`sonnet` or full name); `--effort low|medium|high|xhigh|max`.
- Client budget guard: `--max-budget-usd <amount>` (print mode only) — per ADR 0013 this is a secondary estimate-based guard, not a hard billing ceiling.
- MCP: `--mcp-config <files...>` / `--strict-mcp-config`; `claude mcp add <name> -- <command> [args]` supports stdio servers with env — sufficient to launch the pinned mcp-grafana v1.5.1 stdio binary.
- Tool/permission scoping: `--allowedTools` / `--disallowedTools` / `--tools`; `--permission-mode`; `--permission-prompts none` for unattended Runs.

**Not documented in help:** any custom API base-URL/endpoint configuration (no `ANTHROPIC_BASE_URL`-style variable appears). `--bare` states Anthropic auth is strictly `ANTHROPIC_API_KEY` or `apiKeyHelper` via `--settings`. There is no `config` subcommand in 2.1.272. Endpoint override is documented in the installed `claude-api` skill (F1) and its runtime behavior is now measured (F3).

### F3 — P1 routing probe: measured 2026-09-18 (local, model-free-in-billing)

Prototype commit **`1973f90`** on `prototype/mcp-grafana-eyes` (`prototype/routing_probe/`, evidence `artifacts/routing-probe.json`). The installed client, run as `claude --bare -p` from a throwaway HOME with `ANTHROPIC_BASE_URL` at a loopback mock and a random synthetic sentinel key:

- Routed all Messages traffic to the mock: `POST /v1/messages?beta=true` with the sentinel presented as `x-api-key`; no direct route to the real API occurred. Verdict `supported-routing`.
- Sent `stream: true` and accepted the mock's SSE event sequence, completing the turn (`terminal_reason: completed`, `is_error: false`). Streaming support is therefore a hard requirement for the fifth Forwarder endpoint.
- Defaulted to model `claude-opus-5`, `max_tokens` 64000, `anthropic-version: 2023-06-01`, Stainless SDK headers including `x-stainless-retry-count` — the endpoint must tolerate SDK-level retries (an earlier run showed 4 requests against failing responses).
- Client-reported `$0.00006` is its own list-price estimate; actual billed spend is $0 — the mock terminated every request and the key is invalid everywhere else. Probe elapsed 1.815 s.

**Limit:** this settles routing and request-shape compatibility only. TLS trust of a deployment-local CA, endpoint policy enforcement, billing visibility/rates and the ADR 0012/0013 admission contract remain unverified.

## Gap assessment against Stage B prerequisites

From [experiment-plan.md](experiment-plan.md) §Stage B and ADRs 0012/0013/0014:

| # | Prerequisite | Status | Gap |
| --- | --- | --- | --- |
| G1 | Required `claude-api` skill before asserting model/CLI flags | **Resolved 2026-09-18** | Official `anthropics/skills@claude-api` installed (F1); plan prerequisite 2 satisfied. |
| G2 | Mediated Anthropic path: fifth Forwarder endpoint, per-Run sentinel, real key outside the Run | **Routing compatibility measured** | P1 (F3): client honors the endpoint override, presents the sentinel, streams SSE, tolerates no unusual transport. Remaining: implement the TLS fifth endpoint (ADR 0011 pattern) and ADR 0013 billing/rates preflight. |
| G3 | Diagnostic reservation ($3/attempt, weekly envelope, durable Receiver-owned ledger) | **Not built** | ADR 0013 admission rules. A reservation/ledger format can be drafted locally; no spend occurs in preparation. |
| G4 | Private operator-only evidence capture (100 MiB/Run, 2 GiB total, 30-day, ADR 0014) | **Not built** | Capture layout and sanitizer contract can be drafted locally, reusing Stage A's known-secret scan pattern (`prototype/stage_a/run_stage_a.py:329`). |
| G5 | 270/20/10-second budget with monotonic clock, interruption, reaping, revocation | **Design-ready** | Stage A already demonstrated process reaping and mid-session revocation; the Stage B runner design can carry these over. No new measurement needed pre-authorization. |
| G6 | Model qualification (three representative Fault lifecycles) | **Out of scope here** | Ticket-19 Stage B is a usefulness probe and does not count toward qualification (experiment plan; ADR 0013). |

## Proposed concrete next experiments (require explicit authorization; none launched)

- **P1 — Mediated-path routing probe: COMPLETE 2026-09-18.** User authorized via "proceed"; result in F3. No paid API contact occurred.
- **P2 — Stage B experiment card: DRAFTED 2026-09-18** at [stage-b-experiment-card.md](stage-b-experiment-card.md). Frozen prompt, declared client/model config, TLS fifth-endpoint subset design, time/spend/evidence contracts and a four-item launch checklist. Drafting surfaced one new prerequisite probe: **P4** (client trust of a deployment-local CA — unmeasured, not documented in `--help`; same local/model-free class as P1).
- **P3 — Billing/rates preflight (read-only account checks):** verify current account rates, billing visibility and lag before any paid attempt, per ADR 0013. Requires the user's mediated-account context; no purchase or key creation.

## Missing decisions to request

1. Stage B itself: paid, separately gated — not requested by this document. The remaining technical unknowns G1/G2 are settled; what remains before a well-formed Stage B request is the P2 experiment card, the P3 billing preflight, and the user's explicit authorization.
