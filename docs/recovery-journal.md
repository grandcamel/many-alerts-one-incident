# Receiver recovery journal

The recovery journal is the Receiver-owned durable record that ticket 37
requires: admissions, dedupe decisions and holds, committed before the Receiver
may acknowledge a Notification. This document describes what exists in source
today. The opt-in `journaled_receiver` durably spools and admits before a 202.
The legacy `receiver.py` still acknowledges without a durable record. The
journaled command starts no Run and creates no Incident.

The journal is built in layers: `journal_source` (the sanitized source record),
`journal_records` (the record envelope), `journal_store` (SQLite and the
anchor), `journal_reducer` (a pure fold that makes every decision) and
`recovery_journal` (the shell: `create`, `open`, `admit`, holds and the
snapshot). Unit 17a adds durable ingress refusal records, operator resume at
open and verify-only inspect. Unit 17b connects them through `journal_spool`,
`journaled_receiver` and the `journal_operator` CLI.

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
Never edit the files. Inspect a live journal only through its snapshot, and a
stopped one with `inspect_recovery_journal` (see "Verify-only inspect").

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
so an exact retry of a commit can be recognised. The record types are
`journal_genesis`, `admission`, `dedupe_decision`, `capacity_hold` and
`restart_recovery` (unit 15), plus `ingress_refusal` and `operator_action`
(unit 17a).

A record is accepted only if its `(event_type, schema_version)` pair is
registered, and its actor must be the one registered for that pair:
`operator` for `operator_action`, `receiver` for every other type. For the five
unit-15 types these checks accept and reject exactly as before, at the same
positions and with the same codes. The current binary additionally accepts
the exact private v2 pairs documented below. Unknown future pairs, and these
v2 pairs in an older binary, produce `record_unsupported`. On open, that is
the process hold `journal_schema_unsupported`, which is never persisted.

Stored rows are verified in a fixed order: the raw-byte digest before any
parsing, then a strict parse, the chain link, the columns against the body, and
only then canonical re-encoding and typed validation. A corrupted byte is
therefore always a durable digest failure, never a misleading "newer format".

### Local v2 Run hold record

The `(run_hold, 2)` pair is a no-dispatch extension of this chain. It binds a
job ID to one currently pending admission and stores a closed hold reason,
the prior commit, pending digest, and count/digest of the admission's current
Fingerprint members. It contains no raw source body, command, prompt or OPS
payload. Replay re-derives the membership, pending digest, identity uniqueness
and capacity. A later admission cannot erase the held job. The v1 record
encodings and `rj.state.v1` digest formula remain unchanged; a separate
`rj.run-holds.v2` digest covers held-job state. Verify-only inspect and journal
snapshots expose the count and digest when v2 holds exist.

The journal handle has a narrow `record_restart_run_hold` writer that derives
only the `restart_recovery` reason from its own replayed global hold. It binds
one current pending admission, returns an existing matching hold on exact
retry and latches an uncertain write or capacity refusal as a process hold.
There is no front-door or Run caller. Other reasons still need an independently
verified evidence binding before a writer can expose them. This method cannot
reserve budget, clear a dispatch hold, mint a permit, launch a process,
confirm an effect or authorize a retry. Its per-job projection is separate
from the existing global `dispatch_holds`; a future permit gate must bind and
check both before dispatch. At most 1024 v2 holds can be recorded per
generation, each with a body at most 2048 bytes. A refused plan writes
nothing; the writer surfaces a process hold without
dropping the underlying admission. Older binaries encountering v2 remain on
the non-persisted `journal_schema_unsupported` process hold.

### Local v2 reservation claims

`(reservation_intent, 2)` and `(reservation_confirmation, 2)` are two more
Receiver-only, no-writer pairs in the private v2 registry. An intent links a
currently pending UUID admission to its committed Run hold, immutable attempt,
reservation, Run and lease IDs, and an exact tagged intent digest. Existing
non-UUID v1 admissions still replay but cannot form a new ledger-compatible
intent. A confirmation records a claimed ledger event identity and digest
after one intent. It does not authenticate the ledger. Replay rejects an
intent or confirmation with invalid identity, ordering, digest, reuse or
capacity. A superseded held job remains held.

