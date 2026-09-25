# 35b outcome: admission identity handoff remains open

Status: source-contract correction, 2026-09-25. Ticket 35 remains open.

Read-back of `JournaledReceiver` and `RecoveryJournal.admit` shows an actual
post-commit `AdmissionReceipt` with admission ID, result, decision, source
group and journal sequence. That path is explicitly admission-only. It has no
Run ID, rehearsal ID, telemetry generation, collector queue, native session
mapping or export authorization. The legacy direct launcher creates a Run in
a different path and cannot provide this journaled handoff.

The proposed telemetry specification now requires a trusted
admission-to-rehearsal/Run handoff before a shared record is staged. It keeps
rehearsal-unbound receipts in the journal and distinguishes a deliberately
unassigned, operator-only Notification from an invented Run. An unassigned
record is excluded from every Run read. The 35a gap codec remains a pure
per-Run grammar; it cannot represent loss for the current unbound receipts.

This unit changes documentation only. No Receiver, queue, transport, tenant,
collector, native exporter, dashboard or retention behavior was run or
verified. Native, provider, paid, tenant, venue and human acceptance are
**NOT RUN**. Final identity ownership, enforcement of operator-only scope for
deliberately unassigned Notifications, queue caller, delivery, retention and
audience acceptance remain unresolved. Independent Standards and Spec source
reviews passed after the operator-only clarification; `git diff --check`
passed. No test suite was run for this documentation-only unit.
