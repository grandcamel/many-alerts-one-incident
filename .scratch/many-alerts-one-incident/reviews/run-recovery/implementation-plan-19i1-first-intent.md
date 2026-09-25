# Unit 19i1: no-writer v3 first-attempt intent

Status: local implementation plan, 2026-09-25. Fixed point: `508887e`.
Authority: reviewed 19i design, accepted ADRs 0012–0013, tickets 37–38.
This unit adds record/replay syntax only; no Receiver writer, ledger reserve,
Forwarder grant, Run, process, permit or positive dispatch scan.

## File-by-file sequence

1. `journal_records.py`: add a private v3 validator for one
   `reservation_intent` shape. Preserve public v1 registry, `SCHEMA_VERSIONS`,
   v2 validator and bytes. Require UUID `job_id`, all existing UUID identities,
   exact `member_count`/`member_digest`, v3 rule and 2,048-byte ceiling.
   Unknown v3 pairs and future versions remain `record_unsupported`.
2. `journal_reducer.py`: add a separate immutable v3 claim/projection and
   separately tagged digest. Pure planner requires current pending membership,
   no global hold, no unresolved v2 run hold or v3 claim, unique admission and
   identities across versions, and ordinary-byte capacity. Replay re-derives
   each field and rejects recomputed forgeries. Preserve v2-only digest and
   state projection formulas. V2 intent planning must refuse while a v3
   claim remains unresolved; v2 run-hold replay may retain a same-job recovery
   obligation but cannot reuse that job ID for another admission.
3. `recovery_journal.py`: expose only count/digest plus an explicit
   outstanding flag for v3 claims in snapshot and verify-only inspection;
   include the v3 claim tuple and separately tagged digest in the stopped
   claim view. A reopened v3-only image must never look claim-free. These
   views confer no reservation or dispatch authority.
4. Add focused tests for canonical validation, eligible first attempt,
   forged digest/member/basis, held and duplicate refusals, ID collisions,
   one-Run slot, ordinary-capacity boundary, mixed reopen, read-only v3
   visibility and old-binary unsupported behavior. Verify v1/v2 goldens and
   changed-file Ruff after the record and reducer steps.
5. Add a truthful unit outcome and ticket 37/38 progress. Independent
   Standards and Spec source reviews must pass; run the full local suite
   before the named-file code commit.

V3 confirmation, cross-version confirmation index, no-launch scanner and
application writer are subsequent units. The current v1 Receiver ledger
continues to reject positive reservation events from unknown population.
The v2 `run_hold` member check cannot attach a same-job hold after a newer
admission supersedes all its members; the v3 claim itself remains visible
and outstanding, and later recovery needs a versioned supersession-safe
obligation transition.
