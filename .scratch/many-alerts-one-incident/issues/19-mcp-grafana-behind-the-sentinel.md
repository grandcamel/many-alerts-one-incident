# mcp-grafana behind the sentinel

Type: prototype
Status: claimed
Blocked by: none

## Question

Run `mcp-grafana` as a stdio MCP server inside a copy of the chapter-one image, read-only (`--disable-write --enabled-tools ...`), pointed at the Forwarder with a sentinel as its token, against an `otel-lgtm` with anonymous access off and a Viewer service account, and drive a print-mode Run against it with the allow list naming its tools. Answer what only running it can: do its tool names read well in the log window; do the output cap and the Loki line default fit a five-minute Run; what does the MCP startup wait cost; does the Forwarder's Bearer swap work unchanged; and what does `docker diff` and the denial line show. Compare against a stub of the `eyes` CLI on the same questions if time allows. The throwaway lives on a `prototype/mcp-grafana-eyes` branch.

## Input from ticket 17

[ADR 0011](../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) settles loopback HTTPS with trusted deployment-local CA, a Grafana-specific sentinel, fixed upstream destination and request-aware read/rehearsal scope. The prototype must test client trust and these boundaries rather than assume the old HTTP Basic-auth Forwarder works unchanged. This planning update does not authorize running the prototype.

## Work in progress

Claimed for offline experiment preparation after ticket 17 was resolved. The current session does not execute the model/container prototype. Preserve an explicit NOT RUN result; preparation cannot resolve this measurement ticket or unblock Eyes.

An [experiment protocol](../reviews/ticket-19/experiment-plan.md) now separates real-client transport checks from a later bounded model experiment and defines evidence/decision rules. All execution remains NOT RUN. It requires only an isolated ADR 0011 Grafana subset, not completion of ticket 36, avoiding a dependency cycle through Eyes.

The [offline fact sheet](../reviews/ticket-19/facts.md) resolves historical token-variable naming as a configuration bridge and confirms that the referenced research did not execute mcp-grafana. It therefore provides no measured startup, tool-output or TLS/sentinel compatibility verdict. Ticket 19 stays claimed and unresolved; ticket 12 stays blocked on the actual prototype.

## Protocol refresh after the planning frontier

The accepted decisions through ticket 40 now leave Eyes/Report as the unresolved dependency path for the remaining specifications. The [frontier audit](../reviews/planning-frontier-2026-09-18.md) records the actual edges. The existing experiment protocol has been reconciled with the five-service target, model-free local Stage A subset, mediated Anthropic requirement for Stage B, 300-second Run policy, diagnostic budget and private evidence capture. No stage is executed and no blocker is removed. The next concrete step is explicit authorization to implement/run the bounded local Stage A prototype; model/tenant/cloud gates remain separate.

## Local Stage A authorized — 2026-09-18

The user subsequently authorized implementation and execution of the model-free local subset. Earlier NOT RUN statements above describe preparation history. The isolated prototype starts from `3e17793` on `prototype/mcp-grafana-eyes`; model/container/tenant/cloud gates remain NOT RUN. Local results do not resolve this ticket or unblock Eyes.

## Local Stage A result

[Stage A verdict](../reviews/ticket-19/stage-a-verdict.md): 31 exercised assertions supported, zero refuted, using real pinned mcp-grafana v1.5.1 against synthetic local TLS/Forwarder/backend fixtures. Frozen prototype commit `5f90bfbb20a5a63edecaa118d9a214c0e08389e4`. Full repository suite: 241 passed, 36 skipped. This is transport-scope evidence only. Model usability/budget, container confinement, real tenant and intended-venue gates remain unexecuted; ticket19 stays claimed and ticket12 blocked.

## Stage B readiness assessment — 2026-09-18

[Stage B readiness/gap assessment](../reviews/ticket-19/stage-b-readiness.md): current `claude` CLI 2.1.272 self-documentation captured; the official `claude-api` skill is now installed; and the P1 local routing probe (prototype commit `1973f90`) measured that the client honors a base-URL override with a per-Run sentinel over streaming SSE. Remaining pre-Stage-B work: the TLS fifth-endpoint subset, billing/rates preflight, and the experiment card. Stage B remains NOT RUN and separately unauthorized; no blocker edge changes.

## Stage B attempt 1 — 2026-09-18

The user authorized exactly one bounded attempt; it executed against the synthetic fixtures with a real model through the mediated endpoint. [Outcome](../reviews/ticket-19/stage-b-attempt-1-outcome.md): boundary/budget/containment/sentinel/denial contracts **supported** ($0.286 client estimate vs $3 reservation, 82 s of 270 s, post-run sentinels 401); fixture-question usability **inconclusive due to fixture under-specification** — the exact-query allowlist denies the discovery endpoints a real client needs. Options 1–3 for any second attempt are recorded in the outcome; each needs new authorization and respects the P3 reconciliation hold. Ticket 19 stays claimed; ticket 12 stays blocked.

## Stage B attempts 2–3 — 2026-09-18

User directed unrestricted reads (no SI/PII in synthetic fixtures); fixture amended to permissive-read with discovery endpoints. Attempt 2 was interrupted by an infrastructure containment failure (fixed; no evidence; spend unknown pending daily feed). Attempt 3 completed: [outcome](../reviews/ticket-19/stage-b-attempt-2-3-outcome.md) — mechanics supported (198 s of 270 s, $1.1392 estimate matching token accounting exactly), Q1/Q2/Q4 supported with the model demonstrating discovery-driven probing, Q3 refuted by a named selector gap (fixture exact-match stricter than real Loki). Options for any attempt 4 recorded there; ticket 19 stays claimed, ticket 12 stays blocked.
