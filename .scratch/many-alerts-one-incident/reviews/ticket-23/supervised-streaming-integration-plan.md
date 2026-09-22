# Next offline unit: supervised streaming evidence

2026-09-22. Proposed local fixture integration under standing local-work authority.
This follows the [incremental transport outcome](incremental-streaming-outcome.md).
It starts no native model client, provider operation, paid experiment or C2 retry.

## Missing join

The [streaming harness](../../../../prototype/mediated_client/README.md) now
exercises two TLS loopback hops and bounded partial delivery. Separately, the
[timing rehearsal](../../../../prototype/run_timing/TIMING_REHEARSAL.md) supervises
a fixed child, retains stdout/stderr and checks child-produced artifacts. Neither
currently proves that this supervised child consumed this particular stream.

The next deliverable is a bounded design and then an implementation joining those
existing fixture seams. Define the exact child input, attempt identity, fixture
lease, endpoint/CA binding and evidence receipt before editing multiple files.
Do not infer a native client's event or permission schema from either fixture.

## Required contract and sequence

1. Inspect the existing closed worker/bundle interface and byte limits. Choose a
   fixed scenario and trusted fixture-only launch record; prohibit arbitrary
   executable, code, argument, environment, endpoint and path selection. If the
   existing bundle cap cannot hold the selected sources, report the measured
   conflict and revise the bounded packaging design before implementation.
2. Bind one supervisor attempt to the parent-owned synthetic TLS harness and its
   one-use fixture lease. Parent and child observations must share exact attempt,
   stream sequence and fixture source digests. A child-supplied string alone
   cannot create parent-observed dispatch or process identity.
3. Have the actual fixed child decode the first frame and emit a bounded local
   acknowledgement before the parent releases the final portion. Retain child
   decode/terminal evidence separately from mediator local-write receipts and
   supervisor exit, timeout, cancellation, reaping and capture state.
4. On timeout/cancel, revoke the fixture lease and contain the child within the
   original deadline. Preserve partial delivery and unknown exposure; no retry,
   new deadline, manufactured terminal or automatic settlement. A parsed terminal
   cannot override nonzero exit, failed containment or missing capture.
5. Publish a bounded immutable evidence manifest with exact source artifacts,
   byte counts, digests, chronology and explicit gaps. Re-read the actual child
   and supervisor artifacts through their existing validators; never reconstruct
   a purported child result in the parent after an unrelated child exits.
6. Exercise normal completion, truncation, duplicate terminal, withheld final
   frame, cancellation, child failure, malformed/missing receipt, capture loss
   and interrupted closeout. Delegate implementation and independent tests/review
   with separate file ownership; run the full suite before a local commit.

No source artifact from ticket 19, Ground truth, human rubric, actual account,
provider credential or repository tool belongs in the child's closed bundle.
Fixture keys and sentinel tokens remain synthetic. This integration still is
not an adversarial OS sandbox or a provider-supported client/route experiment.

The outcome must distinguish stream validity, local delivery, child decoding,
process completion/containment, evidence completeness and synthetic accounting.
Human Report adjudication and all native, account, billing, tenant and intended
venue gates remain separate. No new user input is needed for this local unit.

## Selected implementation boundary — 2026-09-22

Measured before editing: the generic worker is 2,246 bytes; the existing timing
bundle is 40,825 of 65,536 allowed bytes, covering 132,280 source bytes. The parent
streaming module alone is 34,029 source bytes. This unit uses a separate standalone
stdlib child instead of bundling the parent harness. Its exact final size must be
checked against the unchanged 64 KiB worker limit before creating an attempt.

The public supervisor signature stays unchanged. Only a closed set of new
`stream_*` scenarios constructs an internal `StreamSession`. The parent creates
the two TLS loopback listeners and a fixed-name private bootstrap file containing
only fixture launch values. The child reads that bounded file with no extra
argument or environment selection. The token is synthetic and temporary; it is
excluded from captured worker source, stdout/stderr, and the retained sidecar.
Cleanup failure remains a gap. This does not establish same-user OS isolation.

The supervisor feeds only retained complete stdout lines to the session. A typed
ACK must match the attempt, lease, bootstrap and first-frame digest/byte count,
and the parent's first-frame-write observation before terminal release. The
release decision also checks sampled cancellation and the original work deadline.
An already released frame is never retroactively marked unsent.

Revocation requests and polling in the selector loop are nonblocking. They record
intent before interruption, prevent further release, and retain pending revocation
until the harness lock can be acquired. Harness stop and evidence publication
occur after process containment, with their own elapsed observations and visible
failure state; they cannot extend the supervisor's original deadline.

Implementation ownership is separate: Terra owns the fixed child and internal
session/evidence module; root owns the supervisor hooks and budgeted wrapper;
Luna owns independent integration tests. Review checks the shared API and state
boundaries before a full repository test run and local commit.
