# Pins and Run knobs

Type: task
Status: resolved
Blocked by: 02

See [spec.md](../spec.md), step 06.

## Answer

**What changed**

- **lgtm is pinned.** `docker-compose.yml` now has
  `${LGTM_IMAGE:-grafana/otel-lgtm:0.33.0@sha256:475319e883b66594d1a2f22ef168c2459802bb94548e6f25d9782bd5f5c19a3a}`.
  - The local `grafana/otel-lgtm:latest` has RepoDigest `sha256:475319e8…c19a3a`, and its labels
    say `org.opencontainers.image.version=0.33.0` (created 2026-09-11, revision `054ceb84`).
  - `docker buildx imagetools inspect grafana/otel-lgtm:0.33.0` gives an OCI index with digest
    `sha256:475319e883b66594d1a2f22ef168c2459802bb94548e6f25d9782bd5f5c19a3a`. It holds
    linux/amd64 (`sha256:da46299699c61dcf4ebcbbfb5004997ea20bc869353570c5824ad5a906e4449c`) and
    linux/arm64 (`sha256:f85f5f8fc8015e238367f6a75b48757134f1d767413ff369e18b74ebd07fcd79`),
    plus two attestation manifests.
  - Not a match: `v0.33.0` does not exist on Docker Hub. `0.33.1` and today's `latest` are both
    `sha256:d6c52678ab5b7144f27ae569fd778608121c0f4a10eb411983750a0d67c1fbe3`, which shows that
    `latest` has already moved on since the laptop pulled it.
  - `docker compose config`, run on a scratch copy against a temporary env built from
    `.env.example`, resolves the default to the pinned reference, and `LGTM_IMAGE=...` in the
    shell replaces it. `.env.example` documents `LGTM_IMAGE` (commented).
  - **The pin moves Grafana a major version.** The pinned image carries Grafana 13.2.1
    (`GRAFANA_VERSION=v13.2.1` in its env; the review's `--network none` run gave
    `grafana --version` 13.2.1). `docs/research/eyes-into-grafana-2026-09.md` records the
    laptop's `latest` on 2026-09-15 as the 2026-01-09 pull, Grafana 12.3.1, and the README's
    3m30s/$0.47 lifecycle was committed on 2026-09-14, so it ran on 12.3.1, not on the pin.
    The alerting provisioning path `/otel-lgtm/grafana/conf/provisioning/alerting` still
    exists in the pinned image. README's pin paragraph now says so.
- **`RUN_MODEL`, default `claude-opus-5`.** It is `run_command.DEFAULT_MODEL`, read by
  `Settings.from_environment` (`__main__.RUN_MODEL_VARIABLE`), and passed as `--model` on every
  Run's argv. Blank means the default. A name with whitespace or a leading `-` is refused at
  startup, named alongside every other failure, because a leading `-` would reach Claude Code as a
  flag. `serve` logs `runs use model <m> (RUN_MODEL)` once the Receiver is listening
  (`log_run_knobs`).
- **`RUN_BUDGET_USD` gives `--max-budget-usd`.** Claude Code 2.1.272 in the image lists
  `--max-budget-usd <amount>  Maximum dollar amount to spend on API calls (only works with --print)`
  (`docker run --rm --entrypoint claude grafana-jsm-sandbox:latest --help`; `--version` gives
  2.1.272). The variable is optional with no default: unset means no flag, and startup logs
  `runs have no spending cap (RUN_BUDGET_USD is not set)`. When set, it must be a finite positive
  number, or startup refuses naming it. Startup logs `each run may spend at most $<n>`.
- **Hints name the knobs.** `HINT_MODEL` says to set `RUN_MODEL` in `.env` and recreate with
  `docker compose up -d demo`. `HINT_BUDGET` names `RUN_BUDGET_USD`.
