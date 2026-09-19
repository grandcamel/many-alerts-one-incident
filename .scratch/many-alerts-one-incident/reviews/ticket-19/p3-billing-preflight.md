# P3 — billing/rates preflight checklist (guided, user-executed)

**Status: corrected 2026-09-19 — provider actuals unavailable; session telemetry only.** The user corrected the earlier daily-feed assumption: daily usage/cost is not available for this account; session telemetry is the only available cost evidence. No daily-feed follow-up remains. Telemetry estimates are not provider billing actuals under ADR 0013. See the [accounting disposition](stage-b-attempt-2-3-outcome.md#accounting-disposition--2026-09-19); unknown charges remain reserved and the P3 paid-dispatch hold remains applied. The original 2026-09-18 verification outcomes follow, with item 3 superseded.

1. **API-billed account access**: confirmed — user holds an Anthropic API-billed account distinct from the OAuth subscription and can mint an execution-time key.
2. **Current account rates**: confirmed on the console, consistent with the documented `claude-opus-5` $5/$25 per MTok list rates (card estimate unchanged).
3. **Billing visibility and lag (superseded 2026-09-19)**: the earlier report of daily console usage/cost was incorrect. Only session telemetry is available; provider actuals and reporting lag cannot be established from a daily feed. Further local work can proceed; paid dispatch remains subject to the accounting hold and separate attempt authorization.
4. **Provider limits**: $3 reservation fits within existing account limits; nothing raised, purchased or changed.

The reservation record format below remains the execution-time artifact.

ADR 0013 requires verifying current account rates, billing visibility and lag, provider limits and the mediated client path **before** any paid Run. Items 1–4 need your account context; the orchestrator cannot do them. Estimated effort: ~10 minutes. Evidence category for every number must be identified (ADR 0013): provider billing page = actual-spend authority; list prices = documentation; client `total_cost_usd` = estimate.

## Known state (already established, no action)

- Current local `claude` auth is **OAuth subscription** (`headless --check`, 2026-09-18). ADR 0013 requires **dedicated metered API billing** for demo Runs — the real key injected at the mediated endpoint must come from an API-billed account, not the subscription OAuth session.
- Documented list price for the declared model: **claude-opus-5, $5 / $25 per MTok (input/output)** — `claude-api` skill `shared/models.md:76`, "a drop-in upgrade at Opus 4.8's pricing ($5/$25 per MTok)". Category: documentation, dated 2026-09-18, not account-verified.
- Expected attempt cost at list prices is far below the $3 reservation: the frozen prompt plus MCP tool schemas and fixture outputs is on the order of 10⁴–10⁵ input tokens and ≤10⁴ output tokens (≤ ~$0.75 worst shape). The reservation holds regardless.
- The mediated endpoint now captures per-request `model` and `usage` (input/output tokens) into operator-only receipts (prototype `ade42e7`), giving per-attempt usage evidence independent of the client estimate.

## To verify (user, with account context)

1. **API-billed account access**: confirm you hold an Anthropic API-billed account (console.anthropic.com) distinct from the subscription, and can mint a key for the demo. Do NOT create the key yet — key creation happens at execution time under the card.
2. **Current account rates**: on the console's pricing/billing page, confirm the effective per-MTok input/output rates for `claude-opus-5` for your account, and record them with date + page URL. If they differ from the documented $5/$25, the card's estimate note is updated; the $3 reservation is unaffected unless rates are >4× documented.
3. **Billing visibility and lag**: confirm the console shows per-request or daily usage/cost, and note the observed reporting lag (e.g., from any prior usage). ADR 0013 holds further dispatch if lag prevents a defensible remaining-budget calculation; knowing the lag beforehand is the point of this step.
4. **Provider limits**: note the account's spend limits/usage caps (monthly limit, any per-key limits) and confirm a $3 reservation fits without raising anything. No purchase, no top-up, no limit change.

## Reservation record format (fill at execution time)

```json
{
  "reservation_id": "stage-b-attempt-1",
  "amount_usd": 3.00,
  "envelope": "diagnostics $30 / weekly $150 (America/New_York)",
  "attempt_number_in_envelope": 1,
  "reserved_at": "<timestamp>",
  "reserved_by": "<operator>",
  "key_fingerprint": "<last-4 of execution-time key, never the key>",
  "released_or_reconciled_at": "<timestamp or pending>",
  "provider_actual_usd": "<from console, or unknown>",
  "client_estimate_usd": "<from claude JSON result>",
  "endpoint_usage": {"input_tokens": null, "output_tokens": null}
}
```

## When done

Tell the orchestrator the four verification outcomes (plain language is fine). They are recorded in the card's evidence section, and the only remaining gate is your explicit authorization of the Stage B experiment card.
