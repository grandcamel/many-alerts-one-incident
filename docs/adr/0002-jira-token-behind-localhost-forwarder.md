# The Jira token lives in the Forwarder, never in a Run

A Run must call Jira without ever holding the API token. Claude Code's native `sandbox.credentials` masking with `injectHosts` does this, but inside an unprivileged container it needs bubblewrap, TLS termination and `enableWeakerNestedSandbox`, which the docs describe as considerably weakening the sandbox, and the docs do not state whether it applies in `-p` mode. We instead run a localhost Forwarder owned by the Receiver: it holds the real token, replaces the basic-auth header on each request, and forwards to the Atlassian site. Each Run gets a scrubbed environment in which `JIRA_SITE_URL` points at the Forwarder and `JIRA_API_TOKEN` is a per-run sentinel. jira-as uses plain HTTP basic auth through the requests library and accepts an http site URL, so no patching is needed.

## Consequences

- Superseded by ADR 0013: the Anthropic API key stays outside Runs behind a fifth mediated endpoint. The original OAuth credential exception no longer applies to the accepted target design.
- Native masking is a stretch goal to show as the built-in equivalent, not a day-one dependency.
