"""Resetting OPS and the traffic before a demo, so the Incidents queue starts empty.

Rehearsals leave Incidents behind. This takes every *open* OPS Incident that a
Run created — the ones carrying a Fingerprint label — out of the Incidents
queue, and starts the synthetic traffic so that Grafana's rule is Normal when
the audience arrives:

    python3 -m grafana_jsm_sandbox.reset

It runs on the laptop with a `jira-as` credential in the shell, like the
end-to-end check, and never through a Run. The exit it takes is the only clean
one on this workflow (ADR 0004): `Resolve` with a resolution, then `Close`.
`Cancel` would leave the Incident in the queue for good, because `Canceled`
carries no resolution and the queue is `resolution = Unresolved`. An open
Incident with no road to `Completed` from where it is, or without a Fingerprint
label at all, is a human's and is reported rather than touched.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

OPEN_INCIDENTS = "project = OPS AND issuetype = Incident AND statusCategory != Done"
"""Everything a Run could still act on, whoever opened it."""

STUCK_INCIDENTS = (
    "project = OPS AND issuetype = Incident AND statusCategory = Done AND resolution = Unresolved"
)
"""Done by status but still in the Incidents queue, which filters on resolution, with no
transition left that could set one (ADR 0004). Only deleting them empties the queue."""

FINGERPRINT_PREFIX = "fp-"
"""What marks an Incident as a Run's: the label a Run keys it by (ADR 0004)."""

COMPLETED = "Completed"
CLOSED = "Closed"
RESOLUTION = "Done"
"""The way out: `Resolve` with this resolution, then `Close`. Never `Cancel`."""

RESET_COMMENT = (
    "Reset before the demo: a rehearsal left this open. Completed and closed by the reset."
)

TRAFFIC_SERVICE = "traffic"
"""The compose service whose absence fires the Alert. Started last, so the rule goes Normal."""

REPOSITORY = Path(__file__).resolve().parent.parent
"""Where `docker compose` must be run from to find this repo's stack."""

JIRA_AS = "jira-as"

JiraAs = Callable[..., str]
"""`jira_as(*arguments) -> stdout`, with `-o json` passed where a JSON answer is read."""

Compose = Callable[..., None]
"""`compose(*arguments)` runs one `docker compose` command against this repo's stack."""


@dataclass(frozen=True)
class Outcome:
    """What the reset did, key by key, so the presenter can read the queue off it."""

    closed: list[str] = field(default_factory=list)
    """Taken out of the queue: Completed with a resolution, then Closed."""

    left: list[str] = field(default_factory=list)
    """A Run's, but with no road to Completed from where it is. A human finishes it."""

    skipped: list[str] = field(default_factory=list)
    """Open without a Fingerprint label, so not a Run's. Not touched."""

    stuck: list[str] = field(default_factory=list)
    """Done without a resolution: in the queue for good unless a human deletes them."""

    traffic_started: bool = False

    @property
    def queue_is_empty(self) -> bool:
        return not self.left and not self.skipped and not self.stuck


def reset(jira_as: JiraAs | None = None, compose: Compose | None = None) -> Outcome:
    """Empty the Incidents queue of every Run-created Incident, then start the traffic."""
    jira_as = run_jira_as if jira_as is None else jira_as
    compose = run_compose if compose is None else compose
    outcome = Outcome()
    for issue in search(jira_as, OPEN_INCIDENTS):
        key = issue["key"]
        if not any(label.startswith(FINGERPRINT_PREFIX) for label in issue["fields"]["labels"]):
            outcome.skipped.append(key)
        elif close(jira_as, key):
            outcome.closed.append(key)
        else:
            outcome.left.append(key)
    stuck = [issue["key"] for issue in search(jira_as, STUCK_INCIDENTS)]
    compose("start", TRAFFIC_SERVICE)
    return Outcome(outcome.closed, outcome.left, outcome.skipped, stuck, traffic_started=True)


def close(jira_as: JiraAs, key: str) -> bool:
    """Complete `key` with a resolution and close it; False if it cannot be completed."""
    if not move_to(jira_as, key, COMPLETED, resolution=RESOLUTION):
        return False
    jira_as("collaborate", "comment", "add", key, "-b", RESET_COMMENT)
    move_to(jira_as, key, CLOSED)
    return True


def move_to(jira_as: JiraAs, key: str, status: str, resolution: str | None = None) -> bool:
    """Take the transition that lands on `status`, read off the issue; False if there is none."""
    wanted = [
        transition
        for transition in json.loads(jira_as("lifecycle", "transitions", key, "-o", "json"))
        if transition.get("to", {}).get("name") == status
    ]
    if not wanted:
        return False
    arguments = ["lifecycle", "transition", key, "--id", wanted[0]["id"]]
    if resolution is not None:
        arguments += ["--resolution", resolution]
    jira_as(*arguments)
    return True


def search(jira_as: JiraAs, jql: str) -> list[dict]:
    answer = jira_as("search", "jql", jql, "--fields", "key,status,labels", "-o", "json")
    return json.loads(answer).get("issues", [])


def run_jira_as(*arguments: str) -> str:
    """The real `jira-as`, with the credential this shell holds."""
    answer = subprocess.run(
        [JIRA_AS, *arguments], capture_output=True, text=True, timeout=120, check=False
    )
    if answer.returncode != 0:
        raise RuntimeError(f"{JIRA_AS} {' '.join(arguments)} failed: {answer.stderr.strip()}")
    return answer.stdout


def run_compose(*arguments: str) -> None:
    """One `docker compose` command against this repo's stack."""
    subprocess.run(["docker", "compose", *arguments], cwd=REPOSITORY, check=True, timeout=120)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print("usage: python3 -m grafana_jsm_sandbox.reset", file=sys.stderr)
        return 2
    outcome = reset()
    for key in outcome.closed:
        print(f"{key}: completed with resolution {RESOLUTION} and closed")
    for key in outcome.left:
        print(
            f"{key}: a Run's, but has no transition to {COMPLETED} from where it is; finish it by hand"
        )
    for key in outcome.skipped:
        print(f"{key}: open without a {FINGERPRINT_PREFIX} label, so not a Run's; left alone")
    for key in outcome.stuck:
        print(
            f"{key}: done without a resolution, so in the Incidents queue for good; "
            f"only `jira-as api call deleteIssue --issueIdOrKey {key}` removes it"
        )
    print(f"{TRAFFIC_SERVICE} started")
    print("queue is empty" if outcome.queue_is_empty else "queue is NOT empty")
    return 0 if outcome.queue_is_empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
