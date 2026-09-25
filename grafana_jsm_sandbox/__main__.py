"""Historical demo settings and its retired executable entrypoint.

The direct-credential Run composition predates ADRs 0011–0013. Importable
configuration parsing remains for isolated historical tests, but invoking
this module or ``serve`` cannot start the old Receiver/Forwarder/Run path.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from grafana_jsm_sandbox.forwarder import IncompleteJiraCredential, JiraCredential
from grafana_jsm_sandbox.run_spawner import (
    RUN_TIMEOUT,
    MissingAnthropicToken,
    anthropic_token_from_environment,
)

Number = TypeVar("Number", int, float)

HOST_VARIABLE = "RECEIVER_HOST"
PORT_VARIABLE = "RECEIVER_PORT"
RUNS_DIRECTORY_VARIABLE = "RUNS_DIRECTORY"
SKILL_DIRECTORY_VARIABLE = "SKILL_DIRECTORY"
RUN_TIMEOUT_VARIABLE = "RUN_TIMEOUT"
"""What the container sets to place the demo; the credential variables are the Forwarder's
and the spawner's. Every one of these has a default that works on a laptop."""

DEFAULT_HOST = "0.0.0.0"
"""Grafana reaches the Receiver from another container; the Forwarder is the loopback one."""

DEFAULT_PORT = 8080
"""What the contact point URL names, so compose publishes one well-known port."""

DEFAULT_RUNS_DIRECTORY = Path("runs")
"""Where each Run's working directory goes, relative to wherever this was started."""

DEFAULT_SKILL_DIRECTORY = Path(__file__).resolve().parent.parent / "skill"
"""The skill in this repo, which is what the container mounts and what a Run reads."""


class IncompleteConfiguration(ValueError):
    """The environment does not describe a demo that could work, and says how."""


class LegacyLaunchDisabled(RuntimeError):
    """The former executable cannot start a Run under the accepted ADRs."""


LEGACY_LAUNCH_DISABLED = "legacy_launch_disabled"


@dataclass(frozen=True)
class Settings:
    """Everything the process needs, read from the environment in one place."""

    credential: JiraCredential
    anthropic_token: str
    host: str
    port: int
    runs_directory: Path
    skill_directory: Path
    run_timeout: float

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> Settings:
        """Read the whole configuration, or raise naming every part of it that is wrong.

        Every failure is collected rather than raised at the first one, so a
        half-filled env file is fixed in one pass instead of three restarts.
        """
        environment = os.environ if environment is None else environment
        failures: list[str] = []
        credential = None
        anthropic_token = ""
        try:
            credential = JiraCredential.from_environment(environment)
        except IncompleteJiraCredential as failure:
            failures.append(str(failure))
        try:
            anthropic_token = anthropic_token_from_environment(environment)
        except MissingAnthropicToken as failure:
            failures.append(str(failure))
        port = _number(environment, PORT_VARIABLE, DEFAULT_PORT, int, failures)
        run_timeout = _number(environment, RUN_TIMEOUT_VARIABLE, RUN_TIMEOUT, float, failures)
        if failures or credential is None:
            raise IncompleteConfiguration("\n".join(failures))
        return cls(
            credential=credential,
            anthropic_token=anthropic_token,
            host=environment.get(HOST_VARIABLE, "").strip() or DEFAULT_HOST,
            port=port,
            runs_directory=_directory(environment, RUNS_DIRECTORY_VARIABLE, DEFAULT_RUNS_DIRECTORY),
            skill_directory=_directory(
                environment, SKILL_DIRECTORY_VARIABLE, DEFAULT_SKILL_DIRECTORY
            ),
            run_timeout=run_timeout,
        )


def serve(settings: Settings) -> int:
    """Refuse direct calls to the historical runtime composition."""
    raise LegacyLaunchDisabled(LEGACY_LAUNCH_DISABLED) from None


def main(argv: list[str] | None = None, environment: Mapping[str, str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print("usage: python3 -m grafana_jsm_sandbox", file=sys.stderr)
        return 2
    print(LEGACY_LAUNCH_DISABLED, file=sys.stderr)
    return 1


def _number(
    environment: Mapping[str, str],
    variable: str,
    default: Number,
    read: Callable[[str], Number],
    failures: list[str],
) -> Number:
    """A number read from the environment, or the default, or one more failure to report."""
    value = environment.get(variable, "").strip()
    if not value:
        return default
    try:
        return read(value)
    except ValueError:
        failures.append(f"{variable} is not a number: {value!r}")
        return default


def _directory(environment: Mapping[str, str], variable: str, default: Path) -> Path:
    return Path(environment.get(variable, "").strip() or default)


if __name__ == "__main__":
    raise SystemExit(main())
