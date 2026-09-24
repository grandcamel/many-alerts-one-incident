"""Legacy-identity tests for the opt-in journaled front door (ticket 37,
unit 17b; Tester T2b, cases L1-L4).

The opt-in is a separate command (``journaled_receiver``); the legacy
Receiver, ``__main__`` and ``replay`` are untouched (see "The user's opt-in
decision and the legacy-identity contract" in
``reviews/receiver-journal/implementation-plan.md``). This file pins that
neither side of the seam leaks into the other: the legacy import graph loads
no journal module or ``sqlite3`` (L1, L2), and the three new modules import
only their allowlists, touch no environment variable or credential name, and
reference no dispatch machinery (L3). L4 pins the shared except-body
discipline over the same three modules.

``journal_spool.py``, ``journaled_receiver.py`` and ``journal_operator.py``
are written in parallel with this file and are not available while it is
drafted; the import allowlists below are transcribed from the plan's "New
modules" section, which is itself the contract these AST checks enforce.

Pure AST and subprocess checks: no journal I/O, no server, no tmp_path.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parent.parent


# === Shared AST helpers ========================================================


def _repo_module_path(name: str) -> Path:
    return REPOSITORY / "grafana_jsm_sandbox" / f"{name}.py"


def _repo_module_ast(name: str) -> ast.Module:
    path = _repo_module_path(name)
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _credential_variable_names() -> frozenset[str]:
    """Every environment-variable NAME that gates a real secret, read from the
    committed modules that hold them -- never hardcoded, never from `.env`."""
    names: set[str] = set()
    forwarder_tree = _repo_module_ast("forwarder")
    for node in ast.walk(forwarder_tree):
        is_environment_variables = (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "ENVIRONMENT_VARIABLES"
            and isinstance(node.value, ast.Dict)
        )
        if is_environment_variables:
            for value in node.value.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    names.add(value.value)

    run_spawner_tree = _repo_module_ast("run_spawner")
    for node in ast.walk(run_spawner_tree):
        is_anthropic_token_variable = (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "ANTHROPIC_TOKEN_VARIABLE"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        if is_anthropic_token_variable:
            names.add(node.value.value)

    # Pinned so a rename in either committed module is noticed here, not
    # silently read as an empty set.
    assert names == {"JIRA_SITE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"}, (
        names
    )
    return frozenset(names)


# === L1: legacy entry points load no journal module or sqlite3 (probe s2) =====

_L1_SCRIPT = """
import json
import sys
import grafana_jsm_sandbox.receiver
import grafana_jsm_sandbox.__main__
import grafana_jsm_sandbox.replay
loaded = sorted(m for m in sys.modules if m == "sqlite3" or "journal" in m)
print(json.dumps(loaded))
"""


def test_l1_legacy_entry_points_load_no_journal_module_or_sqlite3():
    result = subprocess.run(
        [sys.executable, "-c", _L1_SCRIPT], cwd=REPOSITORY,
        capture_output=True, text=True, timeout=30, check=True,
    )
    loaded = json.loads(result.stdout.strip())
    assert loaded == [], (loaded, result.stderr)


# === L2: the legacy modules import none of those either, by source =============

_LEGACY_MODULES = ("receiver", "__main__", "replay", "run_spawner", "notification")


def _banned_journal_import_lines(tree: ast.Module) -> list[int]:
    """Every `journal`-containing or `sqlite3` import target's line number.
    A substring match, not an exact set: it catches `journal_records`,
    `journal_reducer`, `journal_source`, `journal_store`, `journal_ingress`,
    `journal_spool`, `journal_operator`, `recovery_journal` (contains
    "journal") and `journaled_receiver` (starts with "journal") alike, the
    same rule probe s2 used."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "journal" in alias.name or alias.name == "sqlite3":
                    lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            target = node.module or ""
            targets = [target, *(alias.name for alias in node.names)]
            if any("journal" in item or item == "sqlite3" for item in targets):
                lines.append(node.lineno)
    return lines


@pytest.mark.parametrize("name", _LEGACY_MODULES)
def test_l2_legacy_modules_import_no_journal_module_or_sqlite3(name):
    tree = _repo_module_ast(name)
    assert _banned_journal_import_lines(tree) == [], name


# === L3: the three new modules ==================================================

_NEW_MODULES = ("journal_spool", "journaled_receiver", "journal_operator")

_TOP_LEVEL_ALLOW = {
    "journal_spool": frozenset({
        "__future__", "dataclasses", "fcntl", "os", "re", "secrets", "stat", "sys", "threading",
        "pathlib",
    }),
    "journaled_receiver": frozenset({
        "__future__", "argparse", "dataclasses", "io", "json", "logging", "os", "re", "stat",
        "sys", "threading", "time", "types", "collections", "http", "pathlib",
    }),
    "journal_operator": frozenset({"__future__", "argparse", "json", "sys", "pathlib"}),
}

# Relative (`from .x import ...`) imports: exact target -> allowed names.
# `None` means the plan pins only the module target, not its member names
# (journaled_receiver's own `from .journal_spool import ...` is elided with
# "..." in the plan text).
_RELATIVE_ALLOW = {
    "journal_spool": {
        "journal_ingress": frozenset({"MAX_INGRESS_BODY_BYTES", "body_digest"}),
    },
    "journaled_receiver": {
        "journal_ingress": frozenset({
            "INGRESS_HTTP_STATUS", "MAX_INGRESS_BODY_BYTES", "oversize_refusal",
            "refusal_to_json", "sanitize_notification",
        }),
        "journal_spool": None,
        "recovery_journal": frozenset({
            "JournalError", "RecoveryJournal", "ResumeRequest", "new_id", "open_recovery_journal",
        }),
    },
    "journal_operator": {
        "journal_spool": frozenset({
            "SpoolError", "create_spool", "survey_spool", "sync_directory",
        }),
        "recovery_journal": frozenset({
            "JournalError", "create_recovery_journal", "inspect_recovery_journal",
        }),
        "journal_reducer": frozenset({"DEFAULT_BOUNDS", "JournalBounds"}),
    },
}


