# Supervised synthetic streaming outcome

2026-09-22. Local fixture implementation, full-suite validation and internal
review. No native client, provider or paid experiment was launched.

## Delivered boundary

The [supervised integration](../../../../prototype/run_timing/SUPERVISED_STREAMING.md)
connects an actual fixed stdlib child to the existing two-hop loopback TLS
streaming fixture. The supervisor releases the terminal portion only after
retaining and validating the child's first-frame acknowledgement. The child
checks the exact frame bytes and decodes UTF-8 itself.

Attempt, worker source, lease and bootstrap digests link the child's stdout to
the parent receipts and existing process closeout. The sidecar retains separate
parent validation/local-write observations, child decoding/EOF observations,
control chronology, cleanup timing and observed process outcome. Read-back
checks these physical artifacts instead of recreating child output in the parent.

Fixed scenarios exercise completion, partial/truncated streams, duplicate
terminal, withholding, missing/malformed receipts, bad/duplicate acknowledgement
and a deliberately nonzero exit after a successful child result. Cancellation
and capture loss retain their own process observations. An incomplete or
inconsistent join remains held; closeout failure carries the actual process
result and leaves the synthetic ledger claim unresolved.

The closed launcher gains no caller-selected command, endpoint, environment or
credential. Bootstrap and TLS material are temporary synthetic fixture inputs.
Revocation intent precedes interruption, and selector-loop polling is nonblocking.
TLS setup and bounded transport cleanup are outside the existing supervision
duration; cleanup timing is retained separately. Durable artifact publication
remains outside that process measurement.

## Validation and review

- Full repository suite: **874 passed, 36 skipped**, 76.80 seconds. The
  [retained log](supervised-streaming-pytest.txt) records the final run.
- New integration suite: **39 passed**, including separate cancellation and
  deadline outcomes, real after-ACK cancellation, failed closeout retention,
  independent metadata mutations and timing-overrun read-back.
- Existing process and timing-rehearsal suites: **54 passed** in the focused
  regression run; all are also included in the full suite.
- Ruff and whitespace checks passed. The standalone child is **11,418 bytes**,
  below the unchanged 65,536-byte cap.
- Terra implemented the child/session, Luna implemented independent tests, and
  a separate Luna reviewer checked the four integration source modules. Root
  reviewed the final source and tests and independently verified their hashes.

The [validation receipt](supervised-streaming-validation.json) pins source and
artifact hashes, review scope and the full-suite result. Corrections distinguish
normal cleanup from failure; preserve actual timing without clamping; validate
exact types, frame counts, source/lease bindings and chronology; retain partial
bytes; and derive held reasons during read-back even when producer gaps are absent.
These internal code reviews do not constitute human Report adjudication.

## Remaining work

This advances the synthetic process/stream join only. Installed-client stream
compatibility, authenticated audit/control, enforced credential and direct-route
isolation, real accounting, intended venue and human Report adjudication remain
unqualified. The approved rubric is unchanged. Historical charges remain unknown;
no provider, paid experiment, tenant mutation or C2 retry ran.

The next local deliverable is a bounded native-launch evidence contract and
readiness checklist grounded in the existing client source register. It must
identify what can be established by inert/source checks and what requires an
observed qualified attempt, without admitting a model launch on fixture evidence.
Ticket 23 remains open.