At most 256 intents and 256 confirmations can exist per generation, each
with a body at most 2048 bytes. The independent
`rj.reservation-claims.v2` digest covers the sorted immutable projection.
Verify-only inspect and journal snapshots show only intent count,
confirmation count and digest. They do not expose a reserve, ready state,
permit or launch API. The Receiver-facing accounting ledger still rejects
`reservation_created` from its unknown population; a later scanner must
verify both current store histories and hold orphan or mismatched claims.

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
carries the same group and tuple as `notification-firing.json`, so the
journaled front door suppresses the repeat. The legacy replay still starts
three Runs and reads no journal state.

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
  open, and one capacity code per exhausted bound. An operator resume at open
  clears `restart_recovery`; the capacity holds stay.

The journaled front door maps every code `admit` raises to 503 with
`Retry-After: 10`, except `source_invalid` (500), which is a caller bug. The unit-17a codes
are not backpressure: `refusal_invalid` and `resume_invalid` are caller errors,
and `resume_stale` means inspect again.

## Refusal records

`record_refusal(summary)` records one ingress refusal. The summary is the
nine-key output of `journal_ingress.refusal_to_json`. It returns one of
`REFUSAL_OUTCOMES`:
- `recorded`: one `ingress_refusal` commit.
- `coalesced`: a summary with the same key is already recorded in this generation. It is checked first, so a known key coalesces even at the limit.
- `limit`: 256 records exist in this generation. Or the summary carries no Resolved member and 192 such records exist, so the last 64 stay reserved for summaries that do.
- `no_room`: the sealed record's charge (its body plus 384 bytes) would pass the ordinary byte bound.

Only `recorded` writes. Each outcome is counted per boot in
`front_door_status()`. A malformed summary raises `refusal_invalid` and latches
nothing. A clock or ID fault latches a process hold, as in `admit`, and a held
or closed journal raises `journal_held` or `journal_closed`.

**The record.** `ingress_refusal` is an ordinary record written by `receiver`,
with empty `ids`. Its `data` holds four keys:
- `rule`: `first-per-membership-v1`. A different value is `record_unsupported`.
- `summary`: `members` a tuple of `(fingerprint, status)` pairs, every unit-16 consistency rule checked, at most 4,096 canonical bytes.
- `refusal_key`.
- `refusal_seq`, from 1 to 256.

The key is a tagged digest of the summary without `body_bytes` and
`body_digest`. A Grafana re-render, which changes only `message` and so the
body digest, coalesces. A member turning Resolved changes the membership, so it
gets its own record; that lost Resolved is what the record exists to keep.
Replay re-derives the key, its novelty, the sequence, the limit, the reserve
and the byte charge.

**Consequences:**
- **Bytes.** Refusals change no baseline, pending entry, admission count or dispatch hold. They do advance the logical byte count that admissions are checked against. Near the ordinary bound, refusal records can therefore turn an admission into a `capacity_bytes` refusal. The boundary moves by at most their summed charge. The largest summary v1 can hold (32 listed members at the 64-byte Fingerprint limit, 256 alerts, all Resolved) is 2,866 bytes, and 256 records of that size charge under 1 MiB.
- **Reserve limits.** The reserve keeps a benign flood without Resolved members from using up the channel. It does not stop a sender who can reach the port and mints summaries with Resolved members; only webhook authentication would.
- **Restated vocabulary.** `journal_records` must not import `journal_ingress`, so it keeps its own copies of the ingress codes and bounds. Parity tests keep the copies in step. A new ingress code needs a new registered record version.

## Operator resume at open

Every open appends `restart_recovery`, and the hold stays until an operator
resumes. The steps are:

1. **Inspect** the stopped journal and take the `resume.token` it reports: the verified head's `record_digest`.
2. **Open** with `open_recovery_journal(directory, resume=ResumeRequest(token=..., operator=..., reason=...))`.
3. **Checks.**
   - The request is validated before any file is touched, including `lock`. The token must be 64 lowercase hex characters, and `operator` and `reason` must follow the ID grammar. Otherwise the open raises `resume_invalid`.
   - After replay and before anything is written, the token is compared with the verified head. A mismatch raises `resume_stale`. That writes nothing to a journal whose WAL exists; a journal with no WAL gains an empty one from the store's connect.
4. **Commits.** A clean open commits its `restart_recovery`, then exactly one `operator_action` in its own commit. The record is written by `operator`, belongs to the recovery class and is charged to the total region, so a resume works even after the ordinary region is exhausted. Its data holds:
   - `action` (`resume`) and `rule` (`resume-at-open-v1`);
   - `hold` (`restart_recovery`) and the hold's `since_commit_seq`;
   - `inspected`: the head this boot's restart recovered, which the token matched;
   - `pending_digest`;
   - `operator` and `reason`.

   Replay requires the resume to be the first commit after the restart that started its boot. It re-derives the hold, `since`, `inspected` and `pending_digest`, so nothing can be admitted between the inspected state and the resume.
