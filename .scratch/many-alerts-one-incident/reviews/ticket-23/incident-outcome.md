# Ticket 23 — synthetic Incident revisions and effects

2026-09-21. **TRUSTED IN-PROCESS FIXTURES / NATIVE LAUNCH CLOSED.**
Baseline: local commit `f6563c5`.

[TimingIncidents](../../../../prototype/run_timing/timing_incidents.py) starts with an empty
candidate snapshot anchored to the retained pinned Notification. One instance can create one
synthetic Incident and append complete immutable Report revisions. Candidate reads include the
current Report; historical revisions and corrections remain independently readable. The store
preserves an unrelated fixture label, accumulates fingerprint membership, ratchets severity and
urgency, and requires the current expected revision for append. Match judgment stays external.

The [local contract](../../../../prototype/run_timing/TIMING_INCIDENTS.md) bounds text, Report
bytes, references and admitted writes. Each Report inventories all seven Alerts. References must
resolve to a retained query envelope/item in the same TimingQueries instance. These checks prove
identity linkage only; unsupported prose and incorrect causal judgments remain human audit work.

Write admission creates a pending dispatch receipt. A separate controller action simulates the
effect. Confirmed effects commit; definite failures do not. Lost-reply cases model both no write
and a write that applied without confirmation. Both remain unknown and hold future work. Operator
read-back exposes retained state without clearing that hold. Revocation stops new work while
allowing completion of previously admitted dispatch. Returned copies cannot rewrite retained
records. These are volatile correlation observations, not authenticated remote receipts.

## Validation and review

The focused store suite passed **46 tests in 0.18s**. The full suite passed **575 tests,
36 skipped in 28.81s**. Ruff and diff whitespace checks passed. Coverage includes empty/create/
append, immutable correction history, severity/label preservation, input/output mutation,
invalid membership/references/revisions/identities, count/byte bounds, pending writes, revocation,
definite failure and unknown effects before/after apply.

Standards: **zero blocking findings**, one optional suggestion to name the four pending-state
fields with a private tuple/dataclass. Deferred as a readability improvement for this bounded
prototype. Spec: **zero actionable findings**. Both independent reviews were read-only.

The fresh bounded headless Fable review returned **PASS**, with zero required findings and
seven optional suggestions. Clarified five documentation points: unapplied proposal content
is discarded, references depend on the paired query store, aggregate byte limits can reject
individually valid fields, construction is not admission, and effects use dispatch IDs.
Distinct error-message branches and extra shape validation of the hash-pinned corpus were
deferred. Source and tests are unchanged from the reviewed snapshot. The retained review
also lists untested edge cases; this is not exhaustive correctness or native acceptance.
The reviewer reported model `claude-fable-5-1`; its $2.107332 session estimate is separate
from provider actuals, which remain unknown. This was source review, not a timing probe.

[Machine-readable validation](incident-validation.json) pins source hashes, test receipts,
review provenance and unrun boundaries. Raw local evidence is outside Git at
`/Users/jasonkrueger/maoi-ticket23-evidence/20260921-timing-incidents/`.
The preceding manifest and all **63 indexed files** were read from `f6563c5`, checked against
its byte counts/digests and archived under that evidence root's `prior-phase-snapshot/`.
The refreshed packet manifest describes this phase; older validation hashes remain historical.

## Remaining gates

Native query/write binding, effective authorization, authenticated effect receipts, durable
recovery, cross-instance uniqueness, real Jira effects, adversarial isolation, full native
270/20/10 closeout and authoritative billing remain unimplemented or NOT RUN. Human Report
grading/rubric freeze, paid timing/length probes, tenant/model/venue qualification and publication
are NOT RUN. Ticket 23 remains open; this fixture work does not close tickets 38/39 or authorize
an execution card. No Run-visible Skill was installed.
