# Ticket 23 — synthetic diagnostic ledger outcome

2026-09-21. **LOCAL FIXTURE IMPLEMENTATION / NATIVE LAUNCH CLOSED.**

Implemented persistent diagnostic accounting in
[fixture_ledger.py](../../../../prototype/run_timing/fixture_ledger.py), bound only to
the existing fixed local process fixtures. See the
[ledger contract](../../../../prototype/run_timing/FIXTURE_LEDGER.md) and
[validation receipt](ledger-validation.json). Ticket 23 remains open; this is not
completion of ticket 38's lifecycle/Receiver accounting specification.

## Behavior and evidence

- Explicit exclusive fixture initialization; normal operations open existing storage
  only. Missing, corrupt, wrong-scope and busy databases deny admission without treating
  unavailable accounting as zero. SQLite write transactions serialize competing writers.
- Separate committed $3 synthetic reservation and one-time launch claim precede a fixed
  fixture launch. Unknown exposure survives crash/reopen and week rollover. Successful
  process exit is not a bill and cannot automatically release a reservation.
- Exact integer-microdollar totals replace a reservation with its supplied final synthetic
  actual. Identical receipts are idempotent; conflicting receipts preserve the old amount
  and a durable hold. The first hold reason survives subsequent failures.
- Diagnostic admission enforces $30 and ten attempts; weekly model allocation admission
  enforces $150 with America/New_York Monday boundaries. Synthetic other-model actuals
  share the weekly total. Late diagnostic receipts remain in the original attempt week.
- Admission requires room for both attempt and receipt within the 10,000-record bound.
  Intervening receipts can consume the headroom; exhaustion holds without deleting unknown
  exposure. This is not a disk quota, reconstruction procedure or retention policy.
- Shared fixed-harness request validation runs before admission. Invalid scenario, ID or
  scale cannot consume an attempt. Filesystem/spawn failures after admission retain the
  reservation conservatively.

The targeted ledger suite passed **40 tests in 6.65s**. Tests include actual competing
processes, abrupt process exit before/after commit and after claim, database reopen and
lock timeout, receipt conflicts, capacity, clock/week boundaries and fixed fixture launch
ordering. The full repository suite passed **412 tests, 36 skipped in 32.04s**. Ruff and
`git diff --check` passed. No commit or publication was performed.

## Independent review

Codex Standards found one P2: request validation originally occurred after reservation
and claim. The shared validator now rejects invalid inputs before accounting changes;
regressions cover six invalid requests. Final Standards and Spec readbacks each have
**zero outstanding findings**.

A fresh bounded read-only headless Fable review returned **PASS**. Requested and observed
assistant model: `claude-fable-5-1`; session
`28d1bb14-e2ae-4bc8-ad2f-205ca937b219`. Its three low advisory items were addressed:
accurate separate-transaction wording, receipt headroom on admission, and preserving the
first hold reason. Its two informational observations remain intentional: the wrapper
uses one fail-closed exception family, and an explicit synthetic receipt can settle an
unclaimed reservation. Neither enables automatic settlement or native launch.

Fable read the frozen initial source and did not execute tests or review the subsequent
corrections. Parent verification, tests and the final independent Codex readbacks cover
those corrections. Fable's session estimate was **$1.816472**; provider actual is
**unknown**, not zero. This source review is distinct from the closed timing/length
measurement experiment. The review's unverified local runtime/signature/test questions
are covered by the executed suite on this host; cross-host and native gates remain below.

Raw prompt, output, final text and digests are preserved under
`/Users/jasonkrueger/maoi-ticket23-evidence/20260921-fixture-ledger/fable-review/`.
The previous packet's 24 artifacts were verified and archived under that evidence root's
`prior-phase-snapshot/`; `archive-provenance.json` records recovery of the exact previous
process fixture source by reversing only the validator extraction and matching its hash.
The current packet manifest indexes the final source and documents separately.

## Remaining boundaries

No real account balance, provider receipt, user accounting ledger, credential, tenant,
container or paid timing/length probe was accessed by this implementation. Synthetic
billing-readiness booleans, timestamps and receipt inputs are trusted fixture inputs.
These tests do not authenticate provider actuals or prove stale-database restore detection,
same-user tamper resistance, hardware power-loss persistence, production storage custody,
retention/reconstruction, lifecycle/retry allocation or Receiver/Forwarder integration.

The earlier fixed-process limits remain: no full 270/20/10 duration proof, launch-to-durable
closeout bound, adversarial isolation, native stream/permission qualification or mediated
credential/direct-route evidence. Model/tenant/venue acceptance is NOT RUN. The
[measurement card](execution-card.md) stays CLOSED. C2 work and ticket 38 are unchanged.
