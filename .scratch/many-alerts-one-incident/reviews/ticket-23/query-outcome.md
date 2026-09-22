# Ticket 23 — pinned read-only timing queries

2026-09-21. **IN-PROCESS SYNTHETIC FIXTURES / NATIVE LAUNCH CLOSED.**
Baseline: local commit `44ed5f5`; the preceding timing drafts were already committed.

[TimingQueries](../../../../prototype/run_timing/timing_queries.py) now loads five exact
Notification/telemetry files copied from pinned historical source. It never executes the
old generator, runner or stubs. Ground truth and scoring material are excluded. Fixed names,
regular-file bounds and compiled-in SHA-256 values reject missing/changed sources before
an adapter is ready. Storage ancestry and interpreter/source remain trusted operator inputs.

The [local protocol](../../../../prototype/run_timing/TIMING_QUERIES.md) supplies Notification,
metric catalogue/exact-series query, exact-service logs, trace summaries/exact detail and
Changes. It uses canonical inclusive UTC time windows, explicit matched/returned counts
and truncation. A successful empty selection, an unknown exact selector and a rejected
query are distinct. Summary projections cannot establish retrieval of omitted detail.

Responses carry request ID, unique attempt/session/sequence correlation, effective arguments,
virtual observation time, pinned source digest/item pointer/projection and response digest.
Bounded retained serialized responses permit detached read-back after revocation; new
queries require the Lifecycle work window. A rejected request issues no response and consumes
no ID or sequence. Already issued request IDs cannot be reused. This is single-threaded,
in-memory fixture evidence, not durable audit or authenticated native dispatch.

## Validation

The corrected focused adapter suite passed **43 tests in 0.24s**. The final full suite
passed **529 tests, 36 skipped in 28.62s**. Ruff and `git diff --check` passed. Tests cover five-file historical
parity, filtering/window/projection, empty/not-found/rejected distinctions, stable correlation,
truncation, snapshot independence, revocation, count/byte capacity, invalid requests and
missing/tampered/nonregular files. Query-path checks prohibit file opens, process launches
and sockets after initialization.

Independent Standards and Spec reviews found **zero findings each**. The Spec reviewer also
verified all five files byte-for-byte against the historical commit and ran the focused suite
(**36 passed in 0.63s**) before the external-review correction. Both final internal
read-backs found zero outstanding issues after that correction.

The fresh read-only Fable review returned **CHANGES_REQUIRED** for one defect: Unicode
calendar digits passed timestamp validation and then compared incorrectly to ASCII fixture
timestamps. Parent reproduction returned 37 matching logs for the ASCII lower bound but
zero for its full-width-year spelling. Canonical validation now uses `re.ASCII`, with six
regressions spanning both bounds and fullwidth/Arabic/mixed digits. Invalid input raises
without issuing an empty response or consuming request identity. Additional advisories led
to stronger ordinary-file-open checks, a cwd-independent manifest test, explicit earliest-
first truncation documentation, and metric-truncation/until-only tests.

Requested and observed model: `claude-fable-5-1`; session
`3a2fd875-213c-4c7d-a655-8ebc9ee0c9bd`. Session estimate **$1.529522**; provider actual is
**unknown**. Fable reviewed the original snapshot, not the correction. Its verdict is
preserved; parent tests and independent final Codex read-backs cover the corrected source.
Its unverified fixture/hash/Lifecycle/full-suite questions were checked locally, not promoted
to cross-host/native acceptance. Pinned JSONL blank-line parsing is intentionally strict;
changing the pin would require new source review and tests.

Raw prompt/output/final text and hashes are under the evidence root's `fable-review/`.
This source review was not a timing/length measurement. Exact validation/source hashes are
recorded in [query-validation.json](query-validation.json).

The previous 52-file packet was read from `44ed5f5`, verified against its manifest and
archived under `/Users/jasonkrueger/maoi-ticket23-evidence/20260921-timing-queries/prior-phase-snapshot/`.
The timing draft's Run text and rubric are unchanged; only its operator readiness notes
and their manifest digests are updated to acknowledge this local read-only slice.

## Remaining boundaries

The protocol is not registered native tools, a shell/CLI, a sealed Run mount, an Incident
store or a transport authorization mechanism. Request/response IDs and hashes correlate
trusted fixture observations; they do not authenticate caller-supplied evidence. Raw files
must remain supervisor-side in any future binding. Historical Change source labels do not
prove a current coordinator or actuation stage. No real telemetry, Jira/Incident mutation,
credential operation, model measurement, provider accounting or venue acceptance occurred.

Synthetic Incident write/read-back semantics, native adapter and mediated client, audit
custody/retention, full durable-closeout timing, human rubric freeze and separately authorized
paid timing/length probes remain open requirements. Ticket 23 stays open; its card stays
CLOSED. C2 work is unchanged. Nothing was pushed or published.
