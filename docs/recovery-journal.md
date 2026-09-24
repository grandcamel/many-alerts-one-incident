# Receiver recovery journal

The recovery journal is the Receiver-owned durable record that ticket 37
requires: admissions, dedupe decisions and holds, committed before the Receiver
may acknowledge a Notification. This document describes what exists in source
today. It is not wired into the Receiver: `receiver.py` still acknowledges
without a durable record, and nothing here dispatches a Run.

The journal is built in layers. The record, source and store layers exist now.
The pure reducer, the journal shell (`create`, `open`, `admit`, holds and the
snapshot), the admission semantics and the crash matrix are the next unit.

Every limit, field name, code string and storage setting below is a proposed
routine choice under review (ticket-37 specification L341-347). The
[implementation plan](../.scratch/many-alerts-one-incident/reviews/recovery-journal/implementation-plan.md)
lists the ones that freeze into v1 records and need ratification.

## Files, modes and locks

```
<journal_dir>/            0700, owned by the effective uid, not a symlink
  journal.sqlite3         0600
  journal.sqlite3-wal     0600; kept across closes; no -shm file
  anchor                  0600; exactly 8,192 bytes, two 1,024-byte slots
  lock                    0600; flock(LOCK_EX|LOCK_NB) held while the store is open
```

- Every path is checked with `lstat`: no symlinks, the effective uid as owner,
  no group or other permission bits, and one hard link per file. Files the code
  opens itself use `O_NOFOLLOW`.
- A directory path containing `?`, `#` or `%` is refused, because SQLite would
  read those characters as URI syntax. After connecting, `PRAGMA database_list`
  must name exactly the journal's database file.
- One writer: a second open, in the same or another process, gets
  `journal_locked`, and any other SQLite connection gets "database is locked".
- **Runtime constraint.** The journal needs Python 3.12 or newer (for
  `SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE`) and SQLite 3.37 or newer (for `STRICT`
  tables). Otherwise `create` and `open` raise `sqlite_unsupported` before
  touching any file. `pyproject.toml` still allows Python 3.11 for the rest of
  the package.

