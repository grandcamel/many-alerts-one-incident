# Ticket 23 fixed-process harness outcome — 2026-09-21

Added `prototype/run_timing/process_fixture.py`, its fixed `_fixture_worker.py`,
`PROCESS_FIXTURES.md` and `tests/test_timing_process_fixture.py`. The production Receiver,
earlier offline core and rejected C2 packet were not modified. No commits or publication.

## Actual evidence

Real local Python fixture processes on Darwin exercised the supervisor. **32 targeted
tests passed in 15.17 seconds**; final full suite **372 passed, 36 skipped in 25.13 seconds**.
Ruff passed. Shortened 2.7/0.2/0.1-second phase bounds (and scale 0.02 for selected kill
cases) were used; the full-duration
270/20/10 schedule was NOT RUN. No skip is acceptance evidence.

Verified success/error/malformed/duplicate terminal handling; minimal inherited
environment; deadline polling through silence; SIGINT and forced SIGKILL; operator
cancellation; parent exit with live descendants/held pipes; descendants that close pipes
but remain alive; bounded stdout/stderr; exclusive attempts including symlink collisions;
spawn failure; and actual-child cleanup after an injected selector exception. The
supervisor records root reaping, process-group disappearance and pipe EOF separately.
Fixture worker snapshots and hashes are retained in exclusive attempt directories.
Additional regressions cover uncaptured-output exclusion, retrospective malformed
output without invented cancellation, inherited SIGINT ignore, unreadable-worker
admission, and read errors that cannot become complete capture or observed EOF.

This closes the fixed-fixture host-test gap only. It does not prove containment against
escaping descendants, OS adversaries or a native model client. The output parent and
source/interpreter are operator-trusted. Captured data is synthetic; the fixture store
is not the private production audit system. Compact result serialization occurs after
the measured supervision interval and does not establish launch-to-durable-closeout
within the full native Run budget.

## Independent review

Standards: **0 outstanding findings** after correction read-back. Spec: **1 later P2
finding, fixed; 0 outstanding**. Both reviewers independently ran the original 26-test
process suite. The final source corrections and regressions received both review
read-backs; the parent ran the final targeted and full suites.

The fresh Fable review was **usable**, with native assistant identity
`claude-fable-5-1`, clean terminal result and exit zero. Its verdict was
**CHANGES_REQUIRED**, not approval. It identified uncaptured bytes entering the parser,
spurious cancellation after process completion, and inherited ignored SIGINT. All three
were fixed with regressions. Worker bytes are also read before consuming an attempt ID,
selected kill tests have more timing margin, and PID 1/subreaper limitations are explicit.
Spec read-back then caught read errors treated as EOF; the final correction marks capture
incomplete, discards affected pending bytes and refuses EOF confirmation.

The original Fable verdict remains preserved. Fable did not re-review the corrections;
the Codex read-backs adjudicated them. Session-reported review cost was approximately
$1.943272, an estimate, not provider actuals or ticket 23 measurement spend. Provider
actuals remain unknown. This was a fresh isolated read-only review of the new source
batch, not a retry of the prior timeout or a resumption of C2. Evidence and digests are
recorded in process-validation.json.

## Remaining gates

Native Claude binding and version-qualified event/permission normalization; confinement
and protected mounts for untrusted model tools; authenticated external receipt transport;
Forwarder-mediated API credentials/TLS/streaming/revocation and direct-route prevention;
atomic durable ledger/provider reconciliation; private audit storage/retention and named
human adjudication; revised timing Skill/prompt/rubric; exact one-attempt approval.

No paid timing/length probe, container, credential operation or live tenant operation ran.
Every fixture result says `FIXED_HOST_FIXTURES_ONLY` and native launch `CLOSED`. The
[measurement card](execution-card.md) remains **CLOSED**, and ticket 23 remains open.
