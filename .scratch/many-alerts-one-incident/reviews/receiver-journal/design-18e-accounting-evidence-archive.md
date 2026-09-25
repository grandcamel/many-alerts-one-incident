# 18e: accounting evidence candidates and archive failure semantics

Status: proposed local contract, 2026-09-25. Fixed point: `cd1365f`.
Authority: accepted ADR 0013, ticket 38's proposed accounting contract,
the 18c reservation gate record, and the v1 non-reserving store. This is
local specification only. It selects no provider source, account scope,
pricing, billing lag, opening balance, liability U or continuity witness.

## Evidence candidate boundary

Define a private, versioned `accounting-evidence-candidate.v1` envelope for
future importer input. Its fields are a candidate ID; source-kind and
source-revision claims; acquisition time; exact payload-byte digest and
length; private custody reference; claimed account-scope reference; claimed
coverage interval; and an optional claimed predecessor evidence ID. An
absent field remains absent, never a zero value or complete interval. The
envelope contains no credential, raw provider payload, prompt, Report,
Ground truth, account display name or raw charge line. It is not accepted
as accounting evidence because its metadata can be self-asserted.

Separate three stages explicitly:

1. **Candidate syntax:** bounded canonical encoding, fixed field types,
   immutable ID/digest references and duplicate-byte detection. Passing
   means only `structurally_valid_candidate`.
2. **Source-profile review:** a separately approved source-specific profile
   must define authentication, actual account scope, stable charge-line ID,
   adjustment/credit relation, currency/time semantics, coverage interval,
   billing lag/finality, replay protection and conflict handling. No
   generic parser may infer these from column names or a `complete` flag.
3. **Accounting verification:** only after an authenticated complete opening
   history, source-profile checks, current coverage and an independent
   continuity witness can an importer propose ledger events. The current
   v1 Receiver store still refuses reservations; this contract adds no
   importer or positive verifier.

Every failure is a closed reason without payload echo. The initial taxonomy
is `candidate_malformed`, `candidate_conflict`, `source_unsupported`,
`source_unavailable`, `account_scope_unverified`, `line_identity_unverified`,
`coverage_unverified`, `lag_unverified`, `opening_unverified`,
`attribution_unverified`, `adjustment_unverified`,
`continuity_unverified`, and `archive_unverified`. Multiple failures may be
retained in a sorted immutable set; none means only that the local syntax
stage found no problem. A source profile must add evidence-backed rules
before any status can mean verified billing coverage. A replayed or late
line with the same stable source identity and bytes is idempotent; different
bytes under that identity are a conflict, never last-write-wins. Because
the provider's identity semantics are unknown, this rule is a requirement
for a future profile, not an implemented lookup.

## Archive and duplicate-index contract

The active ledger cannot silently shed liabilities to stay within its
8,192-event bound. The proposed 512-active-attempt limit is a separate
future admission bound, with four future-event slots held for each new
reservation. Retained idempotency tombstones are capped at 65,536 entries
or 16 MiB, whichever comes first, and count against active-store capacity.
The current v1 store implements neither a
reservation nor a 52-week archive. Before active capacity or retention
would be exhausted, an operator-controlled handoff must produce a private
append-only archive containing all sanitized events, attempt and reservation
identities, unresolved attempts, charge-line identities, coverage states,
holds and duplicate-rejection tombstones. Its active duplicate-rejection
index must cover archived attempt, reservation and charge-line identities.
The manifest binds source generation/head, ordered event and
index digests, count/byte bounds, archive identity and predecessor archive.
No raw provider payload or scoring audit is placed in the ledger archive.

The handoff is usable only after byte-for-byte read-back of the archive and
index, an independently held continuity witness, and a committed active
registration of the manifest digest. The exact atomic registration and
witness mechanism are unresolved; no deletion/compaction is allowed before
they are specified and verified. A failure before handoff leaves all active
records intact and holds as `history_unavailable`. If archive/index access
fails after a completed handoff and compaction, retain the surviving active
records, hold as `history_unavailable`, and require authenticated
reconstruction of the missing history before model reservation or dispatch
can resume. Bounded Notification admission continues. A
duplicate check must consult the active and archived index; an unavailable
index is unknown, never proof of absence. A late line or correction must be
addressable without erasing the historical event or the original conflict.

The archive must retain 52 completed weeks of accounting provenance and
the bounded tombstone index under ticket 38's proposed caps. Its off-cluster
storage, access policy, retention enforcement, volume durability and
rollback witness require separate decisions and intended-venue validation.
A consistent rollback of active files plus archive is locally undetectable
without that witness. Rehearsal reset, calendar rollover and audit expiry
cannot clear an unresolved accounting obligation.

## Local acceptance boundary

Review this contract against ADR 0013 and tickets 37/38. A future pure
candidate parser may test canonicalization and fixed-code rejection, but
must expose no `verified`, `ready`, `reserve`, `settled` or permit result from
synthetic input. Archive source work requires a separately reviewed physical
format, retention/read-back test plan and selected independent witness.
Provider billing, native client, tenant, venue, paid and power-loss evidence
remain **NOT RUN** under the current approval.