**Operator rules.** `create` is explicit, and the code never deletes a file.
Recovering from a failed create means removing the journal's files by hand.
Back up the whole directory, because recent commits may live only in the WAL.
Never edit the files; inspect a live journal only through the (next unit's)
snapshot.

## Settings and what a commit proves

Each setting is set and then read back; a mismatch raises `sqlite_unsupported`.

| Setting | Value |
| --- | --- |
| no checkpoint on close | on for every connection, set before the first statement and never cleared |
| `locking_mode` | `EXCLUSIVE` |
| `journal_mode` | `WAL`, set only by `create`; `open` only reads it |
| `synchronous` | `FULL` |
| `fullfsync`, `checkpoint_fullfsync` | on (darwin `F_FULLFSYNC`; ignored on Linux) |
| `trusted_schema` / `cell_size_check` | off / on |
| `max_page_count` | 40,960 pages (160 MiB) |
| `journal_size_limit` / `wal_autocheckpoint` | 8 MiB / 1,000 pages |
| `query_only` | on while `open` verifies; off only after verification |

`append` is the only write path. It runs `BEGIN IMMEDIATE`, the inserts and
`COMMIT`, then writes and fully syncs the anchor slot naming the new head. A
successful return means both the SQLite commit and the anchor sync completed.

- **darwin.** SQLite's `fullfsync` issues `F_FULLFSYNC` for WAL syncs, but
  SQLite silently falls back to plain `fsync` when `F_FULLFSYNC` fails (from
  SQLite's source; not probed). The anchor's own sync is `F_FULLFSYNC` with no
  fallback, so on a volume without it no append ever succeeds.
- **Linux.** SQLite uses `fsync`/`fdatasync`, and the anchor uses `os.fsync`.
  The local suite runs on macOS, so the Linux primitive is covered only by
  selection.
- Any other platform raises `journal_sync_unsupported`.
- **After any write or sync failure the store latches broken** and refuses
  every later write through that store object; a new open re-verifies from
  disk. It never retries, because a kernel can report a later `fsync` as
  successful after losing pages.
- `create` fully syncs the directory around the genesis commit and anchor, so
  the new files' directory entries are durable.

A commit does not prove that the device honours flushes, that the volume
survives a pod restart, that no consistent rollback of all three files happens
later, or that Runs cannot reach the journal (they run as the same uid).

**No evidence is destroyed on open.** Because close never checkpoints, opening a
damaged journal and closing it leaves the database and WAL byte-identical; the
anchor changes only when a verdict is persisted into it. A database file shorter
than one page is reported as `journal_truncated` without connecting, because
SQLite would otherwise delete the WAL.

## Anchor and durable verdicts

A hash chain cannot detect a lost suffix, and SQLite drops committed
transactions silently when the WAL is truncated or a middle frame is damaged.
The anchor records the last anchored commit outside SQLite's files.

Each slot is a magic, a length, canonical ASCII JSON and a SHA-256 checksum,
zero-padded to the next slot. The body names a counter, the format
`rj.anchor.v1`, the head (`commit_seq`, `event_seq`, `generation`,
`record_digest`), an optional hold and the `journal_uuid`. Writes alternate
slots by counter parity, so a torn write can damage only the older slot, and
the newest valid slot wins.

Open classifies what it finds:

- **Verified physical failures are durable recovery holds**: a digest, chain or
  column mismatch; SQLite corruption; two rows with one `event_id`; a DDL or
  format mismatch. The journal shell (next unit) persists the verdict into both
  anchor slots before closing SQLite, and also checks the head against the
  anchor. Once held, the writer refuses any hold-free slot and any different
  verdict, and every later open reads the hold from the anchor without opening
  SQLite. A missing or invalid anchor cannot carry a verdict; it is left
  unchanged, and every open re-derives the hold from those bytes.
- **Transient, environmental or newer-format findings are process holds**: an
  `OSError` other than "not found" or a non-corruption SQLite error while
  opening or reading; `user_version` above 1; a newer anchor format; a typed
  failure on a row whose digest and chain verify. They are never persisted, so
  a flaky mount at startup or an older binary cannot brick the journal.

Replacing the database or WAL after a verdict is persisted changes nothing,
because they are not read. **Non-claim:** a consistent replacement of the
database, WAL and anchor with an older self-consistent set, or a same-uid
process writing a valid hold-free anchor, clears a verdict silently; the
digests are unkeyed. Nothing lifts a durable hold in place: a later
reconstruction unit builds a new journal in a new directory and leaves the held
one as evidence.

## Records

Every record is canonical ASCII JSON with exactly 15 envelope keys:
`schema_version`, `journal_generation`, `event_id`, `event_seq`, `commit_seq`,
`commit_index`, `commit_size`, `event_type`, `wall_time`, `mono_us`, `boot_id`,
`actor`, `ids`, `data` and `prev_record_digest`. `record_digest` is a tagged
SHA-256 (`rj.record.v1`) of the exact body bytes and chains each record to its
predecessor. `content_digest` covers the schema version, generation, event ID,
type, actor, identities and data but not positions, stamps or the predecessor,
so an exact retry of a commit can be recognised. The record types in scope are
`journal_genesis`, `admission`, `dedupe_decision`, `capacity_hold` and
`restart_recovery`.

Stored rows are verified in a fixed order: the raw-byte digest before any
parsing, then a strict parse, the chain link, the columns against the body, and
only then canonical re-encoding and typed validation. A corrupted byte is
therefore always a durable digest failure, never a misleading "newer format".

The sanitized source record (`journal_source`) holds only the group digest,
per-alert Fingerprint, status and canonical numeric values sorted by refId,
`starts_at`, `truncated_alerts`, a body digest and fixed provenance. It never
holds a raw HTTP body, prompt, tool body, credential or Ground truth. Strings
are limited to closed grammars; numbers compare by value, so `100`, `100.0` and
`1e2` are equal.

## Tests

Local deterministic, real-SQLite and real-sync tests cover the record,
source and store layers: canonical encoding and goldens, every validator's
fixed codes, file custody, locking, settings read-back, the anchor codec,
sync ordering and fail-closed sync failure, open-time classification, hold
persistence and stickiness, and evidence preservation. They run on macOS; the
Linux sync primitive is skipped there.

```sh
pytest -q tests/test_journal_source.py tests/test_journal_records.py tests/test_journal_store.py
```

No Receiver integration, dispatch, run, effect, accounting, reset or
reconstruction behavior is implemented or qualified. Venue durability, device
flush honesty, Linux behavior and isolation from Runs are not qualified.
