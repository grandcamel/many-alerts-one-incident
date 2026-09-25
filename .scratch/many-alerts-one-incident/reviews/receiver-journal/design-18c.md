# Unit 18c: durable accounting ledger design

Status: proposed local design for independent critique, 2026-09-24.
Baseline: `221dab94c8828b101bb1f3a35bbe131e0b1d23bd`.
Authority: local source, tests, review and commits only. This is not an ADR
amendment, production reservation, dispatch approval or ticket-38 acceptance.

## Decision and seam

Use the separate Receiver-owned store selected in
`next-accounting-transition-design.md`. The present journal v1 rejects an added
table and has a rehearsal-scoped retention cap. The proposed one-store ticket-38
spec remains a viable later migration; this choice is conditional on the 18d
cross-store recovery proof. The 18c ledger never reads or changes journal v1.

The durable ledger module owns file custody, the exclusive writer, physical
head verification, replay, append and committed read-back. Its small interface
is `create`, `open`, `append`, `inspect` and `close`. The future reservation
module will own journal/provenance verification and will ask this module to
serialize a re-evaluation and append. An arbitrary event or a returned
projection cannot act as a financial receipt. Runs cannot mount the ledger.

Implement 18c in two explicit gates:

1. **18c-storage:** persist and verify receiver-origin v1 events, including an
   unknown-population genesis. It can return a committed *event* receipt. It
   exposes no production reservation call and refuses fixture genesis. It
   neither creates a trusted-complete marker nor imports a charge. This gate
   is implementable and testable locally against the existing 18b format.
2. **18c-reservation:** separately review a compatible event-format extension,
   an external opening-history/coverage verifier, and the reservation
   transaction. This gate cannot be accepted from local ledger creation, a
   process exit, a fixture, or a synthetic billing snapshot. The provider's
   stable charge identity, account scope, coverage/lag and adjustment semantics
   are still open ticket-38 prerequisites. Until they are evidenced, the
   reservation method remains absent and model dispatch stays held.

## Physical v1 store and custody

The 18c-storage directory is created at a nonexistent path, owner-only 0700, with
`ledger.sqlite3`, retained `ledger.sqlite3-wal`, `anchor` and `lock` files at
0600. All are regular, owner-uid, one-link, no-symlink paths. Reject URI
metacharacters (`?`, `#`, `%`) in the directory before SQLite connects; check
`PRAGMA database_list` against the exact database path. A second opener,
including the same process, fails without mutating events. Do not delete or
silently recreate any file. A failed create is evidence, not a reusable empty
ledger. Copying/backing up means all files while the writer is stopped.

Use a distinct SQLite `application_id` (`0x41434c47`, ACLG), `user_version=1`,
STRICT table, and the following v1 DDL. Store only immutable event bytes and
their external digest. The codec and replay enforce canonical field values
beyond these physical shape checks.

```sql
CREATE TABLE ledger_events (
  sequence INTEGER PRIMARY KEY CHECK (sequence BETWEEN 1 AND 8192),
  event_id TEXT NOT NULL UNIQUE CHECK (length(event_id) = 36),
  event_type TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 64),
  body BLOB NOT NULL CHECK (length(body) BETWEEN 2 AND 16384),
  event_digest TEXT NOT NULL UNIQUE CHECK (length(event_digest) = 64)
) STRICT;
CREATE TRIGGER ledger_events_no_update BEFORE UPDATE ON ledger_events
  BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER ledger_events_no_delete BEFORE DELETE ON ledger_events
  BEGIN SELECT RAISE(ABORT, 'append_only'); END;
CREATE TRIGGER ledger_events_contiguous BEFORE INSERT ON ledger_events
  WHEN NEW.sequence != (SELECT coalesce(max(sequence), 0) + 1 FROM ledger_events)
  BEGIN SELECT RAISE(ABORT, 'sequence'); END;
```

The schema verifier compares the
complete `sqlite_schema` tuple, `application_id`, `user_version`, page size,
WAL mode and integrity check before replay. Unknown/newer format is a process
hold; damaged or contradictory v1 is a recovery hold. A duplicate identity
with changed bytes is a conflict, never a second accounting effect.

Use Python >=3.12 and SQLite >=3.37, `SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE`,
exclusive locking, WAL, `synchronous=FULL`, `fullfsync=ON` and
`checkpoint_fullfsync=ON`, `trusted_schema=OFF`, `cell_size_check=ON`,
`page_size=4096`, `max_page_count=40960`, `journal_size_limit=8 MiB`, and
`wal_autocheckpoint=1000`. Set and read back settings. Use the platform's
full-sync primitive without weakening fallback. Creation syncs the parent,
directory and new entries; normal append runs `BEGIN IMMEDIATE`, inserts one
event, commits, syncs the anchor slot, then reads back the exact stored row and
anchor before returning. Any ambiguous write/sync/read-back latches the open
store; retry requires a fresh verified open. No automatic retry or rollback
assumption follows a reported sync error.

The anchor is a separate 8192-byte two-slot file. Its exact version-1 body
contains `format: acct.anchor.v1`, monotonic `counter`, `ledger_uuid`,
`ledger_generation`, `experiment_id`, `head` (`sequence`, `event_digest`), and
nullable durable `hold` (`code`, `observed_sequence`, `boot_id`). Slots have
distinct `ACANCHOR` magic, length, canonical ASCII JSON and tagged SHA-256,
zero padding, at offsets 0 and 4096; the higher valid counter wins. The
genesis row fixes identity, and every row must agree. A valid anchor ahead of
rows, wrong identity/digest, gap, fork, tampered body, replay contradiction or
more than one complete event ahead of the anchor is a hold. Exactly one
verified committed event ahead may be adopted only by writing and reading
back an anchor with a durable `tail_adopted_unreconciled` hold in both slots.
The held image remains inspectable but has no append or reservation path;
clearing it requires a separately reviewed reconciliation or a new generation
with continuity evidence. The store never interprets a missing/unreadable
counterpart as zero history.
The actual device/volume flush guarantee is unqualified by local tests.

