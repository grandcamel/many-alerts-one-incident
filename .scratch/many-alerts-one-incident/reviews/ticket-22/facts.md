# Ticket 22 facts (offline, 2026-09-18)

Historical sources only: timing prototype commit `79a14c8` and the unchanged research files now on `main` at
`6f53e17`. No account, price, CLI, or model availability was refreshed.

- **The $4.74 is a reported-estimate subtotal, not billed spend.** The three arms with result lines report
  $0.1462 + $1.8582 + $2.7403 = $4.7447 (rounded to $4.74); xhigh was killed without a result, so
  its spend is unrecorded and the total cannot be established from these records
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:14-24,129-135`). All five arms
  took about 33 minutes of process wall time (`:135-136`). The artifact itself says its costs,
  turns and tokens are Transcript-result values, not a billing receipt (`:22-24`).

- **The research separately labels the estimate non-authoritative.** It records that the SDK compares
  budget against a client-side estimate from a bundled price table, and that a recorded OAuth run had
  `costBasis: list`; on a subscription that is a spend proxy rather than a bill
  (`main:docs/research/model-and-effort-on-a-headless-run-2026-09.md:178-185`). Consequently neither
  the $4.74 sum nor projected per-Run dollars establishes an invoice or allowance debit.

- **Fable refusal is one historical observed model result, not proof of independent balances.** The
  Fable arm has one turn, zero reported cost/tokens, and “never ran — rate limited”
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:14-24`). The published account snapshot recorded
  `seven_day` 0.76, `seven_day_overage_included` 1.01, `out_of_credits`, and subsequent Opus/Haiku
  runs while Fable alone was refused
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:129-144`). This establishes differential observed
  availability at that moment; it does **not** establish an independent per-model credit balance or
  predict current availability.

- **`--max-budget-usd` behavior was not tested.** Ticket 11 says no arm reached its $3 cap
  (`main:.scratch/many-alerts-one-incident/issues/11-does-a-high-effort-run-fit-the-slot.md:108-114`).
  The historical research also says no live `-p` Run was started with that flag and leaves OAuth/API-
  key equivalence unverified (`main:docs/research/model-and-effort-on-a-headless-run-2026-09.md:292-303`).

- **The “8% of the cost” comparison is a quality-limited historical ratio.** Haiku’s $0.1462 is about
  7.9% of the $1.8582 Opus-high result, but it made four Eyes calls versus fourteen and asserted
  healthy `payment`/`ad` services it never queried; the prototype calls that fabricated control
  disqualifying under the citation rule
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:16-18,33-51`). It is
  not evidence that a cheaper model is acceptable for the demo.
