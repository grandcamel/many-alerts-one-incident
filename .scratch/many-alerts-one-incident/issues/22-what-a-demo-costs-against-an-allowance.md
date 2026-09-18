# What a demo costs against an allowance

Type: grilling
Status: resolved
Blocked by: none

## Question

Graduated from the map's fog once the timing prototype put numbers on a Run.

A rehearsal of five Runs cost $4.74 by the Transcripts' own accounting and took 33
minutes. It also exhausted the account's **usage credits** — and that is a different
constraint from the one it first appeared to be. At the moment of refusal the plain
`seven_day` window read 0.76 while `seven_day_overage_included` read 1.01, with
`overageDisabledReason: "out_of_credits"`. Checked immediately afterwards, Opus 5 and
Haiku 4.5 both ran; only Fable 5.1 was refused. So the binding constraint is a
**per-model credit balance**, topped up at claude.ai/settings/usage, not a weekly window
that heals on its own — and it can take one model away while leaving others working.

What is the billing basis for the demo: an API key at list price ($5/$25 per million for
Opus 5, $10/$50 for Fable 5.1) or OAuth against a subscription with a seven-day window?
The two behave differently under load and only one has a number a slide can carry.
What does one full demo cost, what does a rehearsal week cost, and how many Runs is the
budget — in allowance, not in money? What does the answer do to the model choice, given
that Haiku 4.5 reached the same root cause for eight percent of the Opus 5 cost — but got there
by making four Eyes calls instead of fourteen and then asserting a control it never checked, so
the cheap option bought its speed against the citation rule?

Also decide the guard: `--max-budget-usd` is accepted by the CLI but no arm reached its
cap, so whether it terminates a Run on this auth is untested ("Which model, at what
effort, on a headless Run" left the same gap).

## Work in progress

Claimed after ticket 21 was committed. Offline historical-evidence review and billing/budget policy decisions only; no account probe, paid Run, API-key change, top-up or model availability assumption. Current Codex account limits are not Claude demo allowance evidence.

## Evidence correction before decisions

[Historical fact check](../reviews/ticket-22/facts.md): $4.7447 is the subtotal of three reported estimates, with killed-Run spend unknown, not the billed cost of all five attempts. Differential model availability does not prove independent per-model credit balances. CLI dollar-cap termination was not tested. [Official billing documentation](../reviews/ticket-22/billing-sources.md) was checked separately without inspecting or changing this account.

The human accepted all four recommendations in the first [decision round](../reviews/ticket-22/round-1.md): dedicated metered API billing, explicit cost-evidence categories, a bounded rehearsal envelope and evidence-qualified model selection. No paid execution or credential change is authorized. The second [decision round](../reviews/ticket-22/round-2.md) records numeric budgets, enforcement, credential custody and qualification evidence; the human accepted all four recommendations with “Agree.”

## Answer

Both decision rounds are accepted in [ADR 0013](../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md). Dedicated metered API billing; $150 weekly planning envelope split into three $30 rehearsals, one $30 presentation and $30 diagnostics/retries; $3 reserved per attempt and ten-attempt allocation limits. Durable reservations and attributed provider billing gate admission, with unknown exposure held and no automatic top-up. These are not proven hard provider charge caps.

The Anthropic credential exception is superseded by a fifth mediated endpoint. Three representative complete Fault lifecycle samples, cited evidence and the 300-second Run bound qualify a candidate; historical cheaper/fabricated or incomplete arms do not. Until qualification and enforcement pass, use labelled replay. Cloud spend is separate.

The opening question's $4.74 total-bill and per-model-balance claims are refuted by the linked facts; no current price, account balance, available model or CLI enforcement was established. Tickets 36/37 consume the new boundaries and [ticket 38](38-budget-accounting-and-model-qualification.md) specifies accounting/qualification acceptance. Planning is resolved; implementation, paid execution and live acceptance remain unperformed and unauthorized.
