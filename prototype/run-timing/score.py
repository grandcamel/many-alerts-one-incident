#!/usr/bin/env python3
"""PROTOTYPE — throwaway. Mechanical pre-check of each Report against the Ground truth.

It does not grade. It pulls out what a human grader needs — did the Report name the
flag, did it cite the two traces, did it swallow either red herring, how many of the
seven Fingerprints reached the Incident — and prints the Report itself to read.

    python3 score.py            # every arm
    python3 score.py opus5-high # one arm, with the full Report
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
RUNS = HERE / "runs"

FINGERPRINTS = [
    "f1a2b3c4d5e60718", "a9b8c7d6e5f40312", "0c1d2e3f4a5b6970", "7e6d5c4b3a291807",
    "2b3c4d5e6f708192", "8f9e0d1c2b3a4556", "4d5e6f708192a3b4",
]
CAUSE_TRACE = "3f5c1a90b7d4e2118a6c0f3e9d215b47"
BASELINE_TRACE = "bb70c4e2119d3a5f8e61c0742a9f3d16"

CHECKS = {
    "names the flag": r"recommendation.?cache|recommendationCache|feature.{0,10}flag",
    "names the flip time": r"14:02(:00)?",
    "cites the cause trace": re.escape(CAUSE_TRACE[:16]),
    "cites the baseline trace": re.escape(BASELINE_TRACE[:16]),
    "cites the cache_hit attribute": r"cache_hit",
    "cites the Change id": r"\b412\b",
    "states a confidence": r"[Cc]onfidence",
    "bounds the blast radius": r"cart|payment|shipping|checkout",
    "RED HERRING blames the payment deploy": r"payment\s+v?1\.8\.3|deploy.{0,40}payment.{0,40}cause|payment deploy.{0,30}(cause|root)",
    "RED HERRING blames host capacity": r"(host|node).{0,40}(capacity|out of|scale up|insufficient|exhaust)",
}


def adf_text(blob: str) -> str:
    """Pull the plain text out of a Description whose ADF arrived as a JSON string."""
    try:
        fields = json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        return blob or ""
    return " ".join(re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', json.dumps(fields)))


def look(arm: Path, verbose: bool) -> None:
    summary = arm / "meta.json"
    if not summary.exists():
        return
    final = ""
    transcript = arm / "transcript.jsonl"
    if transcript.exists():
        for line in transcript.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                final = event.get("result") or ""

    state_path = arm / "hands-state.json"
    report = ""
    labels: list[str] = []
    comments: list[str] = []
    if state_path.exists():
        state = json.loads(state_path.read_text())
        for issue in state.get("issues", {}).values():
            report += adf_text(issue.get("custom", "")) + "\n"
            labels += issue.get("labels", [])
            comments += issue.get("comments", [])

    haystack = "\n".join([final, report, "\n".join(comments)])
    print(f"\n=== {arm.name} " + "=" * (58 - len(arm.name)))
    for label, pattern in CHECKS.items():
        hit = re.search(pattern, haystack, re.IGNORECASE) is not None
        mark = "yes" if hit else "no "
        if label.startswith("RED HERRING"):
            mark = "SWALLOWED" if hit else "avoided"
        print(f"  {mark:10} {label}")
    found = sum(1 for fingerprint in FINGERPRINTS if f"fp-{fingerprint}" in " ".join(labels))
    print(f"  {found}/7 of 7   Fingerprint labels on the Incident")
    print(f"  {len(report.split()):<10} words in the Report's Description")
    if verbose:
        print("\n--- Report (Description, text only) ---")
        print(report.strip()[:6000] or "(none filed)")
        print("\n--- Final lines ---")
        print(final.strip()[-2500:])


def main() -> int:
    if not RUNS.exists():
        print("no runs yet")
        return 1
    wanted = sys.argv[1:] 
    arms = [RUNS / one for one in wanted] if wanted else sorted(
        one for one in RUNS.iterdir() if one.is_dir())
    for arm in arms:
        look(arm, verbose=bool(wanted))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
