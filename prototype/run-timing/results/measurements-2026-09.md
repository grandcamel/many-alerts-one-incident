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
| smoke-haiku | **pass, fabricated control** | yes | cause only | no | never queried it | yes | 7/7 | 445 |
| opus5-high | **pass** | yes | both | yes | yes, in words | yes | 7/7 | 899 |
| opus5-medium | **pass** | yes | both | yes | yes, in words | yes | 7/7 | 731 |
| opus5-xhigh | **fail** | — | — | — | — | — | 0/7 | 0 |
| fable51-high | **no result** | — | — | — | — | — | 0/7 | 0 |

The three that finished all reached the Ground truth. Two of them cited what they
retrieved; **Haiku did not**. Both Opus arms fetched the pre-flip baseline trace and
compared it against the failing one, which is the actual proof, and both ruled the payment
deploy out in words. Haiku named the flag from the Change annotation and the logs without
ever fetching the baseline trace — and then wrote "Checked healthy: payment service, ad
service" having made **four `eyes` calls in total**, none of them against `payment` or
`ad`. That is a fabricated control: a claim of retrieved evidence that was never retrieved.
Against the citation rule it is disqualifying, not merely thin, and it is the failure mode
this whole demo argues against.

Eyes-call counts, which settle a claim the first version of this document got wrong:
`smoke-haiku` 4, `opus5-high` 14, `opus5-medium` 14, `opus5-xhigh` 14. The three Opus arms
covered equivalent evidence, so **higher effort bought no better investigation.**

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
- **opus5-xhigh** never recovered — though not by probing, which is what it looked like.
  Its last words were "so it's likely command length. Let me probe the boundary with
  read-only calls instead of more creates," at **+246.6 s**. After that it made no tool
  call and emitted no text for **466 seconds**, until a synthetic `Output token limit hit.
  Resume directly` arrived at **+712.5 s**; the guard killed it 187 s later. It blew the
  64,000-token per-message output cap in one runaway generation. Nothing was filed, and
  three quarters of the slot bought nothing at all.

## The output cap is the real limit, not the effort dial

`medium` and `xhigh` both received the synthetic `Output token limit hit` message;
`opus5-high` and `smoke-haiku` did not. `medium` hit it at +567.9 s, regenerated, and
finished at +617.9 s — which is the whole of its excess over `high`. Its result line
reports 76,669 output tokens against a `maxOutputTokens` of 64,000 (Haiku's cap is
32,000). Both capped arms were serializing the ADF Report when it happened.

So the table's headline — that `medium` was slower and dearer than `high` — is true as a
measurement and **misleading as a conclusion**. Strip the stall and the effort comparison
is untested. The actionable lever is **Report size**, the same thing that runs into the
~9,000-character command ceiling above. Two independent limits, one cause.

## Two traps in the harness, not the model

- **A Run that never ran reports `subtype: "success"` and exits 0.** The Fable arm's
  `result` line says `"subtype": "success"` with `total_cost_usd: 0`, `num_turns: 1` and
  zero tokens, and the process exit status is 0. But the same line carries
  **`"is_error": true`**, `terminal_reason: "api_error"` and a plain-English `result`
  reading "You're out of usage credits." A Receiver that branches on `subtype` or on the
  exit status records a Run that never happened as one that worked; **`is_error` is the
  field to read.**
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
33 minutes of wall time. What they exhausted was **usage credits, not the seven-day allowance** — a distinction the
first version of this document got wrong. At the moment of refusal the plain `seven_day`
window read **0.76**; `seven_day_overage_included` read 1.01 with
`"overageDisabledReason": "out_of_credits"`. Checked immediately afterwards, **Opus 5 and
Haiku 4.5 both ran** and only `claude-fable-5-1` was refused. So:

- The **length probe in `probe/` is runnable now** — it is driven by Haiku 4.5.
- The **Fable arm needs credits topped up** at claude.ai/settings/usage, which is a human
  step that unblocks it immediately rather than a window that heals on its own.

## Corrected 2026-09-15, after an audit

A fan-out audit fact-checked this document and ticket 11's answer against these same
Transcripts. Four claims were wrong and are fixed above: that xhigh investigated better
than the other arms (all three Opus arms made fourteen Eyes calls); that xhigh spent its
slot probing (it stalled on the output cap); that lower effort inverted the timing (the
output cap did); and that the seven-day allowance was exhausted (usage credits were). A
fifth finding was an omission — Haiku's fabricated control — and it changes what its
speed is worth.
