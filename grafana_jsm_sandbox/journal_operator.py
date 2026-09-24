"""The operator CLI: create a state directory and verify-only inspect it
(ticket 37, unit 17b). Never starts the front door and never touches a
running one's files except through the read-only, lock-taking inspect path.

    python3 -m grafana_jsm_sandbox.journal_operator create --state-dir S
    python3 -m grafana_jsm_sandbox.journal_operator inspect --state-dir S

Error discipline matches ``journal_spool`` and ``recovery_journal``: every
``except`` body only assigns a local variable, and a fresh error is raised
after the ``try`` statement with ``from None``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .journal_reducer import DEFAULT_BOUNDS, JournalBounds
from .journal_spool import SpoolError, create_spool, survey_spool, sync_directory
from .recovery_journal import JournalError, create_recovery_journal, inspect_recovery_journal

OPERATOR_ERROR_CODES = frozenset({"operator_argument", "state_exists"})


class OperatorError(Exception):
    """A fixed, non-diagnostic operator-CLI rejection; never embeds caller data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _mkdir(path: Path) -> None:
    """0700, refusing an existing path. Also the shape a crash midway through
    ``create_state`` leaves behind, since nothing here is idempotent by design
    (plan L332: remove ``S`` by hand; nothing was ever acknowledged)."""
    failed = False
    try:
        path.mkdir(mode=0o700)
    except OSError:
        failed = True
    if failed:
        raise OperatorError("state_exists") from None


def create_state(
    state_directory: Path, *, bounds: JournalBounds = DEFAULT_BOUNDS, **clocks_and_ids,
) -> dict:
    """Create ``S``, ``S/spool`` and ``S/journal`` with genesis, all 0700,
    syncing the parent after ``mkdir S`` and ``S`` after both subdirectories
    exist (V23; critic 13). Refuses an existing path.
    """
    if not isinstance(state_directory, Path):
        raise OperatorError("operator_argument")
    _mkdir(state_directory)
    sync_directory(state_directory.parent)

    create_spool(state_directory / "spool")
    _mkdir(state_directory / "journal")
    sync_directory(state_directory)

    journal = create_recovery_journal(state_directory / "journal", bounds=bounds, **clocks_and_ids)
    try:
        journal_uuid = journal.snapshot()["journal_uuid"]
    finally:
        journal.close()
    return {"journal_uuid": journal_uuid}


def inspect_state(state_directory: Path) -> tuple[int, dict]:
    """Verify-only. The report, plus the spool survey once the journal is
    verified ready; exit codes 0-6 (see ``main``)."""
    code = None
    inspection = None
    try:
        inspection = inspect_recovery_journal(state_directory / "journal")
    except JournalError as error:
        code = error.code
    if code is not None:
        exit_code = 3 if code == "journal_locked" else 4
        return exit_code, {"verdict": "error", "code": code}

    report = dict(inspection.report)
    verdict = report["verdict"]
    if verdict != "ready":
        report["spool"] = None
        return (6 if verdict == "unverified" else 1), report

    spool_code = None
    survey = None
    try:
        survey = survey_spool(state_directory / "spool", inspection.references)
    except SpoolError as error:
        spool_code = error.code
    if spool_code is not None:
        report["spool"] = None
        report["spool_error"] = spool_code
        return 4, report

    report["spool"] = survey
    inconsistent = bool(
        survey["missing_total"] or survey["mismatched_total"] or survey["mismatched_orphans_total"]
    )
    return (5 if inconsistent else 0), report


def _inspect_stderr_code(report: dict) -> str | None:
    """The one code most worth a human seeing on stderr, if any (critic 8d)."""
    code = None
    if "spool_error" in report:
        code = report["spool_error"]
    elif "code" in report:
        code = report["code"]
    elif report.get("finding") is not None:
        code = report["finding"]["code"]
    elif report.get("reason") is not None:
        code = report["reason"]
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create or verify-only inspect a journaled-receiver state directory."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "inspect"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--state-dir", required=True)
    arguments = parser.parse_args(argv)
    state_directory = Path(arguments.state_dir)

    if arguments.command == "create":
        code = None
        result = None
        try:
            result = create_state(state_directory)
        except (OperatorError, JournalError, SpoolError) as error:
            code = error.code
        if code is not None:
            print(json.dumps({"error": code}))
            print(code, file=sys.stderr)
            return 1
        print(json.dumps(result))
        return 0

    exit_code, report = inspect_state(state_directory)
    print(json.dumps(report))
    if exit_code != 0:
        stderr_code = _inspect_stderr_code(report)
        if stderr_code is not None:
            print(stderr_code, file=sys.stderr)
    return exit_code


__all__ = [
    "OPERATOR_ERROR_CODES",
    "OperatorError",
    "create_state",
    "inspect_state",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
