# 18g accounting archive format outcome

Verdict: documentation-only local contract reviewed PASS, 2026-09-25.
Ticket 38 remains open.

The proposed wire format pins same-generation event segments, a derived
duplicate index, manifest, tagged digests, overlap verification and ordered
read-back/witness/registration failure rules. It explicitly cannot compact
across generations or supply a production reserve. Independent Standards and
Spec reviews passed after their concrete format and replay findings were
corrected. Whitespace and protected-artifact read-back are recorded in
`validation-18g.json`.

No source code changed; focused and full tests: NOT RUN for this unit. No
archive writer, source verifier, independent witness, off-cluster destination,
active registration, compaction, positive reservation, dispatch permit or
Run was created. Provider, native, tenant, paid, venue and power-loss
acceptance: NOT RUN.