- **Healthcheck through `env -i`** (deferred from step 01's review). The test is now
  `[CMD, env, -i, /usr/bin/python3, -c, ...]`, and the compose comment says why: Docker gives
  exec'd processes the whole container environment, as the Runs' uid and dumpable, so the
  healthcheck's Python held the real token in `/proc/<pid>/environ` every 10 s.
  - `docker run --rm --entrypoint sh grafana-jsm-sandbox:latest -c 'command -v env; command -v python3'`
    gives `/usr/bin/env` and `/usr/bin/python3`.
  - In a throwaway container of the local image (`--network none`, read-only, caps dropped, fake
    credentials, no compose), the exact probe exited 0 against the running Receiver and 1 against
    a wrong port. The same `env -i` probe read its own `/proc/self/environ` as `b''`, while a plain
    exec listed `JIRA_API_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN`.
  - There is an ADR 0002 amendment (step 06), and README now says only `docker compose exec`
    still carries the token.
- **Docs.**
  - README:
    - `build_run_command` names `--model`/`--max-budget-usd`;
    - the variable table gains `RUN_MODEL` and `RUN_BUDGET_USD`;
    - the lgtm pin and `LGTM_IMAGE` are described;
    - the fixture samples are marked as recorded on Fable 5.1;
    - the 3m30s/$0.47 measurement says it was Fable 5.1 and is pending re-measurement on Opus 5.
  - `docs/demo-runbook.md` qualifies its two cost statements the same way.
  - `.env.example` has `RUN_MODEL` and `RUN_BUDGET_USD` (commented, with honest comments).

**Test evidence**

- New and changed tests:
  - `tests/test_run_command.py`: +7. Covers the default `--model claude-opus-5`, the override,
    no budget flag by default, the budget value (3 cases), the allow list and prompt unchanged by
    the knobs, and the by-hand CLI printing `--model`.
  - `tests/test_startup.py`: +22 cases. Covers the model default, override and blank; bad models
    (3); no budget by default; budgets parsed (3); bad budgets (6); all named together; `serve`
    hands the spawner the argv with model and budget; the two startup log lines; and the log
    order after listening.
  - `tests/test_container.py`:
    - the healthcheck test follows the new argv;
    - new `test_the_healthcheck_starts_with_an_empty_environment`;
    - the lgtm pin by tag and index digest;
    - `LGTM_IMAGE` override and its presence in the example;
    - no pulled image is `:latest` or untagged (parametrized over the pulled services);
    - a text scan that any `:latest` in the file is only a locally built image's name;
    - `RUN_MODEL`/`RUN_BUDGET_USD` in the example;
    - an opt-in `DEMO_CONTAINER` test that runs the healthcheck's own argv via `compose exec`
      and asserts the probe's environ is empty.
  - `tests/test_log_formatter.py`: +2 (the hints name `RUN_MODEL` and `RUN_BUDGET_USD`).
- Focused (`test_run_command`, `test_startup`, `test_container`, `test_log_formatter`,
  `test_run_spawner`, `test_receiver`): 322 passed, 32 skipped.
- Python 3.11 basic-demo subset (the 15 listed files): 505 passed, 41 skipped.
- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 3764 passed, 41 skipped (2m56s).
- `ruff check` and `ruff format --check` are clean on every touched Python file.
- After review fixes (test docstring on the pin, the serve-order test breaking out through its
  `log_run_knobs` stand-in instead of patching `threading.Event.wait` process-wide, the live
  environ check asserting the exec succeeded, README wording and reflow): full suite 3764
  passed, 41 skipped (2m51s); Python 3.11 basic-demo subset 505 passed, 41 skipped.
- Review nits left: the startup log prints the budget as a float (`$2.0`), and `HINT_CREDITS`
  does not name `RUN_MODEL` (changing it would also change the README's quoted refused-Run
  sample). Both are harmless.

**Deferred / to note**

- **`:latest` in the compose file (owner decision).** `grafana-jsm-sandbox:latest` and
  `grafana-jsm-sandbox-rolldice:latest` remain. They are the names compose gives the two images
  it builds locally, and nothing is pulled by them. The test allows `:latest` only on a service
  with `build:`. Renaming them would touch the spec's own docker commands and the docs, so that
  is left for a decision: either rename the local tags (e.g. `:demo`, with the docs and the
  spec's commands), or record in the spec that "no `:latest`" means pulled images only, which
  is what the tests encode.
- **Pin rehearsal (live, owed).** 0.33.0 is what the laptop's `latest` was on 2026-09-23, not a
  release the demo was rehearsed on. The recorded lifecycle ran on Grafana 12.3.1; the pin is
  13.2.1. The owed live lifecycle on the pin must show the provisioned rule loading, firing when
  traffic stops, and resolving when it resumes on Grafana 13: with noDataState OK, a rule that
  silently never fires is exactly the F12 risk the pin exists to prevent.
- **No default budget.** The spec gave none, so an unset `RUN_BUDGET_USD` means no cap. The cap
  is Claude Code's own estimate-based check, not a billing limit (ADR 0013), and the docstring
  says so.
- **By-hand CLI.** `python3 -m grafana_jsm_sandbox.run_command` prints the default model and no
  budget whatever `.env` says. Its docstring and README say so.
- **Unmeasured on Opus 5.** The Opus 5 timing and cost are unmeasured, and the docs say
  "pending re-measurement".
- **Still exposed.** `alpine:3.20` and the Dockerfiles' `FROM` tags are pinned by tag only, not
  digest, which is outside this step. Every `docker compose exec demo ...` (step 09's
  `doctor --in-container` among them) still carries the token. ADR 0002's lasting fix stands.

No settings change is needed.
