# Unit 18g3 active/archive overlap verifier

Status: **PASS_LOCAL_STRUCTURAL_OVERLAP**, 2026-09-25. Fixed point: `59c1392`.

`accounting_archive_overlap.compare_archive_active` re-decodes complete
same-generation segment/index bytes and each caller-supplied active event. It
requires a contiguous active range ending at the supplied active head, exact
original bytes and digests at every overlap, and an immediately chained
suffix. It replays one union so duplicate identities and accounting semantics
remain enforced. Its result contains only a projection and structural counts;
it does not authenticate the active store or an independent archive witness.

The [plan](implementation-plan-18g3-overlap.md) and independent Standards and
Spec reviews pass. Six focused tests and changed-file Ruff pass. The full
local suite passes **5,449**, skips **39**, in 385.61 seconds. Cases include
complete and partial overlap, two segments, immediate suffix, a stopped
SQLite active history, changed/missing/reordered overlap, suffix chain and
semantic conflict, generation mismatch, forged head, damaged index and
invalid active input.

No active-store adapter, archive registration, read-back channel, continuity
witness, compaction, capacity release, production reserve or dispatch path was
added. The v1 Receiver accounting ledger remains `population=unknown` and
rejects reservation events. Provider/source charge identity, opening history,
coverage/lag/finality, liability U and retention/venue evidence remain open.
Native, provider, tenant, paid, venue, deployment, power-loss and human
adjudication are **NOT RUN**. Ticket 38 stays open. No push or publication.
