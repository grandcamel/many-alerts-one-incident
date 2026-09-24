"""Starting one Run for real: a child process that can only talk to Jira.

The Receiver injects one of these as its spawner. Around each Run it does the
three things that make the credential boundary true (ADR 0002): it builds the
Run's environment from scratch rather than inheriting one, it registers that
Run's sentinel with the Forwarder before the process starts, and it clears the
sentinel the moment the process ends, so a sentinel that leaks out of a
Transcript is worth nothing by the time anyone reads it.

Everything the Run says on stdout is a Transcript, rendered into the log by the
formatter as it arrives. A Run that runs long is killed, because a demo cannot
wait and the queue behind it cannot either.
"""

from __future__ import annotations

import logging
import os
import secrets
import signal
import subprocess
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import IO, cast

from grafana_jsm_sandbox.forwarder import ENVIRONMENT_VARIABLES, Forwarder
from grafana_jsm_sandbox.log_formatter import format_stream, redact
from grafana_jsm_sandbox.receiver import Run

logger = logging.getLogger(__name__)

ANTHROPIC_TOKEN_VARIABLE = "CLAUDE_CODE_OAUTH_TOKEN"
"""The one real credential a Run holds. Nothing documented can mask it; the demo says so."""

RUN_TIMEOUT = 300.0
"""Seconds a Run may take before it is killed. Long enough for the five operations, short
enough that a stuck Run does not eat the slot."""

SITE_OPERATIONS_VARIABLE = "JIRA_ALLOW_SITE_OPERATIONS"
"""jira-as refuses site-scoped calls unless this says otherwise, and a Run needs exactly one
of them: `getServerInfo`. A Run has no clock — `date` is not on its allow list — so every
duration it reports is Jira's `serverTime` minus the Incident's `created` (ticket 04). Without
this, a Run outside a tree holding a jira-as settings file cannot read the time at all.

It is not narrow. jira-as has no switch for one site-scoped call: this unlocks all of them,
610 of its operations in 2.0.0, users, groups and schemes among them, besides the one a Run
needs. What any of those can then do is whatever the account behind the Forwarder may do,
because the Forwarder swaps the sentinel for that account's real token on every request. So
the limit on a Run's site-wide reach is the Skill it follows and that account's own Jira
permissions, and the account the demo runs as should hold no more than the demo needs."""

TRUST_STORE_VARIABLES = (
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "PIP_CERT",
    "NODE_EXTRA_CA_CERTS",
)
"""What the image sets, image-wide, so that every TLS client in it trusts the system bundle
and whatever corporate CA was installed into it at build time (ticket 02). A Run inherits
exactly these from the Receiver, when the Receiver has them: on a laptop behind an
intercepting proxy its Anthropic traffic goes through the same proxy the build did, and
Claude Code reads `NODE_EXTRA_CA_CERTS` for the CA. Its Jira traffic needs none of them,
because that goes to the Forwarder over loopback in plain HTTP.

They are the only thing a Run inherits: the environment is still built from scratch, and
the real Jira token still never reaches it (ADR 0002)."""

SENTINEL_BYTES = 24
"""How much randomness each Run's sentinel carries."""

STDERR_TIMEOUT = 5.0
"""Seconds to wait for a killed Run's stderr after the process is gone."""

STDERR_TAIL = 2000
"""How much of a failed Run's stderr reaches the log: the end of it, where a crash says
what went wrong. The log window is a screen in a room, not a file anyone will scroll."""


class MissingAnthropicToken(ValueError):
    """No Anthropic token, so no Run could ever start."""


def anthropic_token_from_environment(environment=None) -> str:
    """Read the token a Run authenticates with, or say which variable is not set."""
    environment = os.environ if environment is None else environment
    token = environment.get(ANTHROPIC_TOKEN_VARIABLE, "").strip()
    if not token:
        raise MissingAnthropicToken(f"{ANTHROPIC_TOKEN_VARIABLE} is not set")
    return token


def trust_store_from_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """The trust-store variables the Receiver was started with, and only those that are set."""
    environment = os.environ if environment is None else environment
    return {name: environment[name] for name in TRUST_STORE_VARIABLES if name in environment}


