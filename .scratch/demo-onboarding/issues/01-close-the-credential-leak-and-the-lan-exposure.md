# Close the credential leak and the LAN exposure

Type: task
Status: resolved

See [spec.md](../spec.md), step 01.

## Answer

**What changed**

- **Read is scoped.** `build_run_command(skill_directory, runs_directory)` now allows
  `Bash(jira-as *)`, `Read(//<runs dir>/**)` and `Read(//<skill dir>/**)`, both resolved to absolute
  paths (`allowed_tools`, `read_rule` in `grafana_jsm_sandbox/run_command.py`). The bare `Read`
  that let the probe's Run read `/proc/1/task/1/environ` is gone. The by-hand CLI takes both
  directories (`run_command skill runs`). `__main__.serve` passes `settings.runs_directory`.
- **The Receiver is non-dumpable on Linux.** `__main__.refuse_to_be_read()` calls
  `prctl(PR_SET_DUMPABLE, 0)` before serving. Startup refuses if the call fails. It does nothing
  on macOS. This covers jira-as's own file reads, which no Read rule sees.
- **Compose publishes on loopback only.** The Grafana and Receiver ports are published as
  `${BIND_ADDRESS:-127.0.0.1}:${GRAFANA_HOST_PORT:-3000}` and
  `${BIND_ADDRESS:-127.0.0.1}:${RECEIVER_HOST_PORT:-8080}`, and 4317/4318 are no longer
  published. `replay.default_receiver()` / `laptop_url()` follow the same variables, and so does
  `tests/test_grafana.py`.
- **Ignore files.** `.gitignore` adds `.claude/settings.local.json`. `.dockerignore` adds
  `.claude/`, `prototype/` and `**/__pycache__/`. A test checks that every COPY source of both
  Dockerfiles still reaches the build context.
- **Docs.** The `SITE_OPERATIONS_VARIABLE` docstring in `run_spawner.py` now says the flag
  unlocks every site-scoped operation. There are amendments to ADR 0002 (the non-dumpable
  Receiver and the open exec route described below) and ADR 0003 (the scoped Read). README and
  `docs/demo-runbook.md` are updated for the allow list, the two-argument CLI, loopback
  publishing and the port variables.
- **Review follow-ups made here.**
  - The exec'd-process route is named in ADR 0002 and README.
  - `allowed_tools` takes its directories in the same order as `build_run_command`.
  - `prctl` gets explicit ctypes `argtypes`.
  - A replay docstring was wrapped.
  - The build-context test also reads `docker/rolldice/Dockerfile`.

**Test evidence**

- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 3528 passed, 39 skipped (5m28s).
- Python 3.11 basic-demo subset (test_container, test_end_to_end, test_fixtures, test_forwarder,
  test_grafana, test_log_formatter, test_notification_fixtures, test_receiver, test_replay,
  test_reset, test_run_command, test_run_spawner, test_startup): 269 passed, 39 skipped.
- The new tests are in `test_startup.py`, `test_run_command.py`, `test_replay.py` and
  `test_container.py`.
- The kernel behaviour was checked by hand in a throwaway container from the local image
  (network none, read-only, uid 1000). A same-uid read of a non-dumpable process's
  `/proc/<pid>/environ` and `task/<pid>/environ` got EACCES.

**Deferred**

- **Token in exec'd processes.** Docker gives every exec'd process the container's full
  environment, `JIRA_API_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN` included, as uid `demo`, and
  those processes stay dumpable. That covers the healthcheck (every 10s) and any
  `docker compose exec demo ...`, including step 9's `doctor --in-container`. While one is alive,
  jira-as's file-reading paths could read its `/proc/<pid>/environ`.
  - The lasting fix is to keep the real token out of the container environment: a file read and
    unlinked at startup, or a Receiver under a separate uid.
  - A cheaper narrowing is `env -i` on the healthcheck. It was not applied, because it cannot be
    verified without `compose up`.
  - This is recorded in ADR 0002's amendment.
- **Laptop mode binds the LAN.** `python3 -m grafana_jsm_sandbox` on the host still binds the
  Receiver to `0.0.0.0` (`__main__.DEFAULT_HOST`), so audit F11's exposure remains in that mode.
  Step 11 marks laptop mode development-only. A later option is to default `RECEIVER_HOST` to
  `127.0.0.1` and set `RECEIVER_HOST=0.0.0.0` in the Dockerfile's `ENV`.
- **`.env.example`** does not list `BIND_ADDRESS` / `GRAFANA_HOST_PORT` /
  `RECEIVER_HOST_PORT` yet. Steps 2 and 11 rewrite that file.
- **Ports moved only in `.env`.** `replay.default_receiver()` and the Grafana URL in
  `test_grafana.py` read these variables from the shell only, so a port moved only in `.env`
  needs `--receiver`. README says so. Step 2's `.env` parser should take this over.
- **No `Read(//proc/**)` deny rule.** The audit suggested one, but it was not added, because the
  spec's step 01 does not ask for it. The scoped allow rules plus the non-dumpable Receiver cover
  it.
- **Unrun opt-in checks.**
  - The `DEMO_CONTAINER` check (`docker compose exec demo cat /proc/1/environ` refused) has not
    run against a live stack. It needs an image rebuild, which is out of scope offline.
  - The Linux-only real-kernel test in `test_startup.py` is skipped on macOS.
- **Skill rule and `--add-dir`.** Step 3 is expected to drop the skill-directory Read rule and
  `--add-dir` once the Skill is rendered under the runs directory.
- **Timing-sensitive test.** Not caused by this step:
  `test_replay.py::test_the_pause_falls_between_the_notifications_and_not_after_the_last` has a
  0.9s upper bound, and the reviewer saw it fail under heavy load (load average 8-11). It passed
  in both runs here (load average about 9). Loosening it is a separate task.

**jira-as source findings**

- `JIRA_AS_ALLOW_SITE_OPERATIONS` has no per-operation switch. In jira-as 2.0.0's index it
  unlocks all 610 site-scoped operations (465 platform, 52 service desk, 93 software). What those
  can reach is bounded only by the Skill and the Forwarder account's Jira permissions.
- jira-as opens local files for an attachment upload, a template or a batch file. No Claude
  permission rule sees those reads, which is why the Receiver itself is made non-dumpable.

**Proposed settings change**

None.
