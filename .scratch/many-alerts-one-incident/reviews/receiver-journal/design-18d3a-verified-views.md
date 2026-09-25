# 18d3a: verified read-only reservation views

Status: accepted local source design, 2026-09-25. Baseline: `92aace8`.
Authority: ADR 0013, tickets 37 and 38, the 18c accounting store, 18d1
hold-only comparator and 18d2 journal claim replay. This unit exposes
bounded facts from verified stopped local histories. It performs no cross-
store join, reservation, append, permit or launch.

## Why the current inspection reports are insufficient

`inspect_recovery_journal` replays the complete journal without acknowledgement
but reports only a claim count and digest. `LedgerStore.inspect` verifies its
store without acknowledgement but reports only the head and ledger identity.
The current v1 durable ledger accepts only Receiver/`unknown` genesis and
rejects every `reservation_created` event on create and replay. It cannot
yield a verified durable reservation fact or a positive SQLite triple.
The new journal view supplies replayed claim facts; the narrowed ledger view
supplies verified negative evidence for this exact store version. Directly
constructing 18d1 dataclasses from arbitrary caller data would leave
`read_back` self-asserted.

## Journal view

Add a separate verify-only `inspect_reservation_claim_view(directory)` that
shares the existing journal custody, WAL-absence, lock, row replay, anchor
and close rules. Its `ready` result contains journal UUID/generation/head,
immutable tuples of the replayed `ReservationIntentClaim` and
`ReservationConfirmationClaim`, and their digest. It reports fixed `held` or
`unverified` codes with no facts otherwise. The ordinary public inspection
report remains count/digest only. An anchor lag of one commit is a mandatory
`unverified` result with no claim facts for this view, although the existing
inspection report can describe a later reanchor. The view never acknowledges
or adopts a lagging anchor.
The WAL-presence check is repeated after the store lock is taken and before
SQLite opens, then the opened store's WAL observation is checked before facts
are released. This closes the preflight/open disappearance window for the
stopped-image contract.
The view is a reading of one stopped image, not a continuing lease on it.

## Ledger view

Add a separate verify-only `LedgerStore.inspect_reservation_view(directory)`
through the same custody, lock, SQLite `query_only`, full replay and anchor
checks as `inspect`. A `ready` result contains ledger UUID/generation,
experiment ID, population=`unknown`, verified anchored head and an empty
immutable reservation tuple. That emptiness follows from the exact v1 store
validation and replay rules, not from a query over unchecked rows. A held or
unverified result contains no facts. Fixture genesis and crafted reservation
rows must be rejected, not reported as `ready`. No raw event bytes, profile,
price, prompt, credential or Ground truth is exposed. Durable positive
reservation evidence needs a separately reviewed compatible store format;
pure synthetic accounting transition tests are not a substitute.

## Custody and limitations

Each view verifies its own image independently, closes handles on every
path, and does not append or rewrite an anchor. Apart from the existing
inspect lock-file behavior, no file is created. WAL absence and tail lag are
unverified. Custody and corruption use each existing inspector's fixed-code
`held`/`unverified` classifier, always without facts. The new journal
view catches observable `os.close` failures and drops all facts; lower-level
SQLite-close and unlock errors are currently suppressed by `JournalStore`
and cannot be claimed as detected. The old journal inspection result and
exception behavior stay exact. The ledger view retains its existing checked
handle-release behavior.
Neither view accepts an externally supplied `read_back` boolean. The views
are not an atomic cross-store snapshot; a later scanner must still compare
current heads and hold any absence, conflict or uncertainty. Even a matching
pair is not a production reserve: opening population, provider coverage,
liability U, continuity witness and archive policy remain unresolved.

18d3b will invoke both inspectors directly and always return a hold. It can
compare no-intent and intent-only journal images with the verified empty v1
ledger. A ledger-only or exact durable triple cannot be produced by this
store; those positive paths remain pure synthetic until a compatible
non-production format is separately designed and reviewed. This unit stops
at the independently verified views to keep custody and replay reviewable.
