"""The log formatter renders one Run event into audience lines.

`format_event` is a pure function: one parsed Run event in, zero or more display
lines out. The table below is driven by events taken straight from the recorded
Transcript in `fixtures/run-transcript.jsonl` wherever a real event exists for
the case, so the expectations are pinned to what the Claude CLI actually emits
rather than to what we imagine it emits.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass

import pytest

from grafana_jsm_sandbox.log_formatter import (
    DIAGNOSTIC,
    RESULT,
    RUN,
    format_event,
    format_stream,
)
from tests.conftest import FIXTURES

REPO_ROOT = FIXTURES.parent
TRANSCRIPT = FIXTURES / "run-transcript.jsonl"


def recorded(match) -> dict:
    """The first event in the recorded Transcript satisfying `match`."""
    for line in TRANSCRIPT.read_text().splitlines():
        event = json.loads(line)
        if match(event):
            return event
    raise AssertionError("no recorded event matched")


def assistant_event(content: list[dict]) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


def tool_call_event(name: str, tool_input: dict) -> dict:
    return assistant_event(
        [{"type": "tool_use", "id": "toolu_01", "name": name, "input": tool_input}]
    )


def bash_event(command: str) -> dict:
    return tool_call_event("Bash", {"command": command})


def tool_result_event(content, is_error: bool = False) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_01",
                    "content": content,
                    "is_error": is_error,
                }
            ],
        },
    }


def result_event(**fields) -> dict:
    return {
        "type": "result",
        "subtype": "success",
        "duration_ms": 1500,
        "num_turns": 2,
        "total_cost_usd": 0.1,
        **fields,
    }


@dataclass
class Case:
    id: str
    event: object
    expected: list[str]


CASES = [
    Case(
        id="run-start-names-the-permission-mode-and-allowed-tools",
        event=recorded(lambda e: e.get("subtype") == "init"),
        expected=["[run]    model=claude-fable-5-1 permission-mode=dontAsk tools=Bash,Read"],
    ),
    Case(
        id="assistant-text",
        event=recorded(
            lambda e: e.get("type") == "assistant" and e["message"]["content"][0]["type"] == "text"
        ),
        expected=["[claude] I'll run the two bash commands in order and report which worked."],
    ),
    Case(
        id="assistant-text-over-several-lines",
        event=assistant_event(
            [{"type": "text", "text": "Alert is firing.\n\nOPS-41 is the Match."}]
        ),
        expected=[
            "[claude] Alert is firing.",
            "[claude] OPS-41 is the Match.",
        ],
    ),
    Case(
        id="bash-tool-call-shows-its-command",
        event=recorded(
            lambda e: (
                e.get("type") == "assistant" and e["message"]["content"][0]["type"] == "tool_use"
            )
        ),
        expected=["[tool]   Bash: seq 1 40"],
    ),
    Case(
        id="read-tool-call-shows-its-path",
        event=tool_call_event(
            "Read", {"file_path": "/runs/20260915T164012-9f3ac1/notification.json"}
        ),
        expected=["[tool]   Read: /runs/20260915T164012-9f3ac1/notification.json"],
    ),
    Case(
        # Presenter story 5 wants every jira-as command in the log. A command cut
        # off halfway is the line that invites the question of what the rest said.
        id="long-command-is-shown-in-full",
        event=bash_event(
            "jira-as issue create --project OPS " + "--label fp-a1b2c3d4e5f60718 " * 12
        ),
        expected=[
            "[tool]   Bash: jira-as issue create --project OPS "
            + "--label fp-a1b2c3d4e5f60718 " * 12
        ],
    ),
    Case(
        id="tool-result-longer-than-the-trim-limit-is-trimmed",
        event=recorded(
            lambda e: e.get("type") == "user" and not e["message"]["content"][0].get("is_error")
        ),
        expected=[
            "[out]    1",
            "[out]    2",
            "[out]    3",
            "[out]    4",
            "[out]    5",
            "[out]    + 35 more lines",
        ],
    ),
    Case(
        id="tool-result-line-wider-than-the-trim-limit-is-truncated",
        event=tool_result_event("OPS-41 " + "x" * 400),
        expected=["[out]    OPS-41 " + "x" * 193 + "..."],
    ),
    Case(
        id="result-of-a-denied-call-is-not-echoed-a-second-time",
        event=recorded(lambda e: e.get("type") == "user" and e.get("tool_result_meta")),
        expected=[],
    ),
    Case(
        id="failing-tool-result-is-marked-as-error",
        event=tool_result_event("jira-as: no Incident matched", is_error=True),
        expected=["[err]    jira-as: no Incident matched"],
    ),
    Case(
        id="permission-denied-is-unmistakable",
        event=recorded(lambda e: e.get("subtype") == "permission_denied"),
        expected=[
            (
                "[DENIED] Bash: Permission to use Bash has been denied because Claude Code "
                "is running in don't ask mode."
            ),
        ],
    ),
    Case(
        id="permission-denied-without-a-message-still-says-so",
        event={
            "type": "system",
            "subtype": "permission_denied",
            "tool_name": "WebFetch",
            "decision_reason_type": "mode",
        },
        expected=["[DENIED] WebFetch: denied (mode)"],
    ),
    Case(
        id="final-result-carries-cost-and-duration",
        event=recorded(lambda e: e.get("type") == "result"),
        expected=[
            "[DENIED] Bash: ls /etc",
            "[result] success in 10.0s, 3 turns, $0.4527",
        ],
    ),
    Case(
        id="result-without-denials-is-a-single-line",
        event=result_event(permission_denials=[]),
        expected=["[result] success in 1.5s, 2 turns, $0.1000"],
    ),
    Case(
        id="result-missing-its-numbers-still-ends-the-log",
        event={"type": "result", "subtype": "error_during_execution"},
        expected=["[result] error_during_execution in unknown"],
    ),
    Case(
        id="system-chatter-renders-nothing",
        event=recorded(lambda e: e.get("subtype") == "task_summary"),
        expected=[],
    ),
    Case(
        id="unknown-event-type-gets-one-diagnostic-line",
        event={"type": "wobble", "payload": 1},
        expected=["[?]      unrecognised event type 'wobble'"],
    ),
    Case(
        id="event-that-is-not-an-object-gets-one-diagnostic-line",
        event=[1, 2, 3],
        expected=["[?]      event is not a JSON object"],
    ),
    Case(
        id="malformed-known-event-gets-one-diagnostic-line",
        event={"type": "assistant", "message": "this should have been an object"},
        expected=["[?]      'assistant' event could not be rendered"],
    ),
    Case(
        id="assistant-event-with-no-content-renders-nothing",
        event=assistant_event([]),
        expected=[],
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_event_renders_its_audience_lines(case):
    assert format_event(case.event) == case.expected


# A per-Run sentinel is a random token with no recognisable prefix. The earlier
# version of this table used an ATATT-prefixed value, which the prefix rule
# rescued no matter what the rule under test did; four of these commands leaked.
# This one carries punctuation, so the catch-all for long opaque values cannot
# rescue the rules either: each has to fire on its own.
SENTINEL = "xK3-mZ9_qB7tW2vR5nL8pC4y"
BARE_SENTINEL = "9f3ac1d7e4b8c05a1d2e3f405162738495a6b7c8"
ATLASSIAN_TOKEN = "ATATT3xFfGF0aBcDeFgHiJkLmNoP"
BASIC_CREDENTIAL = "ZW1haWw6c2VjcmV0dG9rZW4="

CREDENTIAL_COMMANDS = [
    pytest.param(
        f"curl -H 'Authorization: Basic {SENTINEL}' https://site/rest", SENTINEL, id="basic-header"
    ),
    pytest.param(
        f'curl -H "Authorization: SSWS {SENTINEL}" https://site/rest', SENTINEL, id="other-scheme"
    ),
    pytest.param(
        f"curl -u jason@example.com:{SENTINEL} https://site/rest", SENTINEL, id="curl-user-flag"
    ),
    pytest.param(f"jira-as issue get OPS-41 --token {SENTINEL}", SENTINEL, id="token-flag"),
    pytest.param(
        f'jira-as issue get OPS-41 --token "{SENTINEL}"', SENTINEL, id="quoted-token-flag"
    ),
    pytest.param(f"jira-as issue get OPS-41 --api-key={SENTINEL}", SENTINEL, id="api-key-flag"),
    pytest.param(
        f"env JIRA_API_TOKEN={SENTINEL} jira-as issue get OPS-41", SENTINEL, id="env-assignment"
    ),
    pytest.param(f'{{"jira_api_token": "{SENTINEL}"}}', SENTINEL, id="json-field"),
    pytest.param(
        f"machine site.atlassian.net login me password {SENTINEL}", SENTINEL, id="netrc-line"
    ),
    pytest.param(
        f"echo {BARE_SENTINEL} | mail me", BARE_SENTINEL, id="bare-value-with-no-clue-around-it"
    ),
    pytest.param(f"echo {ATLASSIAN_TOKEN} | mail me", ATLASSIAN_TOKEN, id="atlassian-token"),
    pytest.param(
        f"echo 'Basic {BASIC_CREDENTIAL}' >> notes", BASIC_CREDENTIAL, id="bare-basic-credential"
    ),
]


@pytest.mark.parametrize(("command", "credential"), CREDENTIAL_COMMANDS)
@pytest.mark.parametrize(
    "as_event",
    [
        pytest.param(bash_event, id="in-a-tool-call"),
        pytest.param(lambda text: tool_result_event(text), id="in-a-tool-result"),
        pytest.param(
            lambda text: result_event(
                permission_denials=[{"tool_name": "Bash", "tool_input": {"command": text}}]
            ),
            id="in-a-denied-command",
        ),
    ],
)
def test_no_line_ever_carries_a_credential(as_event, command, credential):
    lines = format_event(as_event(command))

    assert lines, "the event rendered nothing, so the redaction was not exercised"
    rendered = "\n".join(lines)
    assert credential not in rendered
    leaked = [
        credential[at : at + 8]
        for at in range(len(credential) - 8)
        if credential[at : at + 8] in rendered
    ]
    assert not leaked, f"part of the credential survived: {leaked}"
    assert "Authorization: Basic" not in rendered
    assert "<redacted>" in rendered


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "The token is a sentinel, so the real password never reaches the Run.",
            id="prose-about-credentials",
        ),
        pytest.param(
            "jira-as issue create --project OPS --label fp-a1b2c3d4e5f60718",
            id="a-fingerprint-label",
        ),
        pytest.param(
            "https://site.atlassian.net/rest/api/3/issue/10001 at 2026-09-15T16:40:12Z",
            id="urls-and-timestamps",
        ),
    ],
)
def test_redaction_leaves_the_demo_vocabulary_alone(text):
    assert format_event(assistant_event([{"type": "text", "text": text}])) == [f"[claude] {text}"]


def test_stream_renders_a_recorded_transcript_end_to_end():
    lines = list(format_stream(TRANSCRIPT.read_text().splitlines()))

    assert lines[0].startswith("[run]")
    assert any(line.startswith("[claude]") for line in lines)
    assert "[tool]   Bash: seq 1 40" in lines
    assert "[out]    + 35 more lines" in lines
    assert "[DENIED] Bash: ls /etc" in lines
    assert lines[-1].startswith("[result] success in ")


def test_stream_survives_a_line_that_is_not_json():
    lines = list(format_stream(["not json at all", '{"type": "result", "subtype": "success"}']))

    assert lines[0].startswith("[?]")
    assert lines[1].startswith("[result]")


def test_stream_reads_the_bytes_a_run_writes():
    written = json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "OPS-41 opened"}]}}
    ).encode()

    assert list(format_stream([written])) == ["[claude] OPS-41 opened"]


def test_stream_ignores_blank_lines():
    assert list(format_stream(["", "   ", ""])) == []


@pytest.mark.parametrize(
    ("argv", "stdin"),
    [
        pytest.param([str(TRANSCRIPT)], None, id="transcript-named-on-the-command-line"),
        pytest.param([], TRANSCRIPT.read_text(), id="transcript-on-standard-input"),
    ],
)
def test_command_line_entry_renders_the_recorded_transcript(argv, stdin):
    result = subprocess.run(
        [sys.executable, "-m", "grafana_jsm_sandbox.log_formatter", *argv],
        cwd=REPO_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0].startswith("[run]")
    assert "[DENIED] Bash: ls /etc" in lines
    assert lines[-1].startswith("[result] success in ")


def test_a_rate_limit_event_is_not_worth_a_line():
    """Every real Transcript carries these; none of them is news to an audience."""
    assert format_event({"type": "rate_limit_event", "rate_limit": {"status": "allowed"}}) == []


INCIDENT_TRANSCRIPT = FIXTURES / "run-transcript-repeat-firing.jsonl"
"""A whole real Run: the repeat Firing that commented the trend and moved OPS-7 on."""


def test_a_whole_real_run_renders_without_a_single_diagnostic():
    """The Transcript a demo actually produces, rendered by the code a demo runs."""
    lines = list(format_stream(INCIDENT_TRANSCRIPT.read_text().splitlines()))

    unrendered = [line for line in lines if line.startswith(DIAGNOSTIC)]
    assert not unrendered, f"the formatter did not understand a real Run: {unrendered}"

    # The audience has to be able to read every jira-as command in full.
    assert any("jira-as collaborate comment add OPS-7" in line for line in lines)
    assert any("jira-as lifecycle transition OPS-7 --id 31" in line for line in lines)
    assert lines[0].startswith(RUN)
    assert lines[-1].startswith(RESULT)


def test_a_whole_real_run_puts_nothing_credential_shaped_on_the_screen():
    text = "\n".join(format_stream(INCIDENT_TRANSCRIPT.read_text().splitlines()))
    assert "Authorization" not in text
    assert "JIRA_API_TOKEN" not in text
