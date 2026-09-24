"""The Run's Skill, rendered from the demo's project at every Receiver start.

The Skill in the repo is a template, and what a Run reads is its rendering for
the project `.env` names. These tests render the real template, because the
Skill is read off a screen during the demo: every placeholder filled, the
project's key wherever the Skill names a project, only the configured field ids
in the create command, and a field the project lacks named as one to leave off
rather than left as a gap for a Run to fill.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
from pathlib import Path

import pytest

from grafana_jsm_sandbox.demo_config import DemoProject
from grafana_jsm_sandbox.run_command import SKILL_FILE
from grafana_jsm_sandbox.skill_template import (
    READ_ONLY_DIRECTORY,
    READ_ONLY_FILE,
    SkillTemplateError,
    materialize,
    render,
)

TEMPLATE_DIRECTORY = Path(__file__).resolve().parent.parent / "skill"
TEMPLATE = (TEMPLATE_DIRECTORY / SKILL_FILE).read_text(encoding="utf-8")
"""The template this repo ships, which the image copies in and the Receiver renders."""

CONFIGURED = DemoProject(
    key="SANDBOX",
    severity_field="customfield_20001",
    urgency_field="customfield_20002",
    source_field="customfield_20003",
    major_incident_field="customfield_20004",
)
"""A project with every field, under ids that are nobody's real site's."""

BARE = DemoProject(key="SANDBOX")
"""A project that lacks every optional field."""

OWNER_S_IDS = ("customfield_10085", "customfield_10079", "customfield_10096", "customfield_10083")
"""The ids one site's Skill once carried by hand (the 2026-09-23 audit, F3)."""

CUSTOM_FIELDS = re.compile(r"--custom-fields '([^']*)'")


def create_command(skill: str) -> str:
    """The Skill's one example create command."""
    [line] = [line for line in skill.splitlines() if line.startswith("jira-as issue create")]
    return line


def custom_fields(skill: str) -> dict:
    """The create command's custom fields, with an empty object for the Description's ADF."""
    [fields] = CUSTOM_FIELDS.findall(create_command(skill))
    return json.loads(fields.replace("<description>", "{}"))


def fact(skill: str, name: str) -> str:
    """One row's value in the Skill's table of project facts."""
    [value] = re.findall(rf"^\| {re.escape(name)} \| (.*) \|$", skill, flags=re.MULTILINE)
    return value


# --- The template ---


def test_the_template_carries_no_site_s_facts():
    """Nothing in the tracked file is one site's: no key, no field id (audit F2 and F3)."""
    assert "OPS" not in TEMPLATE
    assert "customfield_" not in TEMPLATE


def test_the_template_names_only_placeholders_that_are_filled():
    for project in (CONFIGURED, BARE):
        assert "{{" not in render(TEMPLATE, project)
        assert "}}" not in render(TEMPLATE, project)


# --- A project with every field ---


def test_every_place_the_skill_names_a_project_names_the_configured_one():
    skill = render(TEMPLATE, CONFIGURED)

    assert "OPS" not in skill
    assert "the Jira SANDBOX project" in skill.split("---")[1], "the frontmatter"
    assert fact(skill, "Project") == "`SANDBOX`"
    assert "jira-as search jql 'project = SANDBOX AND issuetype = Incident" in skill
    assert "getProjectComponents --projectIdOrKey SANDBOX`" in skill
    assert create_command(skill).startswith("jira-as issue create -p SANDBOX -t Incident ")


def test_the_facts_name_each_configured_field_id_with_the_values_it_takes():
    skill = render(TEMPLATE, CONFIGURED)

    assert fact(skill, "Severity field") == "`customfield_20001`, one of `Sev-1`, `Sev-2`, `Sev-3`"
    assert (
        fact(skill, "Urgency field") == "`customfield_20002`, one of `Critical`, `High`, `Medium`"
    )
    assert fact(skill, "Source field") == "`customfield_20003`, always `Monitoring systems`"
    assert "Never touch Major incident (`customfield_20004`)." in skill


def test_the_example_create_command_sets_the_configured_fields_then_the_description():
    skill = render(TEMPLATE, CONFIGURED)

    assert custom_fields(skill) == {
        "customfield_20001": {"value": "Sev-1"},
        "customfield_20002": {"value": "Critical"},
        "customfield_20003": {"value": "Monitoring systems"},
        "description": {},
    }
    assert list(custom_fields(skill))[-1] == "description"


