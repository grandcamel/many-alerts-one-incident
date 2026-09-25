# 19q implementation plan: no-writer effect claims

Baseline: `4900467`. Source design:
[design-19q-no-writer-effect-replay.md](design-19q-no-writer-effect-replay.md),
independent Standards and Spec design reviews PASS.

1. In `journal_records.py`, register only private v3 `effect_intent`
   (ordinary) and `effect_receipt` (recovery) with exact actor, key/type
   checks, closed claimed-state/reason vocabulary and 4,096/2,048-byte
   ceilings. Keep legacy record families and ceilings unchanged. Verify
   existing codec/claim tests before reducer work.
2. In `journal_reducer.py`, add bounded unqualified intent/receipt maps,
   exact Run/attempt/grant/flight/operation/request/target identity checks,
   current-head one-record planners, same-boot time and deadline checks,
   duplicate refusal and replay re-planning. The receipt planner accepts
   historical evidence after a hold/deadline, never clears a hold or marks
   an effect confirmed. Verify pure/focused tests before inspection work.
3. In `recovery_journal.py`, expose only separately tagged counts/digests,
   unmatched-intent count and `effects_unqualified` in live and stopped
   verified-head inspection. Add no public writer or positive decision.
4. Add `tests/test_effect_claim_journal.py`: exact and forged/recomputed
   records, duplicate operation/receipt, wrong route/grant/flight/digest,
   64/65 and ordinary/recovery capacity edges, hold/deadline/restart
   prefixes, maximal legal encoded shapes, real-store read-back, old binary
   refusal and no-writer/route-unavailable assertions. Run focused tests
   and changed-file Ruff between source steps.
5. Update `docs/recovery-journal.md` and tickets 36/37 with the source-only
   boundary. Obtain independent Standards and Spec source review, fix
   findings, then run the full suite after the last code edit. Read back
   protected dirty files; stage only named 19q files and commit locally.

No Receiver authorization endpoint, accounting reserve, live permit,
Forwarder route opening, external effect, native/provider/tenant/venue
experiment, push or publication is part of this unit.
