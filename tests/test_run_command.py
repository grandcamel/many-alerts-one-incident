"""The command line that starts one Run.

The flags here are the demo's permission boundary (ADR 0003): a Run is started
in a mode where anything outside the allow list is denied without a prompt, and
the allow list is jira-as and reading. These tests are what stops a later change
from quietly widening that, which no other test in this repo would notice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grafana_jsm_sandbox.notification import NOTIFICATION_FILENAME
from grafana_jsm_sandbox.run_command import ALLOWED_TOOLS, SKILL_FILE, build_run_command

SKILL_DIRECTORY = Path("/srv/skill")


@pytest.fixture
def command() -> list[str]:
    return build_run_command(SKILL_DIRECTORY)


def value_of(command: list[str], flag: str) -> str:
    """The single value given to `flag`."""
    assert flag in command, f"{flag} is not on the command line"
    return command[command.index(flag) + 1]


def values_of(command: list[str], flag: str) -> list[str]:
    """Every value given to a flag that takes a list, up to the next flag."""
    assert flag in command, f"{flag} is not on the command line"
    rest = command[command.index(flag) + 1 :]
    taken = []
    for argument in rest:
        if argument.startswith("--"):
            break
        taken.append(argument)
    return taken


def test_the_run_is_a_headless_claude_invocation(command):
    assert command[0] == "claude"
    assert "--print" in command


def test_anything_outside_the_allow_list_is_denied_without_a_prompt(command):
    assert value_of(command, "--permission-mode") == "dontAsk"


def test_the_run_may_execute_jira_as_and_read_files_and_nothing_else(command):
    assert values_of(command, "--allowedTools") == ["Bash(jira-as *)", "Read"]
    assert "--dangerously-skip-permissions" not in command
    assert "--allow-dangerously-skip-permissions" not in command
    assert "--disallowedTools" not in command


def test_the_transcript_is_stream_json_one_run_event_per_line(command):
    assert value_of(command, "--output-format") == "stream-json"
    assert "--verbose" in command, "stream-json in print mode needs --verbose"


def test_the_run_can_reach_the_mounted_skill_directory(command):
    assert value_of(command, "--add-dir") == str(SKILL_DIRECTORY)


def test_the_system_prompt_appendix_names_the_notification_and_the_skill(command):
    appendix = value_of(command, "--append-system-prompt")
    assert NOTIFICATION_FILENAME in appendix
    assert str(SKILL_DIRECTORY / SKILL_FILE) in appendix


def test_the_run_is_told_the_same_allow_list_that_is_enforced_on_it(command):
    """A Run that knows what it may do stops reaching for what it may not."""
    appendix = value_of(command, "--append-system-prompt")
    for tool in ALLOWED_TOOLS:
        assert tool in appendix


def test_the_prompt_is_the_last_argument_and_is_not_a_flag(command):
    prompt = command[-1]
    assert not prompt.startswith("-")
    assert NOTIFICATION_FILENAME in prompt


def test_a_relative_skill_directory_is_made_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    command = build_run_command(Path("skill"))
    assert value_of(command, "--add-dir") == str(tmp_path / "skill")
