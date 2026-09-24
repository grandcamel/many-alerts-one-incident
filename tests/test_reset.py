"""Resetting the demo's project and the traffic before a demo, so the Incidents queue starts empty.

The reset talks to Jira through `jira-as` and to the stack through `docker
compose`, both injected, so these tests drive it against a fake OPS whose
workflow is the real one's (ADR 0004): `Resolve` is the only transition that
takes a resolution, `Canceled` has no way out, and an Incident without a
resolution stays in the Incidents queue. The last tests start a real `jira-as`
stand-in, to show what the reset hands it comes from `.env` and not the shell.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from grafana_jsm_sandbox.reset import OPEN_INCIDENTS, RESOLUTION, STUCK_INCIDENTS, main, reset
from grafana_jsm_sandbox.run_spawner import TRUST_STORE_VARIABLES

KEY = "OPS"
"""The project the fake answers for, whose workflow ticket 04 read."""

WORKFLOW = {
    "Open": {"11": "Work in progress", "21": "Completed", "31": "Canceled"},
    "Work in progress": {"21": "Completed", "31": "Canceled"},
    "Pending": {"31": "Canceled"},
    "Completed": {"41": "Closed", "51": "Open"},
    "Canceled": {"41": "Closed"},
    "Closed": {},
}
"""The OPS Incident workflow as ticket 04 read it off real issues: transition id to
the status it lands on. `Pending` is the one open status with no road to Completed."""

DONE = {"Completed", "Canceled", "Closed"}


@dataclass
class FakeIncident:
    status: str
    labels: list[str]
    resolution: str | None = None
    comments: list[str] = field(default_factory=list)


@dataclass
class FakeOps:
    """A stand-in for `jira-as` against OPS: answers the queries the reset makes and
    moves Incidents the way the real workflow would."""

    incidents: dict[str, FakeIncident]
    key: str = KEY
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def __call__(self, *arguments: str) -> str:
        self.calls.append(arguments)
        open_incidents = OPEN_INCIDENTS.format(key=self.key)
        match arguments:
            case ("search", "jql", jql, *_):
                assert jql in (open_incidents, STUCK_INCIDENTS.format(key=self.key)), jql
                keys = self._open() if jql == open_incidents else self._stuck()
                return json.dumps({"issues": [self._issue(key) for key in keys]})
            case ("lifecycle", "transitions", key, *_):
                return json.dumps(
                    [
                        {"id": id, "name": f"to {status}", "to": {"name": status}}
                        for id, status in WORKFLOW[self.incidents[key].status].items()
                    ]
                )
            case ("lifecycle", "transition", key, "--id", id, *rest):
                incident = self.incidents[key]
                assert id in WORKFLOW[incident.status], f"{id} is not a transition from {key}"
                incident.status = WORKFLOW[incident.status][id]
                if rest:
                    assert rest[0] == "--resolution" and id == "21", "only Resolve takes one"
                    incident.resolution = rest[1]
                return ""
            case ("collaborate", "comment", "add", key, "-b", body, *_):
                self.incidents[key].comments.append(body)
                return ""
        raise AssertionError(f"the fake does not answer {arguments}")

    def _open(self) -> list[str]:
        return [key for key, incident in self.incidents.items() if incident.status not in DONE]

    def _stuck(self) -> list[str]:
        """Done by status, unresolved by resolution: what the Incidents queue still shows."""
        return [
            key
            for key, incident in self.incidents.items()
            if incident.status in DONE and incident.resolution is None
        ]

    def _issue(self, key: str) -> dict:
        incident = self.incidents[key]
        return {
            "key": key,
            "fields": {"status": {"name": incident.status}, "labels": incident.labels},
        }


@dataclass
class FakeCompose:
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def __call__(self, *arguments: str) -> None:
        self.calls.append(arguments)


@pytest.fixture
def compose() -> FakeCompose:
    return FakeCompose()


def test_open_incidents_with_a_fingerprint_label_leave_the_queue_completed_and_closed(compose):
    ops = FakeOps(
        {
            "OPS-20": FakeIncident("Open", ["fp-87e2f184874a3b71"]),
            "OPS-21": FakeIncident("Work in progress", ["fp-deadbeef00000000"]),
        }
    )

    outcome = reset(KEY, jira_as=ops, compose=compose)

    assert outcome.closed == ["OPS-20", "OPS-21"]
    assert outcome.left == []
    for key in ("OPS-20", "OPS-21"):
        assert ops.incidents[key].status == "Closed"
        assert ops.incidents[key].resolution == RESOLUTION, f"{key} would sit in the queue"


def test_each_closed_incident_says_it_was_a_rehearsal_leftover(compose):
    ops = FakeOps({"OPS-20": FakeIncident("Open", ["fp-87e2f184874a3b71"])})

    reset(KEY, jira_as=ops, compose=compose)

    assert len(ops.incidents["OPS-20"].comments) == 1
    assert "reset" in ops.incidents["OPS-20"].comments[0].lower()


def test_an_open_incident_without_a_fingerprint_label_is_a_humans_and_is_left_alone(compose):
    ops = FakeOps(
        {
            "OPS-22": FakeIncident("Open", ["customer-reported"]),
            "OPS-23": FakeIncident("Open", []),
        }
    )

    outcome = reset(KEY, jira_as=ops, compose=compose)

    assert outcome.closed == []
    assert outcome.skipped == ["OPS-22", "OPS-23"]
    assert ops.incidents["OPS-22"].status == "Open"
    assert ops.incidents["OPS-23"].status == "Open"
    assert not any(call[:2] == ("lifecycle", "transition") for call in ops.calls)


def test_an_incident_with_no_road_to_completed_is_reported_and_not_forced(compose):
    ops = FakeOps({"OPS-24": FakeIncident("Pending", ["fp-87e2f184874a3b71"])})

    outcome = reset(KEY, jira_as=ops, compose=compose)

    assert outcome.closed == []
    assert outcome.left == ["OPS-24"]
    assert ops.incidents["OPS-24"].status == "Pending", "Canceled would park it in the queue"


def test_incidents_already_out_of_the_queue_are_not_asked_about(compose):
    ops = FakeOps(
        {
            "OPS-13": FakeIncident("Completed", ["fp-87e2f184874a3b71"], resolution="Done"),
            "OPS-12": FakeIncident("Closed", ["fp-87e2f184874a3b71"], resolution="Done"),
        }
    )

    outcome = reset(KEY, jira_as=ops, compose=compose)

    assert outcome.closed == outcome.left == outcome.skipped == outcome.stuck == []
    assert outcome.queue_is_empty
    assert all(call[:2] == ("search", "jql") for call in ops.calls)


def test_a_done_incident_without_a_resolution_is_reported_as_stuck_in_the_queue(compose):
    ops = FakeOps(
        {
            "OPS-6": FakeIncident("Canceled", ["fp-87e2f184874a3b71"]),
            "OPS-1": FakeIncident("Closed", []),
            "OPS-13": FakeIncident("Completed", ["fp-87e2f184874a3b71"], resolution="Done"),
        }
    )

    outcome = reset(KEY, jira_as=ops, compose=compose)

    assert outcome.stuck == ["OPS-6", "OPS-1"], "both sit in the queue and nothing can move them"
    assert not outcome.queue_is_empty
    assert not any(call[:2] == ("lifecycle", "transition") for call in ops.calls)


def test_traffic_is_started_after_the_queue_is_cleared_and_even_when_it_already_was(compose):
    ops = FakeOps({})

    outcome = reset(KEY, jira_as=ops, compose=compose)

    assert compose.calls == [("start", "traffic")]
    assert outcome.traffic_started


def test_the_queue_is_cleared_before_the_traffic_moves():
    order: list[str] = []
    ops = FakeOps({"OPS-20": FakeIncident("Open", ["fp-87e2f184874a3b71"])})
    inner = ops.__call__

    def jira_as(*arguments: str) -> str:
        order.append("jira")
        return inner(*arguments)

    def compose(*arguments: str) -> None:
        order.append("compose")

    reset(KEY, jira_as=jira_as, compose=compose)

    assert order[-1] == "compose" and order.count("compose") == 1


# --- The project and the credential come from .env (step 02 of demo-onboarding) ---


def test_the_reset_searches_the_project_it_is_given_and_no_other(compose):
    ops = FakeOps({"SANDBOX-3": FakeIncident("Open", ["fp-87e2f184874a3b71"])}, key="SANDBOX")

    outcome = reset("SANDBOX", jira_as=ops, compose=compose)

    assert outcome.closed == ["SANDBOX-3"]
    searched = [call[2] for call in ops.calls if call[:2] == ("search", "jql")]
    assert searched and all(jql.startswith('project = "SANDBOX" AND ') for jql in searched)


RECORDING_JIRA_AS = """\
#!{python}
import json, os, pathlib, sys
with pathlib.Path({record!r}).open("a") as record:
    record.write(json.dumps({{"argv": sys.argv[1:], "environment": dict(os.environ)}}) + "\\n")
