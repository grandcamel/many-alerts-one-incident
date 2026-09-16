#!/usr/bin/env python3
"""PROTOTYPE — throwaway. Runs one arm of the timing experiment and measures it.

    python3 measure.py run opus5-high   --model claude-opus-5   --wait 600
    python3 measure.py run fable51-high --model claude-fable-5-1
    python3 measure.py run opus5-medium --model claude-opus-5 --effort medium
    python3 measure.py report

Each arm gets a fresh working directory, so every arm faces the same world: no open
Incident, the same Cascade, the same telemetry. `--safe-mode` is what makes a laptop Run
resemble the container: no user CLAUDE.md, no plugins, no skills, no MCP servers.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent.resolve()
RUNS = Path(os.environ.get("RUN_TIMING_OUT", HERE / "runs"))
SKILL_DIR = HERE / "skill"
SKILL_FILE = "incident-report/SKILL.md"

SYSTEM_PROMPT = """\
You are a Run: one headless invocation handling exactly one Grafana Notification.

The Notification is the file notification.json in your working directory. It carries a
Cascade of Alerts. Your instructions are the skill at {skill}. Read it first and follow
it exactly.

Your tools are exactly these: {tools}. Every other tool call will be denied, so do not
reach for one — the skill never needs one. You have no clock and you cannot write files."""

PROMPT = (
    "Read the skill, then handle the Cascade in notification.json as it says: "
    "investigate it with eyes, file one Incident for the Fault, and write the Report. "
    "Finish with the lines the skill's Finish section names."
)

ALLOWED_TOOLS = ("Bash(eyes *)", "Bash(jira-as *)", "Read")


def build_command(model: str, effort: str | None, budget: float) -> list[str]:
    command = [
        "claude", "--print",
        "--safe-mode", "--strict-mcp-config",
        "--permission-mode", "dontAsk",
        "--permission-prompts", "none",
        "--allowedTools", *ALLOWED_TOOLS,
        "--output-format", "stream-json", "--verbose",
        "--add-dir", str(SKILL_DIR),
        "--model", model,
        "--max-budget-usd", str(budget),
        "--append-system-prompt",
        SYSTEM_PROMPT.format(skill=SKILL_DIR / SKILL_FILE, tools=", ".join(ALLOWED_TOOLS)),
        PROMPT,
    ]
    if effort:
        command[command.index("--model"):command.index("--model")] = ["--effort", effort]
    return command


def run(args) -> int:
    workdir = RUNS / args.arm
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    shutil.copy(HERE / "fixtures" / "notification-cascade.json", workdir / "notification.json")

    environment = {
        **os.environ,
        "PATH": f"{HERE / 'bin'}:{os.environ['PATH']}",
        "EYES_DATA": str(HERE / "telemetry"),
        "HANDS_LOG": str(workdir / "hands.log"),
        "HANDS_STATE": str(workdir / "hands-state.json"),
    }
    command = build_command(args.model, args.effort, args.budget)
    (workdir / "command.txt").write_text("\n".join(command) + "\n")

    transcript = workdir / "transcript.jsonl"
    started = time.monotonic()
    with transcript.open("w") as sink:
        process = subprocess.Popen(
            command, cwd=workdir, env=environment, stdout=sink,
            stderr=subprocess.PIPE, text=True, start_new_session=True,
        )
        try:
            _, errors = process.communicate(timeout=args.wait)
            killed = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, 9)
            _, errors = process.communicate()
            killed = True
    wall = time.monotonic() - started

    (workdir / "meta.json").write_text(json.dumps({
        "arm": args.arm, "model": args.model, "effort": args.effort or "high (default)",
        "wall_seconds": round(wall, 1), "exit_status": process.returncode,
        "killed_at_wait": killed, "wait_seconds": args.wait,
    }, indent=2) + "\n")
    if errors.strip():
        (workdir / "stderr.txt").write_text(errors)
    print(f"{args.arm}: {wall:.1f}s wall, exit {process.returncode}"
          + (" (KILLED at --wait)" if killed else ""))
    return 0


def summarise(workdir: Path) -> dict | None:
    transcript = workdir / "transcript.jsonl"
    if not transcript.exists():
        return None
    meta = json.loads((workdir / "meta.json").read_text())
    tools: dict[str, int] = {}
    commands: list[str] = []
    denials = 0
    errors = 0
    result: dict = {}
    init: dict = {}
    for line in transcript.read_text().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init = event
        elif event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    tools[name] = tools.get(name, 0) + 1
                    if name == "Bash":
                        commands.append(block.get("input", {}).get("command", ""))
        elif event.get("type") == "user":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    text = json.dumps(block.get("content", ""))
                    if block.get("is_error"):
                        errors += 1
                    if "permission" in text.lower() or "denied" in text.lower():
                        denials += 1
        elif event.get("type") == "result":
            result = event

    usage = result.get("usage", {})
    hands = workdir / "hands.log"
    return {
        "arm": meta["arm"],
        "model_asked": meta["model"],
        "model_seen": init.get("model", "?"),
        "effort": meta["effort"],
        "wall_seconds": meta["wall_seconds"],
        "killed": meta["killed_at_wait"],
        "exit_status": meta["exit_status"],
        "result_subtype": result.get("subtype", "(no result line)"),
        "duration_ms": result.get("duration_ms"),
        "api_ms": result.get("duration_api_ms"),
        "turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_write": usage.get("cache_creation_input_tokens"),
        "cache_read": usage.get("cache_read_input_tokens"),
        "tool_calls": sum(tools.values()),
        "tools": tools,
        "eyes_calls": sum(1 for one in commands if one.strip().startswith("eyes")),
        "hands_calls": sum(1 for one in commands if one.strip().startswith("jira-as")),
        "hands_logged": len(hands.read_text().splitlines()) if hands.exists() else 0,
        "tool_errors": errors,
        "denials": denials,
        "final_text": (result.get("result") or "")[-1400:],
    }


def report(args) -> int:
    rows = [summarise(one) for one in sorted(RUNS.iterdir()) if one.is_dir()] if RUNS.exists() else []
    rows = [row for row in rows if row]
    if not rows:
        print("no runs yet")
        return 1
    print(f"{'arm':16} {'model':20} {'effort':16} {'wall':>7} {'turns':>6} {'tools':>6} "
          f"{'eyes':>5} {'hands':>6} {'cost':>9} {'out tok':>8} {'result':>16}")
    for row in rows:
        print(f"{row['arm']:16} {str(row['model_seen'])[:20]:20} {str(row['effort'])[:16]:16} "
              f"{row['wall_seconds']:>6.1f}s {str(row['turns']):>6} {row['tool_calls']:>6} "
              f"{row['eyes_calls']:>5} {row['hands_calls']:>6} "
              f"{('$' + format(row['cost_usd'], '.4f')) if row['cost_usd'] is not None else '-':>9} "
              f"{str(row['output_tokens']):>8} {str(row['result_subtype'])[:16]:>16}")
    (RUNS / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"\nwrote {RUNS / 'summary.json'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    runner = subparsers.add_parser("run")
    runner.add_argument("arm")
    runner.add_argument("--model", required=True)
    runner.add_argument("--effort")
    runner.add_argument("--budget", type=float, default=3.0)
    runner.add_argument("--wait", type=float, default=900.0,
                        help="outer wall-clock guard; the CLI has none")
    runner.set_defaults(handler=run)
    reporter = subparsers.add_parser("report")
    reporter.set_defaults(handler=report)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
