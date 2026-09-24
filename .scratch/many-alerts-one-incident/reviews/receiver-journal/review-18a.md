# Unit 18a review

Baseline `1d04b7dc1174924de52a8927059f9eb6cbaca3a3`. Local pure/synthetic
policy review only. Source implementation, independent reviews, mutation
probes and the full repository suite are distinct evidence below.

## Standards

Independent Standards review accepted the final source. No documented-standard
violations or actionable smell findings. Its own focused tests and 969 malformed
field substitutions plus two extreme-year probes passed. Full report and
hashes are retained in review-evidence-18a.txt.

## Spec

Independent Spec review found one context-identity collision gap. Fifteen
red/green regressions and the validated context-ID union fix close it; all ten
reviewer collision probes now refuse. No open Spec findings. The report's
initial hash block was captured after repair and is labelled accordingly.

## Fresh final review

# Unit 18a independent final review

Verdict: ACCEPTED_LOCAL_PURE_SYNTHETIC

Reviewed 2026-09-24 against baseline `1d04b7dc1174924de52a8927059f9eb6cbaca3a3`. No open findings. This is a fresh read-only source/test/documentation review, not durable, provider, paid, native, tenant, deployment, publication, C2, or runtime admission acceptance. CLAUDE.md and CONTEXT.md were read.

## Hash-bound inputs

- `grafana_jsm_sandbox/accounting_policy.py`: `cdb14d136672c730eb4635f0a59e9ae394b2add2c84c7fcfbb6b398ad7c67e9d`
- `tests/test_accounting_policy.py`: `32fbff1a3d194a9925707082f9eef13c4839ed8655dd6c3644c06afde1e9e9a8`
- `docs/accounting-policy.md`: `cc9e8388a4cd5699183dac27bd0be191eba0f76989e089f75c262ebb476dcbe2`
- `.scratch/many-alerts-one-incident/reviews/receiver-journal/implementation-plan-18a.md`: `59ae70d05897b8f15d0e4bc88277f9dd657280d0e5af65435f8e2d4ec9b896ee`
- `.scratch/many-alerts-one-incident/reviews/receiver-journal/next-accounting-unit-design.md`: `e721e75a257e659881e865da71f9c612f880f1e6c1b2a3e54248cbecf02e66b2`
- `.scratch/many-alerts-one-incident/reviews/ticket-38/accounting-specification.md`: `88c090f26a265e3139958cdee3b8a2480f9ef334bda6afb2575d405833bed561`
- `docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md`: `987ddb7841e300151565bd8cb15ab4713c1ea93690f3b6a15208bcc435a2cbc9`

## Independent verification

- Own bounded focused command: `python3 /tmp/maoi-handoff-codex/maoi-loopback-guard.py -q -p no:cacheprovider tests/test_accounting_policy.py`: 123 passed; `NON_LOOPBACK_ATTEMPTS []`.
- Copied source, original tests and documentation to `/tmp/maoi-codex-18a/final`; byte-for-byte `cmp` passed before and after probes. Independent tests import the exact scratch source copy.
- Own bounded scratch command: `python3 /tmp/maoi-handoff-codex/maoi-loopback-guard.py -q -p no:cacheprovider /tmp/maoi-codex-18a/final/test_independent.py`: 30 passed; `NON_LOOPBACK_ATTEMPTS []`.
- Scratch probes cover unrelated current/old-week lifecycle and diagnostic counter breaches, unrelated diagnostic spend breaches, retry exhausting each counter independently, historical boundary overlap versus explicitly unauthenticated timezone shape, all 20 candidate-ID/context-role combinations, and 161 malformed-field/subclass checks. First scratch run had only a mistaken assertion about the number of executed checks (188 versus 161); all behavioral assertions passed. Corrected that scratch bookkeeping assertion and reran successfully.
- Static inspection confirms 413 source lines, allowed imports only, no application caller, no current-clock/network/process/persistence path, exact type checks before potentially unsafe equality/hash operations, immutable results, fixed refusal codes, and no mutable returned containers.
- `git diff --name-only 1d04b7dc1174924de52a8927059f9eb6cbaca3a3 -- grafana_jsm_sandbox tests` returned empty. Reviewer made no repository edits or staging changes. Full-suite verification belongs to the root reviewer and was not rerun here.

## Contract and documentation assessment

Money representation, signed-64 overflow refusal, strict lifetime cap, independent inclusive model/bucket caps, complete historical bucket checks, retained counts, settled-actual replacement, non-model isolation, original-week attribution, stale/unknown exposure, strict chronology, latest-tip retry linkage, cross-week refusal and context-disjoint identities conform to the approved plan. Existing tests cover the principal arithmetic mutants; the additional probes independently cover less-direct history/count paths.

Documentation correctly separates accepted ADR policy from proposed U/microdollar/lifetime choices. Completeness, settlement, configuration and effect reconciliation are hypothetical inputs; structural retry checks cannot detect a failed initial semantically relabeled before the first retry. Historical timezone values receive shape validation only. Same-key current values must agree with fresh boundaries. These limitations are explicit rather than overstated guarantees. No proposal is a receipt, reservation, readiness result or launch permit. The durable ticket-38 seam and all external acceptance gates remain unmet.

Independent probe SHA-256: `6e4a02b9cfd658561f30c4013689b6daa24e710b5f6cdde4f940a4f3b8e4c366`.


## Root verification

All six deliberate policy mutants were killed: inclusive-$50 error, R replacing U,
duplicate weekly retry charge, missing retry diagnostic attribution,
unknown-to-zero and lost counters. The scratch mutation runner/patches and
results are retained as evidence, not applied to this repository.

Full suite: **5062 passed, 39 skipped**.
Focused new-file suite: **123 passed**, loopback guard clean.
Ruff, E501, whitespace, all 137 baseline source/test/config hashes and all
18 prior 17b artifact hashes passed. Four protected dirty artifact hashes
remain unchanged. No existing application source calls the new component.

Counts per axis: Standards zero; Spec one found/closed, zero open. Final
review verdict is scoped to local source and synthetic policy, not durable
reservation, runtime launch, provider evidence, native/tenant/venue or paid work.
