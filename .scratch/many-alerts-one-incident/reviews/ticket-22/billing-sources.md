# Ticket 22 — official billing documentation check, 2026-09-18

This is a public documentation check, not an account/balance check, current model-price quotation, or CLI enforcement test.

- [API billing](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage), retrieved lines 471–479 and 490–510: most Console organizations use prepaid credits; some have invoicing arrangements. Billing/usage is shown in Console. A client disconnect/timeout can still incur a charge for a request that otherwise succeeds. This supports separating cancellation from billing finality.
- [Subscription versus Console](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console), lines 471–479: Console/API and paid chat plans are separate products/billing setups. This is not proof of the user's particular billing arrangement.
- [Agent SDK on a Claude plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan), lines 470–474: the June 15 update pauses the previously announced programmatic-usage changes and says subscription limits still apply. The content below that update is explicitly preserved historical text, not the effective new plan. Do not infer the user's allowance from its obsolete credit table or from a historical model refusal.

No purchase, auto-reload change, API key creation, authentication switch or paid request occurred. Exact applicable rates, permissions, balances and enforcement must be verified for the selected account before any future execution.