@pytest.mark.parametrize("name", _NEW_MODULES)
def test_l3_imports_stay_within_allowlist(name):
    tree = _repo_module_ast(name)
    top_level: set[str] = set()
    relative: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                top_level.add((node.module or "").split(".")[0])
            else:
                assert node.level == 1, (name, node.lineno, "unexpected relative import depth")
                target = node.module or ""
                relative.setdefault(target, set()).update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            is_dunder_import = isinstance(func, ast.Name) and func.id == "__import__"
            is_importlib = isinstance(func, ast.Attribute) and func.attr == "import_module"
            assert not is_dunder_import and not is_importlib, (name, "dynamic import call found")

    assert top_level <= _TOP_LEVEL_ALLOW[name], name
    assert set(relative) <= set(_RELATIVE_ALLOW[name]), name
    for target, names in relative.items():
        allowed = _RELATIVE_ALLOW[name][target]
        if allowed is not None:
            assert names <= allowed, (name, target)


@pytest.mark.parametrize("name", _NEW_MODULES)
def test_l3_no_environment_access(name):
    tree = _repo_module_ast(name)
    for node in ast.walk(tree):
        banned = {"environ", "environb", "getenv", "getenvb"}
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            assert not banned.intersection(alias.name for alias in node.names), name
        if isinstance(node, ast.Attribute) and node.attr in banned:
            pytest.fail(f"{name}:{node.lineno} touches os.{node.attr}")
        if isinstance(node, ast.Name) and node.id in banned:
            pytest.fail(f"{name}:{node.lineno} references an environment accessor")


@pytest.mark.parametrize("name", _NEW_MODULES)
def test_admission_only_mode_has_no_os_process_creation(name):
    tree = _repo_module_ast(name)
    banned = {"fork", "forkpty", "system", "popen"}
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.Attribute):
            names = [node.attr]
        elif isinstance(node, ast.Name):
            names = [node.id]
        assert not any(
            item in banned or item.startswith(("exec", "spawn", "posix_spawn"))
            for item in names
        ), (name, node.lineno)


_BANNED_IDENTIFIERS = frozenset({
    "RunSpawner", "Forwarder", "JiraCredential", "spawn_run", "parse_json",
})


@pytest.mark.parametrize("name", _NEW_MODULES)
def test_l3_no_reference_to_dispatch_or_json_parser_names(name):
    tree = _repo_module_ast(name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _BANNED_IDENTIFIERS:
            pytest.fail(f"{name}:{node.lineno} references {node.id!r}")
        if isinstance(node, ast.Attribute) and node.attr in _BANNED_IDENTIFIERS:
            pytest.fail(f"{name}:{node.lineno} references .{node.attr}")


@pytest.mark.parametrize("name", _NEW_MODULES)
def test_l3_no_credential_variable_name_as_a_string_constant(name):
    tree = _repo_module_ast(name)
    credential_names = _credential_variable_names()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in credential_names, (name, node.lineno, node.value)


_BANNED_EXACT_MODULES = (
    "grafana_jsm_sandbox.forwarder", "grafana_jsm_sandbox.run_spawner",
    "grafana_jsm_sandbox.receiver", "grafana_jsm_sandbox.notification",
    "grafana_jsm_sandbox.run_command", "grafana_jsm_sandbox.__main__",
)

# Not a `forwarder*` prefix match: `grafana_jsm_sandbox.forwarder_json` is an
# expected transitive load through `journal_records`/`journal_ingress`
# (critic 15), asserted present below rather than banned.
_FRESH_INTERPRETER_TEMPLATE = """
import json
import sys
import grafana_jsm_sandbox.{module}
banned = {banned!r}
result = {{
    "subprocess_loaded": "subprocess" in sys.modules,
    "loaded_banned": sorted(m for m in sys.modules if m in banned),
    "forwarder_json_loaded": "grafana_jsm_sandbox.forwarder_json" in sys.modules,
}}
print(json.dumps(result))
"""


def _fresh_interpreter_import(module: str) -> dict:
    script = _FRESH_INTERPRETER_TEMPLATE.format(module=module, banned=_BANNED_EXACT_MODULES)
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=REPOSITORY,
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(result.stdout.strip())


def test_admission_only_mode_fresh_interpreter_loads_no_dispatch_modules():
    """One of this unit's `test_admission_only_mode_*` pins (critic 7;
    U17-P18): the lifecycle unit supersedes exactly this test by name once
    dispatch exists. Every other assertion in this file must survive that
    unchanged."""
    result = _fresh_interpreter_import("journaled_receiver")
    assert result["subprocess_loaded"] is False, result
    assert result["loaded_banned"] == [], result
    assert result["forwarder_json_loaded"] is True, result


def test_l3_fresh_interpreter_journal_operator_loads_no_dispatch_modules():
    result = _fresh_interpreter_import("journal_operator")
    assert result["subprocess_loaded"] is False, result
    assert result["loaded_banned"] == [], result
    assert result["forwarder_json_loaded"] is True, result


# === L4: except-body discipline (matches the journal modules' own rule) =======


@pytest.mark.parametrize("name", _NEW_MODULES)
def test_l4_except_bodies_only_assign_or_pass_and_never_raise(name):
    tree = _repo_module_ast(name)
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), (
                name, handler.lineno, type(statement).__name__,
            )
        for inner in ast.walk(handler):
            assert not isinstance(inner, ast.Raise), (name, inner.lineno)
