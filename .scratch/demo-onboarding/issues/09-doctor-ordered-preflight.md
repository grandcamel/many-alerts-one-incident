# doctor: ordered preflight

Type: task
Status: resolved
Blocked by: 03, 05, 08

See [spec.md](../spec.md), step 09.

## Answer

**What changed**

- New `grafana_jsm_sandbox/doctor.py`:
  `python3 -m grafana_jsm_sandbox.doctor [--only LAYER[,LAYER...]] [--with-model]`, plus
  `--in-container`, which the stack layer runs. The runtime is stdlib only. The same
  version gate as `configure` gives Python < 3.11 one sentence and exit 2.
- **Layers.** They run in order: host, env, jira, facts, stack, grafana. It stops at the first
  layer with a FAIL and prints `not checked: <layers>; an earlier layer failed`.
  - **host**
    - Checks this Python, and Docker Engine (`docker version --format {{.Server.Version}}`).
    - Checks Compose v2 (`docker compose version --short`). Below 2.17 it warns and names
      `cpus` (and `pids_limit` below 2.2).
    - Checks jira-as 2.x. Below 2.0 is a FAIL; 3.x or later is a WARN.
    - Checks the pulled images (`docker image inspect`). They are read from
      `docker-compose.yml` with `${LGTM_IMAGE:-...}` interpolated, and the locally built
      `grafana-jsm-sandbox*` images are skipped. A missing image is a WARN naming `docker-admin`.
    - Checks the Grafana and Receiver ports on `BIND_ADDRESS`, from `.env` with the shell over it.
      A port is fine when free (a bind probe) or when `docker compose ps` shows this stack
      publishing it. Otherwise it is a FAIL naming the variable that moves it. A non-loopback
      `BIND_ADDRESS` is a WARN.
  - **env**
    - `.env` exists, and is readable UTF-8 (anything else is a FAIL line, not a traceback).
    - No value only the engineer can give (`JIRA_SITE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`,
      `CLAUDE_CODE_OAUTH_TOKEN`, `DEMO_PROJECT_KEY`) is left as `.env.example` has it. Other
      example values may be real defaults, which `.env` is free to keep.
    - `JIRA_SITE_URL` is https with no query. It is either a bare `*.atlassian.net` or
      `https://api.atlassian.com/ex/jira/<uuid>`; a custom domain is a WARN.
    - The Claude token is present and never printed. `sk-ant-api` is a FAIL; a token that is not
      `sk-ant-oat` is a WARN.
    - `DEMO_PROJECT_KEY` is set. `Settings.from_environment` accepts `.env`, which covers
      `RUN_MODEL`, `RUN_BUDGET_USD` and ports.
  - **jira**. Through `jira-as` with `jira_as_environment(.env)`, as `configure` does:
    - `getCurrentUser` comes first. A refusal there is classified and stops the layer.
    - Then `getServerInfo` (deploymentType Cloud), and `configure.check_project` and
      `check_permissions`.
  - **facts**
    - Runs `configure`'s `find_component` (only to know whether components is filled),
      `check_issue_type`, `check_fields`, `check_statuses` and `check_resolution`.
    - Then holds each `DEMO_*_FIELD` in `.env` against the id the project gives:
      - equal is OK;
      - `.env` empty while the project has one is a WARN;
      - `.env` naming a stale or absent id is a FAIL (a WARN for Major incident).
    - An empty `DEMO_QUEUE_URL` is a WARN.
  - **stack**
    - Reads `docker compose ps --all --format json`, both NDJSON and array forms.
    - lgtm, demo and rolldice must be running. Stopped traffic is a WARN.
    - demo `unhealthy` is a FAIL, and `starting` is a WARN.
    - Then runs `docker compose exec -T demo python3 -m grafana_jsm_sandbox.doctor
      --in-container --project-key <.env key> [--with-model]` and passes on only its
      `container`/`model` lines.
      - An image that predates doctor ("No module named") is told to rebuild.
      - A crash keeps whatever lines were printed and adds one redacted FAIL.
  - **grafana**. Stdlib `urllib`, with no proxy, on `laptop_url(GRAFANA_HOST_PORT, 3000)` as
    anonymous admin. It is the assertions of `tests/test_grafana.py` turned into checks:
    - one provisioned webhook at `http://demo:8080/notification`, sending Resolved;
    - the policy routes to it, with no child routes, `repeat_interval` 1m and `group_wait` ≤ 30s;
    - rule `rolldice-rate-zero` exists, with group interval 10, `for` 30s, both labels the
      Skill's field mapping reads (`severity`, `service`) and service=rolldice;
    - the rule's own prometheus expr, POSTed through the datasource proxy, returns ≥ 1 series;
    - rule state `inactive` is OK, any other state is a WARN.
