# Ticket 23 — fixed-fixture evidence closeout

2026-09-21. **LOCAL FIXTURE IMPLEMENTATION / NATIVE LAUNCH CLOSED.**

The preceding offline core, process harness and synthetic ledger were committed locally
as `414b689` after **412 passed, 36 skipped in 29.62s**. This continuation adds retained
bytes and verifiable closeout; it does not complete ticket 23's measurement experiment.

## Implementation

[fixture_evidence.py](../../../../prototype/run_timing/fixture_evidence.py) stores the fixed
harness's retained capture alongside its result and worker snapshot. Exclusive file writes,
file/directory flushes and a final manifest link prevent replacement of prior evidence.
Read-back checks bounded sizes, digests, the exact manifest file set and result linkage.
Missing, malformed, duplicate-key, oversized, symlinked and nonregular leaf evidence is
rejected. A crash before publication leaves partial files without an accepted receipt.

The capture merges stdout/stderr in supervisor read order; it has no stream identity and
is not a replayable native transcript. Failed execution and incomplete capture remain
failed/incomplete after successful byte verification. A closeout failure after child exit
preserves the ledger's unknown claimed reservation and denies relaunch. Evidence read-back
never reconciles billing. See the [contract](../../../../prototype/run_timing/FIXTURE_EVIDENCE.md)
for the exact scope and crash-after-publication behavior.

A valid manifest after an interrupted final directory flush can establish matching retained
bytes, but cannot establish that the writer returned successfully or the flush completed.
The closeout operations occur after supervision and have no bounded storage latency.
Neither supervision time nor successful read-back proves the native 300-second total bound.

## Validation and review

Final evidence suite: **52 passed in 1.92s**. Full repository suite: **464 passed, 36 skipped
in 32.08s**. Ruff and `git diff --check` passed. Tests include actual process
crashes before/after publication, failed final sync with a readable manifest, write limits,
exact cost serialization, receipt corruption and ledger hold after closeout failure.

Independent Codex Standards and Spec reviews each found **zero outstanding findings**.
A fresh bounded read-only Fable review returned **PASS** for the byte-integrity contract.
Requested and observed assistant model: `claude-fable-5-1`, session
`f6310703-eeea-4de4-94a4-7a396d9de1e8`. Its session estimate was **$1.396932**; provider
actual remains **unknown**. This review was not a timing/length measurement attempt.

Advisories prompted strict JSON serialization with explicit Decimal conversion, preservation
of observed diagnostics in `FixtureCloseoutError`, nonblocking regular-file checking at
snapshot flush, expanded failure/shape tests, and clearer alias/containment/postpublication
limitations. Fable read the frozen original snapshot only. Parent tests and final independent
Codex Standards/Spec readbacks cover the corrections, with zero outstanding findings.
Its unverified host test/runtime questions are covered by the executed suite on this host;
this does not add cross-host or native acceptance.

Raw review, frozen prompt, final text and hashes are preserved outside Git in the evidence
root's `fable-review/` directory. Exact source/evidence hashes and final suite counts are in
[closeout-validation.json](closeout-validation.json).

The previous packet's 30 artifacts were read from commit `414b689`, verified against its
manifest and archived at
`/Users/jasonkrueger/maoi-ticket23-evidence/20260921-fixture-closeout/prior-phase-snapshot/`.
The new packet preserves historical receipts rather than relabelling prior source hashes
as the current implementation.

## Remaining boundaries

This is byte integrity for trusted fixed synthetic fixtures. It does not authenticate
provenance or defeat a same-user actor replacing the entire packet. Directory ancestry,
mount custody, secrets sanitization, production disk quota/retention, stale-copy detection,
hardware power-loss behavior and independent semantic re-adjudication are not implemented.
There is no native client, real provider accounting, Receiver/Forwarder integration,
paid timing/length probe or model/tenant/venue acceptance. The measurement card stays
CLOSED, ticket 23 stays open, and C2 work is unchanged. No push or publication occurred.
