# Unit 18g3: active/archive overlap verifier plan

Status: local implementation plan, 2026-09-25. Fixed point: `59c1392`.

The accepted 18g same-generation format requires exact overlap between a
retained active ledger and a proposed archive. The current segment and index
codecs verify an archive prefix, but no local function checks an active suffix
against it. This is a pure structural verifier, not an archive registration,
continuity witness, ledger migration or reservation path.

1. Add `accounting_archive_overlap.py` with one function accepting complete
   segment/index objects, a bounded nonempty active-event tuple and an
   explicit active head `(sequence, digest)`. Re-decode all archive bytes and
   derive the index. Require each active event to be self-consistent, ordered,
   contiguous and within the same ledger generation. An active history may
   overlap any contiguous tail of the archive or begin immediately after it;
   every overlapping original body and digest must be identical. The active
   head must be at or beyond the archive head, and the first suffix event must
   chain to that head. Replay exactly one union and return its projection and
   structural counts.
2. Bound active rows by the v1 8192-event limit. Return fixed errors without
   caller bytes or paths for missing, changed, reordered, gapped,
   cross-generation, forged-head and invalid index cases. No input object is
   treated as an authenticated store or off-cluster witness.
3. Add tests with real encoded v1 event histories covering complete overlap,
   partial overlap, immediate suffix, missing/conflicting overlap, suffix
   chain mismatch, active head mismatch, index mismatch and invalid inputs.
   Keep current store and admission behavior unchanged.
4. Update accounting documentation and ticket 38 with exact local evidence.
   Run focused tests/Ruff, independent Standards and Spec reviews, and the
   full local suite before a named-file code commit. Leave archival handoff,
   retention, billing, reservation and venue gates open.
