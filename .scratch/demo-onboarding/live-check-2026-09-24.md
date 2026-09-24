# Live check: the branch end to end on the owner's site (2026-09-24)

The owner approved the live checks. They ran from this worktree against the owner's OPS project (a
dedicated ITSM project) on the owner's Intel laptop, with Docker Desktop 4.91.0 / Engine 29.8.0 and
Compose 5.5.1. The images were built from the branch under `:onboarding` tags through a scratch
compose override, so `main`'s `grafana-jsm-sandbox:latest` was left untouched. `.env` was a copy of
the owner's with `DEMO_PROJECT_KEY=OPS` added; configure wrote the rest.

## What ran, in the Quickstart's order

| Step | Command | Result |
| --- | --- | --- |
| discover | `configure` | `READY`. It found the four field ids that had been hand-edited into the Skill (Severity, Urgency, Source, Major incident), plus the service desk and the Incidents queue URL; the queue id matches the one in the address bar. |
| leftover | `reset --dry-run`, then `reset` (owner approved) | One unexplained open `fp-` Incident was completed with resolution Done and closed. The compose failure (no stack yet) was reported without losing the rest of the report; exit 1 as designed. |
| write facts | `configure --write` | 5 keys written, `READY` |
| preflight | `doctor --only host,env,jira,facts` | `READY` (30 checks) |
| stack | `docker compose … up -d --build` | Healthy within about 16s |
| preflight | `doctor --only stack,grafana` | `READY`. `/proc/1/environ` is unreadable to the Runs' uid (non-dumpable Receiver, live). The Skill was rendered for OPS. The in-container Jira call through a Forwarder returned 200. The rule's query matches 1 series on the pinned Grafana 13.2.1. |
| model | `doctor --only stack --with-model` | `READY`, $0.1227. Opus 5 ran, `Bash(jira-as *)` was allowed, and `Read` reached the rendered Skill. |
| lifecycle | `verify --replay` | `VERIFIED` in 85s: Open → Work in progress → Completed with resolution Done. Three Runs, $1.1384. |
| lifecycle | `verify --live` | `VERIFIED` in 198s: Firing 52s after the stop, Incident 38s after that, Work in progress 68s after creation, Normal 15s after the start, Completed 22s after that. Three Runs, $1.1298. |
| reset | `reset` | Traffic started, queue empty, exit 0 |
| container checks | `DEMO_CONTAINER=1 pytest tests/test_container.py tests/test_grafana.py` | 120 passed, 1 skipped (no corporate CA configured) |

Each Run on Opus 5 took 22–25s, 7–11 turns and $0.33–$0.46. No Run logged `[FAILED]`, `[DENIED]` or
`[retry]`. Total live spend this session, probes included, was about $2.80.

## Friction the live run itself found

- **Claude Code's auto mode refused the Jira-reading helpers as "production reads".** The first
  `configure` got through; a later read-only `reset --dry-run` was refused. The owner added local
  allow rules (`.claude/settings.local.json`, git-ignored) to go on. The engineer's agentic setup
  skill will meet the same refusal, so the skill now has a ground rule for it: hand the blocked
  command back and never route around it, and suggest allow rules for the read-only commands only,
  so every Jira write still stops at a permission prompt.
- **Build names.** `docker compose build` from any clone of either repo tags
  `grafana-jsm-sandbox:latest`, which silently replaces the other one's image. Harmless for an
  engineer with one clone; the owner has both.
