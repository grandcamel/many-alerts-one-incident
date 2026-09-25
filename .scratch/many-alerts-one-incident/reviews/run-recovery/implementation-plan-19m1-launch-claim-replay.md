# 19m1: unqualified launch-claim replay implementation plan

Status: local multi-file source plan, 2026-09-25. Baseline: `984f50c`.
Authority: reviewed [19m design](design-19m-no-writer-launch-claim.md),
ADRs 0011–0013 and tickets 36–38. No application writer, grant registration,
process or permit is in scope.

1. `journal_records.py`: add only `(launch_claim, 3)` with actor `receiver`,
   ordinary class, exact keys/types, five-service ceiling and a measured
   type-specific 6,144-byte ceiling. Keep all v1/v2 and existing v3 bytes,
   validators and private size limits unchanged. Verify codec/older-decoder
   behavior before changing projection code.
2. `journal_reducer.py`: add one frozen `LaunchClaim` projection slot and a
   separate tagged digest. Pure planning requires the current boot and
   Run-intent slot, exact journal basis, original members still current, no
   dispatch or Run hold, identical sorted service claims, distinct bounded
   opaque grant IDs, same boot/generation claims, and checked origin/deadline
   arithmetic. Replay re-plans and compares exact canonical bytes/digest.
   Grant/clock authenticity stays unverified; the outcome and projection use
   `outstanding_unqualified_launch_claim` only. Verify pure and mixed-version
   tests before moving to store inspection.
3. `recovery_journal.py`: add the separate claim count/digest/state to live
   snapshot and stopped verify-only inspection. Add no writer, operator action
   or positive status. Verify real SQLite/WAL reopen and old-binary refusal.
4. `tests/test_launch_claim_journal.py`: cover wrong service/claim/grant,
   duplicate IDs, wrong boot/generation, stale basis, member supersession,
   new holds, deadline/expiry edges, forged recomputed record, maximal bytes,
   ordinary-capacity edge, mixed reopen and older decoder. Test the no-writer
   boundary and stable older digests.
5. Update only the relevant source docs and ticket 37 after independent
   Standards/Spec review. Run focused tests, Ruff and the full local suite
   after the last code edit, read back protected dirty-file hashes, and stage
   only named 19m1 paths for a local commit.

The current ledger cannot authenticate a reservation; synthetic record tests
cannot create a production grant, barrier release or Run acceptance. Native,
provider, tenant, paid and intended-venue work remains NOT RUN.
