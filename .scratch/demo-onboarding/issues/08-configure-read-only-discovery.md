# configure: read-only discovery

Type: task
Status: resolved
Blocked by: 02

See [spec.md](../spec.md), step 08.

## Answer

**What changed**

- New `grafana_jsm_sandbox/configure.py`: `python3 -m grafana_jsm_sandbox.configure [--write]`.
  - It reads `.env` through `demo_config` and starts `jira-as` with `jira_as_environment`, through
    `reset.jira_as_with`. The `jira_as` callable is injectable, as in `reset.py`.
  - The field ids already in `.env` are not validated before the run, so a malformed old id does
    not stop the command that fixes it.
  - It only reads. It never creates, edits or transitions anything.
  - For the optional `rolldice` component it prints a command instead of running it:
    `JIRA_SITE_URL=<.env site> JIRA_ALLOWED_PROJECTS=<KEY> jira-as api call createComponent --project <KEY> --field name=rolldice --field project=<KEY>`.
    It also names the UI path (project settings, Components).
    - The site and key are pinned on the command line. jira-as 2.0.0 takes each of the site,
      email and token from the environment first (`config_manager.py:96-111`), so the engineer's
      own shell, keychain or settings file cannot send the write to another site. No email or
      token is printed.
- **What it checks.**
  - **project:** the project is a service desk (`projectTypeKey`). A team-managed project only
    warns.
  - **permissions:** Browse, Create, Edit, Transition, Resolve, Close and Add comments are required.
    Administer projects and Delete issues only warn.
  - **issue type:** the project offers an Incident type.
  - **Fields**, by exact name from the project's own createmeta, never the site-wide `getFields`:
    - Severity must offer Sev-1..3, Urgency Critical/High/Medium, and Source "Monitoring systems".
      A disabled option counts as missing.
    - A field that is absent, ambiguous, not a custom field or lacks an option is written empty.
      The line is a FAIL naming `jira-admin-incident-fields`.
    - A missing Major incident is OK. Two of them warn.
  - **create screen:** Labels and Description are present, and no field is required, without a
    default, that no Run fills.
  - **statuses:** the Incident workflow has Open, Work in progress, Completed and Closed, and
    only the last two are in the Done category.
  - **resolution:** Done exists.
  - **service desk and queue:**
    - `getServiceDeskById` with the key. On a 404 or 400 it pages `getServiceDesks` and matches
      `projectKey` or getProject's `id`. Only if nothing matches is it a FAIL.
    - The queue named "Incidents" gives
      `DEMO_QUEUE_URL=<site>/jira/servicedesk/projects/<KEY>/queues/custom/<id>`. For a site
      reached through the api.atlassian.com gateway, the site comes from `getServerInfo.baseUrl`.
    - It warns when the queue's JQL lacks `resolution = Unresolved`, `resolution is EMPTY`,
      `= EMPTY` or `is null`.
  - **component:** whether `rolldice` exists.
  - **dedicated:** open Incidents without an `fp-` label warn "doesn't look dedicated".
  - A 401, an IP-allowlist 403, another 403, a 404 or an unreachable site (503 "HTTP transport
    failed") on the first call is classified, and the command stops there.
  - A later refused call fails that check alone, and the other checks still run.
  - A refusal with no status (jira-as's own) adds a next step: check `jira-as --version` is 2.0.x
    and the key.
  - A `search jql` answer that cannot be read becomes a FAIL line, not a traceback.
- **`--write`:**
  - It refuses without `.env`, with the `cp .env.example .env` message, and exits 2.
  - It changes only the five keys, in place, keeping indentation, `export`, inline comments,
    order, CRLF line endings and file mode.
  - Keys `.env` lacks go under a `# --- site facts written by configure ... ---` block, which
    later runs add to rather than repeat.
  - The write is atomic: a temp file, then a rename.
  - A check that could not be made leaves its key alone.
- Docs:
  - The README's `getFields` workaround is replaced by the configure paragraph: what it checks,
    `--write`, the `not checked` line, READY semantics and the exit codes. Two Layout rows are
    added.
  - The `.env.example` comment says to leave the ids to `configure --write`.
  - `docs/demo-runbook.md` says configure prints the queue address.
- Sanitized fixtures are under `fixtures/jira/`: a made-up `SANDBOX` project on
  `sandbox.example.invalid`, with createmeta, permissions, statuses, resolutions, service desk,
  service-desk list, queues and components.
- `tests/test_configure.py` is added to the `--basic-demo` list in `tests/conftest.py`.

**Usage and output format** (stable. It is documented in the module docstring and `--help`, and
the setup skill parses it.)

```
OK   <check>: <what it found>
WARN <check>: <what is off, and what that costs the demo>
FAIL <check>: <what stops the demo>[; ask: docs/admin-requests.md#<anchor> ...]
.env: not checked: <NAME>, ...; left as .env has them
.env: up to date | .env: <n> change(s) planned; ... | .env: <n> change(s) written; ...
- <NAME>=<value .env has now>        (redacted)
+ <NAME>=<value configure found>
READY | NOT READY: <the first FAIL's check>: <what it said>
```

- Every line is one line: whatever Jira or jira-as said has its whitespace folded, and each
  message is cut at 300 characters, after `log_formatter.redact`.
- `.env: up to date` appears only when every key was compared and none differs.
- A key whose check could not be made is named on the `not checked` line instead.
- Only a FAIL names an admin request.
- READY or NOT READY is about the project. The `.env:` line says whether `.env` holds what the
  project said, so a run without `--write` can end READY with changes still planned.
- Check names: `project`, `permissions`, `issue type`, `severity`, `urgency`, `source`,
  `major incident`, `create screen`, `statuses`, `resolution`, `service desk`, `queue`,
  `component`, `dedicated`.
- Admin anchors used: `jira-admin-create-project`, `jira-admin-incident-fields`,
  `jira-admin-resolution-screen`, `jira-admin-workflow-statuses`, `jira-admin-permissions`,
  `atlassian-org-admin-agent-licence`, `atlassian-org-admin-api-tokens`,
  `atlassian-org-admin-ip-allowlist`. A test holds them to step 11's list.

**Exit codes:** 0 READY. 1 NOT READY: something needs an admin, or Jira could not be asked. 2 is
a usage or configuration error before Jira was asked anything:
- bad arguments;
- no `.env`;
- a missing credential or key;
- no `jira-as` on PATH;
- Python older than 3.11, which gets a one-sentence message with no traceback. The file compiles
  on 3.9.

**jira-as 2.0.0 operations, each verified offline**

The check was `jira-as api describe <op>`: each is GET and "Risk: safe", and has the flags used.
`test_every_operation_it_calls_is_a_safe_get_jira_as_describes_with_those_flags` re-checks them
against the installed jira-as on every run.

| Operation | Flags |
| --- | --- |
| getProject | `--project-id-or-key` |
| getMyPermissions | `--project-key`, `--permissions` |
| getProjectComponents | `--project-id-or-key` |
| getCreateIssueMetaIssueTypes | `--project-id-or-key`, `--start-at`, `--max-results` |
| getCreateIssueMetaIssueTypeId | `--project-id-or-key`, `--issue-type-id`, `--start-at`, `--max-results` |
| getAllStatuses | `--project-id-or-key` |
| searchResolutions | `--start-at`, `--max-results` |
| getServiceDeskById | `--service-desk-id` |
| getServiceDesks | `--start`, `--limit` |
| getQueues | `--service-desk-id`, `--start`, `--limit` |
| getServerInfo | none; only for a gateway URL |

- `search jql` goes through `reset.search`.
- getServiceDesks' answer shape (`values`, `projectKey`, `projectId`, `isLastPage`) was checked
  with `jira-as api --transport responder call getServiceDesks`. That answers from the pinned
  spec, with no network.
- The `createComponent` flags were checked the same way. The implementer checked the error-JSON
  shape with the responder, and with one call to an unreachable `127.0.0.1:9`.
- Every paged answer is followed by `total`, `isLast` or `isLastPage`.

**Test evidence**

- `tests/test_configure.py`: 85 tests, all passing, none skipped here: the old-Python test, the
  offline `api describe` test and the real `jira-as` stand-in test all ran.
- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 3937 passed, 41 skipped, twice. It was
  3851 before this step.
- Python 3.11 basic demo, fresh-clone venv, `--basic-demo`: 677 passed, 41 skipped, twice. It was
  591 before this step.
- `ruff check` and `ruff format --check` are clean on `configure.py` and `test_configure.py`.

**Review fixes** (the review's should-fix findings and the trivial nits)

- **One line per check.** Refusal text is folded onto one line and capped. So is the queue JQL,
  and every check message. Tests cover a multi-line HTML 403 and a jira-as traceback with no
  JSON.
- **Service desk.** On a 404 or 400 for the key, it falls back to the `getServiceDesks` list.
  Tests match by key and by project id, for both statuses, one desk per page.
- **`.env` lines.** When the project check fails, `.env` no longer claims to be up to date; the
  new `.env: not checked:` line names the keys. There is a test for a refused project and for a
  refused create screen.
- **The component command** is pinned to `.env`'s site and key.
- **Nits:**
  - `check_dedicated` turns an unreadable search into a FAIL.
  - A status-null refusal names a next step.
  - UNRESOLVED accepts EMPTY/null.
  - READY semantics are documented and tested.

**Unverified without a live site (deferred to the live checks at the end)**

- Whether getQueues' queue `id` equals the `/queues/custom/<id>` in the address bar. This is the
  audit's open question. The runbook says to open the URL once.
- Whether the ITSM template's queue is named exactly "Incidents".
- The exact names "Major incident" and "Source", and the option spellings, in createmeta.
- Whether `getServiceDeskById` accepts a project key. The getServiceDesks fallback covers a
  site that does not.
- Whether createmeta field pages come back under `fields` or `results`. Both are read.
- The wording of the IP-allowlist 403.
- The Resolve screen accepting a resolution cannot be seen by a read-only check. The resolution
  OK line says it shows the first time an Incident is completed. `reset` and `verify` read it
  back.

**Other things to note**

- **Level choice.** A Severity, Urgency or Source that is missing, ambiguous or lacks an option
  is FAIL: exit 1, NOT READY, naming `jira-admin-incident-fields`. The demo still runs with the
  Run leaving the field off. The rule is that an admin request is only ever named on a FAIL.
  Change the level if the owner wants field gaps to stay READY.
- Only the five `.env` values are written. Statuses, permissions and the rest are reported.
- The printed component command still uses the engineer's own email and token, from their
  environment, keychain or settings. Pinning the site means a mismatched credential fails on the
  demo's site rather than writing elsewhere.
- **Stale docstring, left alone as not this step's.** `demo_config.jira_as_environment` still
  says the committed `.claude/settings.json` allows only `OPS`. Since 8571319 that file is
  key-neutral.

**Doc follow-ups for step 11**

- Write `docs/admin-requests.md` with the anchors above. Every `ask:` points at them, and the file
  does not exist yet.
- Fold the README configure paragraph into the numbered Quickstart: `configure`, then
  `configure --write`, then `docker compose up -d demo`.
- `docs/demo-runbook.md` still says OPS throughout. Use the key and the `DEMO_QUEUE_URL` configure
  prints.
- Describe configure's line format, check names and exit codes for the setup skill (step 12).
  Say that READY is about the project and that the `.env:` line gates whether `--write` is still
  needed.

No settings change is needed.
