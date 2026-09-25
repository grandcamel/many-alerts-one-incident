# 35b: Receiver admission to Run telemetry identity handoff

Status: source-contract correction, 2026-09-25. Ticket 35 remains open.

The journaled Receiver commits a Notification and returns an `AdmissionReceipt`;
it does not create a Run, know a rehearsal, or own a projection generation.
The legacy one-notification/one-Run path is not the journaled admission path.
The proposed telemetry specification must not imply that a Notification commit
already supplies a Run identity, a rehearsal scope, or permission to export.

## Plan

1. Correct the proposed ticket-35 specification at its identity, event,
   association and queue boundaries. Require a reviewed trusted handoff from
   durable admission to a rehearsal and optional Run before staging shared
   telemetry; do not use journal generation as telemetry generation.
2. Record the source finding and unresolved handoff in ticket 35 and the local
   frontier. No Receiver, telemetry codec, collector, dashboard, or tenant
   behavior changes in this unit.
3. Read back the edited claims against the current Receiver and accepted ADR,
   obtain independent Standards/Spec source reviews, check the diff, and commit
   only named documentation paths. Runtime, native, provider, tenant, venue and
   human acceptance remain NOT RUN.

## Decision boundary

The future handoff must identify the trusted rehearsal, the journal admission
ID, and either the Run ID or an explicit unassigned state; it must define the
authorization and sequencing owner before any record can enter the shared
24-hour feed. A local bounded queue over unbound receipts cannot by itself
be a ticket-35 Run feed or a 35a per-Run gap emitter.