Open takes the lock before reading, verifies custody and SQLite presentation,
scans every row through `decode_event(raw, expected_digest=stored_digest)` and
`replay_accounting`, checks row columns against decoded fields and the anchor,
then enables writes. Refuse to connect when the database is shorter than one
page so SQLite cannot discard surviving WAL evidence. Close retains WAL.
Inspect is verify-only and does not append an event or create a WAL; an absent
lock file is its sole allowed new file. A known damaged image is retained for
reconstruction in a new directory. Complete rollback of SQLite, WAL and anchor
to a mutually consistent older image remains undetectable without an external
witness. Production admission needs that witness and restored-state protocol.

## Event receipts, identity and serialization

`append(event, expected_head)` requires the held writer, exact current head,
receiver actor, matching store identity, valid v1 event, and a successful pure
transition. It rejects `reservation_created` in 18c-storage. A receiver genesis
starts with `population=unknown`; a fixture genesis is invalid for this store.
After confirming no durable hold, `append` checks the same event ID against
the physically verified identity index before evaluating a new event: exact
bytes may return a receipt for the original committed event row against the
current verified anchor, even if later events exist; changed bytes hold as
identity conflict. A distinct event ID reusing a business key
continues through replay and refuses. Historical duplicate lookup never
advances the head. A committed event receipt contains ledger identity,
sequence, event ID and digest, anchor counter, and a read-back marker; it is
not a reservation receipt or launch permit. At capacity, even control append
refuses; anchor-only recovery hold remains available.

For the later reservation module, identity is the tuple `(journal_uuid,
journal_generation,intent_id)` plus the intent's committed digest. The module
must check the verified duplicate index *before* stale-head evaluation: an
identical intent returns its original read-back reservation receipt; changed
digest, candidate, admission or IDs holds. A new intent is evaluated while
the exclusive writer is held against the current verified projection, current
UTC, authoritative opening population/coverage and independently verified
journal evidence. It appends exactly once and reads back the row and anchor.
The receipt records the immutable reservation event and verified journal
intent references. A receipt from an older head never permits launch by
itself. 18d will recheck both stores and hold launch until confirmation.

## Trusted opening history and compatibility gate

Version 1 is closed; it has no trusted complete-population transition and
`fixture/synthetic_complete` has no production standing. Do not reinterpret it.
A future versioned event must bind a verifier result to the exact ledger head,
experiment UUID, account pseudonym, policy/configuration revision, covered
time interval, source snapshot/evidence digests, all known attempts and unique
charge identities, unresolved exposures and U, holds, original weeks and all
prior journal origins. It must state the earliest possible experiment spend
and the latest covered provider time. The verifier must prove the complete
opening population and current billing coverage from authoritative records,
including whether absence of charges is meaningful. It must verify account
identity and lag, not merely attest an operator statement. A gap, unknown U,
ambiguous identity, stale coverage, late adjustment, or unavailable source
holds. A new ledger generation must carry a checked continuity witness from
its predecessor; creating a new directory cannot reset lifetime liability.

Define the exact external record shape, authentication, completeness proof,
freshness interval, stable line keys, adjustment mapping and independent
read-back in a new reviewed plan before coding this extension. Open of newer
events by an older binary is a process hold, not a destructive repair. No
production reservation may depend on a synthetic marker or a caller-provided
`Projection`.

## Capacity, retention and repair

The 18b 8192 bound is a replay-input cap and the 18a 512 bound counts *all*
attempt history. Ticket 38's 512 active/unsettled proposal is a different
capacity measure. 18c-storage retains every event and every ID; no archive,
settlement, tombstone eviction, hold clearing, or cap extension exists. New
events stop at 8192 and the ledger remains inspectable. It does not promise
52-week service at any event rate. For production, an archive must preserve
full sanitized records for 52 completed weeks, all unresolved attempts and
every duplicate key/charge identity across that horizon, plus verified
long-lived summaries for earlier lifetime liability. An archive handoff must
commit a manifest digest and live duplicate index before any deletion; a
missing archive/index holds. The current v1 transition cannot replay across
such a compacted prefix, so archive needs a reviewed compatible transition.

Four reserved future-event slots per attempt cannot bound arbitrary provider
lines, adjustments, holds and repairs. No production admission is enabled
until the plan gives those records durable capacity independent of the active
attempt cap, or a proved finite per-attempt upper bound plus safe spillover.
At any exhausted capacity, retain evidence and hold; no silent truncation or
new-generation reset. The storage-only subset may write a capacity hold to
the anchor when it can no longer append a hold event.

## 18d contract and evidence limits

18d must durably commit journal intent against an existing admission; query
the ledger idempotently; reserve and read back; commit journal confirmation;
and on every restart verify *both* stores and reconcile every intent,
reservation and confirmation before launch. An ambiguous intent commit stops
before ledger access. A ledger reservation without confirmation retains U;
confirmation without a matching reservation holds; missing/unreadable store is
unknown. The journal v1 currently cannot express intent/confirmation, so
18d needs its own reviewed compatibility migration. Later launch requires a
fresh hold/identity check, lease, durable claim and uncertain-effect recovery.

Local SQLite crash images and SIGKILL can exercise ordering, not power-loss
durability, native/provider billing, tenant isolation, venue behavior or paid
dispatch. The first phase's acceptance is a verified, non-reserving store.
