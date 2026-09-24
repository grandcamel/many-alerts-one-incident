# Receiver recovery journal

The recovery journal is the Receiver-owned durable record that ticket 37
requires: admissions, dedupe decisions and holds, committed before the Receiver
may acknowledge a Notification. This document describes what exists in source
today. It is not wired into the Receiver: `receiver.py` still acknowledges
without a durable record, and nothing here dispatches a Run.

The journal is built in layers: `journal_source` (the sanitized source record),
`journal_records` (the record envelope), `journal_store` (SQLite and the
anchor), `journal_reducer` (a pure fold that makes every decision) and
`recovery_journal` (the shell: `create`, `open`, `admit`, holds and the
snapshot).

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
Never edit the files; inspect a live journal only through its snapshot.

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
  format mismatch; replay contradictions; a head below the anchor, more than one
  commit beyond it, or disagreeing with the anchored record. The journal shell
  persists the verdict into both anchor slots before closing SQLite, and
  completes a half-written hold on the next open. Once held, the writer refuses any hold-free slot and any different
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

## The journal shell

`create_recovery_journal(directory, ...)` writes genesis, with the bounds that
every later open uses. Any refusal before a file is written (bad bounds, clock
or ID factory, or a genesis record that fails verification) raises
`journal_argument` and leaves the directory empty; `journal_create_failed` means
files may exist and must be removed by hand. `open_recovery_journal(directory,
...)` verifies the whole chain and replays every commit through the reducer
before it applies anything. It adopts an anchor that lags the database by at
most one commit, re-anchors that commit, and then commits a `restart_recovery`
record. Anything else is held. Once the store is open, every open returns a
handle, and a held handle only reports; a missing, locked, misplaced, wrongly
permissioned or unsupported journal, or a bad argument, raises `JournalError`
instead.

`admit(source)` runs under one lock. It validates the source, stamps it with
the injected clocks, mints IDs, plans the decision in the pure reducer, verifies
the planned records exactly as replay would, commits them, and only then
applies them to memory and returns an `AdmissionReceipt`. Only that receipt may
permit an acknowledgement. A capacity refusal writes at most one `capacity_hold`
per code and raises the capacity code; nothing is evicted. Clock faults, bad or
duplicated IDs and write failures latch a process hold and raise its code;
a failed append leaves the in-memory projection unchanged.

`snapshot()` has a fixed, nonsecret shape and is JSON-encodable. While the
journal is held, its projection fields are null and `pending()` is empty.
`anchor.lag_at_open` is the head's `commit_seq` minus the anchor's at open
(negative when truncated), or null when open stopped before comparing them.

## Admission semantics

