# 18g proposed accounting archive format and handoff

Status: proposed local source design, 2026-09-25. Fixed point: `aa69f7e`.
This is a format and failure contract for a future Receiver-owned accounting
archive **within one ledger generation**. It creates no archive, witness,
billing fact, reservation or launch permit. Cross-generation replay and
compaction need a separate versioned design; 18g cannot authorize either.
Accepted ADR 0013 and ticket 38 limits take precedence over these proposed
encoding choices.

## Current implementation boundary

The v1 Receiver ledger has an 8,192-row append-only SQLite table, anchored
head, `population=unknown`, and no accepted reservation or provider charge
events. Its schema forbids UPDATE/DELETE. It has no archive registration,
off-cluster handoff, tombstone or compaction transition. An archive cannot be
retrofit by deleting rows, resetting a new ledger or storing a digest next to
the same editable files. When v1 fills, admission remains held. A future
versioned ledger migration must be separately reviewed and must preserve the
v1 bytes, replay meaning, event IDs and unknown opening population.

## Proposed immutable segment

One `accounting-archive-segment.v1` covers an exact contiguous sequence range
for one `experiment_id`, ledger UUID and generation. It stores every original
canonical event body and original digest in sequence order, including holds
and corrections, never a projection-only summary. The proposed wire format is:

* Eight ASCII magic bytes `MAOIAR01`, then one unsigned big-endian 32-bit
  header length (1..4096), then exactly that many canonical ASCII JSON bytes.
  The header has exactly `format` (`accounting-archive-segment.v1`),
  `ledger_uuid`, `ledger_generation`, `experiment_id`, `first_sequence`,
  `last_sequence`, `event_count`, `payload_bytes`, `start_previous_digest`,
  and `end_event_digest`. IDs and digests use the v1 ledger's validated UUID
  and lowercase hex grammar; integers are exact nonnegative values no larger
  than `2**53-1`. The header is encoded with the repository's pinned
  `canonical_json(..., ascii_only=True)` serializer.
* Exactly `event_count` entries follow. Each is an unsigned big-endian 64-bit
  sequence, unsigned big-endian 32-bit body length (2..16,384), 32 raw digest
  bytes decoded from lowercase hex, and that many original event-body bytes.
  `payload_bytes` is the total length of these complete entry frames.
  `event_count` is 1..8192, and the whole file is at most 160 MiB. No padding
  or trailing bytes are allowed.
* Segment digest is lowercase hex SHA-256 of
  `b"maoi.accounting.segment.v1\0"` followed by the **entire file**. The
  content-addressed name is `segment-<segment-digest>.bin` under a private
  archive root. A reader re-decodes each event, checks the existing
  `acct.event.v1\0` tagged digest, predecessor chain, exact sequence and
  owner, and derives every header value including the opening/ending heads.
  For the first segment, opening predecessor is the genesis zero digest;
  later segments begin at the previous verified segment head. Holes,
  duplicate sequence, unsupported records, changed bytes, header mismatch
  and cross-ledger identity fail closed.

The within-generation cumulative `accounting-archive-index.v1` has eight ASCII magic bytes
`MAOIAI01`, a big-endian 32-bit header length (1..65,536), canonical ASCII
JSON header, then exactly `row_count` rows. The header has exactly `format`,
`ledger_uuid`, `ledger_generation`, `experiment_id`, `segment_digests` (ordered,
at most 256 lowercase hex digests) and `row_count`. Each row is a big-endian
16-bit length (1..1024) followed by one canonical ASCII JSON object with
exactly `namespace`, `key`, `segment_digest`, `sequence`, `event_digest`.
`namespace` is `event_id`, `claimed_id`, or `provider_line`; `key` is a
one-element array for the first two and a three-element array for
`provider_line`: `[source_profile_id, provider_account_pseudonym,
provider_charge_line_identity]`. This is ticket 38's account-scoped line
identity plus the approved source-profile namespace. Every string is a
bounded, profile-defined opaque ID, never a raw account name or credential.
Rows sort by the canonical JSON bytes of `(namespace,key)` and duplicate keys
are invalid; sequence/digest point to the owning decoded event. The file has
no padding or trailing bytes and is capped at 65,536 rows **and** 16 MiB.
Index digest is lowercase hex SHA-256 of
`b"maoi.accounting.index.v1\0"` followed by the whole file; its name is
`index-<index-digest>.bin`.

Index derivation includes every original event ID and every ID **first added**
to `Projection.claimed_ids` by current replay, including cost, lifecycle,
hold, journal, profile, attempt and reservation identities. A repeated
reference to an already claimed ID adds no row; its owner remains the first
event whose replay transition added it. A future event version must specify
additional namespaces/keys before it can be archived. Provider-line row
ownership is the first accepted authenticated source line under its composite
key; later identical replay is idempotent and different bytes conflict.
Unknown line identity cannot be replaced by a guessed key. The index is
re-derived from all decoded segments **in the same ledger generation** and
must match byte-for-byte. It accelerates duplicate checks, but a future
admission transition must construct one exact same-generation sequence from
the registered archive and active history before an append. While old active
rows are retained, the archived range is an overlapping prefix: every
overlapping sequence must match byte-for-byte and by event digest, then it is
applied **once**. A missing, changed or conflicting overlap holds; the index
does not resolve it. A contiguous **same-generation** active suffix after
the archived head is then replayed once, including late charges, corrections
and control events. A gap or a different-generation suffix holds pending the
separately reviewed migration. The resulting single replay preserves
composite/semantic uniqueness guards. Index absence alone never proves a
new ID safe.
Cross-generation replay has no rule in 18g and remains held pending a
separately reviewed migration. An unreadable index or replay gap makes
duplicate absence unknown and holds admission.