5. **Effect.** Only `restart_recovery` is removed. Capacity holds stay, a durable recovery hold is never lifted, and the next open adds `restart_recovery` again.

`resumed_this_boot` returns the `ResumeReceipt`. If the open ends held, the
resume is not applied, `resumed_this_boot` is None, and `front_door_status()`
reports `not_applied`. A clock, ID, capacity or write fault during the resume
commit latches a process hold, as it does for the restart.

The token is a staleness binding, not authentication: anyone who can read the
directory can compute it, and `operator` is a self-asserted label.

## Verify-only inspect

`inspect_recovery_journal(directory)` runs the same verification and replay as
`open` and returns an `Inspection`, which has two parts:
- `report`: closed-shape JSON, described below.
- `references`: the admitted `body_digest` set.

It never commits and never writes to the database, WAL or anchor. It calls none
of `finish_open`, `write_anchor`, `persist_hold`, `plan_restart` or `append`,
and it always closes the store. The only file it may create is an absent
`lock`, which the report lists under `created`.

**The WAL rule.** Opening SQLite on a journal with no WAL would create one and
change the next restart's `wal_found`. Inspect therefore checks for the WAL
with `lstat` first:
- **WAL absent, DB at least one page:** inspect does not open SQLite and reports `unverified` with reason `wal_absent`. Start and stop the journal once, then inspect again. If that start is held, the hold code the process reports is the verdict.
- **WAL absent, DB absent or shorter than a page:** the store is opened, because it returns its finding before connecting.

**The report** holds these fields:
- `verdict` (`ready`, `held` or `unverified`) and `reason`;
- `finding`, `anchor` and `wal_found`;
- `next_open`: `restart_recovery`, `reanchor` then `restart_recovery`, `persist_hold`, `hold` or `unknown`;
- only when `ready`: the journal head, holds, counts, bytes, bounds and digests (`pending_digest`, `state_digest`, `front_door_digest`), up to 1,024 pending entries, refusal counts with the last 32 summaries, the last resume, and the resume token.

For any other verdict those fields are null and `references` is empty, even
when a prefix verified before the finding. Inspect of a live journal fails with
`journal_locked`.

`inspect_reservation_claim_view(directory)` shares the custody preflight and
full replay but returns immutable intent and confirmation tuples, journal
identity, anchored head and a claim digest only when verification succeeds
with zero anchor lag. A one-commit lag remains `ready` in the ordinary report
because the next open can reanchor it; the claim view reports `unverified`
without facts. The claim view checks WAL presence again after taking the
store lock and checks the opened store's observed WAL before releasing facts.
Held images, WAL absence, and detectable close failure also
release no claim facts. Neither inspection appends, acknowledges, reserves or
authorizes dispatch. Each view describes one stopped image, not a continuing
lease or an atomic cross-store snapshot.

`reservation_scan.scan_reservation` reads those claims and the separate
verified v1 accounting view for one intent. Its closed result always holds:
missing, corrupt or unsupported evidence does not create a permit. It maps
the claimed `ledger_event_id` to a structural comparison field, never to a
trusted accounting receipt. The scanner has no journal writer or Run caller.

The private `(run_intent, 3)` record is a source-only, ordinary-capacity
extension. Pure replay binds an existing v3 initial claim and confirmation,
the unchanged original pending members, a claimed ledger event/head and the
four mandatory service lease claims. The fifth Confluence claim is optional.
It has a 4,096-byte type-specific ceiling; earlier private types retain their
2,048-byte ceiling. Live snapshot and stopped verify-only inspect expose one
separately tagged `run_intent` count/digest with state
`outstanding_unqualified`. Neither replay nor a ledger-head reference
authenticates a reservation. There is no application writer, grant
registration, launch, effect or permit path for this record; the current
ledger's unknown population and absent reservation events keep that gate
closed.