@dataclass(frozen=True)
class RunSpawner:
    """Starts one Run as a child process and renders its Transcript into the log.

    `command` is the same command line for every Run — what differs per Run is
    the working directory it is started in and the sentinel in its environment.
    """

    command: Sequence[str]
    forwarder: Forwarder
    anthropic_token: str
    jira_email: str
    timeout: float = RUN_TIMEOUT
    path: str = field(default_factory=lambda: os.environ.get("PATH", os.defpath))
    trust_store: Mapping[str, str] = field(default_factory=trust_store_from_environment)

    def __call__(self, run: Run) -> int:
        """Run one Run to completion and return its exit status."""
        sentinel = secrets.token_urlsafe(SENTINEL_BYTES)
        self.forwarder.set_sentinel(sentinel)
        try:
            return self._execute(run, sentinel)
        finally:
            self.forwarder.clear_sentinel()

    def _execute(self, run: Run, sentinel: str) -> int:
        timed_out = threading.Event()
        process = subprocess.Popen(
            list(self.command),
            cwd=run.working_directory,
            env=self._environment(sentinel),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            errors="replace",
            # A Run is the Claude CLI, which runs jira-as through a shell of its own.
            # Its own session means the timeout can end all of them at once: a
            # grandchild left alive would hold the Transcript pipe open and the
            # Receiver's one worker would wait on it for as long as it lived.
            start_new_session=True,
        )
        # Both pipes were asked for above, so neither of them is None.
        errors = _Drained(cast("IO[str]", process.stderr))
        killer = threading.Timer(self.timeout, _kill, (process, timed_out))
        killer.start()
        try:
            # The timer stays armed across this whole block, the reaping in
            # `__exit__` included, so nothing here can outlive the timeout.
            with process:
                for line in format_stream(cast("IO[str]", process.stdout)):
                    logger.info("%s", line)
                exit_status = process.wait()
        finally:
            killer.cancel()
        errors.join(STDERR_TIMEOUT)

        if timed_out.is_set():
            logger.error(
                "run %s exceeded its %.0fs timeout and was killed", run.run_id, self.timeout
            )
        if exit_status != 0 and errors.text:
            logger.warning("run %s wrote to stderr: %s", run.run_id, redact(errors.text))
        return exit_status

    def _environment(self, sentinel: str) -> dict[str, str]:
        """Everything the Run's process gets, and it is built here rather than inherited.

        The Jira variables are the ones jira-as reads, so a Run needs no patching
        to talk to the Forwarder — it only ever holds the sentinel. HOME is not
        among them: the Claude CLI falls back to the account's home directory,
        and leaving it out keeps the list short enough to read aloud. The trust
        store is the one thing carried over from the Receiver's own environment,
        and only when the Receiver has one.
        """
        return {
            **self.trust_store,
            ANTHROPIC_TOKEN_VARIABLE: self.anthropic_token,
            ENVIRONMENT_VARIABLES["site_url"]: self.forwarder.url,
            ENVIRONMENT_VARIABLES["email"]: self.jira_email,
            ENVIRONMENT_VARIABLES["api_token"]: sentinel,
            SITE_OPERATIONS_VARIABLE: "true",
            "PATH": self.path,
        }


class _Drained:
    """A stream being read to its end on a thread, so a full pipe can never wedge a Run.

    Only the tail is kept. A Run that never stops complaining is still bounded by
    its timeout, but what it said should not arrive in the log as one vast line.
    """

    def __init__(self, stream: IO[str]):
        self.text = ""
        self._thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self._thread.start()

    def _read(self, stream: IO[str]) -> None:
        self.text = stream.read().strip()[-STDERR_TAIL:]

    def join(self, timeout: float) -> None:
        self._thread.join(timeout)


def _kill(process: subprocess.Popen, timed_out: threading.Event) -> None:
    """End a Run that has taken too long, and everything it started.

    The whole session goes, not just the Run: the Claude CLI's own children hold
    the Transcript pipe, so killing it alone would leave the Receiver reading a
    pipe that never closes.
    """
    if process.poll() is not None:
        # It finished on its own between this timer firing and now, so it did not
        # exceed anything and nothing should say it did.
        return
    timed_out.set()
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()
