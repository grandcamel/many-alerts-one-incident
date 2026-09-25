# A newcomer's host checks work

Type: task
Status: resolved

See [spec.md](../spec.md), step 07.

## Answer

**What changed**

- **`pip install -e '.[dev]'` works.** `pyproject.toml` gains `[build-system]`
  (`setuptools>=64`, the first with the PEP 660 editable installs `-e` needs) and
  `[tool.setuptools] packages = ["grafana_jsm_sandbox"]`.
  - The explicit list is required. Without it setuptools refuses with "Multiple top-level
    packages discovered in a flat-layout" (skill, certs, docker, grafana, fixtures, prototype,
    grafana_jsm_sandbox).
  - The install worked in throwaway venvs on 3.11.16 and 3.13.7. Each imports
    `grafana_jsm_sandbox` from the worktree as an editable install, with pytest and PyYAML.
- **Python 3.11 and `ssl.OP_LEGACY_SERVER_CONNECT`.** 3.11's `ssl` does not name it, so three
  chapter-two test files failed to collect there with an AttributeError.
  - `_verify_context_readback` in `forwarder_upstream.py` now reads
    `getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)`. 0x4 is OpenSSL's
    `SSL_OP_LEGACY_SERVER_CONNECT`.
  - `tests/test_forwarder_upstream.py` builds a module constant the same way and uses it in its
    three places. A new test asserts the constant is 0x4, which on 3.12+ proves the fallback is
    the bit `ssl` itself uses.
  - The AST scoping test in `test_forwarder_upstream_adversarial.py` now counts the option name
    as a string constant as well as an `ssl.` attribute. The invariant still holds: the name
    appears exactly once, inside the read-back.
- **`--basic-demo`.** `tests/conftest.py` registers the option and an explicit
  `BASIC_DEMO_TESTS` list: the 15 known basic-demo files plus the new `test_basic_demo.py`.
  - Under the option, `pytest_ignore_collect` passes over every `test_*` file that is not listed
    or not in `tests/`, before it is imported.
  - Listed files get None, not False, so pytest's own `--ignore` and `norecursedirs` still
    apply to them.
  - Without the option the hook returns None for everything, so the default run is unchanged.
  - **A file named on the command line is still collected.** pytest does not ask
    `pytest_ignore_collect` about paths it was given: `--basic-demo tests/test_forwarder_upstream.py`
    collects its 251 tests. This is kept, since whoever names a file asked for it. The
    docstring says so. (The implementer's report claimed the reverse; review corrected it.)
- **`tests/test_basic_demo.py`** checks four things:
  - every listed file exists;
  - an AST rule, parametrized over every test file: a file is on the list exactly when it
    imports nothing from chapter two (`grafana_jsm_sandbox.forwarder_*`, `prototype.*`, or an
    unlisted test module). Today's split matches the rule exactly;
  - the hook's behaviour with and without the option;
  - a child `pytest --basic-demo --collect-only` with a census plugin, which must collect
    exactly the listed files and load no chapter-two module.
  - A mutation check (putting `test_timing_outcomes.py` on the list) failed both the rule test
    and the census test.
- **Replay pause timing is no longer a wall-clock upper bound.**
  - `replay()` gains a keyword-only `sleep=time.sleep` seam.
  - The old `2*pause <= elapsed < 3*pause` test is replaced by two tests. One records the order
    of posts and pauses against the real Receiver: post, pause, post, pause, post. The other
    keeps the real sleep and asserts only the lower bound.
  - `tests/test_replay.py` passed 5 of 5 runs with a CPU burner on every core.
- **README "Running the tests"** says `pip install -e '.[dev]'` installs the dev dependencies,
  and gives `python3 -m pytest --basic-demo` with a one-line gloss of chapter one.

**Test evidence**

- Before: `pytest --collect-only` on 3.11 gave 3 collection errors (test_forwarder_upstream,
  _adversarial, _integration).
- Full suite on python3 (3.13.7), `python3 -m pytest -q -p no:cacheprovider`:
  3851 passed, 41 skipped (2m55s).
- Full suite on 3.11 (implementer's editable venv): 3851 passed, 41 skipped, with no
  collection errors.
- The 3.11 basic-demo subset (fresh-clone venv, the 15 files plus `tests/test_basic_demo.py`):
  591 passed, 41 skipped. `--basic-demo` on the same venv: 591 passed, 41 skipped.
- ruff check is clean on every touched Python file.

**Deferred / to note**

- **pip needs a package index.** pip's isolated build fetches `setuptools>=64`, and the dev
  extra fetches pytest and PyYAML. A newcomer behind a registry mirror has to point pip at it.
  Step 11's README or admin-requests should say so.
- **README wording.** Only two sentences were added. Step 11's rewrite should fold them into
  the Quickstart. CLAUDE.md's test command could mention `--basic-demo` (step 11).
- **Where the option lives.** `--basic-demo` is registered in `tests/conftest.py`, not a root
  conftest. It works from the repo root (testpaths) and for any path under `tests/`. A run aimed
  only outside `tests/` would reject the flag as unknown.
- **The chapter-two rule is by name.** Chapter two is `grafana_jsm_sandbox.forwarder_*` plus
  `prototype.*`. If chapter two gains a module under another name, `is_chapter_two` in
  `tests/test_basic_demo.py` needs the new prefix.
- `license = {text = "MIT"}` is the table form that recent setuptools calls deprecated. It is
  left alone rather than changed in passing.
- `test_basic_demo.py` spawns one child pytest (`--collect-only`, 1-2 s) per run.

No settings change is needed.
