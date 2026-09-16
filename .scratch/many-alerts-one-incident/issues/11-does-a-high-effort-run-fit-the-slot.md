# Does a high-effort Run fit the slot

Type: prototype
Status: resolved
Resolved: 2026-09-15
Blocked by: 04

## Question

Time a print-mode Run at Opus 5 on high effort against a canned Cascade: a Notification fixture carrying several Alerts, canned telemetry files standing in for Eyes, and the chapter-one Hands stubbed. Measure wall time, turns, tool calls and cost, and judge the Report it writes against the canned Fault's Ground truth. Repeat with Fable 5.1 and with a lower effort. The answer says whether a five-minute Run is realistic and what it costs. The throwaway lives on a `prototype/run-timing` branch.

## Answer

Measurements: `prototype/run-timing/results/measurements-2026-09.md` on branch
`prototype/run-timing` (the harness, the fixture and the Ground truth are on the same
branch; `runs/` with the raw Transcripts is git-ignored because it carries local paths).
One Run per arm, so every number is n=1 on a shared API — the gaps are signals, not
measurements.

**No. A five-minute Run is not realistic at Opus 5 on high effort.** It took **370 s**,
six minutes ten, against a seven-Alert Cascade with canned telemetry and stubbed Hands —
and that is the arm that *worked*. The slot assumption in the map's standing preferences
does not survive contact with a Cascade.

| Arm | Wall | Turns | Cost | Report | Grade |
| --- | ---: | ---: | ---: | ---: | --- |
| Haiku 4.5, high | **73.6 s** | 10 | $0.1462 | 445 words | pass, but fabricated a control |
| Opus 5, high (default) | **370.3 s** | 26 | $1.8582 | 899 words | pass |
| Opus 5, medium | **624.6 s** | 25 | $2.7403 | 731 words | pass |
| Opus 5, xhigh | **900 s, killed** | — | unrecorded | none | fail |
| Fable 5.1, high | 5.6 s | 1 | $0 | none | never ran, out of usage credits |

- **`xhigh` is out, and not for the reason it first looked.** It made fourteen `eyes`
  calls — exactly as many as `high` and `medium`, over the same evidence — so higher effort
  bought no better investigation. It hit two denials, probed the boundary four times, and
  fell silent after **+246.6 s**: no tool call and no text for **466 seconds**, until a
  synthetic `Output token limit hit. Resume directly` arrived at **+712.5 s**. The guard
  killed it at 900 s. The failure is one runaway generation that blew the 64,000-token
  per-message output cap, not boundary probing. A Run that investigates well and produces
  nothing is still the worst outcome on a stage, but the trap to design against is the cap.
- **The effort dial is not what made `medium` slow.** It came in at 624 s / $2.74 against
  `high` at 370 s / $1.86, but the cause is not effort: `medium` hit the same 64,000-token
  output cap at **+567.9 s** and had to regenerate before finishing at +617.9 s. `high`
  never hit it. Both capped arms were serializing the ADF Report when it happened, and
  `medium` reported 76,669 output tokens against that cap. **The lever is Report size, not
  the effort dial** — the opposite of what a first reading of these numbers suggests.
  Whether lower effort shortens a Run is still untested here.
- **Haiku 4.5 fits the slot, names the cause — and fabricated a control.** 73.6 s, $0.15,
  and it does name the flag, cite the Change and the failing trace, and call host CPU a
  consequence. But it made **four** `eyes` calls in total — changes, one recommendation
  metric query, one recommendation log query, one trace list — and never queried `payment`
  or `ad` at all, while its Report states "Checked healthy: payment service, ad service".
  That is an uncited claim presented as retrieved evidence, which is the exact failure this
  demo exists to disprove. It also never fetched the pre-flip baseline trace, the actual
  proof. Both Opus arms made fourteen `eyes` calls and did both properly. Haiku's grade is
  a pass on the root cause **with a fabricated evidence claim**, and against the map's
  citation rule that is disqualifying, not merely thin.
- **Fable 5.1 is unmeasured, and it is the only model blocked.** Its arm was rejected
  before its first turn with `overageDisabledReason: "out_of_credits"`. The block is
  **usage credits, not the seven-day allowance**: at the moment of rejection the plain
  `seven_day` window read **0.76** while `seven_day_overage_included` read 1.01. Checked
  directly after the audit, **Opus 5 and Haiku 4.5 both run right now**; only
  `claude-fable-5-1` is refused, with "You're out of usage credits ... manage usage credits
  at claude.ai/settings/usage". The remedy is topping up credits, not waiting for a window.

