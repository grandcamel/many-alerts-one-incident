"""The command line that starts one Run.

A Run is headless Claude, started in print mode for exactly one Notification,
in a mode where any tool call outside the allow list is denied without a prompt
(ADR 0003). The allow list is jira-as and reading, so a Run can talk to Jira and
nothing else, and the denials show up in its Transcript where an audience can
read them.

The Receiver builds this command line for each Run in ticket 05. Print it to
run one by hand, which is how the skill was verified against the real OPS
project:

    python3 -m grafana_jsm_sandbox.run_command skill
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from grafana_jsm_sandbox.notification import NOTIFICATION_FILENAME

CLAUDE = "claude"
"""The Claude Code executable, on PATH on the laptop and in the container."""

SKILL_FILE = "incident-sync/SKILL.md"
"""The skill a Run follows, relative to the mounted skill directory."""

PERMISSION_MODE = "dontAsk"
"""Anything not on the allow list is denied, without a prompt a Run could hang on."""

ALLOWED_TOOLS = ("Bash(jira-as *)", "Read")
"""Everything a Run may do. Talking to Jira, and reading the Notification and the skill."""

OUTPUT_FORMAT = "stream-json"
"""The Transcript: one Run event per line, rendered into the log as it arrives."""

SYSTEM_PROMPT_APPENDIX = """\
You are a Run: one headless invocation handling exactly one Grafana Notification.

The Notification is the file {notification} in your working directory.
Your instructions are the skill at {skill}. Read it first and follow it exactly.

Your tools are exactly these: {tools}. Every other tool call will be denied, so do
not reach for one — the skill never needs one."""

PROMPT = (
    f"Read the skill, then handle every Alert in {NOTIFICATION_FILENAME} as it says. "
    "Finish with one line per Alert saying what changed in OPS."
)


def build_run_command(skill_directory: Path | str) -> list[str]:
    """The argv that starts one Run, to be executed in the Run's working directory.

    `skill_directory` is the directory mounted into the container that holds the
    skill; it is made absolute, because a Run's working directory is not this
    process's and `--add-dir` is resolved from the Run's.
    """
    skill_directory = Path(skill_directory).resolve()
    return [
        CLAUDE,
        "--print",
        "--permission-mode",
        PERMISSION_MODE,
        "--allowedTools",
        *ALLOWED_TOOLS,
        "--output-format",
        OUTPUT_FORMAT,
        "--verbose",
        "--add-dir",
        str(skill_directory),
        "--append-system-prompt",
        SYSTEM_PROMPT_APPENDIX.format(
            notification=NOTIFICATION_FILENAME,
            skill=skill_directory / SKILL_FILE,
            tools=", ".join(ALLOWED_TOOLS),
        ),
        PROMPT,
    ]


def main(argv: list[str] | None = None) -> int:
    """Print the command line, ready to paste into a Run's working directory."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(
            "usage: python3 -m grafana_jsm_sandbox.run_command <skill-directory>", file=sys.stderr
        )
        return 2
    print(shlex.join(build_run_command(argv[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
