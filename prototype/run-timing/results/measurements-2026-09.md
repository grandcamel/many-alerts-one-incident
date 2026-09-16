# What the four arms measured, 2026-09-15

PROTOTYPE result. One Run per arm, so every number here is n=1 on a shared API: treat the
gaps as signals, not as measurements. `runs/` holds the Transcripts and is git-ignored,
because they carry local paths.

## The arms

Same fixture for all of them: one Notification carrying seven Alerts from
`recommendationCacheFailure`, the same canned telemetry, a fresh Jira with no open
Incident, the draft skill at `skill/incident-report/SKILL.md`, `--safe-mode`,
`dontAsk`, and the allow list `Bash(eyes *)`, `Bash(jira-as *)`, `Read`.

| Arm | Model | Effort | Wall | Turns | Eyes | Hands | Cost | Output tok | Thinking tok | Outcome |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| smoke-haiku | Haiku 4.5 | high (default) | **73.6 s** | 10 | 4 | 3 | $0.1462 | 6,283 | 2,431 | finished, Report filed |
| opus5-high | Opus 5 | high (default) | **370.3 s** | 26 | 14 | 9 | $1.8582 | 32,484 | 13,418 | finished, Report filed |
| opus5-medium | Opus 5 | medium | **624.6 s** | 25 | 14 | 7 | $2.7403 | 76,669 | 1,441 | finished, Report filed |
| opus5-xhigh | Opus 5 | xhigh | **900.0 s, killed** | — | 14 | 6 | — | — | — | killed by the outer guard, nothing filed |
| fable51-high | Fable 5.1 | high (default) | 5.6 s | 1 | 0 | 0 | $0.0000 | 0 | 0 | **never ran — rate limited** |

Effort was set with `--effort`; `high` is the default, so the two default arms carry no
flag. Cost, turns and tokens come from the `result` line of the Transcript; wall time is
measured around the process by `measure.py`.

## How good each Report was

Graded against `fixtures/ground-truth.md`. The pass mark is naming the
`recommendationCache` flag flip as the cause.

| Arm | Grade | Flag | Both traces | `cache_hit` | Rules out the deploy | Host CPU as consequence | Fingerprints | Report words |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| smoke-haiku | **pass** | yes | cause only | no | never mentions it | yes | 7/7 | 445 |
| opus5-high | **pass** | yes | both | yes | yes, in words | yes | 7/7 | 899 |
| opus5-medium | **pass** | yes | both | yes | yes, in words | yes | 7/7 | 731 |
| opus5-xhigh | **fail** | — | — | — | — | — | 0/7 | 0 |
| fable51-high | **no result** | — | — | — | — | — | 0/7 | 0 |

The three that finished all reached the Ground truth and all cited what they retrieved.
The quality gap between them is in the corroboration, not the verdict: both Opus arms
fetched the pre-flip baseline trace and compared it against the failing one, which is
the actual proof, and both ruled the payment deploy out in words rather than by silence.
Haiku named the flag from the Change annotation and the logs without ever fetching the
baseline trace — right answer, thinner case.

One factual slip worth recording: `opus5-high` wrote "54 minutes before the first
symptom" for an interval that is 52 minutes. `opus5-medium` got it right. Neither
changed the conclusion, but a Report that does arithmetic on screen will be read closely.

## The allow list denies a long command

This was not the question and is the most useful thing the prototype found. Under
`dontAsk` with `Bash(jira-as *)` allowed, a `jira-as issue create` carrying the Report as
one line of ADF is **denied once it gets long enough**, with the ordinary don't-ask
denial message and no explanation.

| Length (chars) | Verdict | Arm |
| ---: | --- | --- |
| 92 | accepted | opus5-medium |
| 7,466 | accepted | smoke-haiku |
| 9,337 | accepted | opus5-high |
| 9,417 | accepted | opus5-medium |
| 11,313 | denied | opus5-medium |
| 12,930 | denied | opus5-high |
| 13,844 | denied | opus5-xhigh |
| 13,918 | denied | opus5-xhigh |
| 14,369 | denied | opus5-high |

**Largest accepted 9,417; smallest denied 11,313.** It is length, not content: the xhigh
arm's second attempt removed the only shell metacharacter in the first (a `;`) and was
denied at almost the same length, and none of the denied commands contained a newline, a
`\` continuation, a `$'...'` form or a substitution. The exact threshold is not pinned —
`probe/` holds a ready-made five-point probe that was never run, because the account ran
out of credits first.

### What a denied Report costs

The three arms that hit it reacted differently, and none of them reacted well:

- **opus5-high** was denied twice, shortened the Report to 9,337 characters on the third
  attempt, and filed it. Cost: three turns and two wasted ADF serializations.
- **opus5-medium** was denied once, then **created a junk Incident to test the boundary**
  — `jira-as issue create -p OPS -t Incident -s 'test of change #412 handling' --labels
  'fp-test'` — before filing the real one. Against a real OPS project that junk Incident
  lands in the live queue, which is exactly what ADR 0006 says a Run must not do.
- **opus5-xhigh** never recovered. It had finished a genuinely thorough investigation —
  fourteen `eyes` calls, both traces, the controls and both red herrings — and then spent
  every remaining second of its fifteen minutes probing the permission boundary. Its last
  words were "so it's likely command length. Let me probe the boundary with read-only
  calls instead of more creates." Nothing was filed. From the outside this is a Run that
  investigated perfectly and produced nothing.

## Two traps in the harness, not the model

- **A rate-limited Run reports success.** The Fable arm's `result` line says
  `"subtype": "success"` with `total_cost_usd: 0`, `num_turns: 1` and zero tokens. The
  only honest fields are `terminal_reason: "api_error"` and a `rate_limit_event` line
  carrying `"status": "rejected"` and `"overageDisabledReason": "out_of_credits"`. A
  Receiver that trusts `subtype` alone will record a Run that never happened as a Run
  that worked.
- **`--safe-mode` does not shrink the advertised tool list.** The `init` line of every arm
  advertises twenty-nine tools — Task, Write, Edit, WebFetch and the rest — while
  `--allowedTools` names three. `dontAsk` denies the others at call time, so the boundary
  holds, but the Run is told it has tools it may not use, and the system prompt's "your
  tools are exactly these" is contradicted by the harness in the same context window.

## What this cost, and what it stopped

The three arms that produced a result line cost **$4.74** between them ($0.1462 +
$1.8582 + $2.7403). The xhigh arm's spend is **unrecorded**: it was killed before it
wrote a result line, and fifteen minutes of Opus 5 is not free, so the true total is
higher than $4.74 by an unknown amount. That is itself a finding — a Run killed on a
wall-clock guard takes its cost accounting with it. All five arms together took about
33 minutes of wall time. They also carried the account from 75% to over 100%
of its seven-day allowance: the Fable arm was rejected with `out_of_credits`, and no
further Run can start until the window resets at **2026-09-19 19:00 local**. The Fable
comparison and the length probe are unfinished for that reason, not because they were
judged unnecessary.
