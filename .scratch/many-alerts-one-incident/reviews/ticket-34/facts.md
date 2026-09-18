# Ticket 34: accepted audience constraints

* **What can be shown and its authority.** Show authoritative OPS Incident/member
  state separately from cited directory observations/hypotheses and reviewed
  Confluence knowledge: OPS remains authoritative; Memory cannot establish a
  Match ([ADR 0009:5-13](../../../../docs/adr/0009-memory-has-one-incident-authority-and-reviewed-learning.md:5)). A compact per-Run activity/elapsed/usage/outcome dashboard and linked *sanitized* event timeline are accepted; unknown usage/outcome stays unknown/incomplete ([ADR 0010:25-27](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md:25)). Telemetry explains activity, never independently proves the diagnosis ([ADR 0010:5](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md:5)).

* **Memory/review state.** A draft is not approved knowledge; human review is
  required before reusable guidance, and reopening/pending correction blocks
  promotion ([ADR 0009:11-13](../../../../docs/adr/0009-memory-has-one-incident-authority-and-reviewed-learning.md:11)). Presentation needs distinct draft/reference identities and visible incomplete create/conflict work; human-only originals/provenance/revocation history persist across rehearsals ([ADR 0017:21-29](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md:21)). A changed, archived/deleted, unverifiable, or revoked reference is unavailable rather than silently current ([ADR 0017:15-17](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md:15)); revocation cancellation is not rollback of OPS effects ([ADR 0017:27](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md:27)). Ticket 34 explicitly calls for unavailable/revoked context and incomplete/uncertain draft work, and rejects label-as-approval (`issues/34-what-the-audience-sees-of-memory.md:15-17`).

* **Run-readable versus operator-only.** Runs may read retained sanitized
  execution telemetry only for self/earlier current-rehearsal Runs; dropped,
  expired, and missing data is unavailable, not an empty success ([ADR
  0010:15-19](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md:15)). The operator-owned raw audit bundle is outside Run mounts, Memory,
  shared telemetry and Git; Ground truth/scoring feedback never reaches Runs
  ([ADR 0014:17-23](../../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md:17)). The approval manifest is operator-owned and Run-immutable ([ADR 0017:15](../../../../docs/adr/0017-confluence-references-and-drafts-have-separate-authority.md:15)).

* **Comparison boundary.** The three qualification samples include cold-start
  and Memory-assisted conditions, but are neither a controlled Memory
  comparison nor a success-rate claim ([ADR 0014:27-29](../../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md:27)). Ticket 34 repeats this presentation limit (`issues/34-what-the-audience-sees-of-memory.md:11-13`).

No UI, telemetry, tenant, or runtime work was performed.
