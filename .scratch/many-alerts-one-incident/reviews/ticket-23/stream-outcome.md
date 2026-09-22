# Ticket 23 stream evidence and client register

2026-09-22. **FIXED-FIXTURE IMPLEMENTATION / NATIVE LAUNCH TECHNICALLY CLOSED.**
Baseline `b0e1f8b`. [Plan](stream-plan.md); [validation](stream-validation.json).

The fixed process supervisor now retains independent stdout/stderr bytes alongside
the diagnostic merged capture. The same aggregate capture cap admits or rejects
each chunk before either stream can retain it. Only retained stdout enters the
synthetic parser. Stream lengths/digests are bound into a version-2 closeout with
five fixed filenames; a single nonempty stream must equal the diagnostic capture
byte-for-byte. Partial metadata, downgrade attempts and changed stream links reject.
The trusted descriptor mapping is not authenticated native source identity, and
mixed capture cannot reconstruct cross-stream emission order.

Version-1 closeouts still verify as historical byte evidence with unknown stream
identity. They cannot be promoted to the new integrated rehearsal result. That
reader requires version 2, parses its receipt from retained stdout, and rejects
all nonempty retained stderr, including valid JSON. Generic fixed-process fixtures
may complete with stderr; that is separate from this closed rehearsal's contract.
Existing failure, cancellation, capture-loss and unresolved accounting semantics
remain. No captured process result is replaced with an in-parent simulated flow.

The [client register](client-evidence-register.md) captures local Claude 2.1.278
executable/help hashes and the wrapper's dry command preview. All four commands
used an isolated temporary HOME/workdir, exited zero and produced empty stderr.
Twenty-two documented switches are indexed with exact captured-help excerpts.
No inference, auth command, model availability check or configuration dump ran.
The generic wrapper preview does not configure the experiment binding, mediated
TLS route or budget guard; no native schema or executable experiment is inferred.

## Review and validation

Terra implemented the four production files; Luna independently authored stream
regressions and reviewed the production contract. A separate Luna reviewer checked
Standards and the client register. Root reviewed integration and exact evidence.

Root review added the single-channel byte equality check, so rehashed stream bytes
cannot disagree with the diagnostic capture when only one channel has content.
Review also found a pre-existing semantic read-back defect: string/integer process
status values could pass the completion predicate by truthiness. The integrated
reader now requires exact booleans for capture completeness, root reaping, group
cleanup and pipe closure; valid false values remain held. The byte-integrity reader
retains its deliberately narrower historical contract.

Regression tests update all required outer links before testing inner stream and
semantic rejection. Coverage includes real stderr output, channel substitution,
shared caps, single-stream inconsistency, forged stderr JSON, historical read-back,
partial/downgraded evidence and closeout errors preserving the actual ProcessResult.
The final full suite passed **700 tests, 36 skipped in 43.24s**.
All **127 targeted tests** passed, as did Ruff and diff whitespace checks.
Reviewed source hashes are in the validation receipt.

Retained examples and raw self-documentation are outside Git at
`/Users/jasonkrueger/maoi-ticket23-evidence/20260922-stream-evidence/`.
The prior 90-file packet was archived from `b0e1f8b` and byte-verified. Prior
validation receipts are unchanged; the packet manifest records the archive chain.

## Remaining gates

This batch adds descriptor-attributed fixture storage and exact installed syntax
facts. It does not add a native model launcher, qualified event normalizer, fixed
native tool registration, authenticated transport/effects, provider actuals,
production audit custody/retention or full durable-closeout timing acceptance.
The next work is exact native schema evidence and a versioned normalizer contract,
then its offline fixture matrix and the mediated-client prerequisites.

The user's standing cost approval remains valid below $50 aggregate without repeat
cost-permission questions. No paid experiment or external headless review was
launched in this batch. The local independent reviews do not claim a fresh external
model opinion. Existing real accounting uncertainty is unchanged; synthetic
reservation state is never counted as provider spend. Human Report adjudication,
model/tenant/venue qualification, push and publication remain NOT RUN.
