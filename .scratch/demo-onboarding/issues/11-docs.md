# Docs: quickstart, admin requests, runbook, ADRs

Type: task
Status: resolved
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10

See [spec.md](../spec.md), step 11.

## Carried from step 03

- The project `CLAUDE.md` still says the OPS facts a Run relies on are in `skill/incident-sync/SKILL.md`. Since step 03 that file is a template with no project facts; they come from `.env`, rendered by `grafana_jsm_sandbox/skill_template.py` into `<runs directory>/.skill`. Correct the sentence.
- A sample log line in `README.md` still shows `project+%3D+OPS`.

## Answer

**What changed**

- **README.**
  - A new opening paragraph, then an 11-step Quickstart at the top: prerequisites (with a
    `python3 --version` check and a 3.11 virtualenv when macOS's 3.9 is the `python3`), admin
    requests, the five `.env` values, `configure`, `configure --write`,
    `doctor --only host,env,jira,facts`, `docker compose up -d --build`, a wait of about a minute
    until `docker compose ps` shows demo healthy, then the full `doctor` (and `--with-model`
    once), firing the Alert while watching the log, `verify` or `verify --live`, and
    `reset --dry-run` before `reset`.
  - Step 1 says an `images` WARN before the first `up` is expected, and that the Docker admin
    request applies only if the pull is refused. Step 2 says a FAIL's `ask:` is the one to
    forward and a WARN's is optional. Step 8 says a `[grafana] FAIL series` or a demo still
    `starting` in the first minute means wait and rerun. Step 9 sends the reader to the queue
    address `configure` printed, not into `.env`.
  - After it: "What the basic demo uses and what to ignore", then the chapter-two preamble.
  - The clone URL is `https://github.com/grandcamel/many-alerts-one-incident.git`.
  - "What you need" covers the agent licence, classic versus scoped tokens, how to install
    jira-as 2.0.0, and how to get a Python 3.11+.
  - configure, doctor and verify sit under their own heading. Laptop mode is marked
    development-only (no container boundary, binds `0.0.0.0`).
  - A "Fetching a Transcript" subsection. Its copy-out command is
    `docker compose exec -T demo env -i /bin/cat ...`, the healthcheck's pattern, so only `env`
    holds the tokens, for an instant.
  - The tests section gives the venv and `--basic-demo` commands. The sample log line no longer
    shows OPS. Timings say they were measured on the owner's laptop, and costs stay labelled
    Fable 5.1, pending Opus 5. The Layout table gains `docs/admin-requests.md`.
- **`.env.example`** is rewritten with honest comments, grouped as yours to fill in, written by
  `configure`, optional, and container-internal. The placeholder values are unchanged.
- **New `docs/admin-requests.md`.** It has the ten headings `configure`, `doctor` and `verify`
  name, plus a Network section. Each is a copy-paste request with a why, which check notices it,
  and the Atlassian or Claude documentation page. The Docker section says which images are
  pulled (lgtm, overridable with `LGTM_IMAGE`; `alpine:3.20`, fixed in compose) and which are
  build bases (`node`, the `BASE_IMAGE` build argument; `python:3.13-slim` in the rolldice
  Dockerfile).
- **`docs/demo-runbook.md`.** Owner specifics are gone: OPS, the 2026-09-15 probe deletions and
  the stale settings sentence. The key and queue come from `configure` and `DEMO_QUEUE_URL`.
  `doctor` is pre-demo check 2, with the health endpoint as the quick glance (noting
  `RECEIVER_HOST_PORT`). There is a day-before `verify --live` rehearsal. The T+1:35 row now says
  Sev-1 and Urgency Critical, because the rule's severity is critical and the Skill maps
  critical to Sev-1. Its `exec ... cat` commands go through `env -i /bin/cat`.
- **ADR 0002** has an amendment dated 2026-09-24 on the execs that remain. The healthcheck runs
  through `env -i`. `doctor --in-container` becomes non-dumpable through `nondumpable.py` before
  it reads its environment or runs its imports (about 0.45 s), so the interpreter's start-up is
  the only window left. Any other `docker compose exec` still carries both tokens.
- **ADR 0004** has an amendment. Creating the project needs a Jira admin: `createProject` needs
  Administer Jira, and the template key that works is not in the published enum. `configure`
  reads the ids and the queue. The Incidents queue filters on resolution as well as issue type,
  which corrects "issue type alone".
- **`CLAUDE.md`.** The OPS-facts sentence is corrected: the Skill is a template, rendered from
  the demo's configuration, and `configure` supplies the site facts. A new line points agents at
  `.claude/skills/demo-setup/` and `python3 -m pytest --basic-demo`.
- **Code, as the orchestrator directed.**
  - `configure`: a Severity, Urgency or Source that is missing, ambiguous, not a custom field or
    lacks an option is now a WARN naming `jira-admin-incident-fields`, not a FAIL. The run can
    end READY. This settles step 08's open level choice. A create screen that lacks Labels or
    Description, or requires a field no Run fills, stays a FAIL. So does a stale id in `.env`
    for a field the project lacks, in `doctor`'s facts layer.
  - The `demo_config.jira_as_environment` docstring no longer says the committed settings allow
    only OPS.
  - The code's pointers to the README now all name the section that exists,
    "README, What you need". `configure`, `doctor` and `verify` had mixed in a
    "Prerequisites" section that does not exist.
- `pyproject.toml`'s description says "Jira Service Management Incident", not "Jira OPS
  Incident".

**Tests**

- New `tests/test_docs.py`, on the `--basic-demo` list:
  - all ten required anchors are headings in `docs/admin-requests.md`;
  - every `docs/admin-requests.md#anchor` in the package, the README, `.env.example` and
    `docs/**` lands on a heading there, by GitHub's slug rules. This covers printed references,
    and bare anchor constants found by AST. A guard makes sure the search finds every anchor
    `configure` and `doctor` name;
  - the slug rules themselves;
  - every relative link, fragment included, lands. The check covers README, `docs/*.md`, ADRs
    0001 to 0005 and `CLAUDE.md`, including links wrapped across lines.
  - As a mutation check, renaming "## Docker admin" failed 4 tests.
- `tests/test_configure.py` and `tests/test_doctor.py` follow the WARN level. There is a new
  doctor test: a missing Source with an empty `.env` value is a WARN carrying the ask, with no
  FAIL.
- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 4198 passed, 41 skipped (3m12s). That
  is up from 4182 after step 10.
- Python 3.11 basic demo, fresh-clone venv, `--basic-demo`: 938 passed, 41 skipped (35s). That is
  up from 922.
- `ruff check` and `ruff format --check` are clean on every touched Python file.

**Live evidence (2026-09-24)**

A live `python3 -m grafana_jsm_sandbox.configure` against the owner's OPS project returned
READY. It discovered exactly the Severity, Urgency, Source and Major incident field ids that had
been hand-edited into the Skill before step 03, plus the service desk and the Incidents queue
URL. That confirms the discovery path end to end.

**Deferred / unverified**

- `CLAUDE.md` points at `.claude/skills/demo-setup/`, which step 12 writes. The pointer dangles
  until that commit.
- `CONTEXT.md` (the chapter-two vocabulary: "the Jira OPS project", "OPS issue") and several
  test fixtures still say OPS. The spec does not list them for this step.
- The runbook's Sev-1 correction was not re-checked against the ticket 08 rehearsal record. Its
  timings are labelled Grafana 12.3.1 with Fable 5.1 Runs. The Grafana version is inferred from
  step 06's note.
- These claims in `docs/admin-requests.md` are hedged there and unverified:
  - whether a scoped token also needs a Jira Service Management scope for `configure`'s service
    desk and queue reads;
  - that a project admin cannot edit a company-managed project's screens;
  - the exact names of Claude's managed version-bound settings.
- The README H1 stays `grafana-jsm-sandbox`, although the clone is `many-alerts-one-incident`.
  Retitling is the owner's call.
- `doctor --only host` before `.env` exists relies on step 09's smoke run, and was not re-run
  here.
- The `env -i /bin/cat` copy-out relies on the image's merged `/usr` (trixie). It has not been
  run against a live container, since this step is offline.
- `doctor`'s `images` WARN still carries the `docker-admin` ask before a first pull. The
  Quickstart explains it rather than changing the code.

No settings change is needed.