The dedupe key covers one Notification's sorted `(fingerprint, status,
values)` list, with numbers compared by value. It is compared with the latest
**admitted** key of the same source group (ticket 31):

- a different key is admitted, or `pending_reduced` when it replaces a waiting
  entry for one of its Fingerprints;
- an identical key is `suppressed`, unless the arrival or its baseline was
  truncated (`truncated_alerts` not 0, including null);
- a suppressed repeat never moves the baseline, and never settles, deletes or
  downgrades an obligation.

Pending keeps the latest arrival per Fingerprint together with every superseded
admission identity. A suppressed repeat changes pending only when another
group holds the entry for one of its Fingerprints: it reclaims that entry, and
it never creates one. In the spec's failed A / new B / A example, B and then A
each differ from the latest admitted tuple, so each is recorded (as
`pending_reduced`, replacing the waiting entry), and a further A is suppressed.
After any restart, every decision carries the `restart_recovery` dispatch hold.

Consequence for the legacy replay fixtures: `notification-firing-repeat.json`
carries the same group and tuple as `notification-firing.json`, so once the
journal is wired in, the repeat is suppressed.

## Holds

- **Recovery holds** are durable (see "Anchor and durable verdicts"):
  `journal_truncated`, `journal_anchor_missing`, `journal_anchor_invalid`,
  `journal_anchor_conflict`, `journal_identity_mismatch`,
  `journal_schema_invalid`, `journal_corrupt`, `journal_record_invalid`,
  `journal_chain_broken`, `journal_tail_unverified`, `journal_replay_mismatch`
  and `journal_event_conflict`.
- **Process holds** are never persisted and clear on reopen:
  `journal_open_failed`, `journal_schema_unsupported`, `journal_write_failed`,
  `journal_clock_invalid`, `journal_divergence` and `journal_capacity_recovery`.
- **Dispatch holds** leave admission running: `restart_recovery` after every
  open, and one capacity code per exhausted bound. Nothing clears them yet.

Every code is retryable backpressure for the later Receiver integration, except
`source_invalid`, which is a caller bug.

## Crash windows

| Window | Next open |
| --- | --- |
| Before the commit is durable | ready; the arrival was never recorded, so a retry is admitted |
| Commit durable, anchor not yet written, torn or reverted | ready at lag 1: re-anchored, then `restart_recovery`; a retry is suppressed |
| Anchor synced, before the receipt | ready; a retry is suppressed |
| Write or sync failure while running | process hold now; the next open verifies and adopts at most one commit |
| During open's re-anchor or restart commit | ready, with lag at most one |
| During hold persistence | held; the next open completes the hold |
| Storage loses acknowledged commits, or a row is damaged or forged | a recovery hold, persisted (a missing or invalid anchor is re-derived instead); database and WAL untouched; a typed failure on a verified row is a process hold |
| Consistent rollback of every file, or a same-uid forger | ready; undetectable (non-claim) |

Run intent, spawn, effect and terminal windows belong to later units.

## Bounds

Proposed v1 limits: 10,000 admissions per generation (suppressed arrivals
count), 1,024 pending Fingerprints, 112 MiB of ordinary records within a
128 MiB total with a 16 MiB recovery reserve, 16 KiB per record, and 32 alerts,
64 values and 4 KiB per source record. Each is checked before writing. Tests
may lower the bounds at create time; genesis records them. Nothing is ever
deleted: there is no UPDATE or DELETE, no retention and no compaction. Open time
grows with the journal, on the order of 1.5-2 ms per admission pair on the
development Mac, and nothing is admitted during open.

## Ingress

`journal_ingress.sanitize_notification(body)` turns one raw Grafana
Notification body into either an admissible `SourceRecord` or a refusal. It is
pure and is not yet called by the Receiver.

**What is read.** It reads only `groupKey`, `truncatedAlerts` and, per alert,
`fingerprint`, `status`, `values` and `startsAt`. Every other field, including
Grafana's templated `message`, is parsed under the house parser's rules and
dropped. Its content never appears in the record, a refusal summary or an
error, although a parser-level problem in it can still cause a refusal.

**Mapping rules:**
- Absent `truncatedAlerts` or `values` become null.
- Numbers go through `canonical_number`, and values are sorted by refId.
- `startsAt` never causes a refusal. Go's zero time maps to null. An offset time
  or an invalid date is dropped, and only the member's Fingerprint is listed in
  `starts_at_dropped`.
- `body_digest` covers the exact raw bytes.
- Provenance is `HTTP_PROVENANCE`.

**Checks run in two phases.** Every 400-class check runs over every member
before any member-level 422-class check, so a member-level 422 means that
Grafana could have sent the body and v1 cannot represent it. Parser-level
refusals come first. A parser code that covers any cause Go's encoder can emit
(a NUL, an integer beyond 2^53-1, any array over 256 items) is
`ingress_json_unsupported` (422), even for a body that would otherwise fail
phase 1. The same code also covers causes Go cannot emit, such as a lone
surrogate or an over-long number.

**Bounds.** Bodies may be up to 256 KiB. Records are limited to 32 alerts, 64
values and a 4 KiB canonical record. In practice that allows 28 two-value alerts,
21 three-value alerts or 32 value-free alerts; the captures peak at 4. The parse
raises `forwarder_json.parse_json`'s new `max_string_bytes` keyword to the body
bound, because Grafana's `message` passes 16 KiB at about 20 alerts. The default
is unchanged, and only this module passes the keyword.

| Class (proposal) | Codes |
| --- | --- |
| 413 | `ingress_too_large` |
| 400 | `ingress_json_invalid`, `ingress_shape`, `ingress_group_key`, `ingress_truncated`, `ingress_fingerprint`, `ingress_status`, `ingress_values`, `ingress_duplicate_fingerprint` |
| 422 (lost real data) | `ingress_json_unsupported`, `ingress_group_key_unsupported`, `ingress_ref_id_unsupported`, `ingress_too_many_alerts`, `ingress_too_many_values`, `ingress_record_too_large` |
| 500 | `ingress_divergence` |

The HTTP classes are a proposal for the later Receiver integration, and
response bodies must carry only the code.

**Refusal summary.** A refusal has a summary of nine keys, with no HTTP status.
Member-level 422 refusals name up to 32 members, Resolved first, with counts
and an omitted count. `refused_group` gives a key that stays stable across
Grafana's resends. `refusal_to_json` validates internal consistency and a
4 KiB bound. `oversize_refusal(declared_length)` refuses from a
`Content-Length` header without reading the body. Nothing persists a refusal
yet.

**Not claimed.** Grafana's real wire bytes (the captures store re-encoded
bodies), Grafana's retry and resend behaviour after a refusal, and the Receiver
integration.

## Tests

Local deterministic, real-SQLite and real-sync tests cover every layer:
- canonical encoding and goldens, and every validator's fixed codes;
- file custody, locking, settings read-back and the anchor codec;
- sync ordering and fail-closed sync failure;
- open-time classification, and hold persistence and stickiness;
- the ticket-31 fixture scenarios and a property test against an independent
  reference model;
- crash images for every detectable window above, including two-crash cases,
  torn WAL frames, stale restores and a SIGKILL loop, plus a test that pins
  the consistent-rollback non-claim;
- a golden journal that later units must keep replaying;
- a mutation matrix and custody checks.

They run on macOS; the Linux sync primitive is skipped there.

```sh
pytest -q tests/test_journal_source.py tests/test_journal_records.py tests/test_journal_store.py tests/test_journal_reducer.py tests/test_recovery_journal.py tests/test_recovery_journal_crash.py tests/test_recovery_journal_adversarial.py tests/test_journal_ingress.py tests/test_journal_ingress_corpus.py tests/test_journal_ingress_adversarial.py tests/test_forwarder_json_string_cap.py
```

No Receiver integration, ingress refusal persistence, dispatch, Run, effect,
accounting, operator action, reset, retention or reconstruction is implemented
or qualified. Venue durability, device flush honesty, Linux behavior, isolation
of the journal from Runs, and Grafana's retry and resend behaviour after a
refusal are not qualified, and every v1 semantic above still awaits
ratification.
