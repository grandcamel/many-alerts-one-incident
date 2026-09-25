# Unit 18g2 cumulative accounting archive index

Status: **PASS_LOCAL_INDEX**, 2026-09-25. Fixed point: `705fc12`.

The pure index codec re-decodes ordered 18g1 segment bytes, replays one exact
same-generation v1 history from genesis and derives `event_id` plus first-added
`claimed_id` rows. It checks the derived claim set against the replay
projection, sorts by canonical `(namespace,key)`, applies row/header/file
bounds and compares the complete canonical index bytes on read. No v1 event
authenticates a provider charge line, so this version emits no `provider_line`
row and rejects a supplied index that invents one. The tagged content digest
binds bytes only relative to a separately trusted manifest and witness.

The [plan](implementation-plan-18g2-index.md) and independent Standards and
Spec reviews pass. Six focused tests and changed-file Ruff pass. The full
local suite passes **5423**, skips **39**, in 378.42 seconds. Tests include
ordered two-segment derivation, first ownership of a repeated journal claim,
a stopped and reopened SQLite ledger, changed/reordered/omitted/extra rows,
truncation/trailing bytes, missing/changed segments and a bounded capacity
refusal. This is local source and synthetic/stopped-store evidence.

The index cannot authenticate storage continuity or establish absence of
unknown provider lines. The v1 ledger cannot register an archive, compact or
reserve production spend. The manifest, private export/read-back, independent
witness, archive registration, cross-generation migration and full retention
acceptance remain open, as do opening history, billing source/account scope,
line/adjustment identity, coverage/lag/finality, liability U and venue
durability. Provider, native, tenant, paid, venue, power-loss and human
adjudication are **NOT RUN**. Ticket 38 stays open. No push, publication or
provider experiment occurred.
