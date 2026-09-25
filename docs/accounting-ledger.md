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

`LedgerStore.inspect_reservation_view(directory)` uses the same query-only
verification and checked handle release. A `ready` view contains the anchored
head, ledger identity and generation, experiment ID, `population=unknown`, and
an empty reservation tuple. This v1 format rejects fixture genesis and every
`reservation_created` row, so the empty tuple is verified negative evidence;
it cannot supply a durable positive reservation fact. Held or unverified views
release no identity, head or reservation facts. This read is one stopped-image
observation, not a continuing lease or a reservation permit.

`reservation_scan.scan_reservation` combines the two read-only views for one
intent and always returns a hold. For a verified journal intent, this v1
ledger can supply only missing reservation evidence; a journal confirmation
is never treated as a ledger reservation. The views are taken separately, so the
result is a stopped-image observation and cannot authorize a launch.

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

The [18e evidence/archive contract](../.scratch/many-alerts-one-incident/reviews/receiver-journal/design-18e-accounting-evidence-archive.md)
defines only future input and archival failure rules. A candidate envelope
is a source claim, not authenticated billing. The proposed archive handoff
needs read-back, an independent continuity witness and an active duplicate
index covering attempts, reservations and charge lines. If its history is
unavailable, model reservation and dispatch remain held; bounded Notification
admission continues. No importer, archive or witness is implemented here.

The [18g proposed archive format](../.scratch/many-alerts-one-incident/reviews/receiver-journal/design-18g-archive-format.md)
pins contiguous event segments, a derived cumulative duplicate index and an
ordered read-back/witness/registration handoff for a future ledger version.
The current v1 append-only schema has no registration or compaction transition,
so it cannot perform that handoff. The 18g format covers one ledger generation;
cross-generation replay and compaction remain separately gated. A local digest
or off-cluster copy without an independent witness cannot prove continuity.
This is documentation only; no archive bytes or reserve method are created.

`accounting_evidence_candidate` parses only bounded canonical private
metadata envelopes. It preserves source, account-scope, coverage and payload
digest as unverified claims, and detects changed bytes under a repeated
candidate ID within one bounded batch. This is not a persistent duplicate
index. It never reads the claimed payload or
authenticates a billing source. A parsed claim is not an opening balance,
charge line, coverage proof, archive entry or reservation input. The current
v1 store still rejects every production reservation.

The [reviewed 18c design](../.scratch/many-alerts-one-incident/reviews/receiver-journal/design-18c.md)
and [implementation plan](../.scratch/many-alerts-one-incident/reviews/receiver-journal/implementation-plan-18c.md)
define the physical format and local tests. Local SQLite/restart/crash-image
tests do not qualify power-loss durability, storage volume flush honesty,
provider billing, native/model execution, tenant/venue behavior, paid dispatch
or human Report adjudication. A consistent rollback of the database, WAL and
anchor needs an external witness and cannot be detected from these files alone.
