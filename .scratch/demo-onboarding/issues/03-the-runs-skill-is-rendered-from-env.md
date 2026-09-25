# The Run's Skill is rendered from .env, never hand-edited

Type: task
Status: resolved
Blocked by: 02

See [spec.md](../spec.md), step 03.

## Answer

**What changed**

- `skill/incident-sync/SKILL.md` is now a template. It has no `OPS` and no `customfield_` id. Its placeholders are `{{PROJECT_KEY}}`, `{{SEVERITY_FIELD}}`, `{{URGENCY_FIELD}}`, `{{SOURCE_FIELD}}`, `{{MAJOR_INCIDENT}}` and `{{CUSTOM_FIELDS}}`. One static paragraph now says the Run sets only the fields that have an id, and never looks up or guesses a missing one. Rendered with `OPS` and the owner's four ids, the output matches the old hand-edited Skill byte for byte, apart from that paragraph.
- New `grafana_jsm_sandbox/skill_template.py`:
  - `render(template, project)` is pure. It refuses a template if any placeholder is unknown, misspelled or unclosed, or if the project key is empty.
  - `materialize(source, target, project)` removes any earlier rendering, renders every `.md` in memory before writing, copies other files unchanged, and leaves the result read-only (files `0444`, directories `0555`).
  - A template that is not UTF-8 is also refused by file name. This came from the review.
- `__main__.serve` renders the Skill into `<runs directory>/.skill` at every start, before the Forwarder starts. If the Skill cannot be rendered, it prints "cannot render the Run's Skill: ..." and returns 1.
- `build_run_command(runs_directory, key)`: the allow list is exactly `Bash(jira-as *)` and `Read(//<runs dir>/**)`, and `--add-dir` plus the system prompt name `<runs dir>/.skill`. The by-hand CLI is now `python3 -m grafana_jsm_sandbox.run_command runs <KEY>`.
- Docs:
  - The README covers the field ids coming from `.env` and the skill and command-line section. It also covers the configuration table, the file map, and how to `chmod` before deleting a laptop's `runs/.skill` by hand.
  - The runbook's Skill tab now shows the rendered Skill, and its allow-list sentence and CLI example are updated.
  - ADR 0003 has a step 03 amendment. `CONTEXT.md` defines the Skill as a template rendered from `.env`. The `.env.example` comment is updated.
- Review fix, must-fix: the README had said to "restart the container after changing `.env`". It now says to recreate it with `docker compose up -d demo`. `docker compose restart` keeps the environment the container was created with (the `env_file:` in docker-compose.yml:57-58), so the Receiver would render the Skill from the old values.
- Review nits fixed: docstrings for `OPENING` and `READ_ONLY_FILE`, the UTF-8 refusal, and the README note about deleting a laptop's `runs`.

**Test evidence**

- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 3622 passed, 40 skipped.
- Python 3.11 basic-demo subset: 363 passed, 40 skipped. It ran the 13 listed files plus `tests/test_demo_config.py` and the new `tests/test_skill_template.py`.
- New `tests/test_skill_template.py`: 27 tests. There are new tests in `test_run_command.py` and `test_startup.py` (5 new), and in `test_container.py`: a static tmpfs check, plus an opt-in `DEMO_CONTAINER` check that is skipped offline.

**Deferred**

- It is unverified offline whether `Read(//<runs dir>/**)` covers the dot-named `.skill` directory. Gitignore-style `**` matches dot entries, but the 2026-09-23 probe only confirmed `./notification.json`. The ADR 0003 amendment says so. Step 09's `doctor --with-model` or step 10's live verification should have a Run read its Skill explicitly.
- Two stale sentences remain in the project `CLAUDE.md` (it still names `skill/incident-sync/SKILL.md` as holding the OPS facts) and the README sample log line `project+%3D+OPS`. Both are added to step 11's issue. `CLAUDE.md` was left untouched because it is an agent-instruction file.
- The mapping bullets in Step 2a still describe Severity when the project lacks it. The facts table and the new paragraph tell the Run to leave the field off. This has not been tried with a live Run.
- Running `run_command` by hand assumes a runs directory that a Receiver has already rendered the Skill into. There is no stand-alone render CLI because the spec did not ask for one.

**jira-as source findings:** none new in this step.

No settings change was needed.
