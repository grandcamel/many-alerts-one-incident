# The engineer's setup skill

Type: task
Status: resolved
Blocked by: 11

See [spec.md](../spec.md), step 12.

## Answer

**What changed.**

- `.claude/skills/demo-setup/SKILL.md` is the skill an engineer's Claude Code follows from a
  fresh clone to one verified Incident lifecycle and a clean reset on their own project. It
  follows the audit's section 6 in ten stages, each ending on a "Done when" line: orient, host
  check, admin prerequisites, credentials, project facts (`configure`, then `configure --write`
  on a yes), build and start, the optional model preflight (`doctor --only stack
  --with-model`), the first lifecycle (`verify --replay`, then optionally `--live`), reset
  (`reset --dry-run`, then `reset` on a yes), and hand-off. A "Resuming" section lets a second
  session pick up from the first failing `doctor` layer.
- Ground rules: the engineer alone creates tokens and types them into `.env`, runs `claude
  setup-token`, sends admin requests and adds the optional component. The only commands of the
  skill's that name `.env` are `ls .env` and `cp .env.example .env`; what is in it reaches the
  agent only through `doctor` and `configure`. Each `verify`, real `reset` and `doctor
  --with-model` waits for its own yes. It acts on the named blocker and reruns blind only for
  the waits it names. It sets itself apart from `skill/incident-sync/SKILL.md` and never runs
  anything against it. A rule notes that the agent's shell forgets an `export` between
  commands, so every prefix is written on each command.
- `.claude/skills/demo-setup/READING-OUTPUT.md` is loaded only on the failure branch. It holds
  the stable line formats and exit codes of `configure`, `doctor`, `verify` and `reset` (from
  the module docstrings), a blocker-to-action table, and how to fetch and render a failed
  Run's Transcript into the gitignored `runs/`.
- `tests/test_setup_skill.py` (28 tests, in `BASIC_DEMO_TESTS`) reads the skill the way the
  agent does. It checks the frontmatter, that every module and flag it names exists in that
  command's `--help`, that every `--only` layer exists, and that every `--with-model` use reaches
  `stack`. It also checks that every admin request and document anchor lands, that every repo
  path and compose service exists, that no command in a fenced block or in prose names `.env`
  beyond the two allowed, and that no command touches `skill/incident-sync`.
- `README.md` points to the skill in one Quickstart sentence and one Layout row.

**Review round.** Each finding was checked against the code first.

- Must-fix: there was no path for a laptop behind an intercepting TLS proxy. This was
  confirmed: `demo_config.jira_as_environment` passes the shell's trust-store variables to
  `jira-as`, and the Dockerfile reads `EXTRA_CA_CERT`. Stage 3 now has a "Behind an
  intercepting proxy" branch. It walks runbook steps 1 to 3 and has the agent prefix every
  helper with `REQUESTS_CA_BUNDLE=certs/<file>` and every `docker compose up` with
  `EXTRA_CA_CERT=certs/<file>`, because exports do not persist between its commands. Stage 6
  adds the runbook's step-4 glance. READING-OUTPUT classifies certificate errors from the
  laptop's `jira-as`, from inside the build (npm/pip), from the container and model checks, a
  DER export, and an `x509` pull, which is Docker Desktop's own trust.
- Should-fix: `verify --live` has no SIGTERM handling. This was confirmed: only
  `KeyboardInterrupt` is caught, and `live()`'s `finally` does not run on a kill. Its worst case
  is about 26 minutes (180 + 360 + 180 + 360 + 120 + 360 s). Stage 8 now says to always run it
  in the background and to expect up to about 30 minutes. If it ends without its own verdict
  line, the agent runs `docker compose start traffic` at once, then `doctor --only stack`.
- Should-fix: READING-OUTPUT's configure format was stale. This was confirmed against
  configure's docstring and `match_field`. The WARN line now carries the optional `[; ask:
  ...]`, a severity, urgency or source `ask:` is described as optional, and "Acting on a
  blocker" says an `ask:` on a WARN blocks nothing.
- Nits taken:
  - The prerequisites map now covers items 4 and 7.
  - Stage 9's skip branch checks the traffic with `doctor --only stack` and has its own done
    criterion.
  - Stage 2 gains a pipx PATH check and a `.venv/bin/pip` fallback with a `PATH` prefix.
  - If `cp .env.example .env` is refused, the engineer runs it.
  - Resuming checks `.venv/bin/python` and `certs/` first, and routes an `env` or `jira`
    blocker through READING-OUTPUT instead of stage 4's full hand-over.
  - The Transcript is copied under `runs/`.
  - Stage 6 tells the engineer that the demo is now live on their project.
  - The test scans inline commands for `.env` and checks `--with-model` against `--only`.
  - Each new check fails on a planted mutation: an inline `cat .env`, and a prose or fenced
    `doctor --only env --with-model`.

**Evidence.**

- Full suite: `python3 -m pytest -q -p no:cacheprovider`, 4227 passed and 41 skipped (4198
  before this step).
- Python 3.11 basic demo, fresh-clone venv, `--basic-demo`: 967 passed and 41 skipped (938
  before).
- `ruff check` and `ruff format --check` are clean on the test.
- Live, 2026-09-24: `python3 -m grafana_jsm_sandbox.configure` against the owner's project
  returned READY. It discovered the same Severity, Urgency, Source and Major incident field ids
  that had been hand-edited into the Skill, the service desk, and the Incidents queue URL. That
  confirms stage 5's discovery path end to end.

**Deferred.**

- No agent has run the skill against a live setup. Its waits (15 s polls for up to 3 minutes;
  three reruns for a first-minute `series` FAIL) and verify's durations come from rehearsal
  timings, not from Opus 5 or Grafana 13.
- `verify` could handle SIGTERM the way it handles SIGINT, so that a killed `--live` starts the
  traffic itself. That is a code change to `verify.py`, outside this step. For now the skill's
  recovery line covers it.
- Where a `claude setup-token` token is revoked, and its lifetime, are phrased generically.
- The wording of Docker Desktop's policy and TLS errors, and the certificate error strings
  from npm, pip and jira-as, are not verified against real output.
- The skill uses no `reset --yes`, which the audit sketched, because reset has no such flag.
