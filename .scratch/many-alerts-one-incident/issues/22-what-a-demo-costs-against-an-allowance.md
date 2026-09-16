# What a demo costs against an allowance

Type: grilling
Status: open
Blocked by: none

## Question

Graduated from the map's fog once the timing prototype put numbers on a Run.

A rehearsal of five Runs cost $4.74 by the Transcripts' own accounting, took 33 minutes,
and carried the account from 75% to over 100% of its seven-day allowance — after which
no Run could start at all until the window reset four days later. So the binding
constraint on rehearsal is not dollars, it is the allowance, and that is a fact about how
many times this demo can be practised in the week before it is given.

What is the billing basis for the demo: an API key at list price ($5/$25 per million for
Opus 5, $10/$50 for Fable 5.1) or OAuth against a subscription with a seven-day window?
The two behave differently under load and only one has a number a slide can carry.
What does one full demo cost, what does a rehearsal week cost, and how many Runs is the
budget — in allowance, not in money? What does the answer do to the model choice, given
that Haiku 4.5 did the same job for eight percent of the Opus 5 cost?

Also decide the guard: `--max-budget-usd` is accepted by the CLI but no arm reached its
cap, so whether it terminates a Run on this auth is untested ("Which model, at what
effort, on a headless Run" left the same gap).
