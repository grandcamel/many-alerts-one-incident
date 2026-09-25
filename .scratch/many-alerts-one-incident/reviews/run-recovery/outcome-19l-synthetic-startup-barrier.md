# 19l closed synthetic startup barrier outcome

Date: 2026-09-25. Baseline: `26a0948`.

The [19l plan](implementation-plan-19l-synthetic-startup-barrier.md) produced
a fixed inert Python child in
`prototype/run_timing/synthetic_barrier.py`. Its isolated, no-site process
starts a new session, acknowledges that it is blocked on a parent-owned pipe,
and emits one inert marker only after an exact release byte. The parent checks
the blocked acknowledgment and same-session leader identity before release.
Closing the release pipe or sending a wrong byte exits without the marker.
This fixture accepts no caller-selected command, environment or endpoint.

Independent Standards and Spec source reviews pass after fixes for second-pipe
allocation cleanup, `-I -S` startup isolation, failed-handoff reaping and
observation-descriptor cleanup on reap failure. Eight focused tests pass,
including those fault paths; Ruff passes. The full local suite passes:
**5,504 passed, 39 skipped in 384.23 seconds**. `git diff --check` passes.

This is synthetic process evidence only. The fixture does not persist a
launch/spawn observation, authenticate a ledger reservation, register or
activate a Forwarder grant, prove stable group identity after root exit,
contain a native client, or release a production Run barrier. Native,
provider, tenant and intended-venue acceptance are **NOT RUN**. Ticket 37
remains open.
