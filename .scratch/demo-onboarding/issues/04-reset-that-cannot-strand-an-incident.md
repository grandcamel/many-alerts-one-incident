# Reset that cannot strand an Incident

Type: task
Status: resolved
Blocked by: 02

See [spec.md](../spec.md), step 04.

## Answer

What changed, in `grafana_jsm_sandbox/reset.py`:

- **Read-back before Close.** `complete` moves a Run's Incident to Completed with resolution
  Done, then reads `issue get KEY --fields resolution`. A null resolution is not closed and is
  left with "completed without a resolution: ask your Jira admin to put Resolution on the
  Resolve screen" (`UNRESOLVED`).
- **The road back, not a delete hint.** Completed-and-unresolved has its own search
  (`UNRESOLVED_COMPLETED`), and `STUCK_INCIDENTS` now excludes `status = "Completed"`, so only
  the true dead ends (Canceled, or Closed with no resolution) get the delete hint. On the next
  run a Run's Completed-unresolved Incident is reopened (Completed to Open), resolved with Done,
  read back, and closed. It is left with `NO_ROAD_BACK` when there is no Reopen, and with
  `NOT_A_RUNS` (reopen and resolve it by hand) when it has no `fp-` label. Both searches are read
  before anything moves, so the Incident a run has just left on Completed is not reopened in that
  same run. (Review must-fix: before this, a rerun after the admin fix printed
  `deleteIssue ... --confirm` for a recoverable Incident.)
- **A failed Close means left.** A `RuntimeError`, or no Completed-to-Closed transition, leaves
  the Incident with `NOT_CLOSED` and its reason. The reset comment still goes first, because a
  Closed Incident may take no comment. On failure a second comment (`CLOSE_FAILED_COMMENT`) says
  the Close did not happen. That comment's own failure is ignored, since the report already says
  it. The Incident is resolved and so out of the queue: `Outcome.unclosed` records it,
  `queue_is_empty` does not count it, and the summary reads `queue is empty; N left for a human
  to close`. The exit is still 1 (`Outcome.finished`).
- **Paging.** `search` follows `nextPageToken` until `isLast`, a missing token or an empty
  page. Every page is read before anything moves.
- **Compose failures.** `CalledProcessError`, `FileNotFoundError` and `TimeoutExpired` (because
  `run_compose` has its own 120 s timeout) are caught. The report still prints, then "start the
  traffic with `docker compose start traffic`", and the exit is 1.
- **Delete hint.** It is `jira-as api call deleteIssue --issueIdOrKey KEY --confirm`, with a
  warning that deletion is permanent.
- **`--dry-run`.** It runs only the searches and `lifecycle transitions` reads, and prints the
  conditional report. When anything would be closed, it adds a line saying that a Resolve screen
  which drops the resolution shows only in a real run. The exit is 0 when the queue would be
  empty and nothing would be left, else 1.
- The project and credential come from `.env` (step 02). `main` also accepts an injected
  `jira_as`, so tests can drive the printed report.

`README.md` and `docs/demo-runbook.md` describe all of this. The runbook's delete example
carries `--confirm` and the permanence warning.

jira-as 2.0.0 source findings (the implementer checked these offline):
- `search jql` has `--max-results` (default 50) and `--page-token`. `-o json` returns the raw
  `/rest/api/3/search/jql` body with `nextPageToken` and `isLast`.
- `lifecycle transition` retries without the resolution and only warns when the screen rejects
  it (`lifecycle_cmds.py:941`, `:267-273`).
- `deleteIssue` is a dry run without `--confirm` and is rated "Risk: irreversible".

Test evidence:
- `tests/test_reset.py`: 30 passed, up from 13 before step 04. The compose-failure test is
  parametrized three ways. `FakeOps` pages 50 at a time with offset tokens, answers
  `issue get --fields resolution`, clears the resolution on Reopen, and can stand for a site
  whose Resolve screen lacks Resolution or whose Close is refused. With
  `tests/test_end_to_end.py`: 30 passed, 1 skipped.
- Full suite (`python3 -m pytest -q -p no:cacheprovider`): 3640 passed, 40 skipped in 166 s.
- Python 3.11 basic-demo subset (the 13 listed files): 318 passed, 40 skipped.

Deferred:
- A `RuntimeError` on the Resolve or Reopen transition still propagates and ends the report,
  as before. The spec covers only the failed Close.
- A dry run checks only the first step out (a road to Completed, or back to Open). It cannot
  foresee a Resolve screen that drops the resolution, or a missing Close. It says so.
- The runbook's `OPS` delete example and its `.claude/settings.json` note are owner-site
  details that step 11 removes.
- The dry-run exit code (0 only when nothing would be left) is this step's own choice.

No settings change is needed.
