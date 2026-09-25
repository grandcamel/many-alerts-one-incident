# Unit 19i2: no-writer v3 confirmation and shared ledger identity

Status: local implementation plan, 2026-09-25. Fixed point: `abe75ba`.
Authority: reviewed 19i design, accepted ADR 0012–0013, tickets 37–38.
This unit adds descriptive record/replay and read-only inspection only. It
does not authenticate a ledger, reserve spend, write a confirmation from the
Receiver, grant a Run, or permit dispatch.

## File-by-file sequence

1. `journal_records.py`: add the private v3
   `reservation_confirmation` validator/actor pair with exact v2-shaped
   fields, v3 rule and 2,048-byte cap. Keep v1 public and v2 registry/bytes
   unchanged. Unknown version/type pairs stay unsupported.
2. `journal_reducer.py`: add a separately tagged v3 confirmation projection
   and pure planner/replay. Require exactly one v3 intent and one confirmation
   per intent, distinct claim/ledger IDs, shared aggregate 256-confirmation
   cap, recovery-byte capacity, and exact v3 intent digest. Both v2 and v3
   confirmation planners consult the same cross-version ledger event and
   `(ledger_uuid, generation, sequence)` identity check, in either arrival
   order. The v2-only digest and v3 initial-intent digest stay unchanged.
3. `recovery_journal.py`: expose v3 confirmation count/digest as an
   unverified, outstanding claim in snapshot and verify-only inspection,
   plus typed facts in the stopped claim view. No field says confirmed or
   permitted. A held, lagged or failed-close image releases no v3 facts.
4. `reservation_scan.py`: after both stopped images verify, return an
   explicit `v3_unsupported` hold for a target present in the v3 claim view.
   Its existing v2-only bridge cannot truthfully call that target missing;
   this unit does not extend the comparator or admit a positive path.
5. Add focused validator, forged recomputed record, duplicate identity,
   capacity, mixed-version and real SQLite/WAL reopen tests. Run changed-file
   Ruff and the full local suite after independent Standards and Spec reviews.
   Write a truthful outcome and ticket 37/38 updates before the named-file
   commit.

The cross-version ledger check is future-proof: current replay cannot hold
both v2 and v3 reservation intents in one valid history because v2 requires
an unresolved hold and v3 refuses one. It still must reject collisions in
both directions once a reviewed disposition transition allows such history.
No positive accounting or external acceptance is implied.
