# Receiver accounting ledger (local non-reserving store)

`accounting_store` persists receiver-origin version-1 accounting events in a
separate owner-only SQLite/WAL directory. `accounting_ledger` constructs an
unknown-population genesis and later receiver events from a verified head. It
is not wired into the Receiver, recovery journal, Forwarder or Run launch path.
No method reserves model spend or returns a launch permit.

The directory contains `ledger.sqlite3`, retained `ledger.sqlite3-wal`, an
8192-byte two-slot `anchor`, and an exclusive `lock`. Creation requires an
absent path and leaves failed-create evidence in place. Open verifies file
custody, exact version-1 schema, integrity, every stored event and the anchor
before exposing its projection. A second writer, missing WAL, symlink,
hard-link, malformed row or physical-head mismatch is refused. Inspect takes
the lock and reports a verified head or a fixed reason code without appending
an event; an absent lock file is the only file it may create.

An append replays the proposed event against the current projection while the
writer lock is held. It commits one row, fully syncs the next anchor slot and
reads both back before returning an `EventReceipt`. Exact event-byte retries
return the historical row identity against the current verified anchor;
changed bytes under an existing event ID persist an `event_conflict` hold.
Any ambiguous commit or sync result latches the open store. An open that sees
exactly one valid committed event beyond the anchor records a durable
`tail_adopted_unreconciled` hold in both anchor slots. A larger gap or corrupt
image holds; no row is discarded or guessed away. Held images remain
inspectable and require a separately reviewed reconciliation or new-generation
continuity procedure.

The receiver genesis has `population=unknown`. A fixture genesis and every
`reservation_created` event are refused. The ledger has no trusted opening
population, provider coverage, bill import, settlement, credits/refunds,
archive, hold-clearing, or cross-store journal handshake. It retains all v1
events up to the 8192 replay/input bound and does not promise 52-week service
at any event rate. The 18a lifetime 512-attempt bound is distinct from ticket
38's proposed 512-active capacity. Creating a new ledger does not prove zero
prior spend or clear an old experiment's liability.

The [reviewed 18c design](../.scratch/many-alerts-one-incident/reviews/receiver-journal/design-18c.md)
and [implementation plan](../.scratch/many-alerts-one-incident/reviews/receiver-journal/implementation-plan-18c.md)
define the physical format and local tests. Local SQLite/restart/crash-image
tests do not qualify power-loss durability, storage volume flush honesty,
provider billing, native/model execution, tenant/venue behavior, paid dispatch
or human Report adjudication. A consistent rollback of the database, WAL and
anchor needs an external witness and cannot be detected from these files alone.
