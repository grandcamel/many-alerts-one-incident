# Ticket 23 offline execution core

The core executes **synthetic replay observations**. A separate
[fixed host-process harness](PROCESS_FIXTURES.md) now supervises reviewed Python fixture
programs to test real scheduling and cleanup. Neither entry point can launch Claude,
arbitrary commands, containers or network requests. Production Receiver and historical
`prototype/run-timing` source are unchanged. Ticket 23's measurement card remains CLOSED.

The [synthetic diagnostic ledger](FIXTURE_LEDGER.md) adds SQLite reservation and one-time
launch claims for those fixed fixtures. It tests persistent unknown exposure, receipt
reconciliation, concurrent admission and weekly limits using synthetic inputs only.
It does not access real account balances or authorize a paid model call.

[Fixed-fixture closeout](FIXTURE_EVIDENCE.md) now retains the bounded capture bytes and
verifies worker/capture/result linkage on read-back. These byte-integrity receipts do not
establish semantic success, real audit acceptance or a durable-closeout time bound.

`outcomes.py` parses bounded synthetic Claude-shaped JSON events and derives execution
outcomes without discarding malformed evidence, duplicate terminals or receiver-observed
failures. The deliberately small schema accepts assistant messages with explicit model
identity, init metadata and result records with explicit success/error fields. It rejects
other shapes. It is not a qualified native-client adapter, and must not consume an actual
native stream as if its schema compatibility had been established. Missing cost remains
unknown; a returned estimate is never a provider actual. `comparison: eligible` concerns
observed identity only, not diagnostic quality or model qualification.

`executor.py` provides:

- A virtual-clock lifecycle with fixed 270/20/10 boundaries, early cancellation,
  descendant/pipe observations and dispatch revocation. Returned interrupt/kill actions
  are simulated requirements. They do not send signals or prove host containment.
- An inert fixed-grid length probe. It compares command bytes and issues receipts from
  an in-memory stub; it never executes the command. Receipt object identity rejects
  fabricated/copied/foreign receipts within this trusted process. This is not a security
  boundary against arbitrary code in that process or a native receipt transport. `begin`
  records a tool request before resolving permission; `dispatch` can begin it implicitly.
  Cleanup may collect a pending request's result but cannot begin another. Provider
  refusal/fallback cancels the linked lifecycle and exposes the required cleanup actions.
- A diagnostic admission predicate over explicit supplied ledger snapshots. Unknown
  prior-week exposure holds admission too. This does not persist a ledger, reserve real
  funds, authenticate provider actuals, or supply atomic/concurrent admission. Empty
  synthetic data is not evidence of an empty real ledger. Lifecycle/rehearsal-specific
  accounting remains ticket 38's integration work.
- Bounded in-memory capture of synthetic bytes. It is not a credential sanitizer or
  private disk audit store. Replay input must be synthetic, contain no secrets and be
  bounded before loading; the functions do not authorize reading private transcripts.
- `replay`: a finite observation driver that advances deadlines even during silence,
  classifies terminal evidence and labels every result `OFFLINE_REPLAY_ONLY` with native
  launch `CLOSED`. Missing reaping/exit observations at EOF cannot become success.

Run offline acceptance from the repository root:

```sh
python3 -m pytest -q tests/test_timing_outcomes.py tests/test_timing_executor.py
```

Tests verify the five inert command strings against the frozen planning fixtures. They
cover execution outcomes, identity, dispatch and budget/capture predicates from the 26
case specifications. Reservation persistence now has separate synthetic ledger tests;
authoritative provider accounting and semantic audit/qualification verdicts remain
integration gates. The abstract case data
is not treated as native events and its embedded commands are never executed.

## Before any native executor can be admitted

Implement and review an OS isolation/process binding with descendant membership and
reaping evidence, fixed executable resolution and protected fixture mounts; native
stream/permission normalization qualified against the exact CLI; authenticated external
receipt correlation; mediated Forwarder auth/routing/TLS/revocation; atomic durable
budget reservation and provider reconciliation; bounded sanitized private audit storage
with retention and exclusive attempt directories; revised timing Skill/prompt and human
rubric. The native binding must enforce emitted actions on time, not wait for transcript
activity. Offline comparisons or booleans cannot stand in for these proofs.

Output collision and process-group cleanup now have fixed-fixture host evidence;
adversarial containment, direct-route denial, credential custody, actual model/fallback
behavior, provider charges, tenant effects and venue qualification remain NOT RUN. No
local result here opens the execution card or authorizes a paid experiment.
