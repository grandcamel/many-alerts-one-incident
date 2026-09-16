# What a demo costs against an allowance

Type: grilling
Status: open
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
