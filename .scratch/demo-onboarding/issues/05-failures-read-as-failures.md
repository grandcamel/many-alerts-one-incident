# Failures read as failures

Type: task
Status: resolved
Blocked by: 03

See [spec.md](../spec.md), step 05.

## Answer

What changed:

- **Formatter (`log_formatter.py`).** A result with `is_error: true`, or a subtype starting
  `error_`, renders as `[FAILED] <terminal_reason or subtype>: <first line of the result text>`
  (else the first of `errors`, else "no result text"). A `[hint]` line follows for the five known
  causes: the Claude token, usage credits, a rate limit, the model, the budget. The hint reads the
  subtype, `api_error_status` and the words of the result, words first, because the recorded
  credit refusal has `api_error_status` null. `system/api_retry` renders as `[retry]`;
  `rate_limit_event` renders as `[limit]` only when its status is not `allowed`. The public
  `run_failure(event)` gives the spawner the same text, redacted, so `[FAILED]` and the Receiver's
  reason always agree.
- **Receiver (`receiver.py`).** New `RunOutcome(exit_status, failure)`; a spawner may still
  return a bare exit status, and any nonzero status is a reason. After "finished with exit
  status" a failed Run logs `run <id> FAILED: <reason>` at ERROR; a spawner exception logs
  `run <id> FAILED after ...: the spawner raised`. Each accepted Notification logs
  `notification accepted: N alert(s), run <id> queued, K ahead`. Each rejected POST logs at
  WARNING with its reason and client address; a path it names is logged with `%r`, so a control
  character never reaches a projected terminal raw.
- **Spawner (`run_spawner.py`).** Tees the raw stream-json, line-buffered, to
  `<run dir>/transcript.jsonl` and logs that path. The outcome's reason is, in order: the
  timeout, the result's failure, a nonzero exit, "the Transcript ended without a result". A
  transcript that cannot be opened or written costs one warning and the copy, never the Run.
  Transcript lines log at ERROR for `[FAILED]` and WARNING for `[hint]`, `[DENIED]`, `[retry]`
  and `[limit]` (a little beyond the spec, so a warnings-only filter still shows why).
- **Forwarder (`forwarder.py`).** Upstream 4xx/5xx log at WARNING; `diagnose()` adds a likely
  meaning for 401, 403 and 404. A 403 whose body reads like an IP-allowlist refusal gets its own
  diagnosis. The body is only searched, never logged: the first 4 KB, with gzip or deflate
  (zlib-wrapped or raw) undone by stdlib `zlib`, capped at that length. A Run's own
  Accept-Encoding goes upstream and jira-as's `requests` client asks for gzip and deflate, so
  this matters (review should-fix). A 403 whose body cannot be read (another coding, or one that
  does not inflate) names both likely causes rather than only the permission.
- **Logging (`__main__.py`).** `%(asctime)s %(levelname)-7s %(message)s`, to the second. Only
  the Receiver's format changed; the `replay` and stand-alone `forwarder` CLIs still print bare
  messages to a person's terminal.
- **Skill.** After the create step: do not retry a failed create with other fields, never
  create an Incident to probe, finish that Alert as `failed` with jira-as's error. The Finish
  list now allows that ending and says it names no Incident key (review should-fix: the two
  instructions conflicted).
- **Fixture.** `fixtures/run-transcript-refused.jsonl`: init, Claude Code's synthetic assistant
  message and the result, with the recorded facts (`subtype: success`, `is_error: true`,
  `terminal_reason: api_error`, `api_error_status` null, zero cost, one turn, exit 0). Ids are
  made up; no token or account data.
- **Docs.** README (Receiver and Forwarder log lines, the `[FAILED]`/`[hint]`/`[retry]`/`[limit]`
  rendering, a refused-Run sample, the tee, fetching a Transcript), `docs/demo-runbook.md` (log
  window, T+1:10 row, what a failed Run looks like), an ADR 0003 amendment (the kept Transcript
  sits inside the existing Read scope, raw by design), and the `CONTEXT.md` Transcript entry.
  The runs directory is a tmpfs, emptied when the demo container stops as well as when it is
  recreated; README, runbook and the `TRANSCRIPT_FILENAME` docstring say so and tell the reader to
  copy a Transcript out before a restart (review should-fix).

Review fixes beyond the four should-fixes: the `[hint]` guard now ignores an `errors` field that
is not a list (it could cost the `[FAILED]` line), the token hint no longer fires on a bare
"authentication" that may be Jira's (it needs `authentication_error` or a 401), the rate-limit
hint also matches Claude Code's subscription-limit wording ("usage limit", "hit your limit",
"limit reached"), `LOG_FORMAT` and `LOG_TIME_FORMAT` each carry their own docstring, the killed-Run
tee test waits 3 s rather than 0.5 s, and `DIAGNOSES` says it names `.env` because the Receiver
reads its credential there.

Test evidence (all from the worktree):

- Focused: `tests/test_log_formatter.py` 108 passed; `tests/test_receiver.py` 22 passed (five runs
  in a row, no stray server tracebacks); `tests/test_forwarder.py` with
  `tests/test_skill_template.py` 74 passed.
- Full suite (`python3 -m pytest -q -p no:cacheprovider`): 3725 passed, 40 skipped in 175 s.
- Python 3.11 basic-demo subset (the 15 listed files; no new test files): 466 passed, 40 skipped.
- `ruff check` and `ruff format --check` clean on every file this step touched.

Deferred or unverified:

- The refused-Run fixture is rebuilt from the owner's note, not recorded. The elided middle of
  the refusal text is filled with Claude Code's usual " · "; the assistant line's shape (model
  `<synthetic>`, zero usage) is inferred, and the SDK's assistant `error` field is left out.
- Hint triggers with no recorded evidence here: 401 for the token, 429 and the
  subscription-limit wordings for the rate limit, 404 and the "selected model ... may not exist"
  wording for the model. The `api_retry` fields and the `rate_limit_event` statuses come from the
  documented SDK shapes. The IP-allowlist 403 wording is the audit's and unverified live.
- A refused Run shows its refusal twice, once as Claude Code's synthetic `[claude]` message and
  again on `[FAILED]`; no marker for synthetic messages is guessed at.
- A Run that exits 0 with no result event now counts as FAILED, as the prototype's
  missing_terminal did.
- `HINT_CREDITS` and `HINT_MODEL` suggest running another model, which has no knob until step 06
  adds `RUN_MODEL`: step 06 should name `RUN_MODEL` in both hints.
- The kept `transcript.jsonl` is raw, readable by later Runs through the existing
  `Read(//<runs dir>/**)` rule, and not made read-only the way the Skill is; the ADR 0003
  amendment records this. The runs tmpfs is 64 MB; when full, teeing stops with a warning.
- Step 11's docs rewrite may rework the new README and runbook paragraphs.

No settings change is needed.