print(json.dumps({{"issues": []}}))
"""
"""A stand-in for `jira-as` on PATH that records how it was started and finds nothing open.
The record's path is written into it, because its environment is not the test's to extend."""

ENV_FILE = """\
JIRA_SITE_URL=https://demo-site.atlassian.net
JIRA_EMAIL=demo@example.invalid
JIRA_API_TOKEN=the-token-in-dot-env
CLAUDE_CODE_OAUTH_TOKEN=an-anthropic-oauth-token
DEMO_PROJECT_KEY=SANDBOX
"""

PLATFORM_ADDITIONS = {"LC_CTYPE", "__CF_USER_TEXT_ENCODING"}
"""What macOS adds to every child process; the laptop helpers run there."""


@pytest.fixture
def jira_as_on_path(tmp_path, monkeypatch) -> Path:
    """Put the stand-in first on this shell's PATH, in a shell configured for production."""
    record = tmp_path / "jira-as-calls.jsonl"
    stand_in = tmp_path / "bin" / "jira-as"
    stand_in.parent.mkdir()
    stand_in.write_text(RECORDING_JIRA_AS.format(python=sys.executable, record=str(record)))
    stand_in.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stand_in.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("JIRA_SITE_URL", "https://production.atlassian.net")
    monkeypatch.setenv("JIRA_API_TOKEN", "the-token-for-production")
    monkeypatch.setenv("JIRA_ALLOWED_PROJECTS", "PROD")
    monkeypatch.setenv("JIRA_AS_TRANSPORT", "simulation")
    return record


