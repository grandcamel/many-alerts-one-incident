# verify: replay and live

Type: task
Status: resolved
Blocked by: 02

See [spec.md](../spec.md), step 10.

## Answer

**What changed**

- New `grafana_jsm_sandbox/verify.py`, `python3 -m grafana_jsm_sandbox.verify [--replay | --live]`.
  - It reads `.env` through `demo_config`: the key from `DemoProject`, and jira-as from
    `jira_as_environment` and `reset.jira_as_with`.
  - Like `configure` and `doctor`, it gates on Python 3.11: an older Python gets exit 2 and one
    sentence, not a traceback.
  - Every outside party comes through an injected `World` dataclass: `jira_as`, `compose`,
    `post`, `grafana_state`, `now`, `sleep` and `out`.
- **Preflight.**
  - It fails, naming `reset`, when an *open* Match exists, because the Runs would then comment on
    that Incident instead of creating one.
  - It records every Incident already carrying the Fingerprint label, so a rehearsal's leftover
    is never taken for this run's.
  - It asks Grafana for the rule's state. `--live` needs the rule Normal and evaluated.
    `--replay` fails when the rule is Firing or Pending, and only WARNs when Grafana does not
    answer, since that is one reason to replay.
- **`--replay`** (the default) posts the Firing, then waits for the Incident to be created with
  its opening comment. It then posts the repeat and waits for Work in progress with at least two
  comments. Last, it posts the Resolved and waits for Completed.
- **`--live`** runs `docker compose stop traffic` and waits for Grafana Firing, then for created,
  commented and Work in progress. Only then does it `docker compose start traffic`, wait for
  Grafana Normal and then Completed.
  - A `finally` starts the traffic on the way out after a failure, a failed stop or a Ctrl-C. It
    first prints a `WAIT traffic started` line that gives the manual command, in case a second
    Ctrl-C cuts the start short.
  - Compose output is captured, so it does not land between the parsed lines.
- **Deliberate deviation from the spec's wording.** The spec says `--live` "starts [the traffic]
  again after the Firing". Doing that straight after the Firing would stop Grafana's repeat, and
  the Incident would never reach Work in progress. So verify restarts the traffic only after
  Work in progress, which is the runbook's order (the T+2:50 row).
- **Timeouts.** The defaults come from the rehearsal record
  (`.scratch/alert-to-incident-sync/issues/08`), with wide margins, and each has a flag:
  - `--firing-timeout`: 180s (measured about 60s).
  - `--repeat-timeout`: 180s (measured 70s after the first Run).
  - `--resolved-timeout`: 120s (measured 15–19s).
  - `--run-timeout`: each Run's stage in all. The default is `.env` `RUN_TIMEOUT` (or 300)
    plus 60, so 360s. In live, the Work in progress stage gets the repeat timeout plus the Run
    timeout.
- **Failures name a cause.**
  - A timed-out stage says what did not happen and where to look, e.g. "no Incident within 360s
    of posting the Firing: check `docker compose logs demo` for [FAILED]". When an Incident with
    another `fp-` label appeared meanwhile, the message suggests `--fingerprint`.
  - A status off the path (e.g. Canceled) fails at once.
  - Completed without a resolution fails with `; ask: docs/admin-requests.md#jira-admin-resolution-screen`.
  - A resolution other than Done, fewer than three comments, or a second Incident for one Firing
    is a WARN; with two Incidents, the earliest is watched.
  - jira-as failures are ridden out up to three in a row, then FAIL pointing at
    `doctor --only env,jira`. They cover a refusal, a non-JSON answer, JSON of another shape, and
    a `subprocess.TimeoutExpired`, which is said as "no answer within 120s".
  - jira-as missing from PATH fails at once, naming `doctor --only host`.
  - Every message passes through `doctor.said`, so it is redacted.
- **Cleanup.** It never creates, transitions, closes or deletes anything. A final `NOTE cleanup`
  line says where the Incident was left and that `reset` takes out a leftover. In `--live`, once
  the traffic is running again, the note adds that the Resolved's Run may still complete the
  Incident, and that `reset --dry-run` shows what is left.
