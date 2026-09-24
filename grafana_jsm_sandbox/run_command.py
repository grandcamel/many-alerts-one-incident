"""The command line that starts one Run.

A Run is headless Claude, started in print mode for exactly one Notification,
in a mode where any tool call outside the allow list is denied without a prompt
(ADR 0003). The allow list is jira-as and reading two directories, the runs
directory and the skill, so a Run can talk to Jira and nothing else, and the
denials show up in its Transcript where an audience can read them.

The Receiver builds this command line for each Run in ticket 05. Print it to
run one by hand, which is how the skill was verified against the real OPS
project, naming the skill, the runs directory and the demo's project key:

    python3 -m grafana_jsm_sandbox.run_command skill runs OPS
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

JIRA_AS = "Bash(jira-as *)"
"""Talking to Jira: the one command a Run may execute."""

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
    "Finish with one line per Alert saying what changed in {project_key}."
)
"""What a Run is asked to do, naming the demo's project, which is `DEMO_PROJECT_KEY`."""


def allowed_tools(skill_directory: Path, runs_directory: Path) -> tuple[str, ...]:
    """Everything a Run may do: talk to Jira, and read under two absolute directories.

    A bare `Read` would let a Run read any file its uid can, and the container's
    main process runs as that uid with the real Jira token in its initial
    environment. A live Run asked for it got the token back from
    `/proc/1/task/1/environ` (the 2026-09-23 probe, ADR 0003's amendment). A rule
    scoped to absolute paths denies that and every alias of it: `//` is Claude
    Code's prefix for an absolute path, which a directory's own leading `/` supplies.

    The runs directory holds each Run's working directory and so its Notification.
    The skill directory is here only until the Skill is rendered under the runs
    directory, when the second rule goes.
    """
    return (JIRA_AS, read_rule(runs_directory), read_rule(skill_directory))


def read_rule(directory: Path) -> str:
    """A Read rule for everything under one absolute directory."""
    return f"Read(/{directory}/**)"


def build_run_command(
    skill_directory: Path | str, runs_directory: Path | str, project_key: str
) -> list[str]:
    """The argv that starts one Run, to be executed in the Run's working directory.

    `skill_directory` is the directory mounted into the container that holds the
    skill, and `runs_directory` the parent of every Run's working directory. Both
    are made absolute, because a Run's working directory is not this process's,
    `--add-dir` is resolved from the Run's, and a Read rule names an absolute path.
    `project_key` is the demo's project, which the prompt names.
    """
    skill_directory = Path(skill_directory).resolve()
    tools = allowed_tools(skill_directory, Path(runs_directory).resolve())
    return [
        CLAUDE,
        "--print",
        "--permission-mode",
        PERMISSION_MODE,
        "--allowedTools",
        *tools,
        "--output-format",
        OUTPUT_FORMAT,
        "--verbose",
        "--add-dir",
        str(skill_directory),
        "--append-system-prompt",
        SYSTEM_PROMPT_APPENDIX.format(
            notification=NOTIFICATION_FILENAME,
            skill=skill_directory / SKILL_FILE,
            tools=", ".join(tools),
        ),
        PROMPT.format(project_key=project_key),
    ]


def main(argv: list[str] | None = None) -> int:
    """Print the command line, ready to paste into a Run's working directory."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print(
            "usage: python3 -m grafana_jsm_sandbox.run_command"
            " <skill-directory> <runs-directory> <project-key>",
            file=sys.stderr,
        )
        return 2
    print(shlex.join(build_run_command(argv[0], argv[1], argv[2])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