The private `(launch_claim, 3)` record is another ordinary-capacity,
no-writer extension. Pure replay requires the same-boot Run intent, current
original members, no new dispatch or Run hold, and an exact sorted mapping
from each journal service lease claim to one distinct opaque Forwarder grant
ID. It checks origin-plus-270/290/300-second arithmetic and a claimed grant
expiry with a 6,144-byte type-specific record limit. Live snapshot and
stopped inspection expose a separate `launch_claim` digest labelled
`outstanding_unqualified_launch_claim`. Grant IDs, boot/generation and
monotonic expiry are replayed claims: neither the codec nor a matching
record authenticates the Forwarder registry or shared clock domain. There is
no grant registration, process creation, barrier release, effect or permit
writer here. A future writer must commit and read back the claim before a
blocked child can be created, then separately record spawn attestation and
release/containment observations.

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
| Refusal commit not yet durable | ready; nothing was recorded, and a re-sent refusal is recorded |
| Refusal durable, before `record_refusal` returns | ready; a re-sent refusal coalesces |
| After the start's `restart_recovery`, before `operator_action` | ready, with `restart_recovery` a dispatch hold again; the old token is stale because the head moved |
| `operator_action` committed, anchor not synced | ready at lag 1: adopted, re-anchored, then a new `restart_recovery`, so `restart_recovery` is a dispatch hold again |
| Resume with a stale token | nothing written to a journal whose WAL exists; a WAL-absent journal gains an empty WAL |
| During inspect | unchanged; the kernel releases the lock |

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
pure and is called by the journaled front door after bounded body receipt.

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

The journaled front door sends these HTTP classes with code-only response
bodies. Grafana's handling of them remains unqualified.

**Refusal summary.** A refusal has a summary of nine keys, with no HTTP status.
Member-level 422 refusals name up to 32 members, Resolved first, with counts
and an omitted count. `refused_group` gives a key that stays stable across
Grafana's resends. `refusal_to_json` validates internal consistency and a
4 KiB bound. `oversize_refusal(declared_length)` refuses from a
`Content-Length` header without reading the body. `record_refusal` can persist
a summary (see "Refusal records"); the front door attempts that write before
sending the refusal. A recording failure counts `unrecorded` and does not
change the HTTP class.

**Not claimed.** Grafana's real wire bytes (the captures store re-encoded
bodies) and Grafana's retry and resend behaviour after a refusal.

## Front door (journaled, admission-only)

Opt in explicitly; the default demo command and its environment are unchanged:

```sh
python3 -m grafana_jsm_sandbox.journal_operator create --state-dir /path/to/S
python3 -m grafana_jsm_sandbox.journaled_receiver --state-dir /path/to/S --runs-directory /path/to/runs
```

`S` contains `journal/` and `spool/`; all three directories are private to the
owner (created 0700). `S` may not be a symlink. Its resolved path and the
resolved runs directory must not contain each other. Use the actual legacy
`RUNS_DIRECTORY` as `--runs-directory` when both commands are used. Both paths
are printed at startup, followed by the admission-only notice. The command
reads no environment variable. It defaults to `127.0.0.1:8080`; Grafana in a
container cannot reach that listener without deliberate network configuration
and a reachable bind address such as `--host 0.0.0.0`.

