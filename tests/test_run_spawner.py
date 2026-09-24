"""The real Run spawner: the Receiver starting one headless Claude as a child process.

Every test here starts a real child process with a stand-in for the Claude CLI,
because what the ticket asks about a Run is true of the process or it is not
true at all: the environment it was given, what its sentinel can reach, what its
output turned into in the log, and whether a stuck one can be killed.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import pytest

from grafana_jsm_sandbox.notification import NOTIFICATION_FILENAME
from grafana_jsm_sandbox.receiver import Receiver, Run
from grafana_jsm_sandbox.run_spawner import (
    ALLOWED_PROJECTS_VARIABLE,
    ANTHROPIC_TOKEN_VARIABLE,
    SITE_OPERATIONS_VARIABLE,
    TRUST_STORE_VARIABLES,
    RunSpawner,
)
from tests.conftest import (
    REAL_EMAIL,
    REAL_TOKEN,
    firing_notification,
    http_request,
    post_notification,
    wait_for_log,
)

ANTHROPIC_TOKEN = "an-anthropic-oauth-token-no-forwarder-can-hide"

PROJECT_KEY = "SANDBOX"
"""The demo's project, as `DEMO_PROJECT_KEY` names it: deliberately not OPS."""

ENVIRONMENT_FILE = "environment.json"
"""Where a stand-in Run writes the environment it was started with."""

PLATFORM_ADDITIONS = {"LC_CTYPE", "__CF_USER_TEXT_ENCODING"}
"""What macOS adds to every child process below the spawner. The container is Linux
and adds nothing, so these are excluded rather than allowed for."""

A_RUNS_VARIABLES = {
    ANTHROPIC_TOKEN_VARIABLE,
    "JIRA_EMAIL",
    "JIRA_SITE_URL",
    "JIRA_API_TOKEN",
    ALLOWED_PROJECTS_VARIABLE,
    SITE_OPERATIONS_VARIABLE,
    "PATH",
}
"""Everything a Run is started with when the Receiver has no trust store to hand on."""

SYSTEM_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
"""Where the image points every TLS client, and so what a Run inherits (ticket 02)."""


def _program(*parts: str) -> list[str]:
    """A stand-in for the Claude CLI: this interpreter running the given source."""
    return [sys.executable, "-c", "\n".join(parts)]


DUMP_ENVIRONMENT = f"""\
import json, os, pathlib
pathlib.Path({ENVIRONMENT_FILE!r}).write_text(json.dumps(dict(os.environ)))
"""

CALL_JIRA = """\
import base64, os, urllib.request
credential = f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()
request = urllib.request.Request(
    os.environ["JIRA_SITE_URL"] + "/rest/api/3/search/jql?jql=project+%3D+OPS",
    headers={"Authorization": "Basic " + base64.b64encode(credential).decode()},
)
urllib.request.urlopen(request, timeout=5).read()
"""

EMIT_A_TRANSCRIPT = """\
import json
for event in [
    {"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Searching OPS for a Match."},
        {"type": "tool_use", "name": "Bash", "input": {"command": "jira-as search jql 'project = OPS'"}},
    ]}},
    {"type": "result", "subtype": "success", "duration_ms": 1200, "num_turns": 2},
]:
    print(json.dumps(event), flush=True)
"""

COMPLAIN_AND_FAIL = """\
import sys
print("claude: onboarding was never accepted", file=sys.stderr)
sys.exit(3)
"""

LEAK_A_CREDENTIAL_ON_STDERR = """\
import sys
print("Authorization: Basic c2VudGluZWw6bm90LWZvci1hLXNjcmVlbg==", file=sys.stderr)
sys.exit(1)
"""

HANG = """\
import time
time.sleep(30)
"""

HANG_WITH_A_CHILD_OF_ITS_OWN = """\
import subprocess, sys, time
subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
time.sleep(30)
"""
"""What a real Run looks like: the Claude CLI with a shell of its own under it, holding
the same Transcript pipe. Killing only the Run leaves the Receiver reading that pipe."""


