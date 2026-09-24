# Runs use `--permission-mode dontAsk` with an allow list, not skip-permissions

Every existing wrapper on this machine launches headless Claude with `--dangerously-skip-permissions`. We deliberately do not. A Run starts with `--permission-mode dontAsk` and `--allowedTools "Bash(jira-as *)" "Read"`, so any tool call outside that list is denied without a prompt and surfaces as a `permission_denied` event in the stream-json output. This is what lets the audience see a run that cannot do anything except talk to Jira.

## Consequences

- The purpose-built skill mounted into the Run must describe every operation in terms of `jira-as` invocations, because nothing else will execute.
- The log formatter prints denials, so a misbehaving prompt is visible rather than silent.

## Amendments

**2026-09-23, from the `/proc` probe (demo-onboarding step 01).** The bare `Read` on the allow list is replaced by `Read` scoped to two absolute directories: `Read(//<runs directory>/**)`, which holds each Run's working directory and its Notification, and `Read(//<skill directory>/**)` until the Skill is rendered under the runs directory. A leading `//` is Claude Code's form for an absolute path. The probe ([probe-2026-09-23.md](../../.scratch/demo-onboarding/probe-2026-09-23.md)), on Claude Code 2.1.272 in the hardened container, showed why: with the bare rule, a Run whose prompt asked for the Jira token read it from `/proc/1/task/1/environ`, the Receiver's environment, which the Run's uid could read. With the scoped rules that path, `/proc/self/root/...`, a `..` walk out of the runs directory and `/home/demo/.claude.json` were all denied by permission, while the Notification and the Skill stayed readable. The allow list is still two tools; `Read` now reaches only what a Run is meant to read. A permission rule covers Claude's own tools and not the files jira-as opens itself, so the Receiver is also non-dumpable (ADR 0002's amendment).
