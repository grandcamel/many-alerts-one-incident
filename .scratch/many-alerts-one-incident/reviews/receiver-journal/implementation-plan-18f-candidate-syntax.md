# 18f accounting evidence-candidate syntax plan

Status: local source plan, 2026-09-25. Baseline: `2a901d2`.
Authority: reviewed 18e claim/archive contract and ticket 38. This is a
syntax and replay-identity unit, not billing verification or reservation.

1. Add a pure `accounting_evidence_candidate.py`. Parse only canonical ASCII
   JSON bytes up to 2,048 bytes through the existing bounded JSON codec.
   Require an exact `accounting-evidence-candidate.v1` shape: candidate ID,
   source-kind/revision claims, acquisition UTC time, payload SHA-256 and
   byte length (0 to 64 MiB), and an opaque private custody reference. Optional account
   scope, coverage start/end and predecessor are claims; omitted keys stay
   omitted. Reject unknown keys, wrong scalar types, noncanonical encodings,
   malformed IDs/times/digests and reversed claimed coverage with the fixed
   `candidate_malformed` code. No raw provider payload or charge line enters
   the envelope. The parser neither reads a clock/file nor authenticates the
   source or checks the claimed payload digest against payload bytes.
2. Add a bounded pure batch function for at most 256 candidate envelopes.
   Repeated identical bytes under one candidate ID are idempotent;
   different bytes under that ID fail as `candidate_conflict`. Return only
   the immutable unique claim tuple and replay count. Do not infer source
   support, account scope, opening balance, coverage, bill lag, actual cost,
   settlement or permission to reserve.
3. Test real canonical bytes, optional omission, exact type/encoding bounds,
   bad time/digest/coverage, duplicate and conflict, fixed error-code/no
   input echo, batch bound and immutability. Update accounting docs and
   ticket 38 with the source-only boundary.
4. Run focused tests, Ruff, independent Standards and Spec source reviews,
   protected dirty-artifact read-back and the full suite before a local code
   commit. Record hashes and unrun gates. Stage only named 18f files.

No provider source profile, custody reader, payload store, archive, billing
importer, opening reconstruction, continuity witness, positive ledger event,
reserve method, dispatch permit or launcher is added. Those need separate
decisions, reviews and intended-venue evidence.