- **`--in-container`**
  - Run as a command, it makes itself non-dumpable right after the version gate and before any
    other import, through the new dependency-free `grafana_jsm_sandbox/nondumpable.py` (the
    prctl helpers moved there from `__main__`, which imports them back). `in_container()` reports
    that outcome before it reads `os.environ`. If prctl fails, it prints one FAIL and stops
    without reading the environment.
  - Checks, in order:
    - non-dumpable;
    - `/proc/1/environ` unreadable. PermissionError is OK, readable is a FAIL (rebuild), running
      as root is a WARN;
    - `Settings.from_environment`;
    - `--project-key` against the container's `DEMO_PROJECT_KEY`. A mismatch is a FAIL,
      "recreate with `docker compose up -d demo`";
    - the rendered Skill carries the row `` | Project | `KEY` | `` and no `{{`;
    - `/rest/api/3/myself`, through a Forwarder of its own with a sentinel, so the request leaves
      exactly as a Run's does. It prints only the status and the Forwarder's diagnosis, never the
      body. A 3xx the Forwarder hands back is reported ("JIRA_SITE_URL redirects") and never
      followed past the Forwarder.
  - It starts no child with the real token. The Forwarder is a thread, and the model Run gets a
    Run's environment.
  - The package logger gets a `NullHandler`, so the Forwarder and spawner logs cannot interleave
    with the parsed stdout.
  - **Residual window**, documented in the module docstring and README: from the exec to the
    prctl, the doctor's own `/proc/<pid>/environ` holds the real token and is readable by the
    Runs' uid. That is now the interpreter's start-up alone; the package's imports (~0.45 s
    without bytecode, the container's case, per the review) come after the prctl.
- **`--with-model`**
  - It makes a working directory `doctor-<timestamp>-<hex>` under the container's runs directory.
  - It builds the argv with `build_run_command(runs, key, model=RUN_MODEL,
    budget_usd=RUN_BUDGET_USD, prompt=MODEL_PROMPT)`. There is a new `prompt=` seam in
    `run_command.py`, and only the last argument differs; a test asserts that.
  - It runs through the real `RunSpawner`, with a `_Nowhere` stand-in Forwarder whose URL is
    `http://127.0.0.1:9` and whose set/clear sentinel do nothing. The environment is exactly a
    Run's: throwaway sentinel, `JIRA_ALLOWED_PROJECTS`, the OAuth token, PATH and the trust store.
  - It reads the teed `transcript.jsonl` back. It reports:
    - the `model` from the init event (a different one is a WARN);
    - `jira-as` and `skill read`: the Bash `jira-as` call and the Read of
      `<runs>/.skill/incident-sync/SKILL.md`. A denial of exactly the call asked for
      (`jira-as --version`, the Skill's path) is a FAIL naming `claude-org-owner` (managed
      permission rules). A denied call the model wrote otherwise (a compound command, another
      path) is a WARN with no request, since the Run's own allow list may deny it. A call never
      made is a WARN;
    - `run`. The failure is `log_formatter.run_failure` via the spawner's `RunOutcome`, plus the
      `[hint]` text from `format_event`. The credits and model hints name `claude-org-owner`;
      the refused-token hint names none, since `claude setup-token` again is the engineer's own
      fix (the env layer names `claude-org-owner` when there is no token at all).
  - The Skill read also covers step 03's deferred question: does `Read(//<runs>/**)` reach
    `.skill`?
