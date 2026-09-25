# Unit 18g1 accounting archive segment codec

Status: **PASS_LOCAL_CODEC**, 2026-09-25. Fixed point: `9b92e5b`.

The pure `accounting_archive_segment` codec encodes original v1 event bodies
and digests into the proposed 18g physical segment format. The reader checks
the tagged whole-file digest, exact bounded framing and canonical header,
contiguous sequence, predecessor chain, same-generation owner and complete
accounting replay. A later segment requires the exact verified prior prefix.
It returns a replay projection, not a trusted archive receipt or permission to
drop active history.

Independent Standards and Spec reviews pass on the final staged diff. Six
focused tests and changed-file Ruff pass. The full local suite passes **5417**,
skips **39**, in 385.26 seconds; `git diff --cached --check` passes. Tests
cover first and second segments, byte preservation, content digest, truncation,
trailing bytes, changed identity/end head, duplicate sequence, semantic replay
conflict, noncanonical header and unsupported format. This is local synthetic
codec evidence, not an off-cluster export or power-loss test.

The cumulative index, archive manifest, private writer/export/read-back,
independent witness, active registration, cross-generation migration and
compaction remain unimplemented. The current v1 ledger remains capped and
cannot register an archive or reserve production spend. Opening history,
source/account-scoped billing identities and coverage, lag/finality, liability
U and venue durability remain external decisions. Native, provider, tenant,
paid, venue, power-loss and human adjudication are **NOT RUN**. Ticket 38 stays
open. No push, publication or provider experiment occurred.
