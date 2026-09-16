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
| Haiku 4.5, high | **73.6 s** | 10 | $0.1462 | 445 words | pass |
| Opus 5, high (default) | **370.3 s** | 26 | $1.8582 | 899 words | pass |
| Opus 5, medium | **624.6 s** | 25 | $2.7403 | 731 words | pass |
| Opus 5, xhigh | **900 s, killed** | — | unrecorded | none | fail |
| Fable 5.1, high | 5.6 s | 1 | $0 | none | never ran, rate limited |

- **`xhigh` is out.** It investigated better than any other arm — fourteen `eyes` calls,
  both traces, the controls, both red herrings — then hit a denial, spent the rest of the
  slot probing the permission boundary, and was killed with nothing filed. A Run that
  reasons perfectly and produces nothing is the worst outcome on a stage.
- **Lower effort did not buy speed.** `medium` was *slower and dearer* than default
  `high` (624 s / $2.74 against 370 s / $1.86), with a tenth of the thinking tokens and
  more than twice the output tokens. The assumption that dialling effort down shortens a
  Run is not supported here; on this sample it inverted.
- **Haiku 4.5 fits the slot and passes.** 73.6 s, $0.15, a correct Report that names the
  flag, cites the Change and the failing trace, and calls host CPU a consequence. Its
  case is thinner: it never fetched the pre-flip baseline trace, which is the actual
  proof, and it never mentions the payment deploy at all, so it rules the red herring out
  by silence rather than in words. Both Opus arms did both.
- **Fable 5.1 is unmeasured.** Its arm was rejected before its first turn: the four arms
  carried the account past its seven-day allowance and the Run came back
  `out_of_credits`. It can be run after **2026-09-19 19:00 local**.

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

- **A rate-limited Run reports success.** The Fable arm's result line says
  `"subtype": "success"`, `total_cost_usd: 0`, `num_turns: 1`. Only `terminal_reason:
  "api_error"` and a `rate_limit_event` carrying `"status": "rejected"` tell the truth. A
  Receiver trusting `subtype` will log a Run that never happened as one that worked.
- **A Run killed on a wall-clock guard takes its cost accounting with it.** The xhigh arm
  wrote no result line, so fifteen minutes of Opus 5 is unaccounted. The three arms that
  finished cost $4.74 together; the real total is higher by an unknown amount.

Also: `--safe-mode` is what makes a laptop Run resemble the container (no user `CLAUDE.md`,
no plugins, skills, hooks or MCP, auth still working), but it does **not** shrink the
advertised tool list — every arm's `init` line offers twenty-nine tools while the allow
list names three. `dontAsk` holds the boundary, but the Run is told it has tools it may
not use.

What this settles for the map: the slot budget for a Run is **about two minutes at Haiku
4.5 or about six at Opus 5**, not five at Opus 5; "fit-to-slot" now has numbers behind it
and the model choice is a real trade of about ninety seconds and $1.70 against a thicker
evidential case. The Report has a hard ceiling of roughly 9,000 characters per `jira-as`
command, which is a constraint on "The Report" rather than a free choice. Three questions
graduated out of this: what a Run does when Hands refuses, what a demo actually costs
against a seven-day allowance, and finishing the Fable arm.

Could not verify: Fable 5.1's time, cost or Report quality; the exact denial threshold
between 9,417 and 11,313 characters (`prototype/run-timing/probe/` holds a ready five-point
probe that never ran); whether `--max-budget-usd` terminates a Run on this auth, since no
arm reached its $3 cap; per-turn latency against a real Grafana rather than canned files;
and whether a second Run against an existing Incident is faster, which nothing here tested.