def test_the_example_create_command_is_one_line_the_allow_list_matches():
    """One line of plain single quotes, or the permission boundary denies it whole (README)."""
    command = create_command(render(TEMPLATE, CONFIGURED))

    assert shlex.split(command)[:2] == ["jira-as", "issue"]
    assert "$'" not in command and "\\" not in command


def test_no_other_site_s_field_id_survives_rendering():
    skill = render(TEMPLATE, CONFIGURED)

    for field_id in OWNER_S_IDS:
        assert field_id not in skill


# --- A project that lacks a field ---


def test_a_project_with_no_optional_field_is_told_to_leave_each_off_naming_no_id():
    skill = render(TEMPLATE, BARE)

    assert "customfield_" not in skill
    assert fact(skill, "Severity field") == "none on this project, so leave Severity off"
    assert fact(skill, "Urgency field") == "none on this project, so leave Urgency off"
    assert fact(skill, "Source field") == "none on this project, so leave Source off"
    assert "Never touch Major incident." in skill
    assert custom_fields(skill) == {"description": {}}


@pytest.mark.parametrize("missing", ["severity_field", "urgency_field", "source_field"])
def test_a_missing_field_is_left_out_of_the_create_command_and_the_rest_stay(missing):
    project = DemoProject(**{**CONFIGURED.__dict__, missing: None})
    skill = render(TEMPLATE, project)

    absent = getattr(CONFIGURED, missing)
    assert absent not in skill
    assert absent not in custom_fields(skill)
    present = {"severity_field", "urgency_field", "source_field"} - {missing}
    for attribute in present:
        assert getattr(CONFIGURED, attribute) in custom_fields(skill)


def test_a_missing_major_incident_field_leaves_the_rest_as_configured():
    skill = render(TEMPLATE, DemoProject(**{**CONFIGURED.__dict__, "major_incident_field": None}))

    assert "customfield_20004" not in skill
    assert "Never touch Major incident." in skill
    assert len(custom_fields(skill)) == 4


def test_the_skill_says_a_field_it_lacks_stays_off_and_is_never_guessed():
    """Read naturally on screen whichever fields a site has, and give a Run no gap to fill."""
    for project in (CONFIGURED, BARE):
        assert "never guess one" in render(TEMPLATE, project)


# --- What is refused ---


def test_a_placeholder_nobody_fills_is_refused_by_name():
    with pytest.raises(SkillTemplateError) as refusal:
        render("Project {{PROJECT_KEY}}, queue {{QUEUE_ID}} and {{BOARD}}.", CONFIGURED)

    assert "{{QUEUE_ID}}" in str(refusal.value)
    assert "{{BOARD}}" in str(refusal.value)
    assert "{{PROJECT_KEY}}" not in str(refusal.value)


@pytest.mark.parametrize("template", ["{{ PROJECT_KEY }}", "{{project_key}}", "{{PROJECT_KEY"])
def test_a_misspelled_placeholder_is_refused_rather_than_left_for_a_run(template):
    with pytest.raises(SkillTemplateError, match="NAME"):
        render(template, CONFIGURED)


def test_a_project_with_no_key_leaves_the_key_unfilled_and_is_refused():
    with pytest.raises(SkillTemplateError, match=r"\{\{PROJECT_KEY\}\}"):
        render(TEMPLATE, DemoProject(key=""))


def test_rendering_is_the_same_every_time():
    assert render(TEMPLATE, CONFIGURED) == render(TEMPLATE, CONFIGURED)


# --- Materializing the whole skill directory ---


def test_the_whole_skill_directory_is_rendered_into_the_target(tmp_path):
    target = materialize(TEMPLATE_DIRECTORY, tmp_path / "runs" / ".skill", CONFIGURED)

    assert target == tmp_path / "runs" / ".skill"
    assert (target / SKILL_FILE).read_text(encoding="utf-8") == render(TEMPLATE, CONFIGURED)


