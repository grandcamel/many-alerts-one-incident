# 19u outcome: unqualified reconciliation after restart

Date: 2026-09-25. Fixed point: `5cd58c8`.

The reviewed [design](design-19u-no-writer-restart-reconciliation.md)
and [implementation plan](implementation-plan-19u-no-writer-restart-reconciliation.md)
add a private v3 recovery claim for a fresh reported Jira OPS readback
after Receiver restart. Replay binds an earlier-boot mutation intent,
current boot, active restart hold, latest verified restart commit/digest,
recovered predecessor head, exact target and predecessor. It does not
assume the hold's stored origin equals the latest restart sequence. Up to
four new-boot observations per operation persist across all restarts,
with at most 884,736 recovery bytes at the 64-operation bound. No writer
or escrow was added.

Live and stopped inspection display the original effect boot and recovery
boot with each reported state under `reconciliation_unqualified`.
`confirmed` and `absent` remain untrusted reports, not effect settlement or
proof of no prior write. The claim cannot clear a hold or authorize retry.

Independent Standards and Spec design/source reviews passed after the
boot-boundary inspection correction. Six direct tests and 30 focused
journal/architecture tests passed; changed-file Ruff and `git diff --check`
passed. The full local suite passed **5,624 tests, 39 skipped in 399.65s**.
Native, provider, paid, tenant, venue, power-loss and human acceptance are
**NOT RUN**. Ticket 37 remains open.