Creation refuses an existing state path. It syncs the parent after creating
`S`, then `S` after both children exist, before journal genesis. The journal
performs three explicit full syncs (plus SQLite's own commit synchronization).
A failed create leaves evidence in place; nothing was acknowledged. Inspect
that incomplete layout before removing it by hand and creating a fresh one.
The serving command creates none of these directories. It binds before opening
the journal, so a bind failure cannot append a restart record.

**Spool.** Each body is a 0600 regular file named by its exact `body_digest`.
For a new body, the order is temporary write, full file sync, close, rename,
full directory sync, journal admission and anchor sync, then 202. An entry from
an earlier boot must pass ownership, mode, single-link, size and digest checks;
its directory is synced before reuse. Verified entries are cached within one
boot. Any write/sync/close failure latches the spool; a short write is refused
without retry. Conflicts also latch it. Later requests get `spool_broken`
until restart and verification. There is no deletion path.

The default limits are 256 MiB of digest-named entries and 20,000 directory
entries; temporaries and unexpected names count toward the entry limit. A full
spool refuses a new body but can reuse an existing verified one. After a durable
`capacity_admissions` hold, the front door refuses before spooling. Other
capacity refusals can leave orphans. Inspect verifies referenced entries and
orphans and reports at most 32 names in each finding list, with complete counts.

**HTTP order.** Only `POST /notification` and `GET /health` are served.
Errors contain one ASCII code and fixed reason phrases, with no reflected
caller text. The first applicable row answers:

| Condition | Response | Body handling / effect |
| --- | --- | --- |
| 32 open connections | immediate close, no response or handler thread | connection refusal counted |
| malformed protocol | stdlib status 400/414/431/501/505, mapped fixed code | close; protocol error counted |
| unknown route | 404 `not_found` | close if body framing is present; otherwise normal keep-alive |
| 8 Notification requests in flight | 503 `busy`, `Retry-After: 1` | no body read; close |
| opening, held or closed journal; latched spool | 503 `journal_opening`, `journal_held`, `journal_closed` or `spool_broken`, `Retry-After: 10` | no body read; close |
| Transfer-Encoding or missing Content-Length | 411 `http_length_required` | close |
| duplicate, invalid or out-of-range length | 400 `http_content_length_invalid` | close |
| length above 262,144 | 413 `ingress_too_large` | no body read; attempt refusal record; close |
| body EOF or deadline | 400 `http_body_incomplete`, best effort | close; no admission |
| sanitizer refusal | ingress 400/422/500 class and code | attempt refusal record; consumed body permits keep-alive |
| capacity precheck, spool error or admission error | 503 and code, `Retry-After: 10` | consumed body permits keep-alive; `source_invalid` is 500 |
| unexpected exception | 500 `receiver_error`, best effort | close; log exception type only |
| durable receipt | 202 JSON | spool durable before journal admission before response |

Every request has one ten-second monotonic read deadline across idle wait,
request line, headers and body; a byte trickle cannot extend it. Keep-alive
gets a fresh deadline for its next request. Responses get a separate bounded
write timeout. Requests asking for `Connection: close` and nonpersistent
HTTP/1.0 requests stay nonpersistent. GET bodies and wrong-route POST bodies
are not drained; their connections close to prevent body bytes from becoming
a second request. A consumed refusal can share a connection with a later
request. There is no TLS, authentication or per-peer quota. These limits bound
work; a peer occupying all slots can still deny availability.

The receipt contains exactly `admission_id`, `arrival_seq`, `commit_seq`,
`decision`, `dispatch_holds`, `result` and `run: "not_dispatched"`. A 202 means
that the Notification is durably admitted and retained, not that a Run starts.

**Health.** `GET /health` returns JSON with `Cache-Control: no-store`. Its top
level has `mode`, `runs`, `journal`, `resume`, `refusals`, `http` and `spool`:
- `mode` is `journaled-admission-only`; `runs` is `not_dispatched`.
- `journal` reports state, hold, dispatch-hold codes, head commit sequence,
  admission count and pending-Fingerprint count; projection fields are null
  unless ready. No Fingerprints, pending entries, digests or tokens appear.
- `resume.this_boot` is `resumed`, `not_requested` or `not_applied`.
- `refusals` reports recorded/limit/reserve and per-code outcomes this boot,
  including front-door `unrecorded` counts.
- `http` reports framing, deadline, busy and connection-refusal counters,
  in-flight/open-connection gauges, protocol errors, backpressure, admission
  results and dropped-start-time counts.
- `spool` reports state/code, bytes/entries and their limits, writes and full
  refusals this boot.

Health is 200 iff the journal is ready and the spool is not latched, otherwise
503. Capacity holds and `spool_full` do not turn it red; inspect those fields
when deciding whether another body can be admitted.

**Operator commands and runbook.** `journal_operator` prints one JSON object.
Create exits 0, 1 on refusal (`error` key), or 2 for usage. Inspect exits:

| Exit | Meaning |
| --- | --- |
| 0 | ready journal and consistent spool; valid orphans are allowed |
| 1 | held journal |
| 2 | usage |
| 3 | journal locked; stop the front door first |
| 4 | another open error, including missing journal or spool custody failure |
| 5 | ready journal but missing/mismatched referenced body or mismatched orphan |
| 6 | unverified, `wal_absent` |

The serving command exits 0 for Ctrl-C, 1 for a refused start, and 2 for usage.
A refused resume releases the listener. A stale token writes nothing on a
WAL-present image. The token and operator label confer no authentication.

1. Create `S`, then serve it with the correct runs-directory placement check.
2. Send local replay Notifications to the printed URL. The journaled fixture
   sequence yields admitted, suppressed and pending-reduced receipts, with
   `decision: held` after an ordinary start. No Run or Incident is created.
3. Stop, then run `journal_operator inspect --state-dir /path/to/S`. Inspect
   appends nothing and creates no WAL; an absent lock is its only permitted
   new file. It reports pending work, recent refusals and the spool survey.
4. If inspect is ready and the image is unchanged, restart with
   `--resume-token TOKEN --operator NAME` (optional `--reason TOKEN`). The
   restart and resume commits precede admission; only `restart_recovery`
   clears. Every later restart holds dispatch again. Still no Run starts.
5. If inspect says unverified, start once, stop and inspect again. If that
   start is held on `/health`, its hold code is the verdict; repeating inspect
   does not repair it.
6. Refusals keep their HTTP class even when recording fails. Inspect shows
   the flood-limited durable summaries, with Resolved members first. Capacity
   holds cannot be cleared for this state directory in this unit. Preserve
   it as evidence and explicitly create a new state directory when needed.
7. For a mismatched orphan, stop and move it out of the spool by hand,
   preserving it as evidence. A later arrival can write the correct body.
   A missing or mismatched referenced body represents acknowledged data loss:
   preserve the state for recovery; replacing the state does not settle that
   obligation.
8. The unchanged legacy demo command remains separate; its Notifications are
   not journaled.

**Front-door crash windows.** These supplement the journal windows above:

| Window | Surviving evidence / next action |
| --- | --- |
| W1: during request receipt | no admission; retry anew |
| W2: temporary written before rename | temporary retained and counted |
| W3: renamed before directory sync | surviving entry verified and directory synced on reuse |
| W4: spool durable before admission | orphan; retry can reuse it |
| W5: admission committed before anchor sync | at most lag 1; adopt, re-anchor, restart hold; retry suppressed |
| W6: anchor synced before 202 | acknowledged state exists though sender lost ACK; retry suppressed |
| W7: after 202 | referenced body and pending work retained; restart holds |
| W8: capacity refusal after spooling | orphan plus at most one capacity hold per code; admission-capacity precheck prevents later spools |
| W9: refusal not durable | retry can record it |
| W10: refusal durable before 4xx | retry coalesces |
| W11: restart committed before resume | old token stale; inspect again |
| W12: resume committed before anchor sync | adopt at lag 1, then a new restart holds again |
| W13: stale token | unchanged WAL-present image; WAL-absent full-size DB may gain an empty WAL |
| W14: during inspect | no journal mutation; kernel releases lock |
| W15: spool write/sync/close fails | latched until restart; temporary or orphan retained |

Local crash injection and SIGKILL are not power-loss qualification. No Linux
no-read response behavior, Grafana retry policy, device flush honesty, deployed
storage, same-uid isolation, paid Run, provider or tenant behavior is qualified.

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
- two golden journals that later units must keep replaying: the unit-15 one,
  and a unit-17a one holding refusals, two restarts, a resume and a later
  admission;
- for the refusal and resume records: validators, check order, the flood rule,
  the byte coupling, a property test over seeded histories, older- and
  newer-binary simulations, and resume crash images;
- inspect on eleven journal images, with a check that inspecting first does
  not change what the next open does;
- a mutation matrix and custody checks.

They run on macOS; the Linux sync primitive is skipped there.

```sh
pytest -q tests/test_journal_source.py tests/test_journal_records.py tests/test_journal_store.py tests/test_journal_reducer.py tests/test_recovery_journal.py tests/test_recovery_journal_crash.py tests/test_recovery_journal_adversarial.py tests/test_journal_ingress.py tests/test_journal_ingress_corpus.py tests/test_journal_ingress_adversarial.py tests/test_forwarder_json_string_cap.py tests/test_journal_front_door_records.py tests/test_recovery_journal_front_door.py tests/test_journal_spool.py tests/test_journaled_receiver.py tests/test_journal_operator.py tests/test_journaled_receiver_crash.py tests/test_journaled_legacy_identity.py
```

The versioned claim tests are in `tests/test_reservation_claim_journal.py`,
`tests/test_initial_reservation_intent_journal.py` and
`tests/test_run_intent_claim_journal.py`; the full repository suite includes
them.

Receiver integration is opt-in and admission-only. Dispatch, Runs, effects,
accounting, reset, retention and reconstruction remain unimplemented here.
The only operator action is resume at open; cancel, retry, abandon, capacity
clear and any online operator channel are not implemented. Venue durability,
device flush honesty, Linux behavior, isolation of the journal from Runs, and
Grafana's retry and resend behaviour after a refusal are not qualified, and
every v1 semantic above still awaits ratification.
