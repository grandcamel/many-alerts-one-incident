# 18e local contract plan

Status: proposed documentation-only plan, 2026-09-25. Baseline: `cd1365f`.
Design: `design-18e-accounting-evidence-archive.md`.

1. Review the envelope's claim/verification distinction against ADR 0013,
   ticket 38 and the 18c v1 store. Check that no field or status asserts
   provider authenticity, complete opening history, line uniqueness or
   billing finality without a selected source profile.
2. Review archive ordering against ticket 38's capacity and retention
   contract. Check that every failure leaves active evidence intact and
   preserves duplicate uncertainty, and that no local read-back is called
   an independent rollback witness.
3. Record independent Standards and Spec review, then update the local
   ticket 38 and accounting docs with the exact remaining decisions.
   Commit documentation only after whitespace and protected-artifact
   read-back. Source and full tests are `NOT RUN` for this unit.

Any later parser, importer, archive format or ledger migration needs its own
reviewed source plan and local tests. The current goal does not authorize
provider access, paid probes, new credentials, resource provisioning or a
production reservation.
