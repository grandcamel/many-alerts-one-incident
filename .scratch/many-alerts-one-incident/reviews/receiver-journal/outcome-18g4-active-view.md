# Unit 18g4 query-only active archive view

Status: **PASS_LOCAL_STOPPED_IMAGE**, 2026-09-25. Fixed point: `818b3f5`.

`LedgerStore.inspect_archive_active_view` reuses the query-only, locked v1
replay and exact-anchor inspection. After successful handle release, a ready
view contains the original event tuple and verified stopped-image head.
Held, unverified and close-failed images release no head or events.
`compare_archive_to_ledger` takes one such image and invokes the same-generation
18g3 overlap verifier. This is a closed historical observation, not a
continuing lease: later archive registration must recheck the current ledger
head under its own writer lock.

The [plan](implementation-plan-18g4-active-view.md) and independent Standards
and Spec reviews pass. Twelve focused archive/view tests and changed-file Ruff
pass. The full local suite passes **5,455**, skips **39**, in 384.32 seconds.
Tests cover a stopped SQLite/WAL history, unchanged active files, absent or
damaged image, persisted `event_conflict` hold, failed close with lock release,
fixture-origin rejection and damaged archive index.

No active writer, archive registration, witness, off-cluster export, retention
release, compaction, positive reservation or dispatch path was added. The v1
Receiver accounting ledger remains `population=unknown` and rejects
reservation events. Provider opening history, charge-line identity,
coverage/lag/finality, liability U, independent continuity, private durability
and intended-venue decisions remain open. Native, provider, tenant, paid,
venue, deployment, power-loss and human adjudication are **NOT RUN**. Ticket
38 stays open. No push or publication.
