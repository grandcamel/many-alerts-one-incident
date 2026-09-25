# 19o legacy executable retirement outcome

Date: 2026-09-25. Baseline: `72ee0c7`.

The reviewed [design](design-19o-legacy-launcher-retirement.md) and
[file-by-file plan](implementation-plan-19o-legacy-launcher-retirement.md)
close the historical `grafana_jsm_sandbox` and standalone `forwarder`
module executables before credential parsing, listener startup, sentinel
creation or Run process creation. Direct `serve` calls fail closed. The
default container entrypoint refuses before changing Claude onboarding
state; an explicitly supplied command passes through without that mutation.
`Settings`, `RunSpawner` and the old Forwarder class remain isolated
historical test subjects, not a current launch path.

The README, Dockerfile, Compose and demo runbook now label the old stack
archival. Former `DEMO_CONTAINER` and `DEMO_END_TO_END` opt-ins are
permanently skipped so their old live paths cannot be mistaken for current
acceptance. The journaled Receiver remains admission-only.

Independent Standards and Spec source reviews report **PASS** after the
test-documentation corrections. Focused startup/container/Forwarder/spawner
checks passed **119, with 36 archived live checks skipped**; changed-file
Ruff, shell syntax and `git diff --check` pass. The full local suite passed
**5,530 passed, 39 skipped in 386.97 seconds**.

No container was built or run; no native client, provider, tenant, paid,
venue, credential, deployment or human experiment was run. This closes
only the legacy executable paths. The guarded production launcher,
durable accounting qualification, Forwarder grant activation, effect
writer and dispatch permit remain open under tickets 36–38.
