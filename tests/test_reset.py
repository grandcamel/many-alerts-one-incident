"""Resetting OPS and the traffic before a demo, so the Incidents queue starts empty.

The reset talks to Jira through `jira-as` and to the stack through `docker
compose`, both injected, so these tests drive it against a fake OPS whose
workflow is the real one's (ADR 0004): `Resolve` is the only transition that
takes a resolution, `Canceled` has no way out, and an Incident without a
resolution stays in the Incidents queue.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from grafana_jsm_sandbox.reset import OPEN_INCIDENTS, RESOLUTION, STUCK_INCIDENTS, reset

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
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def __call__(self, *arguments: str) -> str:
        self.calls.append(arguments)
        match arguments:
            case ("search", "jql", jql, *_):
                assert jql in (OPEN_INCIDENTS, STUCK_INCIDENTS)
                keys = self._open() if jql == OPEN_INCIDENTS else self._stuck()
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

    outcome = reset(jira_as=ops, compose=compose)

    assert outcome.closed == ["OPS-20", "OPS-21"]
    assert outcome.left == []
    for key in ("OPS-20", "OPS-21"):
        assert ops.incidents[key].status == "Closed"
        assert ops.incidents[key].resolution == RESOLUTION, f"{key} would sit in the queue"


def test_each_closed_incident_says_it_was_a_rehearsal_leftover(compose):
    ops = FakeOps({"OPS-20": FakeIncident("Open", ["fp-87e2f184874a3b71"])})

    reset(jira_as=ops, compose=compose)

    assert len(ops.incidents["OPS-20"].comments) == 1
    assert "reset" in ops.incidents["OPS-20"].comments[0].lower()


def test_an_open_incident_without_a_fingerprint_label_is_a_humans_and_is_left_alone(compose):
    ops = FakeOps(
        {
            "OPS-22": FakeIncident("Open", ["customer-reported"]),
            "OPS-23": FakeIncident("Open", []),
        }
    )

    outcome = reset(jira_as=ops, compose=compose)

    assert outcome.closed == []
    assert outcome.skipped == ["OPS-22", "OPS-23"]
    assert ops.incidents["OPS-22"].status == "Open"
    assert ops.incidents["OPS-23"].status == "Open"
    assert not any(call[:2] == ("lifecycle", "transition") for call in ops.calls)


def test_an_incident_with_no_road_to_completed_is_reported_and_not_forced(compose):
    ops = FakeOps({"OPS-24": FakeIncident("Pending", ["fp-87e2f184874a3b71"])})

    outcome = reset(jira_as=ops, compose=compose)

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

    outcome = reset(jira_as=ops, compose=compose)

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

    outcome = reset(jira_as=ops, compose=compose)

    assert outcome.stuck == ["OPS-6", "OPS-1"], "both sit in the queue and nothing can move them"
    assert not outcome.queue_is_empty
    assert not any(call[:2] == ("lifecycle", "transition") for call in ops.calls)


def test_traffic_is_started_after_the_queue_is_cleared_and_even_when_it_already_was(compose):
    ops = FakeOps({})

    outcome = reset(jira_as=ops, compose=compose)

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

    reset(jira_as=jira_as, compose=compose)

    assert order[-1] == "compose" and order.count("compose") == 1
