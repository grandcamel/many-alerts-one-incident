# 19n1 implementation plan: unqualified spawn/release replay

Baseline: `fd4e046`. Source design:
[design-19n1-no-writer-spawn-replay.md](design-19n1-no-writer-spawn-replay.md),
independent Standards and Spec document reviews PASS. No production writer,
containment anchor, child, grant activation, permit or authorization path.

1. Extend `journal_records.py` only with strict `(spawn_attestation, 3)`,
   `(release_intent, 3)` and `(release_observation, 3)` private validators,
   fixed actor/classes, exact data keys and measured 4,096/4,096/2,048-byte
   per-type ceilings. Keep existing v1/v2 and v3 record bytes and ceilings
   unchanged. Verify codec and older-decoder refusal first.
2. Extend `journal_reducer.py` with one separately tagged claim slot per
   phase, pure planners and exact replay verification. Bind the current
   launch/attestation/intent identity and immediate head; preserve the
   pre-release versus historical-observation distinction. Record no positive
   authority, hold clearing or Run completion. Verify pure mixed-version
   replay and capacity behavior before inspection work.
3. Extend `recovery_journal.py` with separately named claim counts/digests
   and an unqualified phase in live/stopped inspection. Use only verified
   exact-head stopped state. Add no application writer or operator control.
4. Add `tests/test_spawn_release_claim_journal.py` for exact order,
   forged/recomputed record, stale head, duplicate/foreign IDs, boot/hold/
   deadline and activation edges, new hold or elapsed deadline before an
   historical observation, capacity ceilings, mixed real-store reopen,
   older-decoder refusal and absence of a writer. Check legacy golden
   digests remain stable.
5. Update `docs/recovery-journal.md` and ticket 37 with the precise local
   outcome. Obtain independent Standards and Spec source review and fix
   findings. Run focused tests and Ruff between major source steps, then
   the full suite after the final code edit. Read back protected dirty
   files, stage exact named files and commit locally.

The 19n1 source cannot validate a protected anchor/witness, escrow recovery
space, authenticate accounting or send a release byte. External and
intended-venue gates remain open and NOT RUN.
