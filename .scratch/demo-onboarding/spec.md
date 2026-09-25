# Spec: another engineer demos chapter one on their own Atlassian site

Status: historical, superseded by the future live design in `docs/demo-runbook.md` on 2026-09-25
Branch: `demo-onboarding` (worktree `/Users/jasonkrueger/projects/maoi-demo-onboarding`)
Evidence: [audit-2026-09-23.md](audit-2026-09-23.md) (six lenses, adversarially verified) and [probe-2026-09-23.md](probe-2026-09-23.md) (live `/proc` probe)

This file records the earlier chapter-one assignment. Its live commands, model default and acceptance claims are not current instructions. The branch was rebased onto `main` after the direct-token path was retired; see [the rebase review](rebase-review-2026-09-25.md).

## Goal

An engineer clones this repo and, from `git clone` to a first successful Incident lifecycle and a clean reset, meets no step that needs a support question to the owner, a hand edit of a tracked file, or an elevated permission they cannot request with a ready-made message. A Claude Code skill for the engineer (`.claude/skills/demo-setup/`) then drives the whole path agentically. The removable frictions come first, the skill comes last.

## Decided scope (owner, 2026-09-23)

- **Chapter one on docker compose.** Not local Kubernetes/kind, not the chapter-two cascade. Chapter-two code stays and must keep passing, but the basic-demo path must not depend on it.
- **A dedicated JSM IT service management project, any key.** A Jira admin creates it; the engineer is its project admin. No `OPS` default anywhere: `DEMO_PROJECT_KEY` is required.
- **The setup skill is agentic end to end.** It runs every step itself and stops only for what a human must do: pasting tokens, and sending admin requests.
- **The default Run model is Opus 5 (`claude-opus-5`)**, overridable with `RUN_MODEL`.
- **Live checks allowed at the end:** the `/proc` probe (done, see the probe file), `doctor --with-model`, and a full lifecycle on the owner's OPS project.

## Constraints for every step

- Work only in the worktree above, on branch `demo-onboarding`. **Never touch `/Users/jasonkrueger/projects/many-alerts-one-incident`.** It is `main`'s working tree, where another session has uncommitted work. **Never push.**
- **Never create, edit or delete `.claude/settings.json` or `.claude/settings.local.json`.** An automated guard blocks this. If a step needs a change there, write the exact proposed change into that step's issue file under `## Proposed settings change`.
- Offline only. No Jira, Confluence or Claude API calls, and no `docker compose up/build/start/stop`. Read-only docker inspection is fine, as is `docker compose config` against a temporary env file. Never read any real `.env`.
- The runtime stays standard library only, with the Receiver and the laptop helpers both stdlib. Tests use pytest, real HTTP on ephemeral ports, and injected fakes, following the `jira_as` callable pattern in `reset.py`.
- **Match the house style.** Module and function docstrings are prose that says *why*. Vocabulary is from `CONTEXT.md` (Run, Receiver, Forwarder, Notification, Alert, Incident, Fingerprint, Skill, sentinel, Transcript). Comment density matches the neighbouring code. There are no drive-by refactors.
- Tests:
  - Run the focused tests while working.
  - Before committing, run `python3 -m pytest -q -p no:cacheprovider` (the full suite, about 3 minutes; `python3` on PATH has pytest and PyYAML) **and** the basic-demo subset on Python 3.11 (`/private/tmp/claude-501/-Users-jasonkrueger-projects-many-alerts-one-incident/d25047eb-92a8-457d-9627-912b47690887/scratchpad/fresh-clone/.venv/bin/python -m pytest -q -p no:cacheprovider tests/<basic files>`, run from the worktree).
  - Both must be green.
- One commit per step. The subject is imperative, like the history ("Scope a Run's Read to its runs directory"). A short body explains why. End the message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Keep `README.md`, `docs/demo-runbook.md` and the ADRs truthful as you go. When a step changes behaviour a doc states, fix that sentence in the same commit. The full docs rewrite is step 11.
- Each step has an issue file under `issues/`. When the step is done, set `Status: resolved` and append `## Answer`: what changed, the test evidence (counts), and anything deferred.

## Configuration model (steps 2–3 establish it, later steps use it)

`.env` at the repo root is the **single source**. Compose hands it to the demo container, and the laptop helpers (`reset`, `replay`, `configure`, `doctor`, `verify`, and the e2e test) read it through one stdlib parser in `grafana_jsm_sandbox/demo_config.py`. They never rely on the shell's own jira-as configuration.