def a_run(directory: Path, run_id: str = "20260915T164012-abc123") -> Run:
    """A Run the way the Receiver prepares one: its own directory, Notification written."""
    working_directory = directory / run_id
    working_directory.mkdir(parents=True)
    (working_directory / NOTIFICATION_FILENAME).write_text(json.dumps(firing_notification()))
    return Run(run_id, working_directory)


def spawner_for(command: list[str], forwarder, **overrides) -> RunSpawner:
    return RunSpawner(
        command=command,
        forwarder=forwarder,
        anthropic_token=ANTHROPIC_TOKEN,
        jira_email=REAL_EMAIL,
        project_key=PROJECT_KEY,
        **overrides,
    )


def environment_of(run: Run) -> dict[str, str]:
    """The environment the stand-in Run recorded for itself."""
    return json.loads((run.working_directory / ENVIRONMENT_FILE).read_text())


@pytest.fixture
def run(tmp_path) -> Run:
    return a_run(tmp_path / "runs")


def test_the_run_starts_in_its_own_working_directory(forwarder, run):
    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)

    assert (run.working_directory / ENVIRONMENT_FILE).exists()


def test_the_runs_environment_is_built_from_scratch(forwarder, run, monkeypatch):
    """A Receiver with no trust store of its own starts a Run with none either."""
    for variable in TRUST_STORE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)

    assert set(environment_of(run)) - PLATFORM_ADDITIONS == A_RUNS_VARIABLES


def test_a_run_trusts_the_certificates_the_receiver_trusts_and_nothing_else_new(
    forwarder, run, monkeypatch
):
    """The image sets the trust-store variables for every process in it, and a Run's
    Anthropic traffic goes through the same intercepting proxy the build did (ticket 02).
    They are the only addition: the scrubbed environment of ADR 0002 stands."""
    for variable in TRUST_STORE_VARIABLES:
        monkeypatch.setenv(variable, SYSTEM_BUNDLE)

    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)

    environment = environment_of(run)
    assert {variable: environment[variable] for variable in TRUST_STORE_VARIABLES} == {
        variable: SYSTEM_BUNDLE for variable in TRUST_STORE_VARIABLES
    }
    assert set(environment) - PLATFORM_ADDITIONS == A_RUNS_VARIABLES | set(TRUST_STORE_VARIABLES)


def test_nothing_of_the_receivers_own_environment_reaches_the_run(forwarder, run, monkeypatch):
    monkeypatch.setenv("JIRA_API_TOKEN", REAL_TOKEN)
    monkeypatch.setenv(
        "AWS_SECRET_ACCESS_KEY", "something the Receiver happened to be started with"
    )

    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)

    environment = environment_of(run)
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert REAL_TOKEN not in environment.values()


def test_the_run_holds_a_sentinel_where_the_jira_token_would_be(forwarder, run):
    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)

    environment = environment_of(run)
    assert environment["JIRA_SITE_URL"] == forwarder.url
    assert environment["JIRA_SITE_URL"].startswith("http://127.0.0.1:")
    assert environment["JIRA_EMAIL"] == REAL_EMAIL
    assert environment["JIRA_API_TOKEN"] not in ("", REAL_TOKEN)
    assert environment[ANTHROPIC_TOKEN_VARIABLE] == ANTHROPIC_TOKEN


def test_the_run_can_read_jiras_clock(forwarder, run):
    """A Run has no clock of its own, so every duration it reports comes from Jira's.

    Reading it is a site-scoped call, which jira-as refuses unless the Run is told
    otherwise. On a laptop a settings file up the tree hides this; in the container
    there is no such tree, and every duration in every comment would break.
    """
    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)

    assert environment_of(run)[SITE_OPERATIONS_VARIABLE] == "true"


def test_the_run_may_name_the_demo_s_project_and_no_other(forwarder, run):
    """jira-as refuses a call naming any other project before it is sent (audit F7)."""
    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)

    assert environment_of(run)[ALLOWED_PROJECTS_VARIABLE] == PROJECT_KEY


def test_each_run_gets_its_own_sentinel(forwarder, tmp_path):
    spawner = spawner_for(_program(DUMP_ENVIRONMENT), forwarder)
    first, second = a_run(tmp_path / "runs", "first"), a_run(tmp_path / "runs", "second")

    spawner(first)
    spawner(second)

    assert environment_of(first)["JIRA_API_TOKEN"] != environment_of(second)["JIRA_API_TOKEN"]


