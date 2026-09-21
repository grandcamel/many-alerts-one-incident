# Ticket 23 synthetic diagnostic ledger plan — 2026-09-21

Implement the diagnostic slice of ADR 0013 for the local fixture harness. This is a
prototype under ticket 23, not completion of ticket 38's Receiver/Forwarder specification
or authorization for live accounting/model execution. Use new temporary fixture databases
only; never load or reconstruct the user's real outstanding budget from guesses.

1. Add a SQLite store with explicit exclusive fixture initialization, open-existing-only
   operations, transactional reserve-before-launch, one-time launch claim and immutable
   receipt attribution. Persist conflict holds and unknown reservations across restart.
2. Enforce the diagnostic $3 reservation, $30/10-attempt and $150 weekly ceilings using
   exact integer microdollars and America/New_York week boundaries. Other model allocation
   actuals may be supplied as labelled synthetic receipts; cloud accounting is excluded.
3. Bind it only to the fixed local process fixtures. Repeated reserve/claim calls cannot
   launch twice; crash windows leave unresolved exposure held. No automatic zero actuals
   or reservation release from a successful fixture exit.
4. Test real SQLite concurrent writers, rollback/crash windows, duplicate/conflicting
   receipts, reopen/rollover, lost/corrupt storage and limits; run the full suite and
   independent Standards/Spec plus bounded Fable review.

Trusted private operator-owned storage and synthetic time/billing observations are inputs.
No production mount/access boundary, authenticated provider billing, power-loss proof,
retention/reconstruction workflow, lifecycle/retry allocation or real Receiver integration
is claimed. Native model launch remains CLOSED in every returned record.
