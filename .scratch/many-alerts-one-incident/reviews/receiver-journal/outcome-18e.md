# 18e accounting evidence and archive contract outcome

Status: documentation-only local contract reviewed, 2026-09-25.
Baseline: `cd1365f`. Design and plan are
`design-18e-accounting-evidence-archive.md` and
`implementation-plan-18e.md`.

Independent Standards and Spec reviews initially found an archive-loss
ambiguity: the draft required retaining transferred active state after
compaction. Spec review also required archived attempt and reservation
identities in the active duplicate index. Both findings were fixed, and
both reviewers confirmed PASS on the revised design. A follow-up Spec
finding narrowed the reconstruction gate to model reservation/dispatch;
bounded Notification admission continues. Spec review confirmed PASS.

The contract defines candidate claims, fixed rejection reasons and a
fail-closed archive handoff. It implements no source profile, importer,
archive writer, continuity witness, positive billing verification or
reservation. Source tests and the full test suite are NOT RUN for this
documentation-only unit. Provider, native, tenant, venue, paid and
power-loss evidence are NOT RUN. Ticket 38 remains open.