def calls_to(record: Path) -> list[dict]:
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text().splitlines()]


def test_jira_as_is_started_with_env_s_credential_and_project_and_nothing_of_the_shell(
    tmp_path, jira_as_on_path, compose, capsys, monkeypatch
):
    for variable in TRUST_STORE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(ENV_FILE)

    assert main([], env_file=env_file, compose=compose) == 0

    calls = calls_to(jira_as_on_path)
    assert [call["argv"][:2] for call in calls] == [["search", "jql"], ["search", "jql"]]
    for call in calls:
        environment = call["environment"]
        assert set(environment) - PLATFORM_ADDITIONS == {
            "PATH",
            "HOME",
            "JIRA_SITE_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
            "JIRA_ALLOWED_PROJECTS",
            "JIRA_ALLOW_SITE_OPERATIONS",
        }
        assert environment["JIRA_SITE_URL"] == "https://demo-site.atlassian.net"
        assert environment["JIRA_API_TOKEN"] == "the-token-in-dot-env"
        assert environment["JIRA_ALLOWED_PROJECTS"] == "SANDBOX"
        assert environment["JIRA_ALLOW_SITE_OPERATIONS"] == "true"
    assert compose.calls == [("start", "traffic")]
    said = capsys.readouterr()
    assert "production.atlassian.net" in said.err, "the shell's other site is said out loud"
    assert "the-token" not in said.out + said.err


def test_without_an_env_file_the_reset_says_how_to_make_one_and_touches_nothing(
    tmp_path, jira_as_on_path, compose, capsys
):
    assert main([], env_file=tmp_path / ".env", compose=compose) == 1

    assert "cp .env.example .env" in capsys.readouterr().err
    assert calls_to(jira_as_on_path) == []
    assert compose.calls == []


def test_an_env_file_without_a_project_key_is_refused_before_jira_is_asked_anything(
    tmp_path, jira_as_on_path, compose, capsys
):
    env_file = tmp_path / ".env"
    env_file.write_text(ENV_FILE.replace("DEMO_PROJECT_KEY=SANDBOX", "DEMO_PROJECT_KEY="))

    assert main([], env_file=env_file, compose=compose) == 1

    said = capsys.readouterr().err
    assert "DEMO_PROJECT_KEY" in said
    assert "the-token" not in said
    assert calls_to(jira_as_on_path) == []
    assert compose.calls == []
