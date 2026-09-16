# PROTOTYPE — does a high-effort Run fit the slot?

Throwaway. It answers ticket 11 of the many-alerts-one-incident map and nothing else.
Nothing here is meant to survive into the specs; the validated decision goes on the
ticket and the map, and this branch stays as the primary source behind it.

## The question

A demo slot is thirty minutes and one lifecycle, and the map's standing preference is
that one Run may think for about five minutes on screen. Does a print-mode Run at Opus 5
on high effort fit that, against a Cascade rather than chapter one's single Alert? What
does it cost, and what do Fable 5.1 and a lower effort do to both numbers?

## What it fakes, and what it does not

Real: the Claude Code CLI, print mode, `dontAsk`, the allow list, `stream-json`, the
model and effort flags, the skill being read from a mounted directory.

Canned: the Notification (seven Alerts, one Fault), the telemetry behind `bin/eyes`, and
Jira behind `bin/jira-as`. No network, no Grafana, no Atlassian site.

`--safe-mode` is what makes a laptop Run resemble the container: no user `CLAUDE.md`, no
plugins, no skills, no MCP servers, no hooks, with auth still working.

## Run it

```bash
python3 make_fixtures.py     # regenerate the Cascade and the telemetry (already committed)
./arms.sh                    # the four arms, one after another, then the table
python3 score.py             # the mechanical pre-check of every Report
python3 score.py opus5-high  # one arm, with its Report printed in full
```

One arm on its own:

```bash
python3 measure.py run opus5-high --model claude-opus-5 --budget 3 --wait 900
```

`runs/` is git-ignored: transcripts carry local paths. `results/` holds what was
published.

## The pieces

| Path | What it is |
| --- | --- |
| `make_fixtures.py` | Generates the Cascade and the four signals, deterministically |
| `fixtures/notification-cascade.json` | Seven Alerts across five services, one Fault |
| `fixtures/ground-truth.md` | The Fault, the chain, the two red herrings, the scoring |
| `telemetry/` | Metrics, logs, traces and Changes the Eyes answer from |
| `bin/eyes` | Eyes, stubbed: metrics, logs, traces, changes, read-only |
| `bin/jira-as` | Hands, stubbed: the jira-as subset the skill uses, logged to `hands.log` |
| `skill/incident-report/SKILL.md` | A draft of chapter two's skill, written far enough to time |
| `measure.py` | Runs one arm in a fresh directory; parses the Transcript into numbers |
| `score.py` | Pulls each Report apart against the Ground truth for a human to grade |
| `arms.sh` | The four arms |
