# Unit 19i3: v3 claim input to the stopped negative scanner

Status: local implementation plan, 2026-09-25. Fixed point: `b17c5a4`.
Authority: reviewed 19i design and 19i1/19i2 outcomes, ADR 0013, ticket 38.
This unit is read-only. It cannot produce a positive reservation or dispatch
result while the Receiver ledger reports unknown population and no
reservation events.

## File-by-file sequence

1. `reservation_scan.py`: after both stopped images pass existing verification
   and ledger-population checks, convert v2 and v3 journal intent and
   confirmation claims to the common structural bridge facts. Feed the union
   to `assess_bridge`; keep its hold-only result and closed reason gate.
   Retain `v3_unsupported` in the closed vocabulary for older callers, but
   a current verified v3 claim with no ledger counterpart now yields
   `missing_ledger`. Do not trust a claim as ledger evidence, add a ledger
   writer, or bypass the unknown-population gate.
2. Tests: use real stopped SQLite/WAL journal and ledger images for v3
   intent-only and v3-confirmed claims; assert `missing_ledger`, no changed
   bytes, and the existing unverified/unsupported precedence. Preserve
   v2/no-claim results. Run focused tests and changed-file Ruff.
3. Independent Standards/Spec source review, full local suite, truthful
   outcome/ticket update, protected-work readback and named-file commit.

The observations are sequential, not an atomic cross-store snapshot.
Authoritative opening history, charge identity, coverage/lag/finality,
liability U, independent continuity and venue evidence remain external gates.