| Variable | Required | Who writes it | Meaning |
| --- | --- | --- | --- |
| `JIRA_SITE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | yes | the engineer | as today |
| `CLAUDE_CODE_OAUTH_TOKEN` | yes | the engineer | as today |
| `DEMO_PROJECT_KEY` | yes | the engineer | the dedicated project's key; no default |
| `DEMO_SEVERITY_FIELD`, `DEMO_URGENCY_FIELD`, `DEMO_SOURCE_FIELD`, `DEMO_MAJOR_INCIDENT_FIELD` | no | `configure` | `customfield_<n>`; empty means the project lacks it and the Skill leaves it off |
| `DEMO_QUEUE_URL` | no | `configure` | the Incidents queue, for the runbook and `verify` |
| `RUN_MODEL` | no | the engineer | default `claude-opus-5` |
| `BIND_ADDRESS`, `GRAFANA_HOST_PORT`, `RECEIVER_HOST_PORT` | no | the engineer | defaults `127.0.0.1`, `3000`, `8080`; used by compose interpolation and the laptop helpers |
| `LGTM_IMAGE` | no | the engineer | override the pinned lgtm image, e.g. for an internal mirror |

The option values the Skill writes (`Sev-1..3`, `Critical/High/Medium`, `Monitoring systems`), the statuses (Open, Work in progress, Completed, Closed), and the resolution `Done` are **not** configurable. `configure` and `doctor` verify them against the project and name the admin request when they are missing.

## Steps

### Workflow 1: foundation

**01 Close the credential leak and the LAN exposure.** The probe shows that a Run with the bare `Read` rule reads the real Jira token from `/proc/1/task/1/environ`, and that `Read(//abs/**)` rules deny every alias.
- `run_command.build_run_command` takes the runs directory and allows `Bash(jira-as *)` plus `Read(/<absolute runs dir>/**)`. The leading `/` of the absolute path makes the rule start with `//`, which is Claude Code's syntax for an absolute path. Until step 3 moves the rendered Skill under the runs directory, also allow `Read(/<absolute skill dir>/**)`.
- On Linux, the Receiver marks itself non-dumpable at startup (`prctl(PR_SET_DUMPABLE, 0)` via `ctypes`; a no-op elsewhere). That makes `/proc/1/*` root-owned and unreadable by the `demo` uid, which closes the file-reading paths jira-as has (attachment upload, template and batch files) that Claude's permission rules cannot see. Add a unit test through an injected hook, and an opt-in `DEMO_CONTAINER` check that `docker compose exec demo cat /proc/1/environ` is refused.
- Compose publishes `${BIND_ADDRESS:-127.0.0.1}:${GRAFANA_HOST_PORT:-3000}:3000` and `${BIND_ADDRESS:-127.0.0.1}:${RECEIVER_HOST_PORT:-8080}:8080`. Drop the 4317/4318 publications. Make the published-port parsing in `tests/test_container.py`, `tests/test_grafana.py` and `replay.py`'s default follow the new form.
- Add `.claude/settings.local.json` to `.gitignore`. Add `.claude/`, `**/__pycache__/`, `.scratch/` and `prototype/` to `.dockerignore`, provided the image still gets everything it copies.
- Correct the `SITE_OPERATIONS_VARIABLE` docstring: it unlocks jira-as's site-scoped operations and does not "widen nothing".
- Add an amendment to ADR 0003 (bare `Read` replaced by a scoped rule, citing the probe) and to ADR 0002 (non-dumpable Receiver).

**02 One configuration, `.env` as the single source.**
- Add `demo_config.py`. It holds a compose-compatible `.env` reader (comments, blank lines, optional surrounding quotes, no interpolation) and a frozen `DemoProject` built from the environment. `DemoProject` raises one error naming every missing or malformed value; the key must match `^[A-Z][A-Z0-9_]{1,9}$`, and a field id, when set, must match `^customfield_\d+$`. It also holds a helper that builds a jira-as child environment from `.env` values:
  - the three `JIRA_*` variables
  - `JIRA_ALLOWED_PROJECTS=<key>`
  - `JIRA_ALLOW_SITE_OPERATIONS=true`
  - PATH/HOME and the trust-store variables from the shell
  - a warning when the shell's own `JIRA_SITE_URL` host differs from `.env`
- Read jira-as 2.0.0's source (installed under `~/.as-plugins-venv`) to learn how `JIRA_ALLOWED_PROJECTS` interacts with a `.claude/settings.json` found on the cwd path. The committed file allows only `OPS`. If the file can veto the environment, run the helpers' jira-as children with a cwd outside the repo, and say so in a docstring.
- The Receiver refuses to start without `DEMO_PROJECT_KEY`, naming it alongside the other missing variables, and pointing at `python3 -m grafana_jsm_sandbox.configure` (that command arrives in step 8).
- The Run's environment gains `JIRA_ALLOWED_PROJECTS=<key>`.
- `run_command.PROMPT` names the key.
- `reset.py`, `replay.py` (the default receiver URL from `RECEIVER_HOST_PORT`) and `tests/test_end_to_end.py` take the key and credentials from `.env`.
- `.env.example` gains the new variables with honest comments. Its `DEMO_PROJECT_KEY` is empty, so the example no longer "would start": update that test to assert the Receiver refuses and names the key.

**03 The Run's Skill is rendered from `.env`, never hand-edited.**
- `skill/incident-sync/SKILL.md` becomes a template: the project key, the facts-table rows, the "never touch" line, and the example create command with only the configured fields.
- Add `grafana_jsm_sandbox/skill_template.py`:
  - a pure `render(template, project)` that fails on any unfilled placeholder;
  - a function that materializes the whole skill directory into a target.
- At startup the Receiver renders into `<runs directory>/.skill`. Run ids are timestamps, so this cannot collide. The Run's `--add-dir` and its one `Read` rule then cover the runs directory alone: drop the separate skill-directory rule from step 1.
- The rendered Skill must read naturally on screen. When a field is absent it names no id for it and tells the Run to leave it off.
- Placeholders use `{{NAME}}`, which appears nowhere in the Skill today.
- Update the `__main__` docstring, `CONTEXT.md` (Skill entry) and the README sentence about editing field ids.

**04 Reset that cannot strand an Incident.**
- After moving to Completed, re-read the issue. If the resolution is still null, do not Close, and report the key as left: "completed without a resolution: ask your Jira admin to put Resolution on the Resolve screen". jira-as 2.0.0 silently retries a transition without the resolution when the screen rejects it.
- A failed Close means left.
- Page the searches past the first 50 results.
- Catch `CalledProcessError`/`FileNotFoundError` from compose. Print the report anyway, plus "start the traffic with `docker compose start traffic`".
- The printed delete hint carries `--confirm` and a warning that deletion is permanent.
- Add `--dry-run`, which lists what would change and changes nothing.
- The project comes from `.env` (step 2).
- Extend `tests/test_reset.py` for each case.

### Workflow 2: visibility and pins

**05 Failures read as failures.**
- A result event with `is_error: true` (or a subtype starting `error_`) renders as `[FAILED] <terminal_reason or subtype>: <first line of the result text>` with a one-line hint for the known causes: invalid or expired OAuth token, out of usage credits, rate limit, model not available to the seat, budget exceeded. The shapes are in the prototype's outcome normalization and fixtures (`prototype/run_timing/outcomes.py`, `.scratch/many-alerts-one-incident/reviews/ticket-23/fixtures/outcome-cases.json`), and the owner's note records that a refused Run reports `subtype: success` with `is_error: true` and `terminal_reason: api_error`.
- `system/api_retry` renders as `[retry]`.
- A `rate_limit_event` renders only when its status is not `allowed`.
- The spawner learns the outcome from the stream, and the Receiver logs `run <id> FAILED: <reason>`.
- Logging adds a time and a level.
- The Receiver logs each accepted Notification (alert count, run id, queue depth) and each rejected POST with its reason.
- The Forwarder logs upstream 4xx/5xx at WARNING, with a diagnosis for 401, 403 (an IP-allowlist body in particular) and 404.
- Every Run's raw stream-json is teed to `<run dir>/transcript.jsonl`, and its path is logged.
- The Skill gains one line: after a failed create, do not retry with other fields and never create probe Incidents.
- Add a sanitized refused-Run fixture and tests.

**06 Pins and Run knobs.**
- Pin lgtm as `${LGTM_IMAGE:-grafana/otel-lgtm:<tag>@sha256:<index digest>}`, using the tag whose index digest equals the laptop's current `grafana/otel-lgtm:latest` RepoDigest `sha256:475319e883b66594d1a2f22ef168c2459802bb94548e6f25d9782bd5f5c19a3a` (check with `docker buildx imagetools inspect`). Confirm that the index carries linux/amd64 and linux/arm64.
- Add `RUN_MODEL` (default `claude-opus-5`), passed as `--model` and logged at startup.
- Add `RUN_BUDGET_USD` → `--max-budget-usd` **only if** the image's pinned Claude Code (2.1.272) lists that flag. Check with `docker run --rm --entrypoint claude grafana-jsm-sandbox:latest --help`.
- Where the README states a model or cost, say it was measured on Fable 5.1 and is pending re-measurement on Opus 5.
- Add tests for the argv and the compose pin (no `:latest` anywhere).

**07 A newcomer's host checks work.**
- `pyproject.toml` gains `[build-system]` and an explicit `packages = ["grafana_jsm_sandbox"]`, so `pip install -e '.[dev]'` works.
- Python 3.11 compatibility for `ssl.OP_LEGACY_SERVER_CONNECT`: use `getattr` with the documented value, in the source and the tests that name it.
- `conftest.py` adds a `--basic-demo` option. It ignores collection of every test file not in an explicit basic-demo list, so chapter-two files are never even imported. The full default run is unchanged.

### Workflow 3: the commands the skill calls

**08 `python3 -m grafana_jsm_sandbox.configure`: read-only discovery.**
- Discovery uses jira-as through the step-2 environment:
  - permissions on the project;
  - that the project is a service desk with an Incident issue type;
  - project-scoped createmeta for Severity, Urgency, Source and Major incident, with ids and allowed values;
  - the statuses and the resolution `Done`;
  - the Incidents queue URL;
  - components;
  - a warning when the project holds open Incidents without an `fp-` label, which means it isn't dedicated.
- Verify every jira-as operation name offline with `jira-as api search` and `jira-as api describe`.
- By default it prints a diff of the `.env` keys it would write. `--write` applies it, preserving comments and order. It never prints a secret.
- Missing things map to the text of an admin request (see step 11's `docs/admin-requests.md`).
- Tests use an injected fake jira-as and sanitized fixtures under `fixtures/jira/`.

**09 `python3 -m grafana_jsm_sandbox.doctor`: ordered preflight.** It runs these layers in order and stops at the first layer that fails:

| Layer | What it checks |
| --- | --- |
| host | docker and compose versions, python, jira-as ≥ 2.0, free ports |
| env | `.env` present, no `.env.example` placeholder left, `JIRA_SITE_URL` shape including the `api.atlassian.com/ex/jira/<cloudId>` gateway, key set |
| jira | via jira-as with `.env`: who am I, server info, project, permissions; classifies 401, IP-allowlist 403 and 404 |
| facts | the configured field ids and options still valid |
| stack | `docker compose ps`, health, and `docker compose exec -T demo python3 -m grafana_jsm_sandbox.doctor --in-container` |
| grafana | contact point, one-minute repeat, the rule exists, its query returns at least one series |

- `--in-container` does three things:
  - calls Jira `/rest/api/3/myself` with the container's credential, printing only the status;
  - confirms the rendered Skill carries the key;
  - confirms `/proc/1/environ` is unreadable.
- `--with-model` (opt-in, one short Run) uses the real Run flags with a prompt that only runs `jira-as --version`. It reports the model from the init event, `is_error`/`terminal_reason`, and whether the allowed call was denied, which would point to org-managed permission rules.
- Output is one line per check (`OK`/`WARN`/`FAIL` plus the fix), ending `READY` or `NOT READY: <first blocker>`.
- Tests use fakes, including a local fake upstream for the HTTP classifications.

**10 `python3 -m grafana_jsm_sandbox.verify [--replay | --live]`.**
- Watches the configured project by JQL through create → comment → Work in progress → Completed, printing each stage with its elapsed time and naming the stage that timed out.
- Asserts a resolution on Completed.
- `--live` stops the traffic and starts it again after the Firing.
- Reuses and replaces the logic in `tests/test_end_to_end.py`; the test then calls it.
- Tests use a fake jira-as and a fake clock.

### Workflow 4: words and the skill

**11 Docs.**
- `README.md`:
  - correct the clone URL (`https://github.com/grandcamel/many-alerts-one-incident.git`);
  - put a numbered Quickstart at the top (prerequisites, admin requests, `.env`, `configure`, `doctor`, `up`, `doctor`, the alert, `verify`, `reset`);
  - move the chapter-two preamble below it;
  - add a "what the basic demo uses and what to ignore" section;
  - mark laptop mode as development-only;
  - give the `--basic-demo` test command;
  - explain how to fetch a Transcript.
- `.env.example`: rewrite it.
- New `docs/admin-requests.md`, with copy-paste requests for:
  - the Jira admin (create the ITSM project from the UI template and make me its administrator; the fields on the Incident create screen; Resolution on the Resolve screen);
  - the Atlassian org admin (a JSM agent licence; the API-token policy; the IP allowlist; a service account as the fallback);
  - the Claude org owner (`setup-token` allowed; no `allowManagedPermissionRulesOnly`; the version bounds; `availableModels`);
  - the Docker admin (registry access or a mirror).
- `docs/demo-runbook.md`: remove owner-site specifics and use the key and queue URL `configure` prints.
- ADR 0004: add an amendment (project creation needs a Jira admin; what the queue filters on).

**12 The engineer's setup skill**, `.claude/skills/demo-setup/SKILL.md`.
- Agentic end to end, following the stages in the audit's section 6.
- It never reads or edits `.env`: the engineer pastes secrets in their own editor.
- Every Jira write happens only after explicit consent.
- It verifies through `doctor`, and never confuses itself with `skill/incident-sync/SKILL.md`.
- Written per the `writing-for-agents` skill.

## Out of scope

- Local Kubernetes/kind.
- The chapter-two cascade.
- A marker label beyond `fp-`: the project is dedicated.
- Changing Grafana's `noDataState: OK` (intentional; `doctor` covers drift).
- Pushing, or merging into `main`.
