# Unit 19a implementation plan

Status: proposed local source plan, 2026-09-24. Baseline: `832d298`.
Decision: `design-19a.md`. One pure, no-dispatch module; no existing
application or journal file changes.

1. Add `tests/test_run_outcome.py` first. Exercise false-success precedence:
   containment unknown/failure, timeout, cancellation, trusted spawn failure,
   nonzero/signal exit, result error, malformed/missing/duplicate terminal,
   missing exit, success, and unknown usage. Assert frozen/code-only output,
   no receipt, permit, money, effect or caller content.
2. Add `grafana_jsm_sandbox/run_outcome.py`. Use frozen value objects and one
   `assess_execution` interface. Validate process facts strictly; treat an
   invalid terminal as incomplete rather than repairing it. Keep reason and
   state vocabularies closed. Use no filesystem, clock, socket, subprocess,
   Forwarder, ledger or journal import.
3. Add `docs/run-outcome.md` describing the descriptive interface and the
   unverified provenance/effect limits. Do not edit the existing launcher,
   spawner, Receiver, ticket-19 paths, or protected uncommitted files.
4. Run focused tests and Ruff on new Python, line/whitespace checks and
   `git diff --check`. Review source against ADR 0012 and ticket 37 on both
   standards and spec axes. Run the full repository suite with demo execution
   flags unset after all code changes and before a local commit. Record
   hashes, counts, preserved-uncommitted read-back and NOT RUN boundaries.

Exact input contract for this slice:

- `ProcessFacts(spawn_state, exit_observed, exit_code, exit_signal,
  timed_out, cancelled, containment)` uses closed enums and exact booleans.
  An observed exit has exactly one signed-32-bit code or signal 1..64. The
  no-process marker is valid only for `failed_before_process`; otherwise an
  unknown spawn gap is uncertain. `containment` is `confirmed`, `failed`, or
  `unknown`; a possibly started process without confirmed containment cannot
  yield success.
- `TerminalFacts(subtype, is_error, reason, usage_state, evidence_digest)`
  permits `success|error`, exact boolean, nullable ASCII reason at most 64
  bytes, `known|absent|malformed` usage state, and lowercase sha256 digest.
  A nonempty reason on a claimed success is conflicting terminal evidence.
  Zero or two terminals, or one invalid terminal, are incomplete evidence.
- `ExecutionAssessment(state, reasons, usage, never_started)` is immutable.
  State is `succeeded|failed|cancelled|incomplete|containment_failed`;
  `never_started` is true only on trusted pre-process spawn failure. Reasons
  are sorted from a fixed vocabulary. `usage` is `known` only for exactly
  one valid terminal declaring known usage; otherwise `unknown`.

No assessment is a launch permit or OPS effect receipt. For a held admission
with no spawn attempt, this interface is not called; journal dispatch state
remains HELD. A later real Receiver adapter must provide source authority
and preserve the separate reported and derived outcomes.