- **Shared Jira classification** (`refusal_line`). The laptop and the container both reduce
  Jira's answer to a status plus words, and both go through `configure.refused`, which uses
  `forwarder.IP_ALLOWLIST`. `configure.JiraRefused` now decides `ip_allowlist` on the unclipped
  messages, searching the body jira-as quotes after `Failed to <operation>: ` over the same
  `DIAGNOSED_BODY_BYTES` window `forwarder.diagnose` uses. Before, it searched the line clipped
  to 300 characters, so an allowlist page whose words came after its `<head>` sent the laptop
  (and `configure`) to the Jira admin while the container named the org admin.
  - On the laptop, the words are jira-as's messages, which carry the response body. That was
    verified offline with the real jira-as 2.0.0 against a loopback fake.
  - In the container, the words are `forwarder.diagnose(status, headers, body)`.
  - A 404 on whoami means `NOT_A_SITE` on both paths. The Forwarder's own "unreachable" 502 maps
    to configure's unreachable wording. That needs `forwarder.UNREACHABLE_BODY`, a new constant
    that replaces the inline bytes.
- **Deferred items from 05/06.** `HINT_CREDITS` now names `RUN_MODEL` ("set RUN_MODEL in .env to a
  model the account has credits for and recreate the container with `docker compose up -d demo`").
  `HINT_MODEL` already did. The README's quoted refused-Run samples (plain and logged) are
  updated, and a new test holds the README to the fixture's rendering.
- **Output format.** It is documented in the module docstring:
  - `[<layer>] OK|WARN|FAIL <check> — <message>[; ask: docs/admin-requests.md#<anchor> ...]`;
  - `not checked: ...`;
  - `READY` or `NOT READY: [<layer>] <check> — <message>`.

  Exit is 0 READY, 1 NOT READY, 2 usage or old Python (`--with-model` with an `--only` that
  leaves out `stack` is a usage error). Anchors used:
  - the eight `configure` anchors (via its checks);
  - `claude-org-owner`: token missing, denied asked-for call, credits/model hints;
  - `docker-admin`: images not pulled.

  Unlike configure, a WARN can carry an ask (images → docker-admin).
- **Docs.** README gains a `doctor` paragraph after `configure`, a Layout row, and a sentence on
  the exec route next to the healthcheck's `env -i`. `docs/demo-runbook.md`'s pre-demo checks
  mention doctor. `tests/conftest.py` lists `test_doctor.py` under `--basic-demo`.

**jira-as operations** (all read-only GETs through `jira-as api call`, each checked offline
with `jira-as api describe <operation>` against the installed jira-as 2.0.0):

- jira layer: `getCurrentUser` (GET `/rest/api/3/myself`), `getServerInfo`
  (`/rest/api/3/serverInfo`), `getProject` (`/rest/api/3/project/{projectIdOrKey}`),
  `getMyPermissions` (`/rest/api/3/mypermissions`), the last two through `configure`'s checks.
- facts layer, all through `configure`'s checks: `getProjectComponents`,
  `getCreateIssueMetaIssueTypes`, `getCreateIssueMetaIssueTypeId`, `getAllStatuses`,
  `searchResolutions`, and `getServerInfo` for a gateway `JIRA_SITE_URL`.
- How jira-as words a refusal was read in its source
  (`jira_as/error_handler.py`, `handle_jira_error`: `Failed to <operation>: <errorMessages or
  response.text>`) and exercised offline by the real-jira-as test against a loopback fake site.

**Test evidence**

- `tests/test_doctor.py`: 131 passed. It covers:
  - the fake runner for docker and compose;
  - `configure`'s fake jira-as extended with whoami and serverInfo;
  - a fake Grafana HTTP server whose healthy answers are built from the provisioning YAML;
  - `FakeUpstream` behind a real Forwarder for 200, 302 (reported, not followed), 401, 403 with
    an IP-allowlist body (short, and with the words past 300+ characters of `<head>`), 403, 404,
    500 and unreachable;
  - a stand-in `claude` on PATH printing canned streams, including
    `fixtures/run-transcript-refused.jsonl`;
  - an ordering test that `refuse` runs before the environment is read, and a subprocess test
    that, run as `-m ... --in-container`, the prctl runs when only
    `grafana_jsm_sandbox.nondumpable` of the package is loaded, and a failed prctl ends in one
    FAIL line, NOT READY and exit 1 with no Jira call;
  - the rule's `severity`/`service` labels, a default kept from `.env.example`, a denied
    compound command (WARN, no request), the token hint's missing request, and `--with-model`
    without `stack` (exit 2);
  - the real jira-as, offline against the loopback fake, classified the same as the container
    path (it ran here);
  - the old-Python sentence (it ran here).
- `tests/test_run_command.py`: +1 (the prompt seam). `tests/test_log_formatter.py`: +2 (the
  credits hint names RUN_MODEL; the README quotes the refused rendering).
  `tests/test_configure.py`: +1 (an allowlist page read in full before the line is cut).
  `tests/test_startup.py` imports `PR_SET_DUMPABLE` from its new home.
- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 4103 passed, 41 skipped (3m17s),
  twice.
- Python 3.11 basic-demo (fresh-clone venv, `--basic-demo`): 843 passed, 41 skipped, twice.
- `ruff check` and `ruff format --check` are clean on every touched Python file.
- Smoke run offline: `doctor --only host,env,grafana` on this laptop printed real host lines, then
  a FAIL for no `.env`, `not checked: grafana` and NOT READY, exit 1. `--only env --with-model`
  exits 2. `env -i ... python3 -m grafana_jsm_sandbox.doctor --in-container` on the Mac prints
  the non-dumpable WARN, the settings FAIL (with its fix) and NOT READY, exit 1.

**Deferred / unverified (live checks at the end)**

- `--in-container` and `--with-model` have not run in a real container. That needs an image
  rebuild and `compose up`, which is out of scope offline. The first live run should confirm:
  - `/proc/1/environ` is EACCES for the exec'd doctor;
  - the Forwarder path answers 200;
  - the model Run's init `model` string for `claude-opus-5`;
  - that `Read(//app/runs/**)` covers `.skill`.
- A container created from an older `.env` is caught only through the project key
  (`--project-key`). Changed field ids or `RUN_MODEL` in `.env` without a recreate are not
  detected. Compose's `com.docker.compose.config-hash` label could catch any drift, but it is
  unverified whether env_file content feeds the hash.
- The IP-allowlist 403 wording is still the audit's. Real jira-as was shown to carry the body
  into its messages, but not against a real allowlist.
- The `docker compose ps --format json` field names (`Service`, `State`, `Health`, `Publishers`,
  `PublishedPort`) are from compose's documented output, not seen here: no stack was up.
- The model Run costs a little usage each time, so it stays opt-in.

**Doc follow-ups for step 11**

- Fold the README doctor paragraph into the Quickstart: `configure --write`, `doctor`, `up`, then
  `doctor` again (and `--with-model` once).
- `docs/admin-requests.md` must have the `claude-org-owner` and `docker-admin` headings that
  doctor names.
- Describe doctor's line format, layer names, check names and exit codes for the setup skill
  (step 12). A WARN may carry an `ask:`.
- ADR 0002's amendment could name `doctor --in-container` as an exec that closes itself before
  its imports, with its residual window (interpreter start-up), and `nondumpable.py` as where
  the prctl lives.
- `.env.example` may carry real, non-empty defaults for any variable except the five the
  engineer alone gives (`doctor.ENGINEERS_OWN`); those five must stay placeholders or empty.
- README's refusal sentence ("classified exactly as the laptop's is") now holds for long
  allowlist pages too; keep it when the doctor paragraph moves.

**Review fixes applied when finalizing**

- must-fix: the laptop's IP-allowlist match ran on the 300-character clipped line
  (`configure.JiraRefused.ip_allowlist`, above).
- should-fix: prctl before the imports (`nondumpable.py`); the rule's `severity` label; the
  placeholder check limited to the engineer's own variables.
- nits: the container's whoami no longer follows a redirect; only a denial of exactly the
  asked-for call names managed rules; fixes appended to the FAIL lines that lacked one (facts
  jira-as, in-container timeout, Grafana API errors, no prometheus query, rule problems,
  container settings); the version-gate comment says compiled vs executed correctly; an
  unreadable or non-UTF-8 `.env` is a FAIL line; `--with-model` without `stack` is exit 2; the
  refused-token hint names no request.

No settings change is needed.