- `tests/test_end_to_end.py` now just runs `verify.main(verify_arguments(os.environ))`. It is
  still opt-in through `DEMO_END_TO_END`, and `=live` selects `--live`. `DEMO_RECEIVER_URL` is
  passed only to the replay.
  - **Behaviour change:** the test no longer resolves and closes the Incident it watched.
  - `DEMO_END_TO_END_RUN_TIMEOUT` (per Run) replaces `DEMO_END_TO_END_TIMEOUT` (whole run).
- `doctor.py`: `rule_states(base, uid)` is pulled out of `state_line` so verify can reuse it.
  A rule listed without a `state` now counts as not evaluated rather than the string `None`.
  Otherwise doctor's behaviour is unchanged.
- `tests/conftest.py`: `test_verify.py` is in `BASIC_DEMO_TESTS`.
- `README.md`: a verify paragraph after doctor's, a Layout row, and the corrected e2e paragraph
  (it runs verify and closes nothing). `docs/demo-runbook.md`: one sentence on verify in the
  pre-demo checks, and "no `verify`" in the Eyes step.

**Usage, output format and exit codes** (also in the module docstring and `--help`)

```
python3 -m grafana_jsm_sandbox.verify [--replay | --live] [--receiver URL]
    [--fingerprint FP] [--firing-timeout S] [--repeat-timeout S]
    [--resolved-timeout S] [--run-timeout S]

[+<seconds>s] WAIT|OK|WARN|FAIL|NOTE <stage> — <message>[; ask: docs/admin-requests.md#<anchor>]
VERIFIED: <key> Open → Work in progress → Completed with resolution <name> in <seconds>s
NOT VERIFIED: <stage> — <what the first FAIL said>
```

- The stages, in order: `preflight`, then `traffic stopped` and `firing` (live) or `posted`
  before each Run's stage (replay), then `created`, `commented` and `work in progress`, then
  `traffic started` and `normal` (live), then `completed`. `cleanup` (NOTE) comes last, and
  NOT VERIFIED names `interrupted` after a Ctrl-C.
- A FAIL ends the watch, and NOT VERIFIED repeats the first FAIL's stage and text. After a FAIL
  or a Ctrl-C, the only stage lines before the cleanup note are `--live`'s start of the traffic
  on the way out: a WAIT, then an OK, or a second FAIL when compose refused.
- Exit codes: 0 VERIFIED; 1 NOT VERIFIED; 130 interrupted (a Ctrl-C before the watch began
  prints only `NOT VERIFIED: interrupted — …`); 2 for bad arguments (including `--receiver` with
  `--live`), a `.env` error, or Python older than 3.11.

**jira-as operations** (all read-only; jira-as 2.0.0, checked offline with `--help` and its
source under `~/.as-plugins-venv`)

- `search jql <JQL> --fields key,status,labels -o json [--page-token T]`, through `reset.search`,
  which pages on `nextPageToken`/`isLast`. `reset` already uses it. The JQL:
  - `project = "<KEY>" AND issuetype = Incident AND labels = "fp-…"`, the labelled Incidents;
  - the same plus `AND statusCategory != Done`, the Match (ADR 0004);
  - `project = "<KEY>" AND issuetype = Incident AND created >= "-<N>m"`, what was created
    meanwhile.
- `issue get <KEY> --fields status,resolution -o json`, read as `fields.status.name` and
  `fields.resolution.name`. `--fields/-f` and `--output/-o` are in its help. The old e2e test
  used the same call.
- `collaborate comment list <KEY> -o json`, read as `total`. `--output/-o` is in its help, and
  `jira_client.py` documents the answer as `comments`, `total`, `startAt`, `maxResults`.

**Test evidence**