The `accounting-archive-manifest.v1` is one canonical ASCII JSON object,
at most 65,536 bytes, with exactly `format`, `archive_id`,
`previous_manifest_digest`, `ledger_uuid`, `ledger_generation`,
`experiment_id`, `start_head`, `end_head`, `segment_digests`, `segment_bytes`,
`index_digest`, `index_bytes`, `event_count`, `index_row_count`,
`outstanding_attempt_count`, `reservation_count`, `unknown_exposure_count`,
`hold_codes`, `coverage_state`, and `retention_deadline_utc`. Heads are exact
`{sequence,event_digest}` objects; arrays follow segment order and contain
at most 256 elements, while `hold_codes` is sorted and unique. Counts and
byte lengths are exact nonnegative integers at most `2**53-1`; digests are
lowercase hex64; IDs are UUIDs; the previous digest is zero for the first
manifest. `coverage_state` is only a replayed status, never billing proof.
The time is canonical UTC with six fractional digits and `Z`. The manifest
digest is lowercase hex SHA-256 of `b"maoi.accounting.manifest.v1\0"` plus
the entire canonical manifest bytes, excluding no fields because the digest
is not embedded. The name is `manifest-<manifest-digest>.json`.
Every field is derived from verified replay, not caller claims. No manifest
contains raw provider payload, account name, credential, Report, prompt,
Ground truth or scoring audit. These digests detect mismatch only relative to
a separately trusted witness; local self-consistency is not authentication.

## Ordered handoff and read-back

The future same-generation archive handoff must hold the Receiver's exclusive accounting lock,
verify the current anchored ledger through its exact head, and reserve room for
its own control event before preparing bytes. It writes temporary private files
with owner-only permissions, no symlink/hardlink adoption, bounded lengths and
full file/directory sync. It then exports them through a separately selected
private off-cluster channel and performs byte-for-byte read-back of segment,
index and manifest from that destination. Read-back must validate all framing,
event replay, index derivation, digests and the expected source head.

Next, an **independent** continuity witness must durably bind the archive
manifest digest and active ledger head to the predecessor witness. The witness
mechanism, trust domain, rollback behavior and intended-venue durability are
unselected. Local read-back or a second file on the same rollback domain is
insufficient. Only after both read-back and witness acknowledgment may a
future active-ledger registration event bind the archive ID/digest, range and
index head. That event must be replayed and read back from a separately
versioned store capable of it. The v1 store cannot register an archive.

Compaction into a new active generation is **not defined by 18g**. A separate
versioned migration must pin how the old and new heads are witnessed, how the
cross-generation index is represented, and how replay carries every identity,
liability and hold across the boundary. Until that design and its read-back
exist, registration of a same-generation archive does not permit deletion of
old rows or a new production reservation. Any later compaction must preserve
the old image until the new image and all archive/index generations can be
opened and read back together; ambiguous outcomes hold dispatch. No `finally`
cleanup may delete the only copy. No v1 writer or compactor is defined here.

## Crash and unavailable states

| Window | Recovery rule |
| --- | --- |
| Before private export | Keep active v1/vNext history; staged files have no authority. |
| Export or read-back incomplete | Keep active history, hold `archive_unverified`; a partial remote object is not registered. |
| Witness missing or conflicting | Keep active history, hold `continuity_unverified`; local digest agreement cannot clear it. |
| Witness acknowledged, registration absent/ambiguous | Keep active history and hold; inspect exact witness and active head before any retry. Do not emit another archive ID blindly. |
| Registration committed, compaction not started | Reopen both active ledger and archive/index by exact identity; retain old rows. |
| Proposed future compaction or cross-generation replay | Held pending a separate versioned transition, witness and full-history verification; 18g supplies no positive rule. |
| Registered archive/index later unavailable or changed | Hold `history_unavailable`; never infer no duplicate or zero liability. Reconstruct from authoritative source and witness before reservation. |

An orphaned, differently hashed object under the same archive ID is a conflict,
not last-write-wins. A late charge, credit or correction remains a new
append-only accounting event linked by source-defined line/adjustment identity;
it cannot overwrite the archived line. Missing provider coverage, finality or
line identity still holds even when archive bytes are intact. Rehearsal reset,
calendar rollover, audit expiry and venue teardown cannot clear an unresolved
accounting obligation.

## Capacity, retention and acceptance

The future archive must retain at least 52 completed weeks of accounting provenance and
all unresolved obligations for longer when necessary. Retention expiry cannot
silently evict an unresolved attempt or a duplicate tombstone still needed for
late billing. If caps or off-cluster capacity cannot preserve that contract,
hold new reservation/dispatch while bounded Notification admission continues.
The future writer must preflight event, index, archive and control-slot headroom
before any reservation. The proposed 512-active-attempt limit and four
control-event slots per new reservation are additional future bounds, not
features of v1. The one-generation 18g format alone does not demonstrate
52-week service or safe capacity release; new reservations stay held if the
active store cannot retain all required rows.

Offline implementation acceptance must use real stopped SQLite histories and
the future archive reader/writer: exact boundary sizes, two segments, duplicate
line/replay conflict, corrected line, truncated framing, index omission,
tampered but internally rehashed bytes, crash at every handoff step, ambiguous
registration, missing or conflicting active/archive overlap, unavailable
registered archive while active rows remain, late line, rollover, retention
and reset. Post-compaction archive loss belongs to the separately reviewed
cross-generation migration acceptance. Tests must assert that active
liabilities survive failures and no synthetic witness or fixture clears a
production hold. Source-specific
billing authenticity, complete opening history, provider lag/finality,
independent witness, off-cluster durability, paid/provider and venue acceptance
remain separate gates.
