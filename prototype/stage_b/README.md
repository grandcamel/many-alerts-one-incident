# Stage B attempt runner (throwaway, ticket 19)

Executes ONE bounded model attempt per the main-repo experiment card
(`.scratch/many-alerts-one-incident/reviews/ticket-19/stage-b-experiment-card.md`):
mediated endpoint with per-attempt sentinel, monotonic 270/20/10 budget
(ADR 0012), sentinel revocation + SIGINT at the work deadline, SIGTERM at the
flush deadline, SIGKILL/reap at the kill deadline, operator-only evidence with
known-secret sanitizer. The real upstream key is read from the operator's
environment at launch and never written to artifacts.

Execution mode is deliberately inert until the card is authorized; only
`--self-test` runs today.

## Self-test evidence (2026-09-18, `artifacts/runner-self-test.json`, verdict `supported`)

Mock dribbling upstream, synthetic keys, scaled budgets:

- **Attempt A** (60 s work budget): client completed in 5.64 s, `is_error`
  false, client-estimated cost under the $3 `--max-budget-usd` guard.
- **Attempt B** (4 s work budget): deadline fired mid-stream — sentinel
  revoked and SIGINT delivered at t=4.03 s; the client flushed and exited
  within the flush window (t=4.42 s). Containment `contained-after-interrupt`;
  no SIGTERM/SIGKILL needed in this sample; both remain wired with their own
  deadlines.

Explicitly `not_run`: real model/upstream, mcp-grafana wiring (Stage A-proven
transport, assembled at execution via `--mcp-config`), fixture scoring against
the card's frozen prompt, billing reconciliation.
