# Runs use `--permission-mode dontAsk` with an allow list, not skip-permissions

Every existing wrapper on this machine launches headless Claude with `--dangerously-skip-permissions`. We deliberately do not. A Run starts with `--permission-mode dontAsk` and `--allowedTools "Bash(jira-as *)" "Read"`, so any tool call outside that list is denied without a prompt and surfaces as a `permission_denied` event in the stream-json output. This is what lets the audience see a run that cannot do anything except talk to Jira.

## Consequences

- The purpose-built skill mounted into the Run must describe every operation in terms of `jira-as` invocations, because nothing else will execute.
- The log formatter prints denials, so a misbehaving prompt is visible rather than silent.
