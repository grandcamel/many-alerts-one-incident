# 18g accounting archive design review

Status: independent Standards and Spec reviews PASS, 2026-09-25.
Baseline: `aa69f7e`. Reviewed the 18g plan/design and ticket/gate/docs updates.

The reviews required exact segment/index/manifest framing and digest domains,
all current replay uniqueness identities in the index, and an account-scoped
provider-line composite key. The revised design specifies them and requires
full semantic replay. Reviewers then identified generation scope and repeated
ID ownership; the final text limits 18g to one generation and assigns a
claimed-ID row to the first event that introduced it. A registered archive
overlaps retained active history: matching prefix rows are applied once and
later contiguous same-generation active rows once. Missing/conflicting
overlap, gaps and cross-generation history hold. Both reviewers read back the
final correction and confirmed PASS.

This is a proposed format, not a writer, migration or evidence of external
continuity. The selected source profile, opening history, off-cluster store,
independent witness, versioned active registration and cross-generation
compaction remain unresolved. Source and full tests: NOT RUN (documentation
only). Provider, native, tenant, paid, venue and power-loss acceptance: NOT RUN.
