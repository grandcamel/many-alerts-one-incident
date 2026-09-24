# One configuration, .env as the single source

Type: task
Status: resolved
Blocked by: 01

See [spec.md](../spec.md), step 02.

## Answer

**What changed**

- **`grafana_jsm_sandbox/demo_config.py` (new, stdlib).**
  - `read_env_file(path)`: compose's reading of an env file. Comments and blank lines are
    skipped, an `export ` prefix is allowed, whitespace goes, single quotes are literal, double
    quotes unescape `\"` and `\\`, an unquoted value ends at a space-preceded `#` (a tab-preceded
    one is kept, as compose keeps it), and a line with no `=` is skipped. There is no
    interpolation and no `\n`-style escape expansion, which compose does; the docstring says so
    rather than claiming an exact match. An unterminated quote is refused, naming the
    file, the line and the variable, never the value. A missing file says
    `cp .env.example .env`. The rules were read off `docker compose config` against a throwaway
    env file, and `test_compose_itself_reads_those_lines_the_same_way` re-checks them against the
    local compose whenever docker is on PATH.
  - `compose_environment(path, shell)`: `.env` with the shell over it, which is compose's own
    interpolation precedence. Without a `.env` it is the shell alone.
  - `DemoProject`, frozen, built by `from_environment`. It holds `key` (required,
    `^[A-Z][A-Z0-9_]{1,9}$`, lower case refused rather than upper-cased), the four
    `DEMO_*_FIELD` ids (`^customfield_[0-9]+$` when set, `None` when empty) and `queue_url`. One
    `IncompleteDemoProject` names every missing or malformed value. A missing key points at
    `python3 -m grafana_jsm_sandbox.configure`.
  - `jira_as_environment(values, shell, warn)` builds the environment from scratch:
    - the three `JIRA_*` variables from `.env`;
    - `JIRA_ALLOWED_PROJECTS=<key>` and `JIRA_ALLOW_SITE_OPERATIONS=true`;
    - PATH, HOME and the trust-store variables from the shell;
    - the explicit proxy variables (`HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY`, both cases) from the
      shell, added in review: the helpers inherited them before, and a helper holds the real token
      and talks to the real site itself, so passing them widens nothing (a Run still gets none,
      audit F21).

    It warns (to stderr by default) when the shell's `JIRA_SITE_URL` host differs from `.env`'s.
    It raises one `ConfigurationError` naming every missing credential and project value, and no
    value.
- **Receiver.** `Settings` gains `project: DemoProject`. Startup refuses without
  `DEMO_PROJECT_KEY` and names it alongside every other missing variable. It logs
  `jira-as in each run is confined to project <KEY> (JIRA_ALLOWED_PROJECTS)`, worded in review so
  it does not claim a boundary the ADR 0003 amendment says it is not.
- **Run.** `RunSpawner` takes a `project_key`, and a Run's environment gains
  `JIRA_ALLOWED_PROJECTS=<key>` (`run_spawner.ALLOWED_PROJECTS_VARIABLE`, whose docstring says
  what the check is and what it is not). `run_command.PROMPT` names the key through
  `build_run_command(skill, runs, project_key)`. `python3 -m grafana_jsm_sandbox.run_command` now
  takes `<skill> <runs> <project-key>`.
- **`reset.py`.** The JQL is templated on the key, quoted (`project = "KEY"`) so that a key
  which is also a JQL word still parses. `reset(project_key, jira_as, compose)`. `run_jira_as` is
  replaced by `jira_as_with(environment)`, which runs the real `jira-as` with only that
  environment. `main` reads `.env`, and on a `ConfigurationError` prints it and exits 1 before
  any jira-as or compose call.
