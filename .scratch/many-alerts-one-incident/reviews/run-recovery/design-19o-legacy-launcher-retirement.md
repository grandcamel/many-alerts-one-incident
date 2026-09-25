# 19o: close the legacy executable launch path

Status: proposed local source change, 2026-09-25. Fixed point: `72ee0c7`.
Authority: accepted ADRs 0011–0013, tickets 36–38, the journaled
admission-only front door and reviewed 19h/19n contracts. This change
starts no Run, registers no grant and calls no provider or tenant endpoint.

## Finding and decision

`python -m grafana_jsm_sandbox` currently calls `serve`, which constructs
the historical in-process Jira Forwarder and `RunSpawner`. That spawner
puts `CLAUDE_CODE_OAUTH_TOKEN` directly in the child environment, registers
one Jira sentinel and starts the child without a durable reservation,
Run/launch claim, guarded barrier or effect permit. ADR 0013 supersedes the
direct model credential exception, and ADRs 0011/0012 require scoped
Forwarder and durable recovery gates. The standalone
`python -m grafana_jsm_sandbox.forwarder` also starts a credentialed HTTP
Jira proxy and prints a sentinel for arbitrary local requests without the
new reservation/effect controls. The container's `docker/entrypoint.sh`
currently writes Claude onboarding configuration *before* invoking the
module. The separate `journaled_receiver` entrypoint admits Notifications
but starts no Run.

Close the historical executable before credential parsing, listener startup
or process creation. The module's `main` returns a fixed nonzero
`legacy_launch_disabled` diagnostic for an empty argument list and retains
usage code 2 for arguments. Direct calls to `serve` raise the same fixed
exception before doing any work; there is no environment or flag that
reenables it. The standalone Forwarder `main` likewise refuses before
credential parsing, sentinel creation or listener startup, with its usage
code retained for arguments. The default container entrypoint refuses
before creating or changing onboarding files; a custom container command
is passed through without onboarding mutation. Keep
`Settings.from_environment`, `RunSpawner` and the historical `Forwarder`
class as isolated testable modules, but no shipped executable may invoke
their legacy runtime composition. No new launcher is exposed. The
journaled front door remains admission-only.

Update the README, demo runbook, Dockerfile and Compose comments at their entrypoints
so the old commands are not presented as currently usable. Keep the
historical walkthrough labelled as archival reference and point to the
journaled local replay path for admission-only testing. Relabel container
tests that described the old stack as currently launchable. Quarantine
the former `DEMO_CONTAINER` and `DEMO_END_TO_END` live test opt-ins so those
environment variables cannot silently turn archival tests into live
acceptance against this disabled stack. Do not change
credentials, Compose resources, the Skill or a tenant. The only runtime
behavior changes are fail-closed startup of the two legacy executables and
removal of the default entrypoint's onboarding write.

Acceptance: tests call `main` with a complete credential-shaped environment
and with missing credentials, proving identical fixed refusal and no
configuration read, Forwarder, Receiver or spawner construction. A direct
`serve` call refuses before `Forwarder.start`; standalone Forwarder `main`
does not read a credential or start a listener. The default shell
entrypoint exits nonzero without writing onboarding configuration; an
explicit custom command remains pass-through. The old live test opt-ins
remain skipped even when their historical environment flags are set;
importing `RunSpawner` and
historical pure tests remains possible. Subprocess module invocations exit
nonzero without a listener or child. Ruff, independent Standards/Spec
source review and the full local suite precede commit. This is source/local
evidence only; production guarded launch, native client, venue, provider,
tenant and paid acceptance remain NOT RUN.