def test_the_run_reaches_jira_through_the_forwarder_with_its_sentinel(forwarder, upstream, run):
    spawner_for(_program(DUMP_ENVIRONMENT, CALL_JIRA), forwarder)(run)

    assert len(upstream.received) == 1
    assert upstream.received[0].basic_auth == (REAL_EMAIL, REAL_TOKEN)
    assert environment_of(run)["JIRA_API_TOKEN"] not in str(upstream.received[0].headers)


def test_the_sentinel_is_worth_nothing_once_the_run_has_ended(forwarder, upstream, run):
    spawner_for(_program(DUMP_ENVIRONMENT), forwarder)(run)
    sentinel = environment_of(run)["JIRA_API_TOKEN"]

    answer = http_request(forwarder.url + "/rest/api/3/myself", basic_auth=(REAL_EMAIL, sentinel))

    assert answer.status == 401
    assert upstream.received == []


def test_the_transcript_is_rendered_into_the_log(forwarder, run, caplog):
    caplog.set_level(logging.INFO)

    spawner_for(_program(EMIT_A_TRANSCRIPT), forwarder)(run)

    assert "[claude] Searching OPS for a Match." in caplog.text
    assert "[tool]   Bash: jira-as search jql 'project = OPS'" in caplog.text
    assert "[result] success in 1.2s" in caplog.text


def test_the_runs_exit_status_is_returned(forwarder, run):
    assert spawner_for(_program(COMPLAIN_AND_FAIL), forwarder)(run) == 3


def test_a_failed_runs_stderr_is_logged(forwarder, run, caplog):
    caplog.set_level(logging.INFO)

    spawner_for(_program(COMPLAIN_AND_FAIL), forwarder)(run)

    assert "claude: onboarding was never accepted" in caplog.text


def test_a_failed_runs_stderr_is_redacted_like_every_other_log_line(forwarder, run, caplog):
    caplog.set_level(logging.INFO)

    spawner_for(_program(LEAK_A_CREDENTIAL_ON_STDERR), forwarder)(run)

    assert "c2VudGluZWw6bm90LWZvci1hLXNjcmVlbg==" not in caplog.text
    assert "<redacted>" in caplog.text


def test_a_successful_runs_stderr_stays_out_of_the_log(forwarder, run, caplog):
    caplog.set_level(logging.INFO)
    noisy = """\
import sys
print("a warning nobody in the audience needs", file=sys.stderr)
"""

    spawner_for(_program(noisy), forwarder)(run)

    assert "a warning nobody in the audience needs" not in caplog.text


def test_a_run_that_exceeds_the_timeout_is_killed_and_logged(forwarder, run, caplog):
    caplog.set_level(logging.INFO)
    started_at = time.monotonic()

    exit_status = spawner_for(_program(HANG), forwarder, timeout=0.5)(run)

    assert time.monotonic() - started_at < 10, "the timeout did not kill the Run"
    assert exit_status != 0
    assert f"run {run.run_id} exceeded" in caplog.text


def test_the_timeout_also_ends_what_the_run_started(forwarder, run, caplog):
    """A grandchild left holding the Transcript pipe would hang the Receiver's one worker."""
    caplog.set_level(logging.INFO)
    started_at = time.monotonic()

    spawner_for(_program(HANG_WITH_A_CHILD_OF_ITS_OWN), forwarder, timeout=0.5)(run)

    assert time.monotonic() - started_at < 10, "a child of the Run outlived the timeout"
    assert f"run {run.run_id} exceeded" in caplog.text


def test_a_timed_out_run_does_not_stall_the_queue(forwarder, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    receiver = Receiver(
        spawn_run=spawner_for(_program(HANG), forwarder, timeout=0.5),
        runs_directory=tmp_path / "runs",
    )
    receiver.start()
    try:
        post_notification(receiver, firing_notification())
        post_notification(receiver, firing_notification())
        log = wait_for_log(caplog, "finished with exit status", count=2, timeout=15)
    finally:
        receiver.stop()

    assert log.count("exceeded") == 2
