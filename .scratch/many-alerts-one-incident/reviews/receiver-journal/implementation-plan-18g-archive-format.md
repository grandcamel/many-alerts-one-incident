# 18g accounting archive format and handoff plan

Status: documentation-only local plan, 2026-09-25. Baseline: `aa69f7e`.
Authority: ADR 0013, ticket 38, reviewed 18c/18e accounting gates and the
current v1 ledger implementation. This unit selects no provider, account,
source profile, private off-cluster store or independent continuity witness.

1. Pin a proposed future archive segment, derived duplicate index and manifest
   format from independently replayed active events. Specify canonical byte
   framing, ownership, limits, identity, cumulative chain and read-back checks.
2. Specify ordered handoff and crash outcomes without deleting v1 rows or
   claiming a completed handoff. Require verified archive/index read-back,
   independently anchored witness and an active registration record before
   any compaction. Clarify that v1 has no registration/compaction event and
   18g defines no cross-generation replay or compaction transition.
3. Define failed, conflicting, unavailable, late-line, retention and reset
   behavior. Keep unresolved liability and duplicate uncertainty visible; an
   unavailable index is never evidence of absence.
4. Obtain independent Standards and Spec reviews. Update ticket 38 and the
   accounting gate documentation with the exact remaining implementation and
   external decisions. Verify whitespace and protected dirty artifacts, then
   commit only named documentation. Source/full tests are NOT RUN here.

No archive writer, importer, billing verifier, positive reservation or launch
permit is authorized or represented by this documentation.
