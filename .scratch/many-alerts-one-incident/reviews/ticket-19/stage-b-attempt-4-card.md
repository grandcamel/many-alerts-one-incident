# Stage B attempt 4 — continuation card, 2026-09-19

Status: **local preflight passed; paid attempt NOT RUN.** The user directed continuation after the selector correction. Execution still needs a fresh execution-time key and a one-attempt accounting exception to the recorded P3 hold. No attempt-4 reservation has been made and no provider contact occurred during this preflight.

## Concrete attempt

Run the unchanged frozen prompt from the [original experiment card](stage-b-experiment-card.md) once against the corrected synthetic fixture. Prototype execution revision: `3375fdbac41e844266e4c1135748799b019ce924`, including the selector correction at `55677327b021d1445ac85d9b0ef42b9e1fdbc073`. The later commit only corrects two unavailable-billing labels in the output reservation record.

- Client: installed Claude Code **2.1.278**, verified by `claude --version` and `claude --help`. This differs from attempt 3's 2.1.272 and is a comparison limitation. Same explicit `claude-opus-5` model, default effort, print JSON, `--bare`, strict MCP config, allowed Grafana tools, `--permission-prompts none` and $3 client estimate guard as the existing launcher.
- mcp-grafana: pinned binary SHA-256 `d8cdb94e5e3154e1cf7b3ea850c83fd9309c222d96d99784187a57b76545334c`, reverified locally. Writes/API/usage statistics disabled as in the previous assembly.
- One attempt, diagnostics attempt **4/10**, $3 reservation before launch; 270-second work, 20-second flush and 10-second kill budgets. No automatic retry or fallback.
- Use detached supervisor launch (`start_new_session=True` or `os.setsid()`), closed stdin and private redirected logs; retain the proven mediated TLS path and dual-sentinel revocation.
- Supply a fresh key only from `~/.sb-exec-key`, regular file with mode 600, into the supervisor's launch environment without echoing it. Delete that file after the attempt and report deletion. Existing OAuth auth is not an alternative under this card.
- Keep evidence outside git at `~/maoi-stage-b-evidence/attempt-4/`, mode 700 directory and mode 600 files. Refuse an existing attempt-4 destination. Apply ADR 0014's sanitizer, 100 MiB/run and 2 GiB/30-day retention limits. The destination was absent and existing evidence occupied 104,771 bytes before this preflight was saved.

## Accounting decision required before launch

The [accounting disposition](stage-b-attempt-2-3-outcome.md#accounting-disposition--2026-09-19) records provider actuals as unknown for attempts 1–3, $9 of retained reservations and a P3 paid-dispatch hold. Available session estimates for attempts 1 and 3 total $1.4249; attempt 2 remains unknown.

The concrete exception requested is **one attempt 4 using session telemetry and endpoint token accounting as estimates, retaining the previous reservations and adding a new $3 reservation**. That makes $12 allocated in the $30 diagnostics envelope, not $12 of measured or maximum actual spend. No estimate becomes provider actuals, no old reservation is released, and the exception admits no subsequent attempt. The reservation is an admission allocation, not a hard provider billing ceiling. Write the reservation durably before launch; the launcher's embedded after-run record alone is insufficient for that ordering requirement.

## Local preflight evidence

The updated client drove the real pinned mcp-grafana binary through the mediated TLS endpoint with a mock model upstream. A temporary copy of the prototype used one declared runtime override: the rehearsal tool input was `{stream="change"}`. No real credential was used. This validates the current client/MCP transport for the corrected selector, not model-driven Q3 discovery.

- Completed in **3.107 s**, exit 0, child reaped; mock received a tool result.
- Backend receipt shows the single-label Change selector; all backend tokens matched, all four discovery probes returned 200.
- Both post-run sentinel probes returned **401**; sanitizer checked five credential values and found **zero matches**.
- Private evidence: `/Users/jasonkrueger/maoi-stage-b-evidence/preflight-attempt-4-2026-09-19/rehearsal.json`; SHA-256 `02766485c029006bbbe368cc2c4e2dd84692c410e4c680eef8c13cf6aa0f2c55`. Adjacent `manifest.json` records provenance. Original temporary source: `/tmp/maoi-attempt4-preflight-ea6k28s3/`.
- Full suite after the billing-label correction: `env -u DEMO_END_TO_END -u DEMO_CONTAINER python3 -m pytest -q` — **295 passed, 36 skipped**; `git diff --check` passed.

## Adjudication and boundaries

Judge Q1–Q4 against fixture ground truth and request receipts. In particular, Q3 must cite `change-stage-a`, `diagnostic=ready` and `rehearsal=current`; the launcher's heuristic phrase match is not enough. Record model claims, fixture limitations, client-version drift, timing, containment, sentinel probes and cost evidence categories separately. The equality-selector correction also changes unsupported expressions to explicit errors; time/direction/statistics limitations remain.

Attempt 3's verdict remains unchanged. Ticket 19 remains claimed and ticket 12 remains blocked. Real tenant, container/end-to-end, venue and publication remain NOT RUN. All continuation commits remain local.