- `tests/test_verify.py`: 78 tests (67 functions), all passing.
  - They drive a simulated demo on a fake clock with the rehearsal's timings (Pending +30s,
    Firing +60s, group wait 8s, repeat every 70s, Normal +15s, Runs of 30s). jira-as is a fake
    that answers only read calls and fails the test on any write, and compose is faked too.
  - Real HTTP is used for two things: posts at the conftest's real Receiver (three spawns
    recorded), and the rule state from `test_doctor`'s FakeGrafana on an ephemeral port.
  - Also covered: a stand-in `docker` on PATH for `run_compose`, the old-Python subprocess test,
    and the e2e argument builder.
- Focused, `tests/test_verify.py tests/test_end_to_end.py tests/test_doctor.py`: 209 passed,
  1 skipped (the opt-in e2e).
- Full suite, `python3 -m pytest -q -p no:cacheprovider`: 4182 passed, 41 skipped (3m14s, 3m17s), twice.
- Python 3.11 basic-demo (fresh-clone venv, `--basic-demo`): 922 passed, 41 skipped, twice.
- `ruff check` and `ruff format --check` are clean on every touched Python file.

**Review fixes applied when finalizing**

- should-fix: a `subprocess.TimeoutExpired` or a `FileNotFoundError` from jira-as escaped as a
  traceback. It is fixed with the `JIRA_AS_FAILURES` tuple in `wait_for`, `preflight` and
  `elsewhere`; a missing jira-as fails at once with `NO_JIRA_AS`. The same pass found a second
  escape: `created` read the new Incident after its wait rather than inside it, so a failed read
  there also gave a traceback. The read now happens inside the look. A JSON answer of an
  unexpected shape from `issue get` is a `ValueError`, ridden out like the rest. New tests:
  - a timeout once, ridden out;
  - a timeout again and again, FAIL in a line;
  - a timeout in live, where the traffic is still started;
  - no jira-as at preflight;
  - jira-as gone mid-watch, failing at once;
  - another shape once, and every time.
- should-fix: this Answer and the status.
- nits:
  - `rule_states`'s docstring, and a missing state skipped;
  - NOT VERIFIED for `traffic started` now repeats its FAIL text, and the docstring documents
    the way-out lines;
  - the live cleanup note's caveat;
  - `--run-timeout` help wording, and `--receiver` with `--live` is now a usage error (the e2e
    builder passes `DEMO_RECEIVER_URL` only to the replay);
  - a Ctrl-C during setup is exit 130 with a NOT VERIFIED line;
  - the manual traffic-start command is printed before the way-out start.

**Deferred / unverified (live checks at the end)**

- Not run against a live stack or Jira. The first live run should confirm:
  - the `issue get` and `comment list` JSON shapes (`fields.status.name`, `resolution`, `total`);
  - that the relative-date JQL `created >= "-Nm"` is accepted;
  - that Grafana's `/api/prometheus/grafana/api/v1/rules` state strings are `inactive`, `pending`
    and `firing`;
  - that the 360s-per-Run default is not too slow.
- The Fingerprint defaults to the canned Firing's, because Grafana derives it from the labels
  this repo provisions. If another Grafana version computes it differently, the created stage
  times out, names the other `fp-` label it saw, and suggests `--fingerprint`.
- Completed Incidents from verify runs accumulate in the project, outside the queue. `reset`
  leaves them alone.
- On a timeout, verify does not grep `docker compose logs demo` itself; it only points there. A
  read-only log grep could come in the setup skill (step 12).

**Doc follow-ups for step 11**

- Put `verify` in the Quickstart after `doctor` (and after the alert), before `reset`, and fold
  the README verify paragraph into it.
- Describe verify's line format, stage names and exit codes for the setup skill (step 12). A FAIL
  may carry an `ask:`, and in `--live` a way-out `traffic started` WAIT/OK/FAIL may follow the
  first FAIL.
- `docs/admin-requests.md` must have the `jira-admin-resolution-screen` heading that verify
  names.
- The runbook could offer `verify --live` as a rehearsal tool, well before the demo.

No settings change is needed.
