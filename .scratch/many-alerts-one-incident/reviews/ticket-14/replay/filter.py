#!/usr/bin/env python3
"""Offline filter of captured 1m Grafana POSTs; not a scheduler simulation."""
import json
import sys
from pathlib import Path


def sets(row):
    alerts = row["body"]["alerts"]
    return (
        frozenset(a["fingerprint"] for a in alerts if a["status"] == "firing"),
        frozenset(a["fingerprint"] for a in alerts if a["status"] == "resolved"),
    )


def replay(path, repeat):
    # Per (grafana_folder, alertname), retain the last *sent* payload state and time.
    entries, kept = {}, []
    for line_no, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        key = tuple(sorted(row["groupLabels"].items()))
        firing, resolved = sets(row)
        prior = entries.get(key)
        if prior is None:
            send, why = bool(firing), "first"
        else:
            old_t, old_firing, old_resolved = prior
            if not firing <= old_firing:
                send, why = True, "new-firing"
            elif not firing:
                send, why = bool(old_firing), "all-resolved"
            elif not resolved <= old_resolved:
                send, why = True, "new-resolved"
            elif old_t < row["t"] - repeat:  # strictly elapsed > repeat
                send, why = True, "repeat"
            else:
                send, why = False, "-"
        if send:
            entries[key] = (row["t"], firing, resolved)
            kept.append((line_no, row, why))
    return kept


for name in ("paymentUnreachable", "emailMemoryLeak"):
    path = Path(sys.argv[1]) / f"notifications-{name}.jsonl"
    print(f"{name} source={path}")
    for repeat in (60, 300, 600):
        kept = replay(path, repeat)
        print(f"  repeat={repeat}: {len(kept)} lines=" +
              ",".join(f"{line}:{why}" for line, _, why in kept))
