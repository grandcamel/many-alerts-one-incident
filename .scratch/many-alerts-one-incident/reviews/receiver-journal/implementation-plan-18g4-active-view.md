# Unit 18g4: query-only active accounting archive view plan

Status: local implementation plan, 2026-09-25. Fixed point: `818b3f5`.

The existing `LedgerStore._inspect_verified` replays a stopped v1 SQLite/WAL
image under its exclusive lock, checks the anchor and releases the handle
before returning. Unit 18g3 compares an archive with caller-supplied active
rows. This unit joins those two local read-only interfaces without making the
archive authoritative.

1. Add an `ArchiveActiveView` frozen result to `accounting_store`. Its `ready`
   variant contains only the replayed original event tuple and exact anchored
   `(sequence,digest)` head. Held/unverified/close-failed variants contain no
   history or head. Reuse `_inspect_verified`; do not open a writer, append,
   persist a hold, modify the anchor or accept fixture population.
2. Add `compare_archive_to_ledger(directory, segments, index)` to the overlap
   module. It gets exactly one query-only stopped-image view and returns a
   fixed `active_unverified` refusal on any non-ready state. Otherwise it
   invokes the 18g3 structural comparator. The result is historical local
   evidence only: the lock is released, so this cannot register an archive,
   remove rows, reserve money or permit dispatch.
3. Test ready image, held/corrupt/unavailable image, close failure, unchanged
   file bytes/read-only operation and the existing overlap conflicts. Verify
   no positive authority and no fixture-genesis path. Update docs and ticket
   38. Run focused tests and Ruff, independent Standards/Spec review, then the
   full suite before an exact-path local code commit.
