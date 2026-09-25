# Unit 18g2: derived same-generation archive index plan

Status: local implementation plan, 2026-09-25. Fixed point: `705fc12`.

## Scope and sequence

1. Add a pure `accounting_archive_index` codec for the physical index in the
   reviewed 18g format. Accept up to 256 segment bytes and expected digests;
   re-decode each through the 18g1 codec in order. Require one exact v1 history
   from genesis, one ledger identity/generation and contiguous sequence.
2. Derive `event_id` and `claimed_id` rows from the replayed v1 event stream.
   Preserve the first replay transition that added each claim. Check the
   derived claim set equals `Projection.claimed_ids`; compare the complete
   canonical index bytes on read. Current v1 has no authenticated provider
   charge-line event, so emit no `provider_line` rows and reject any supplied
   index that invents one. Do not guess a source profile or account key.
3. Enforce the 18g index bounds, canonical ordering, tagged digest and exact
   framing. Expose only a pure result; add no archive registration, store
   mutation, continuity witness, reserve, permit or dispatch caller.
4. Add focused tests for two segments, stopped real SQLite replay, claim
   ownership, changed/reordered/omitted/duplicated rows, truncation, trailing
   bytes, segment conflict and capacity. Run Ruff, focused tests, two-axis
   independent source review and the full suite before the code commit.
5. Record a truthful local outcome and ticket 38 update. Keep external billing,
   witness, off-cluster durability and venue gates open.

The codec may use the transition module's existing internal body-ID extraction
because replay and the final claim-set comparison bind that derivation. A
future event version must define its own index namespace and source-line key
before archive admission can accept it.
