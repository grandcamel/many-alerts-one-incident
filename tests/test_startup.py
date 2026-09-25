"""Historical settings remain parseable; executable legacy launch refuses."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from grafana_jsm_sandbox import forwarder as legacy_forwarder
from grafana_jsm_sandbox.__main__ import (
    IncompleteConfiguration,
    LegacyLaunchDisabled,
    Settings,
    main,
    serve,
)
from grafana_jsm_sandbox.run_command import SKILL_FILE
from grafana_jsm_sandbox.run_spawner import ANTHROPIC_TOKEN_VARIABLE

COMPLETE = {
    "JIRA_SITE_URL": "https://example.atlassian.net",
    "JIRA_EMAIL": "ops@example.invalid",
    "JIRA_API_TOKEN": "a-real-token",
    ANTHROPIC_TOKEN_VARIABLE: "an-anthropic-oauth-token",
}


def complete_but(**overrides) -> dict[str, str]:
    """The complete environment with variables replaced, or removed when set to None."""
    environment = dict(COMPLETE, **overrides)
    return {name: value for name, value in environment.items() if value is not None}


def test_a_complete_environment_gives_the_receiver_everything_a_run_needs():
    settings = Settings.from_environment(COMPLETE)

    assert settings.credential.site_url == "https://example.atlassian.net"
    assert settings.credential.email == "ops@example.invalid"
    assert settings.credential.api_token == "a-real-token"
    assert settings.anthropic_token == "an-anthropic-oauth-token"


def test_the_skill_directory_defaults_to_the_one_in_this_repo():
    settings = Settings.from_environment(COMPLETE)

    assert (settings.skill_directory / SKILL_FILE).is_file()


def test_the_receiver_listens_where_the_container_expects_it_to():
    settings = Settings.from_environment(COMPLETE)

    assert settings.host == "0.0.0.0"
    assert settings.port == 8080


def test_the_container_can_say_where_everything_lives(tmp_path):
    settings = Settings.from_environment(
        complete_but(
            RECEIVER_HOST="127.0.0.1",
            RECEIVER_PORT="9000",
            RUNS_DIRECTORY=str(tmp_path / "runs"),
            SKILL_DIRECTORY="/srv/skill",
            RUN_TIMEOUT="45",
        )
    )

    assert (settings.host, settings.port) == ("127.0.0.1", 9000)
    assert settings.runs_directory == tmp_path / "runs"
    assert settings.skill_directory == Path("/srv/skill")
    assert settings.run_timeout == 45


@pytest.mark.parametrize(
    "variable",
    ["JIRA_SITE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", ANTHROPIC_TOKEN_VARIABLE],
)
def test_historical_settings_name_a_missing_credential(variable):
    with pytest.raises(IncompleteConfiguration) as error:
        Settings.from_environment(complete_but(**{variable: None}))
    assert variable in str(error.value)


def test_historical_settings_name_every_missing_credential_at_once():
    with pytest.raises(IncompleteConfiguration) as error:
        Settings.from_environment({})
    said = str(error.value)
    for variable in COMPLETE:
        assert variable in said


def test_historical_settings_stop_on_a_site_url_that_is_not_a_url():
    with pytest.raises(IncompleteConfiguration) as error:
        Settings.from_environment(complete_but(JIRA_SITE_URL="example.atlassian.net"))
    assert "JIRA_SITE_URL" in str(error.value)


def test_historical_settings_stop_on_a_port_that_is_not_a_number():
    with pytest.raises(IncompleteConfiguration) as error:
        Settings.from_environment(complete_but(RECEIVER_PORT="eight thousand"))
    assert "RECEIVER_PORT" in str(error.value)


def test_historical_settings_stop_on_a_timeout_that_is_not_a_number():
    with pytest.raises(IncompleteConfiguration) as error:
        Settings.from_environment(complete_but(RUN_TIMEOUT="five minutes"))
    assert "RUN_TIMEOUT" in str(error.value)


@pytest.mark.parametrize("environment", [COMPLETE, {}, complete_but(JIRA_EMAIL=None)])
def test_legacy_module_refuses_before_configuration_or_serve(monkeypatch, capsys, environment):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy startup reached a side effect")

    monkeypatch.setattr(Settings, "from_environment", forbidden)
    monkeypatch.setattr("grafana_jsm_sandbox.__main__.serve", forbidden)
    assert main([], environment=environment) == 1
    assert capsys.readouterr().err == "legacy_launch_disabled\n"


def test_direct_legacy_serve_refuses():
    with pytest.raises(LegacyLaunchDisabled, match="^legacy_launch_disabled$"):
        serve(object())  # type: ignore[arg-type] - refusal precedes configuration use.


def test_standalone_forwarder_refuses_before_credential_or_listener(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy Forwarder reached a side effect")

    monkeypatch.setattr(legacy_forwarder.JiraCredential, "from_environment", forbidden)
    monkeypatch.setattr(legacy_forwarder.Forwarder, "start", forbidden)
    assert legacy_forwarder.main([]) == 1
    assert capsys.readouterr().err == "legacy_forwarder_disabled\n"


@pytest.mark.parametrize("module, diagnostic", [
    ("grafana_jsm_sandbox", "legacy_launch_disabled"),
    ("grafana_jsm_sandbox.forwarder", "legacy_forwarder_disabled"),
])
def test_legacy_module_subprocess_exits_without_starting(module, diagnostic):
    completed = subprocess.run(
        [sys.executable, "-m", module],
        cwd=Path(__file__).resolve().parent.parent,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(Path(__file__).resolve().parent.parent)},
        capture_output=True, text=True, check=False, timeout=5,
    )
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == diagnostic + "\n"
