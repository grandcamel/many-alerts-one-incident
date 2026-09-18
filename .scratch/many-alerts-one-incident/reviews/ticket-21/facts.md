# Ticket 21 facts (offline, 2026-09-18)

Current checkout is `main` at `9dba6d3`; the timing artifact is
`prototype/run-timing` at `79a14c8`.

- **Current exit/result classification is insufficient.** `RunSpawner` streams and formats stdout,
  then returns only the process exit status (`main:grafana_jsm_sandbox/run_spawner.py:143-160`).
  `Receiver` logs that status but does not inspect a parsed result
  (`main:grafana_jsm_sandbox/receiver.py:109-122`).
  The formatter's final line uses only `subtype`, duration, turns, and cost
  (`main:grafana_jsm_sandbox/log_formatter.py:199-216`); it does not render result-level `is_error` or
  `terminal_reason`. Thus a result with `subtype: success` and `is_error: true` has no current
  distinct audience classification.

- **Historical false success is directly recorded, but its underlying Transcript is not committed.**
  The prototype says `runs/` Transcripts are git-ignored
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:3-5`). Its published measurement records the Fable arm as `subtype:
  success`, exit 0, zero cost/tokens, and `is_error: true`, `terminal_reason: api_error`, with the
  result “You're out of usage credits” (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:116-122`).
  This supports the historical classification failure, not a fresh Claude behavior claim.

- **Long-command refusal is historical and bounded.** The same artifact says ordinary `dontAsk`
  denial occurred for one-line ADF creates; largest accepted was 9,417 characters and smallest denied
  11,313, while the exact threshold was not measured
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:57-81`). It documents bad recovery outcomes, including two retries and a junk Incident
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:85-99`).

- **Timeout attempts process-group kill; tests cover queue continuation.** Current spawn starts a new
  session (`main:grafana_jsm_sandbox/run_spawner.py:123-137`); its timer calls `killpg(..., SIGKILL)` with a direct
  kill fallback (`main:grafana_jsm_sandbox/run_spawner.py:202-217`). Focused tests assert the timeout log/nonzero exit, child termination,
  and two queued notifications finishing (`main:tests/test_run_spawner.py:286-322`). Receiver executes
  queue entries serially and catches spawner exceptions so later entries continue
  (`main:grafana_jsm_sandbox/receiver.py:102-122`). The timer returns without signalling when the
  parent has already exited (`main:grafana_jsm_sandbox/run_spawner.py:209-212`), so these tests do
  not establish a whole-tree bound for an exited parent whose descendants retain stdout.

- **Refusal display exists only for tool permission events.** A `permission_denied` system event is
  visibly rendered `[DENIED]` (`main:grafana_jsm_sandbox/log_formatter.py:152-157`), covered by
  `main:tests/test_log_formatter.py:170-188`. There is no equivalent result-level API-refusal display.

- **SIGINT is documentation-only here.** The timing prototype contains no SIGINT/SIGTERM measurement
  (`79a14c8:prototype/run-timing/results/measurements-2026-09.md:1-154`). The repository research
  attributes “SIGINT yields a result line; SIGTERM does not” to headless documentation
  (`main:docs/research/model-and-effort-on-a-headless-run-2026-09.md:187-191`); current code instead
  sends SIGKILL. No fresh Claude/skill claim was made.