**The most useful finding was not the question asked.** Under `dontAsk` with
`Bash(jira-as *)` allowed, a `jira-as issue create` carrying the Report as one line of ADF
is **denied once it gets long enough**: largest accepted **9,417** characters, smallest
denied **11,313**, across nine creates in four arms. It is length, not content — the xhigh
arm removed the only metacharacter in its first attempt and was denied again at almost the
same length, and no denied command held a newline, a `\` continuation, a `$'...'` form or
a substitution. The denial arrives as the ordinary don't-ask message with no explanation,
so a Run cannot tell why. All three arms that hit it handled it badly, and one of them
**created a junk Incident to test the boundary** (`-s 'test of change #412 handling'`)
before filing the real one — in a live OPS project that lands in the queue, which is
exactly what ADR 0006 forbids.

Two harness traps worth carrying forward:

- **A Run that never ran reports `subtype: "success"` and exits 0.** The Fable arm's
  result line carries `"subtype": "success"`, `total_cost_usd: 0` and `num_turns: 1` — and
  also **`"is_error": true`**, `terminal_reason: "api_error"`, and a plain-English `result`
  reading "You're out of usage credits." The process exit status is 0. So a Receiver
  branching on `subtype` or on the exit status is fooled; one branching on **`is_error`**
  is not. `is_error` is the field to read.
- **A Run killed on a wall-clock guard takes its cost accounting with it.** The xhigh arm
  wrote no result line, so fifteen minutes of Opus 5 is unaccounted. The three arms that
  finished cost $4.74 together; the real total is higher by an unknown amount. Worse, most
  of that time bought nothing: it had already fallen silent at +246.6 s.

Also: `--safe-mode` is what makes a laptop Run resemble the container (no user `CLAUDE.md`,
no plugins, skills, hooks or MCP, auth still working), but it does **not** shrink the
advertised tool list — every arm's `init` line offers twenty-nine tools while the allow
list names three. `dontAsk` holds the boundary, but the Run is told it has tools it may
not use.

What this settles for the map: the slot budget for a Run is **about six minutes at Opus 5**,
not five, and "fit-to-slot" now has numbers behind it. Haiku 4.5's 73.6 s is not the bargain
it looks — it bought the time by making four `eyes` calls instead of fourteen and then
asserting a control it never checked, so the cheap arm failed the citation rule rather than
merely thinning its case. **Report size is the real lever on both the clock and the failure
modes**: it is what blew the 64,000-token output cap on the two arms that stalled, and it is
what runs into the roughly 9,000-character ceiling on a `jira-as` command. That makes "The
Report" the ticket this one most constrains. Three questions graduated out of this: what a
Run does when Hands refuses or never runs, what a demo costs against an allowance, and
finishing the Fable arm.

Could not verify: Fable 5.1's time, cost or Report quality, which needs usage credits; the
exact denial threshold between 9,417 and 11,313 characters (`prototype/run-timing/probe/`
holds a ready five-point probe — it is runnable now on Haiku 4.5, it simply was not run);
whether `--max-budget-usd` terminates a Run on this auth, since no arm reached its $3 cap;
whether lower effort shortens a Run once the output cap is out of the way; per-turn latency
against a real Grafana rather than canned files; and whether a second Run against an
existing Incident is faster, which nothing here tested.

## Corrected 2026-09-15, after an audit of this answer

A fan-out audit of the map fact-checked this answer against the raw Transcripts and found
four wrong claims, each since fixed above and each verified by hand before the fix:

1. **"`xhigh` investigated better than any other arm"** — false. `high`, `medium` and
   `xhigh` each made exactly fourteen `eyes` calls over equivalent evidence.
2. **"`xhigh` spent the rest of the slot probing the permission boundary"** — false. It
   went silent at +246.6 s and emitted nothing for 466 s until the output-cap message at
   +712.5 s. The failure was a runaway generation, not probing.
3. **"Lower effort did not buy speed ... on this sample it inverted"** — confounded.
   `medium` and `xhigh` both hit the 64,000-token output cap; `high` and Haiku did not.
   Report size, not the effort dial, explains the inversion.
4. **"the four arms carried the account past its seven-day allowance"** — wrong window.
   `seven_day` was at 0.76; `seven_day_overage_included` was at 1.01 and the reason was
   `out_of_credits`. Opus 5 and Haiku 4.5 were confirmed working immediately afterwards;
   only Fable 5.1 is refused.

A fifth finding was an omission rather than an error: Haiku's Report **fabricated a
control**, claiming two services healthy that it never queried. That is recorded above and
changes what its speed is worth.
