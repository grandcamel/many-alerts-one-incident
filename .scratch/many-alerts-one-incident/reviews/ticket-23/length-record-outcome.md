# Ticket 23 — inert length-case records

2026-09-21. **OFFLINE LENGTH RECORDS ONLY / NATIVE LAUNCH CLOSED.**
Baseline: local commit `def767b`.

`LengthProbe.report()` now exports all five fixed cases with expected/requested/observed
command digests and byte counts, tool identity, virtual request/dispatch/observation times,
synthetic decision/reference/coverage, locally issued receipt metadata, supplied-receipt
trust status, stub exit and classification. Raw command bodies are not exported.

An accepted unresolved request is pending, while untouched cases remain not-attempted.
Missing, copied, foreign and conflicting supplied receipts cannot erase a locally issued
receipt or become proven denial. Refusal/unavailability/fallback preserves the current
observation and untouched cases, holds dispatch and records probe-emitted cleanup actions.
The report separately exposes lifecycle state for external cancellation. Snapshots are
independent of future probe activity and cannot mutate internal records.

Newly retained observation strings and byte arrays are bounded; stub exit integers are
signed 32-bit and exclude booleans. Invalid observations hold without advancing or erasing
the pending request. The existing order, one-dispatch rule and bracket classifications
remain unchanged. See the [record contract](../../../../prototype/run_timing/LENGTH_RECORDS.md).

The [example](fixtures/length-record-example.json) is a generated synthetic fixture with
two locally dispatched cases (stub exit 7) and three supplied synthetic denial observations.
It is not a measured native bracket, real denial evidence or model behavior. It was generated
from the current code and JSON read-back matched the snapshot; no command was executed.

## Validation

- New focused suite: **22 passed in 0.09s**.
- Combined executor/record suite: **88 passed in 0.28s**.
- Full repository suite: **486 passed, 36 skipped in 30.22s**.
- Ruff and `git diff --check`: PASS.
- Independent Standards: **0 findings**. Independent Spec: **0 findings**.

Both reviewers inspected the completed source and tests; the parent executed validation.
This bounded deterministic record export used the two-axis code-review workflow. No fresh
Fable or other external-model call was made or claimed for this batch.

[Validation and source hashes](length-record-validation.json) identify the exact implementation.
The preceding 36-file packet was read from `def767b`, verified against its manifest and
archived under `/Users/jasonkrueger/maoi-ticket23-evidence/20260921-length-records/prior-phase-snapshot/`.

## Remaining boundaries

All timestamps are virtual. Receipt authority is object identity inside the current trusted
probe; exported metadata cannot be re-imported as an authentication capability. Decision
references are opaque synthetic labels, not verified native evidence. The export is not
a sanitizer, native audit adapter or human Mechanism/evidence grade.

Native command-boundary observation, authenticated supervisor receipt transport, actual
policy/model/version/auth context, mediation, provider billing and separately authorized
measurement remain closed gates. No shell command, Jira operation, model probe, credential
change or infrastructure operation occurred. Ticket 23 remains open. C2 changes were
preserved and nothing was pushed or published.