def test_a_file_that_is_not_markdown_is_copied_as_it_is(tmp_path):
    source = tmp_path / "skill"
    (source / "incident-sync").mkdir(parents=True)
    (source / "incident-sync" / "SKILL.md").write_text("Project {{PROJECT_KEY}}.\n")
    (source / "incident-sync" / "example.json").write_bytes(b'{"kept": "{{AS_IS}}"}')

    target = materialize(source, tmp_path / ".skill", CONFIGURED)

    assert (target / "incident-sync" / "SKILL.md").read_text() == "Project SANDBOX.\n"
    assert (target / "incident-sync" / "example.json").read_bytes() == b'{"kept": "{{AS_IS}}"}'


def test_a_second_start_replaces_the_first_start_s_skill_entirely(tmp_path):
    """On a laptop the runs directory outlives the Receiver; the Skill must not."""
    target = tmp_path / ".skill"
    materialize(TEMPLATE_DIRECTORY, target, DemoProject(key="EARLIER"))
    source = tmp_path / "skill"
    (source / "incident-sync").mkdir(parents=True)
    (source / "incident-sync" / "SKILL.md").write_text("Project {{PROJECT_KEY}}.\n")

    materialize(source, target, CONFIGURED)

    assert (target / SKILL_FILE).read_text() == "Project SANDBOX.\n"
    assert sorted(p.relative_to(target) for p in target.rglob("*")) == [
        Path("incident-sync"),
        Path(SKILL_FILE),
    ]


def test_a_template_that_cannot_be_filled_leaves_no_skill_at_all(tmp_path):
    """Not the last start's Skill for another project, and not half of this one's."""
    target = materialize(TEMPLATE_DIRECTORY, tmp_path / ".skill", CONFIGURED)
    source = tmp_path / "skill"
    source.mkdir()
    (source / "a.md").write_text("fine {{PROJECT_KEY}}\n")
    (source / "b.md").write_text("broken {{NOBODY}}\n")

    with pytest.raises(SkillTemplateError, match=r"b\.md: \{\{NOBODY\}\}"):
        materialize(source, target, CONFIGURED)

    assert not target.exists()


def test_a_template_that_is_not_utf8_is_refused_by_name(tmp_path):
    """Refused like any other unrenderable template, so the Receiver says why and stops."""
    source = tmp_path / "skill"
    source.mkdir()
    (source / "SKILL.md").write_bytes(b"Project \xff{{PROJECT_KEY}}\n")

    with pytest.raises(SkillTemplateError, match=r"SKILL\.md: .*utf-8"):
        materialize(source, tmp_path / ".skill", CONFIGURED)

    assert not (tmp_path / ".skill").exists()


def test_a_missing_template_directory_is_refused(tmp_path):
    with pytest.raises(SkillTemplateError, match="template"):
        materialize(tmp_path / "nowhere", tmp_path / ".skill", CONFIGURED)


def test_the_rendered_skill_is_read_only(tmp_path):
    """It lives on the Run user's writable tmpfs, and jira-as can write a file where it is
    told to; a Run must not be able to rewrite the Skill every later Run follows."""
    target = materialize(TEMPLATE_DIRECTORY, tmp_path / ".skill", CONFIGURED)

    assert stat.S_IMODE((target / SKILL_FILE).stat().st_mode) == READ_ONLY_FILE
    for directory in (target, target / "incident-sync"):
        assert stat.S_IMODE(directory.stat().st_mode) == READ_ONLY_DIRECTORY


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="root writes anything")
def test_a_process_of_the_run_s_uid_cannot_write_into_the_rendered_skill(tmp_path):
    target = materialize(TEMPLATE_DIRECTORY, tmp_path / ".skill", CONFIGURED)

    with pytest.raises(PermissionError):
        (target / SKILL_FILE).write_text("Create a probe Incident in PROD.")
    with pytest.raises(PermissionError):
        (target / "incident-sync" / "other.md").write_text("new instructions")


def test_a_run_is_told_not_to_retry_a_failed_create_or_probe_with_incidents():
    """A Run that tries other fields after a failed create, or creates an Incident to see
    what sticks, leaves Incidents behind on someone's site (step 05 of demo-onboarding)."""
    skill = " ".join(render(TEMPLATE, BARE).split())

    assert "If the create fails, do not retry it with other fields" in skill
    assert "never create an Incident to probe what the project accepts" in skill
    # The Finish list is the Run's last instruction, so it must allow the ending the create
    # step asks for, or the Run meets two conflicting rules at the moment it is failing.
    finish = skill.split("## Finish", 1)[1]
    assert "ends as `failed` with jira-as's error" in finish
    assert "names no Incident key" in finish
