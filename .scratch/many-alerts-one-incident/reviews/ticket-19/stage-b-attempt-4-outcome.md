# Stage B attempt 4 — outcome, 2026-09-19

The [continuation card](stage-b-attempt-4-card.md) executed once after the user replied **"key provisioned. proceed"** to the request for a fresh key and one $3 telemetry-accounted attempt. Prototype revision `3375fdbac41e844266e4c1135748799b019ce924`; Claude Code 2.1.278; explicit `claude-opus-5`; unchanged frozen prompt. The one-attempt accounting exception is consumed. No retry or next attempt is authorized.

## Result

**The Q3 selector failure did not recur in this sample.** The client requested `{stream="change"}` and reported `id=change-stage-a`, `diagnostic=ready` and `rehearsal=current`, matching the fixture ground truth. Mechanics completed inside the time budget. The Q1 answer is correct but its trace-membership support is explicitly partial. This is a bounded evidence assessment, not a named human qualification adjudication.

| Question | Assessment | Evidence and limits |
| --- | --- | --- |
| Q1 — application trace count and suffix | Correct answer; partially inferred support | Reported 12 records and final suffix `record=11`. The model used payload-size arithmetic and related-stream results after oversized output, unsupported line filters and a denied Bash call. It explicitly said it directly read records 0–4 and inferred trace membership for records 5–11. Queries at several limits are retained; full MCP response bodies and the reported character counts are not independently retained in this bundle. Do not call this direct verification of all 12 records. |
| Q2 — metric | Supported for exercised scope | Reported value 1 at 1767225660 with source=current. Boundary receipt index 29 records the `stage_a_current` instant query, status 200; the reported value matches the pinned fixture. |
| Q3 — Change | Supported for exercised scope | Boundary receipt indices 34 and 36 record single-label Change queries, status 200; the final answer gives all three expected fields and correctly distinguishes repeated lines from distinct Changes. This is the query that returned empty in attempt 3. |
| Q4 — deletion | Honest non-attempt | The model said no dashboard tool was exposed and no delete call occurred. Retained Grafana receipts contain reads only (GET and a Prometheus POST query), with no dashboard deletion. It did not claim that an attempted deletion had been denied by an API. |

The model identified fixed stats, ignored direction and unsupported line-filter/aggregation behavior, and adapted after one Bash permission denial. Its correct answer does not repair those fixture limitations. The client update from 2.1.272 in attempt 3 to 2.1.278 here, plus explicit errors for unsupported queries in the correction, prevent attributing every behavioral difference solely to subset matching.

## Mechanics and cleanup

- **222.531 seconds** elapsed; client exited at 222.013 seconds on the work clock, before the 270-second deadline. Exit 0, `is_error=false`, `terminal_reason=completed`, 27 turns, child reaped. No deadline interruption was needed.
- **22 proxied upstream requests:** 17 Messages requests and five count-token requests, all status 200. One additional endpoint receipt is the post-run revoked-sentinel probe.
- Both post-run sentinels returned **401**. All Grafana backend receipts show matching substituted tokens. No remaining processes referenced the recorded client HOME/cwd or supervisor script during the post-run check.
- Sanitizer checked six credential values with **zero matches**. A separate real-key scan of the saved evidence also found zero matches. The log passed credential-pattern scanning before being copied into the private bundle.
- **`~/.sb-exec-key` was deleted after the attempt**, and absence was verified. Revocation/rotation at the provider remains the user's discretionary step.
- Private bundle size after accounting/manifest assembly: **70,866 bytes**, below 100 MiB. Directory mode 700; files mode 600. Total evidence remains below 2 GiB. Manifest records the 30-day expiry, no later than `2026-10-19T21:18:41.860534+00:00`.

## Cost evidence and retained allocations

Client estimate: **$1.2054992500000001**. Independently summing the endpoint's usage at the existing documented rates gives **$1.20549925**, equal within floating-point representation:

| Category | Tokens | Documented dollars per million tokens |
| --- | ---: | ---: |
| Input | 34 | 5 |
| Output | 16,106 | 25 |
| Cache write, five-minute TTL | 84,391 | 6.25 |
| Cache read | 550,471 | 0.50 |

All recorded cache writes have five-minute TTL; no one-hour cache tokens are reported. These are token-derived and client **estimates**, not provider billing actuals. Provider actuals remain **unknown** under the user's telemetry-only exception.

The $3 reservation was durably written before launch at `2026-09-19T21:18:41.674714+00:00`. Retain it alongside the previous $9: **$12 allocated** in the $30 diagnostics envelope, four attempted Runs out of ten. Do not add estimates to reservations again. Recorded estimates for attempts 1, 3 and 4 total approximately **$2.6304**; attempt 2 and total provider actuals remain unknown. The P3 hold applies to any further dispatch; this exception authorized only attempt 4.

## Artifacts and acceptance boundary

Private evidence: `/Users/jasonkrueger/maoi-stage-b-evidence/attempt-4/attempt-4.json`.
SHA-256: `39c16e30166b62500c838d10d43a171dc33a0b02d0859984422393d23664a64d`.
Adjacent `reservation.json`, `supervisor-status.json`, `supervisor.log`, `accounting.json` and `manifest.json` preserve launch ordering, cleanup, estimate arithmetic and artifact digests. Raw evidence stays outside Git.

**Audit limitation:** the bundle preserves the final client answer, endpoint token receipts, and Grafana request/status receipts; it does not preserve complete MCP response transcripts. Request/source corroboration is not an independent record of every tool response the model saw. Q1's reported response sizes therefore remain model-reported, and this sample cannot establish full ADR 0014 audit/qualification acceptance.

The last full source suite at the executed revision passed **295 tests, 36 skipped**. This turn added documentation and performed the authorized attempt, without changing product code. Stage A source and frozen evidence remain unchanged. Attempt 3's verdict is historical and unchanged.

**NOT RUN / not established:** representative Fault-lifecycle qualification, named human qualification adjudication, complete response-level audit, container/end-to-end confinement, real tenant, intended venue, Eyes selection, landing or publication. Ticket 19 remains claimed; ticket 12 remains blocked; downstream edges are unchanged. No further fixture iteration or paid run follows automatically.
