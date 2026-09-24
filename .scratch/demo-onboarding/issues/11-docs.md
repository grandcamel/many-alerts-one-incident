# Docs: quickstart, admin requests, runbook, ADRs

Type: task
Status: ready-for-agent
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10

See [spec.md](../spec.md), step 11.

## Carried from step 03

- The project `CLAUDE.md` still says the OPS facts a Run relies on are in `skill/incident-sync/SKILL.md`. Since step 03 that file is a template with no project facts; they come from `.env`, rendered by `grafana_jsm_sandbox/skill_template.py` into `<runs directory>/.skill`. Correct the sentence.
- A sample log line in `README.md` still shows `project+%3D+OPS`.
