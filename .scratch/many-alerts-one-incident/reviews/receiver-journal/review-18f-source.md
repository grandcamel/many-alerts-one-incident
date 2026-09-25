# 18f candidate syntax source review

Status: independent Standards and Spec reviews PASS, 2026-09-25.
Baseline: `2a901d2`. Reviewed source and tests:
`grafana_jsm_sandbox/accounting_evidence_candidate.py` and
`tests/test_accounting_evidence_candidate.py`.

Standards review found no actionable issue. It confirmed the existing bounded
canonical JSON codec, fixed-code/no-input-echo errors, immutable redacted
claim objects and bounded batch behavior. Spec review found no actionable
issue against the 18e design: fields remain unverified claims, omitted
optionals remain absent, exact replay is idempotent only within one batch,
and changed bytes under one candidate ID are a conflict. The batch replay
count is not a persistent duplicate index; the accounting docs say so.

Neither review establishes source authentication, claimed payload custody,
charge-line identity, opening coverage, actual billing, continuity witness,
archive durability or reservation authority. These remain separate gates.
