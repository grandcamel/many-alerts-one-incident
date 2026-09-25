# grafana-jsm-sandbox

Grafana alert Notification -> sandboxed Claude Run -> Jira OPS Incident. See `README.md` for what the demo is and needs; the OPS facts a Run relies on are in `skill/incident-sync/SKILL.md` and `docs/adr/0004-fingerprint-label-and-platform-ops-only.md`.

## Agent skills

### Issue tracker

Issues live as local markdown under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