- **`replay.py`.** `laptop_url`/`default_receiver` read `compose_environment()` by default, so a
  port moved only in `.env` is followed (step 01's deferred item). An unreadable `.env` stops
  `main` with the line named, not a traceback.
- **`tests/test_end_to_end.py`.** It takes the key and the credential from `.env` through a
  module fixture, so a skipped run never opens `.env`, and it passes a `Project(key, jira_as)`
  through its helpers.
- **`.env.example`.** It gains `DEMO_PROJECT_KEY=` (empty), the four field ids,
  `DEMO_QUEUE_URL`, and commented `BIND_ADDRESS`/`GRAFANA_HOST_PORT`/`RECEIVER_HOST_PORT`, with
  comments that say what reads each and what does not yet (the Skill). The container test now
  reads it with `read_env_file`. It asserts that the copied example is refused naming only
  `DEMO_PROJECT_KEY`, and that it starts once a key is added.
- **Docs.**
  - README: prerequisites; the `run_command` usage and the allow-list sentence; the laptop-mode
    table and refusal sentence; the clone step comment; the replay port sentence; the reset and
    end-to-end credential sentences; the Layout row for `demo_config.py`.
  - Runbook: the shell requirement; the `run_command` usage; the reset's project sentence; and,
    in review, a note under the stuck-Incident `deleteIssue` command that it is the shell's own
    `jira-as`, which must point at the demo's site, and that the committed settings refuse any
    key but `OPS` inside the repo.
- **`tests/test_grafana.py`** (review). Its Grafana URL is now `grafana_url()`, worked out on first
  use instead of at import. `laptop_url` reads `.env` by default now, and every suite collects
  this opt-in module, so at import it would have opened a real `.env` in the offline suite and
  failed collection over a line the reader refuses. `test_replay.py`'s
  `test_collecting_the_opt_in_grafana_checks_never_reads_env` guards it (it fails against the
  import-time version).
  - ADR 0003: an amendment for the project allow list.

**jira-as 2.0.0 source findings** (`~/.as-plugins-venv/lib/python3.13/site-packages`)

- **The environment wins over the settings file.**
  - `jira_as/config_manager.py:203-229` `get_allowed_projects`. `os.getenv("JIRA_ALLOWED_PROJECTS")`
    (`:211`) is used whenever it is set (`:213`), even when empty, which allows nothing. The
    settings file's `jira.allowed_projects` is read only in the `elif` (`:215`), that is, when
    the variable is absent.
  - `:231-244` `get_allow_site_operations` does the same for `JIRA_ALLOW_SITE_OPERATIONS` (`:233-238`).
  - **So the committed `.claude/settings.json` (`allowed_projects: ["OPS"]`) cannot veto a key
    the helpers set.** The helpers' jira-as children are not moved out of the repo, and
    `jira_as_environment`'s docstring says why.
- **How the settings file is found.**
  - `assistant_skills_lib/config_manager.py:51-63` `_find_claude_dir` walks up from `Path.cwd()`
    to the home directory and takes the first `.claude` directory. Inside this repo that is the
    committed one.
  - `:65-99` `_load_config` merges its `settings.json`, then its `settings.local.json`, under the
    `jira` key.
- **Where the credential comes from.** `jira_as/config_manager.py:96-120`: the three `JIRA_*`
  variables first (through `assistant_skills_lib/config_manager.py:131-140`, which also accepts
  the generic `SITE_URL`/`EMAIL`/`API_TOKEN`). The keychain (`:101-113`) and
  `settings.local.json` (`:115-120`) are consulted only when one of the three is missing. That
  is why all three come from `.env`.
- **Where the check applies.** Both paths call `project_guard.check_project_access`:
  - the CLI, `jira_as/cli/cli_utils.py:54-56`;
  - the `api call` surface, `jira_as/engine.py:70-80`, which gets the allowlist and site flag from
    the same `ConfigManager`.

  `jira_as/project_guard.py:1-5` says it is "a literal-reference check, not a JQL scope evaluator
  or an HTTP authorization boundary".
- **Other shell variables the child would otherwise inherit.** `JIRA_AS_TRANSPORT`
  (`engine.py:118`, can switch to simulation/responder/cassette), `JIRA_AS_SOCKET`,
  `JIRA_AS_RECORD`, `JIRA_MOCK_MODE` and `JIRA_FIELDS_CACHE_DIR`. The from-scratch environment
  drops all of them.
- **Checked offline** against an unreachable `http://127.0.0.1:9`, with `env -i`:
  - With `JIRA_ALLOWED_PROJECTS=DEMO` inside the repo, `search jql 'project = DEMO'` got through
    to the (failed) connection. Without the variable, inside the repo, it was refused by the
    committed file.
  - With `OPS` allowed:
    - `issue create -p PROD`, `comment add PROD-1`, JQL `project = PROD` and
      `api call deleteIssue --issueIdOrKey PROD-1 --confirm` were refused before sending.
    - So was a numeric `--issueIdOrKey 10001` ("invalid issue key").
    - A create carrying `"Sev-1"` in `--custom-fields`, and a comment body naming `PROD-7`, were
      not refused. Bodies and field JSON are not scanned for those commands.
    - `getServerInfo` without `JIRA_ALLOW_SITE_OPERATIONS` outside the repo is refused
      ("site access is disabled"), so a Run needs both variables.

**Test evidence**

- New `tests/test_demo_config.py`, 36 tests (32, plus 4 proxy cases in review; the compose
  fidelity lines gained a tab-before-`#` case, checked against `docker compose config`): the reader, the compose fidelity check, the
  project, the helper environment and the warning.
- Extended:
  - `test_reset.py` (+4): the key is used; a real `jira-as` stand-in on PATH records an
    environment from `.env` only, in a shell configured for production; no `.env` or no key means
    no jira-as or compose call.
  - `test_startup.py` (+6 cases).
  - `test_run_spawner.py` (+1).
  - `test_run_command.py` (+1, and the main usage).
  - `test_replay.py` (+4, one of them the review's collection guard for `test_grafana`).
  - `test_container.py` (the example now refused naming the key; +1 with a key).
- Python 3.11 basic-demo subset (the 13 listed files plus `tests/test_demo_config.py`):
  328 passed, 39 skipped (after the review fixes; 323 before them).
- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 3587 passed, 39 skipped (3m05s, after
  the review fixes; 3582 before them).
- `ruff check` is clean on the package. `ruff format --check` is clean on every touched file.

**Deferred / to note**

- **Between step 02 and step 03 the Skill still names `OPS`.** A Run whose key is not `OPS` gets
  a prompt and an allowlist naming the key and a Skill naming `OPS`, and its jira-as refuses the
  Skill's OPS searches. Step 03 renders the Skill from `.env`.
- **All-digit Fingerprint.** With the allowlist set, jira-as reads `fp-<digits only>` in JQL as
  an issue key of project `FP` and refuses the Match search. The probability is about
  (10/16)^16 per Alert, and the fixture's `fp-87e2f184874a3b71` is unaffected. It is recorded in
  the variable's docstring and ADR 0003. A fix would sit in the Skill's JQL or jira-as, not here.
- **Proxy variables for a Run** (audit F21/B10) stay a later decision. The helpers' own proxy
  passthrough was fixed in review (above).
- **Review nits left as they are.** `reset.main` builds `DemoProject` a second time after
  `jira_as_environment` has validated it; it is the same function on the same values, so it
  cannot drift, and it reads more plainly than pulling the key back out of the environment.
  The reader still differs from compose on `$` interpolation, `\n`-style escapes and
  `'it''s'` (compose refuses; the reader takes `it`); none occurs in the demo's values, and the
  docstring now names the first two instead of claiming compose's exact reading.
- **README line 36** still says Runs "may name that project and no other"; the `run_command` section
  says it is jira-as's literal-reference check and not a boundary. Step 11 rewrites the docs.
- **Laptop mode** (`python3 -m grafana_jsm_sandbox` on the host) still reads the shell's
  environment, not `.env`, as before. It now needs `DEMO_PROJECT_KEY` there too, and the README
  says so.
- `.env.example`'s `RECEIVER_PORT` knob (audit F22) and the full rewrite are step 11.

## Proposed settings change

Optional, not required by this step. The helpers and Runs set `JIRA_ALLOWED_PROJECTS`, which
overrides the committed file. Only a bare `jira-as` typed from inside the repo tree, by an
engineer or a laptop Claude session, still hits `allowed_projects: ["OPS"]` and is refused for
any other key. Verified offline: `jira-as search jql 'project = DEMO'` in the repo without the
variable gets `Project 'DEMO' is not permitted`. To make the repo key-neutral, remove the key
from `.claude/settings.json`:

```diff
 {
   "jira": {
-    "allowed_projects": ["OPS"],
     "allow_site_operations": true
   }
 }
```

The trade-off: with the key removed, a bare jira-as in the repo tree is unrestricted by project
unless the shell sets `JIRA_ALLOWED_PROJECTS`.
